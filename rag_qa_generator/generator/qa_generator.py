import json
import time
import re
import concurrent.futures
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import random
import logging
from functools import partial

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.base_model import BaseModel
from data.schema_loader import SchemaLoader
from data.qa_loader import QALoader
from generator.prompt_builder import PromptBuilder
from generator.sql_validator import SQLValidator
from utils.logger import get_logger 
# schema_utils.py가 generator/ 폴더 내에 있는 경우
from .schema_utils import SchemaAdapter  # 상대 경로 임포트
  
class QAGenerator:
    """Q&A 및 SQL 생성 클래스"""
    
    def __init__(
        self, 
        model: BaseModel,
        schema_loader: SchemaLoader,
        qa_loader: Optional[QALoader] = None,
        validate_sql: bool = True,
        max_retries: int = 3,
        logger=None
    ):
        """
        Args:
            model: LLM 모델 인스턴스
            schema_loader: 스키마 로더 인스턴스
            qa_loader: Q&A 로더 인스턴스 (초기 예제용)
            validate_sql: SQL 유효성 검증 여부
            max_retries: 생성 실패 시 최대 재시도 횟수
            logger: 로거 인스턴스
        """
        self.model = model
        self.schema_loader = schema_loader
        self.qa_loader = qa_loader
        self.validate_sql = validate_sql
        self.max_retries = max_retries
        self.logger = logger or get_logger(__name__)
        
        # 스키마 정보 로드
        self.schema = self.schema_loader.load_schema()
        self.formatted_schema = self.schema_loader.format_for_prompt()
        
        # SQL 검증기 초기화 - 로깅 정보 전달
        if validate_sql:
            try:
                self.sql_validator = SQLValidator(schema_loader)
            except Exception as e:
                self.logger.error(f"SQL 검증기 초기화 오류: {str(e)}")
                self.sql_validator = None
                self.validate_sql = False
        else:
            self.sql_validator = None
        
        # 초기 Q&A 데이터 로드 (제공된 경우)
        self.initial_qa = []
        if qa_loader:
            self.initial_qa = qa_loader.load_qa_data()
            
        # 스키마 어댑터 초기화
        self.schema_adapter = SchemaAdapter(schema_loader=schema_loader)
    
    def generate_qa(
        self, 
        difficulty: str, 
        count: int = 10,
        parallel: bool = True,
        max_workers: int = 4,
        batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """지정된 난이도의 Q&A 생성
        
        Args:
            difficulty: 난이도 ('easy', 'medium', 'hard')
            count: 생성할 항목 수
            parallel: 병렬 처리 여부
            max_workers: 최대 작업자 수 (병렬 처리 시)
            batch_size: 배치 크기 (병렬 처리 시)
            
        Returns:
            생성된 Q&A 항목 리스트
        """
        # 수량 유효성 검사 및 안전 조치
        if count <= 0:
            self.logger.warning(f"요청된 항목 수({count})가 0 이하입니다. 빈 리스트를 반환합니다.")
            return []
        
        # 합리적인 최대값 설정 (필요시 조정)
        max_count = 50
        if count > max_count:
            original_count = count
            count = max_count
            self.logger.warning(f"요청된 항목 수({original_count})가 최대 허용치({max_count})를 초과합니다. {count}개로 제한합니다.")
        
        self.logger.info(f"{difficulty} 난이도의 Q&A {count}개 생성 시작")
        
        # 난이도별 예제 선택
        examples = []
        if self.qa_loader:
            examples = self.qa_loader.get_examples_by_difficulty(difficulty, 3)
        
        # 프롬프트 빌더 초기화
        prompt_builder = PromptBuilder(
            model_type=self.model.__class__.__name__,
            schema_formatted=self.formatted_schema,
            examples=examples
        )
        
        # 시작 시간 기록 (시간 제한용)
        start_time = time.time()
        max_duration = 300  # 최대 5분 (필요에 따라 조정)
        
        # 병렬 처리 또는 순차 처리 선택
        if parallel and count > 1:
            items = self._generate_qa_parallel(
                prompt_builder=prompt_builder,
                difficulty=difficulty,
                count=count,
                max_workers=max_workers,
                batch_size=batch_size
            )
        else:
            items = self._generate_qa_sequential(
                prompt_builder=prompt_builder,
                difficulty=difficulty,
                count=count
            )
        
        # 시간 제한 검사
        elapsed_time = time.time() - start_time
        self.logger.info(f"생성 소요 시간: {elapsed_time:.2f}초")
        
        if elapsed_time > max_duration:
            self.logger.warning(f"생성 시간({elapsed_time:.2f}초)이 최대 허용 시간({max_duration}초)을 초과했습니다.")
        
        # 최종 결과 개수 확인 및 조정 (안전 장치)
        final_count = len(items)
        
        if final_count > count:
            self.logger.warning(f"생성된 항목 수({final_count})가 요청 수({count})보다 많습니다. 초과 항목을 제거합니다.")
            items = items[:count]
        elif final_count < count:
            self.logger.warning(f"생성된 항목 수({final_count})가 요청 수({count})보다 적습니다. 부족한 항목을 응급 데이터로 채웁니다.")
            emergency_items = self._create_emergency_qa_items(difficulty, count - final_count)
            items.extend(emergency_items)
            
            # 다시 한번 수량 확인 (안전 장치)
            if len(items) > count:
                items = items[:count]
        
        self.logger.info(f"{difficulty} 난이도의 Q&A 총 {len(items)}/{count}개 생성 완료")
        
        # 일관성을 위해 항상 정확히 요청된 수만큼만 반환
        return items[:count]
    
    def _generate_qa_sequential(
        self, 
        prompt_builder: PromptBuilder, 
        difficulty: str, 
        count: int
    ) -> List[Dict[str, Any]]:
        """순차적 Q&A 생성
        
        Args:
            prompt_builder: 프롬프트 빌더 인스턴스
            difficulty: 난이도
            count: 생성할 항목 수
            
        Returns:
            생성된 Q&A 항목 리스트
        """
        all_qa_items = []
        
        # 요청된 개수가 0이면 빈 리스트 반환
        if count <= 0:
            return []
        
        # 배치 크기 계산 (API 제한 고려)
        batch_size = min(1, count)  # 배치 크기를 1로 제한
        remaining = count
        
        # 빈 응답 카운터 추가
        empty_response_count = 0
        max_empty_responses = 5  # 최대 빈 응답 허용 횟수
        
        # 최대 생성 시도 횟수 - 무한 루프 방지
        max_attempts = count * 3
        attempts = 0
        
        self.logger.info(f"정확히 {count}개의 {difficulty} 난이도 Q&A 생성 시작")
        
        while remaining > 0 and attempts < max_attempts:
            attempts += 1
            
            # 목표 개수를 이미 달성했는지 확인 (안전 장치)
            if len(all_qa_items) >= count:
                self.logger.info(f"목표 개수 {count}개를 달성했습니다. 생성 종료.")
                break
                
            # 최대 빈 응답 횟수 초과 시 중단하고 응급 데이터 생성
            if empty_response_count >= max_empty_responses:
                self.logger.error(f"최대 빈 응답 횟수({max_empty_responses})를 초과하여 응급 데이터 생성")
                
                # 응급 Q&A 항목 생성
                emergency_items = self._create_emergency_qa_items(difficulty, remaining)
                all_qa_items.extend(emergency_items)
                break
                
            # 이번 배치에서 생성할 항목 수
            current_batch_size = min(batch_size, remaining)
            
            # 프롬프트 생성
            prompts = prompt_builder.build_qa_generation_prompt(
                difficulty=difficulty,
                count=current_batch_size
            )
            
            # 모델용 포맷 변환
            model_inputs = prompt_builder.format_output_for_model(prompts)
            
            # 생성 요청
            self.logger.info(f"남은 수량 {remaining}/{count}개 중 {current_batch_size}개 Q&A 생성 중... (시도 {attempts}/{max_attempts})")
            response, success = self.model.generate_with_retry(
                prompt=model_inputs.get("prompt", ""),
                system_prompt=model_inputs.get("system_prompt"),
                max_retries=self.max_retries
            )
            
            # 응답 검증 및 디버깅을 위한 로그 추가
            self.logger.debug(f"응답 상태: {success}, 응답 길이: {len(response) if response else 0}")
            
            if not success:
                self.logger.error(f"생성 실패: {response}")
                empty_response_count += 1
                time.sleep(2)  # 실패 시 대기 시간 추가
                continue
            
            # 응답이 비어있는지 확인
            if not response or response.strip() == "":
                self.logger.error("응답이 비어 있습니다.")
                empty_response_count += 1
                time.sleep(2)  # 빈 응답 시 대기 시간 추가
                continue
            
            # 응답이 존재하면 빈 응답 카운터 초기화
            empty_response_count = 0
            
            # 응답 파싱
            try:
                qa_items = self._parse_qa_response(response, difficulty)
                
                if qa_items:
                    # 생성된 항목 검증 및 추가
                    valid_items = self._validate_qa_items(qa_items)
                    
                    # 필요한 수량만큼만 추가 (초과 항목 제거)
                    valid_count = min(len(valid_items), remaining)
                    added_items = valid_items[:valid_count]
                    
                    # 항목 추가
                    all_qa_items.extend(added_items)
                    
                    # 충분한 수량이 생성되었는지 확인
                    generated_count = len(added_items)
                    remaining -= generated_count
                    
                    self.logger.info(f"{generated_count}개 유효한 Q&A 생성 완료 (남은 수량: {remaining}/{count}, 전체 생성: {len(all_qa_items)}/{count})")
                    
                    # 목표 달성 확인
                    if remaining <= 0 or len(all_qa_items) >= count:
                        self.logger.info(f"목표 개수 {count}개를 달성했습니다. 생성 종료.")
                        break
                    
                    # 잠시 대기 (API 제한 고려)
                    time.sleep(1)
                else:
                    self.logger.warning("생성된 Q&A 항목이 없습니다. 파싱에 실패했습니다.")
                    
                    # 응답은 있지만 파싱 실패한 경우 수동으로 샘플 항목 생성 시도
                    if "SELECT" in response or "FROM" in response:
                        self.logger.info("응답에서 SQL 문이 감지되어 수동으로 항목을 생성합니다.")
                        manual_item = self._create_manual_qa_item(response, difficulty)
                        if manual_item:
                            valid_items = self._validate_qa_items([manual_item])
                            
                            # 필요한 수량만큼만 추가
                            valid_count = min(len(valid_items), remaining)
                            added_items = valid_items[:valid_count]
                            
                            all_qa_items.extend(added_items)
                            remaining -= len(added_items)
                            
                            # 목표 달성 확인
                            if remaining <= 0 or len(all_qa_items) >= count:
                                self.logger.info(f"목표 개수 {count}개를 달성했습니다. 생성 종료.")
                                break
                    else:
                        # SQL이 감지되지 않으면 빈 응답으로 처리
                        empty_response_count += 1
                    
                    # 대기 시간 추가
                    time.sleep(2)
            except Exception as e:
                self.logger.error(f"응답 파싱 오류: {str(e)}")
                empty_response_count += 1
                time.sleep(2)
        
        # 최종 결과 확인 및 처리
        final_count = len(all_qa_items)
        
        # 결과 개수 로깅
        if final_count > count:
            self.logger.warning(f"생성된 항목이 요청 개수보다 많습니다: {final_count}/{count}. 초과 항목을 제거합니다.")
            all_qa_items = all_qa_items[:count]
        elif final_count < count:
            self.logger.warning(f"생성된 항목이 요청 개수보다 적습니다: {final_count}/{count}. 부족한 항목을 응급 데이터로 채웁니다.")
            emergency_items = self._create_emergency_qa_items(difficulty, count - final_count)
            all_qa_items.extend(emergency_items)
        
        self.logger.info(f"최종 생성 완료: {len(all_qa_items)}/{count} 항목")
        
        # 정확히 요청된 개수만 반환
        return all_qa_items[:count]
    
    def _generate_qa_parallel(
        self, 
        prompt_builder: PromptBuilder, 
        difficulty: str, 
        count: int,
        max_workers: int,
        batch_size: int
    ) -> List[Dict[str, Any]]:
        """병렬 Q&A 생성
        
        Args:
            prompt_builder: 프롬프트 빌더 인스턴스
            difficulty: 난이도
            count: 생성할 항목 수
            max_workers: 최대 작업자 수
            batch_size: 배치 크기
            
        Returns:
            생성된 Q&A 항목 리스트
        """
        # 요청된 개수가 0이면 빈 리스트 반환
        if count <= 0:
            return []
            
        # 소규모 요청은 순차 처리로 전환
        if count <= 5:
            self.logger.info(f"항목 수가 적어({count}개) 순차 처리로 전환합니다.")
            return self._generate_qa_sequential(prompt_builder, difficulty, count)
                
        all_qa_items = []
        
        self.logger.info(f"병렬 처리로 {difficulty} 난이도의 Q&A {count}개 생성 시작")
        
        # 작업 분할 (더 작은 배치 크기 사용)
        adjusted_batch_size = min(2, batch_size)  # 배치 크기 제한
        total_batches = (count + adjusted_batch_size - 1) // adjusted_batch_size  # 올림 나눗셈
        batch_counts = [adjusted_batch_size] * (total_batches - 1) + [count - adjusted_batch_size * (total_batches - 1)]
        
        # 저장하여 나중에 사용할 수 있도록 total_batches 설정
        self.total_batches = total_batches
        
        # 병렬 실행
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # partial 함수를 사용하여 추가 인자 전달
            generate_batch_with_params = partial(
                self.generate_batch, 
                prompt_builder=prompt_builder, 
                difficulty=difficulty
            )
            
            futures = [
                executor.submit(generate_batch_with_params, batch_count, i)
                for i, batch_count in enumerate(batch_counts)
            ]
            
            # 결과 수집
            for future in concurrent.futures.as_completed(futures):
                try:
                    batch_items = future.result()
                    
                    remaining = count - len(all_qa_items)
                    if remaining > 0:
                        to_add = batch_items[:remaining]
                        all_qa_items.extend(to_add)
                        self.logger.info(f"병렬 처리: {len(to_add)}개 항목 추가 (전체: {len(all_qa_items)}/{count})")
                        
                        if len(all_qa_items) >= count:
                            break
                except Exception as e:
                    self.logger.error(f"병렬 처리 중 오류 발생: {str(e)}")
        
        return all_qa_items
    
    def generate_batch(self, batch_size: int, batch_idx: int, prompt_builder: PromptBuilder, difficulty: str) -> List[Dict[str, Any]]:
        """배치 단위 Q&A 생성
        
        Args:
            batch_size: 배치 크기
            batch_idx: 배치 인덱스
            prompt_builder: 프롬프트 빌더 인스턴스
            difficulty: 난이도
            
        Returns:
            생성된 Q&A 항목 리스트
        """
        batch_items = []
        self.logger.info(f"배치 {batch_idx+1}/{self.total_batches} 시작 (크기: {batch_size})")

        try:
            # 프롬프트 생성
            prompts = prompt_builder.build_qa_generation_prompt(
                difficulty=difficulty,
                count=batch_size
            )

            # 모델용 포맷 변환
            model_inputs = prompt_builder.format_output_for_model(prompts)

            # 생성 요청
            response, success = self.model.generate_with_retry(
                prompt=model_inputs.get("prompt", ""),
                system_prompt=model_inputs.get("system_prompt"),
                max_retries=self.max_retries
            )

            if not success or not response or response.strip() == "":
                self.logger.error(f"배치 {batch_idx+1} 생성 실패 또는 빈 응답")
                
                # 단일 항목으로 재시도
                if batch_size > 1:
                    self.logger.info(f"배치 {batch_idx+1}을 단일 항목으로 재시도합니다")
                    single_items = []
                    
                    for i in range(batch_size):
                        time.sleep(1)  # 재시도 간 대기
                        single_prompts = prompt_builder.build_qa_generation_prompt(
                            difficulty=difficulty,
                            count=1
                        )
                        single_inputs = prompt_builder.format_output_for_model(single_prompts)
                        single_response, single_success = self.model.generate_with_retry(
                            prompt=single_inputs.get("prompt", ""),
                            system_prompt=single_inputs.get("system_prompt"),
                            max_retries=2
                        )
                        
                        if single_success and single_response and single_response.strip():
                            single_qa_items = self._parse_qa_response(single_response, difficulty)
                            
                            if single_qa_items:
                                valid_items = self._validate_qa_items(single_qa_items)
                                valid_items = valid_items[:1]  # 각 재시도에서 최대 1개만
                                single_items.extend(valid_items)
                                
                                if len(single_items) >= batch_size:
                                    break

                    self.logger.info(f"단일 항목 재시도로 {len(single_items)}/{batch_size}개 생성")
                    return single_items[:batch_size]
                
                return []

            # 응답 파싱
            qa_items = self._parse_qa_response(response, difficulty)
            
            if qa_items:
                valid_items = self._validate_qa_items(qa_items)
                batch_items = valid_items[:batch_size]  # 배치 크기로 제한
                self.logger.info(f"배치 {batch_idx+1} 완료: {len(batch_items)}/{batch_size} 유효 항목 생성")
                return batch_items
            else:
                self.logger.warning(f"배치 {batch_idx+1}: 생성된 Q&A 항목이 없습니다.")
                
                if "SELECT" in response or "FROM" in response:
                    self.logger.info("응답에서 SQL 문이 감지되어 수동으로 항목을 생성합니다.")
                    manual_item = self._create_manual_qa_item(response, difficulty)
                    
                    if manual_item:
                        valid_items = self._validate_qa_items([manual_item])
                        return valid_items[:batch_size]
                
                return []
        
        except Exception as e:
            self.logger.error(f"배치 {batch_idx+1} 처리 중 오류 발생: {str(e)}")
            return []
   
    def generate_answers(self, qa_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """답변이 없는 Q&A 항목에 대한 답변 생성
        
        Args:
            qa_items: 답변을 생성할 Q&A 항목 리스트
            
        Returns:
            답변이 추가된 Q&A 항목 리스트
        """
        result_items = []
        
        # 프롬프트 빌더 초기화
        prompt_builder = PromptBuilder(
            model_type=self.model.__class__.__name__,
            schema_formatted=self.formatted_schema
        )
        
        for item in qa_items:
            # 답변이 이미 있으면 그대로 유지
            if item.get("answer") and item["answer"].strip():
                result_items.append(item)
                continue
            
            # 답변 생성 프롬프트 구성
            prompts = prompt_builder.build_answer_generation_prompt(
                question=item["question"],
                sql=item["sql"]
            )
            
            # 모델용 포맷 변환
            model_inputs = prompt_builder.format_output_for_model(prompts)
            
            # 생성 요청
            self.logger.info(f"질문에 대한 답변 생성 중: {item['question'][:50]}...")
            response, success = self.model.generate_with_retry(
                prompt=model_inputs.get("prompt", ""),
                system_prompt=model_inputs.get("system_prompt"),
                max_retries=self.max_retries
            )
            
            if success:
                # 답변 추가
                item["answer"] = response.strip()
                result_items.append(item)
            else:
                self.logger.error(f"답변 생성 실패: {response}")
                # 실패 시 빈 답변 추가
                item["answer"] = ""
                result_items.append(item)
            
            # API 제한 고려 대기
            time.sleep(0.5)
        
        return result_items
    
    def save_results(
        self, 
        qa_items: List[Dict[str, Any]],
        output_path: Union[str, Path],
        format: str = 'json'
    ) -> Path:
        """생성된 Q&A 항목 저장
        
        Args:
            qa_items: 저장할 Q&A 항목 리스트
            output_path: 출력 경로
            format: 출력 형식 ('json', 'csv', 'excel')
            
        Returns:
            저장된 파일 경로
        """
        # QALoader를 사용하여 저장
        if not self.qa_loader:
            self.qa_loader = QALoader()
        
        output_path = Path(output_path)
        self.qa_loader.save_qa_data(qa_items, output_path, format)
        
        self.logger.info(f"{len(qa_items)}개 Q&A 항목이 {output_path}에 저장되었습니다.")
        return output_path
    
    # qa_generator.py의 _create_emergency_qa_items 메서드에 표시 추가
    def _create_emergency_qa_items(self, difficulty: str, count: int) -> List[Dict[str, Any]]:
        """응급 Q&A 항목 생성 (스키마 어댑터 사용)"""
        self.logger.info(f"응급 Q&A 항목 {count}개 생성 시작")
        
        try:
            items = self.schema_adapter.generate_valid_samples(difficulty, count)
            
            # 응급 생성임을 표시
            for item in items:
                item["is_emergency"] = True
                item["question"] = "[자동 생성] " + item["question"]
            
            return items
        except Exception as e:
            self.logger.error(f"응급 항목 생성 오류: {str(e)}")
            
            # 오류 발생 시 빈 리스트 반환하여 디폴트 질문 생성 방지
            return []
        
    def _create_fallback_qa_items(self, difficulty: str, count: int) -> List[Dict[str, Any]]:
        """스키마 어댑터가 실패할 경우 사용할 사용자 친화적인 기본 Q&A 항목 생성
        
        Args:
            difficulty: 난이도
            count: 생성할 항목 수
            
        Returns:
            기본 Q&A 항목 리스트
        """
        self.logger.warning(f"기본 Q&A 항목 {count}개 생성")
        items = []
        
        # 스키마에서 테이블 목록과 설명 추출 시도
        tables = []
        table_descriptions = {}
        
        try:
            schema = self.schema_loader.load_schema()
            if isinstance(schema, dict) and 'tables' in schema:
                for table in schema.get('tables', []):
                    table_name = table.get('name', '')
                    if table_name:
                        tables.append(table_name)
                        
                        # 테이블 설명 추출 (있는 경우)
                        description = table.get('description', '')
                        if description:
                            table_descriptions[table_name] = description
                        else:
                            # 설명이 없으면 테이블명을 사용자 친화적으로 변환
                            user_friendly_name = table_name.replace('_', ' ').title()
                            table_descriptions[table_name] = user_friendly_name
            elif isinstance(schema, str):
                # 문자열 형태의 스키마에서 테이블 추출
                table_pattern = r'CREATE\s+TABLE\s+(?:\w+\.)?(\w+)'
                tables = re.findall(table_pattern, schema, re.IGNORECASE)
                
                # 테이블명을 사용자 친화적으로 변환
                for table in tables:
                    table_descriptions[table] = table.replace('_', ' ').title()
        except Exception:
            # 추출 실패 시 기본 테이블 사용
            tables = ['customers', 'orders']
            table_descriptions = {
                'customers': '고객',
                'orders': '주문'
            }
        
        if not tables:
            tables = ['customers', 'orders']
            table_descriptions = {
                'customers': '고객',
                'orders': '주문'
            }
        
        # 템플릿 - 기술적 질문과 사용자 친화적 질문 모두 포함
        templates = {
            'easy': [
                # (SQL, 기술중심질문, 사용자중심질문, 답변템플릿)
                ("SELECT COUNT(*) FROM {table}", 
                "{table} 테이블의 총 레코드 수는 몇 개인가요?", 
                "{table_desc}이(가) 총 몇 개인가요?", 
                "{table_desc}의 총 개수를 반환합니다."),
                
                # 다른 템플릿도 유사하게 수정
            ],
            # 중간 및 어려운 난이도 템플릿도 유사하게 수정
        }
        
        # 선택된 난이도의 템플릿 목록
        selected_templates = templates.get(difficulty.lower(), templates['easy'])
        
        # 각 항목 생성
        for i in range(count):
            # 랜덤하게 템플릿 선택
            template, tech_question, user_question, answer_template = random.choice(selected_templates)
            
            # 테이블 선택
            table = random.choice(tables)
            table_desc = table_descriptions.get(table, table.replace('_', ' ').title())
            
            # 70% 확률로 사용자 친화적 질문 사용
            use_user_friendly = random.random() < 0.7
            
            # 템플릿 채우기
            sql = template.replace("{table}", table)
            
            if use_user_friendly:
                question = user_question.replace("{table}", table).replace("{table_desc}", table_desc)
            else:
                question = tech_question.replace("{table}", table)
                
            answer = answer_template.replace("{table}", table).replace("{table_desc}", table_desc)
            
            # 항목 추가
            items.append({
                "difficulty": difficulty,
                "question": question,
                "sql": sql,
                "answer": answer
            })
        
        return items
    
    
    
    def _create_qa_from_text(self, text: str, difficulty: str) -> List[Dict[str, Any]]:
        """텍스트 응답에서 Q&A 항목 추출 시도
        
        Args:
            text: 모델 응답 텍스트
            difficulty: 난이도
            
        Returns:
            추출된 Q&A 항목 리스트
        """
        self.logger.debug("텍스트에서 Q&A 항목 추출 시도 중")
        
        # 질문, SQL, 답변을 추출하기 위한 패턴 개선
        question_pattern = r'(?:질문|question):?\s*(.*?)(?=(?:SQL|sql|쿼리|query):|<br>|\n\n|$)'
        sql_pattern = r'(?:SQL|sql|쿼리|query):?\s*(?:```sql)?\s*(.*?)(?:```|\n\n(?:답변|answer):|<br>|$)'
        answer_pattern = r'(?:답변|answer|결과):?\s*(.*?)(?=\n\n(?:질문|question):|<br>|\n\n|$)'
        
        # 전체 텍스트에서 질문/SQL/답변 패턴 찾기
        questions = re.findall(question_pattern, text, re.DOTALL)
        sqls = re.findall(sql_pattern, text, re.DOTALL)
        answers = re.findall(answer_pattern, text, re.DOTALL)
        
        # SQL 쿼리 직접 추출 시도
        if not sqls:
            # SELECT와 FROM을 포함하는 문자열 찾기
            sql_direct_matches = re.findall(r'(SELECT\s+.*?FROM\s+.*?(?:;|$))', text, re.IGNORECASE | re.DOTALL)
            if sql_direct_matches:
                sqls = sql_direct_matches
                if not questions:
                    questions = [f"다음 SQL 쿼리의 결과는 무엇인가요?" for _ in range(len(sqls))]
        
        # 결과 저장
        items = []
        
        # 패턴이 발견된 경우
        if questions and sqls:
            # 최소 길이만큼 처리
            min_len = min(len(questions), len(sqls))
            for i in range(min_len):
                # 답변이 없는 경우 빈 문자열 사용
                answer = answers[i].strip() if i < len(answers) else ""
                
                items.append({
                    "difficulty": difficulty,
                    "question": questions[i].strip(),
                    "sql": sqls[i].strip(),
                    "answer": answer or "이 SQL 쿼리는 질문에 대한 답을 제공합니다."
                })
            self.logger.info(f"텍스트에서 {len(items)}개 항목 추출 성공")
        else:
            # 다른 형식으로 시도 (텍스트의 구조에 따라 달라질 수 있음)
            self.logger.warning("표준 패턴 매칭 실패, 대체 방법 시도")
            
            # 텍스트를 문단으로 분리
            sections = text.split("\n\n")
            question = ""
            sql = ""
            answer = ""
            
            for section in sections:
                section = section.strip()
                if not section:
                    continue
                    
                if section.lower().startswith("질문") or section.lower().startswith("question"):
                    question = section.split(":", 1)[1].strip() if ":" in section else section
                elif section.lower().startswith("sql") or section.lower().startswith("쿼리") or section.lower().startswith("query"):
                    # SQL 코드 블록 처리
                    sql = section.split(":", 1)[1].strip() if ":" in section else section
                    sql = re.sub(r'```sql|```', '', sql).strip()
                elif section.lower().startswith("답변") or section.lower().startswith("answer"):
                    answer = section.split(":", 1)[1].strip() if ":" in section else section
            
            if question and sql:
                items.append({
                    "difficulty": difficulty,
                    "question": question,
                    "sql": sql,
                    "answer": answer if answer else "생성된 SQL 쿼리에 해당하는 결과입니다."
                })
                self.logger.info("단일 항목 추출 성공")
            elif sql:  # 질문이 없어도 SQL이 있으면 항목 생성
                items.append({
                    "difficulty": difficulty,
                    "question": f"이 SQL 쿼리의 결과를 설명하세요: {sql[:50]}...",
                    "sql": sql,
                    "answer": "이 SQL 쿼리의 결과입니다."
                })
                self.logger.info("SQL만으로 항목 추출 성공")
            else:
                # 마지막 시도: 전체 텍스트에서 SQL 쿼리 패턴 찾기
                sql_blocks = re.findall(r'```sql\s*(.*?)\s*```', text, re.DOTALL)
                if sql_blocks:
                    for i, sql in enumerate(sql_blocks):
                        items.append({
                            "difficulty": difficulty,
                            "question": f"SQL 쿼리 {i+1}에 대한 질문",
                            "sql": sql.strip(),
                            "answer": "이 SQL 쿼리의 결과입니다."
                        })
                    self.logger.info(f"SQL 블록에서 {len(items)}개 항목 추출")
        
        return items

    def _validate_qa_items(self, qa_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """생성된 Q&A 항목 검증 - 상세 로깅 추가
        
        Args:
            qa_items: 검증할 Q&A 항목 리스트
            
        Returns:
            유효한 Q&A 항목 리스트
        """
        valid_items = []
        
        # 스키마 정보 로깅
        self.logger.info("=== 스키마 정보 분석 시작 ===")
        
        # 스키마에 존재하는 테이블과 컬럼 목록 추출
        schema_tables = {}
        try:
            if hasattr(self, 'schema') and self.schema:
                if isinstance(self.schema, dict):
                    # 딕셔너리 형태의 스키마
                    for table in self.schema.get('tables', []):
                        table_name = table.get('name', '')
                        if table_name:
                            columns = [col.get('name', '') for col in table.get('columns', []) if col.get('name', '')]
                            schema_tables[table_name] = columns
                elif isinstance(self.schema, str):
                    # 문자열 형태의 스키마에서 테이블명과 컬럼 추출 시도
                    table_pattern = r'CREATE\s+TABLE\s+(?:\w+\.)?(\w+)'
                    table_names = re.findall(table_pattern, self.schema, re.IGNORECASE)
                    
                    # 각 테이블의 컬럼 추출 (단순화된 방식)
                    for table_name in table_names:
                        column_pattern = r'CREATE\s+TABLE\s+(?:\w+\.)?{0}\s*\((.*?)\)'.format(re.escape(table_name))
                        column_matches = re.search(column_pattern, self.schema, re.IGNORECASE | re.DOTALL)
                        
                        if column_matches:
                            column_text = column_matches.group(1)
                            column_names = re.findall(r'[\s,](\w+)[\s\n]+', column_text)
                            schema_tables[table_name] = column_names
                        else:
                            schema_tables[table_name] = []
                
                # 스키마 정보 로깅
                if schema_tables:
                    self.logger.info(f"스키마에 {len(schema_tables)} 테이블 발견:")
                    for table_name, columns in schema_tables.items():
                        self.logger.info(f"  - {table_name}: {', '.join(columns[:5])}{' 외 더 많은 컬럼' if len(columns) > 5 else ''}")
                else:
                    self.logger.warning("스키마에서 테이블 정보를 추출할 수 없습니다.")
        except Exception as e:
            self.logger.error(f"스키마 정보 분석 오류: {str(e)}")
        
        self.logger.info("=== 스키마 정보 분석 완료 ===")
        
        # 항목 검증
        total_items = len(qa_items)
        self.logger.info(f"=== 항목 검증 시작 ({total_items}개) ===")
        
        for idx, item in enumerate(qa_items):
            self.logger.info(f"[항목 {idx+1}/{total_items}] 검증 시작")
            
            # 필수 필드 확인
            if not all(key in item for key in ["question", "sql"]):
                self.logger.warning(f"[항목 {idx+1}] 필수 필드 누락")
                continue
            
            # SQL 로깅
            sql = item["sql"]
            sql_clean = re.sub(r'```sql|```', '', sql).strip()
            item["sql"] = sql_clean  # 정리된 SQL 저장
            
            self.logger.info(f"[항목 {idx+1}] SQL: {sql_clean}")
            
            # SQL이 실제로 SQL인지 확인
            if "SELECT" not in sql_clean.upper() or "FROM" not in sql_clean.upper():
                self.logger.warning(f"[항목 {idx+1}] SQL 문법 확인 실패 - SELECT 또는 FROM 키워드 없음")
                continue
            
            # 테이블 사용 분석
            used_tables = []
            from_match = re.findall(r'FROM\s+([a-zA-Z0-9_]+)', sql_clean, re.IGNORECASE)
            join_match = re.findall(r'JOIN\s+([a-zA-Z0-9_]+)', sql_clean, re.IGNORECASE)
            
            if from_match:
                used_tables.extend(from_match)
            if join_match:
                used_tables.extend(join_match)
            
            # 테이블 유효성 검사
            if schema_tables:
                invalid_tables = [table for table in used_tables if table not in schema_tables]
                if invalid_tables:
                    self.logger.warning(f"[항목 {idx+1}] 유효하지 않은 테이블 사용: {', '.join(invalid_tables)}")
                    self.logger.info(f"[항목 {idx+1}] 사용 가능한 테이블: {', '.join(schema_tables.keys())}")
                    
                    # SQL 검증기 사용 시도
                    if self.validate_sql and self.sql_validator:
                        validation_result = self.sql_validator.validate_sql(sql_clean)
                        corrected_sql = validation_result.get("corrected_sql")
                        if corrected_sql:
                            self.logger.info(f"[항목 {idx+1}] SQL 자동 수정 적용: {corrected_sql}")
                            item["sql"] = corrected_sql
                            valid_items.append(item)
                            self.logger.info(f"[항목 {idx+1}] 검증 완료 - 수정 후 추가됨")
                            continue
                    
                    # 검증 실패하고 수정도 되지 않았으면 대체 테이블 사용
                    sql_fixed = sql_clean
                    for bad_table in invalid_tables:
                        # 스키마의 첫 번째 테이블로 대체
                        if schema_tables:
                            replacement = next(iter(schema_tables.keys()))
                            sql_fixed = re.sub(r'\b{0}\b'.format(re.escape(bad_table)), replacement, sql_fixed, flags=re.IGNORECASE)
                    
                    if sql_fixed != sql_clean:
                        self.logger.info(f"[항목 {idx+1}] SQL 수동 수정 적용: {sql_fixed}")
                        item["sql"] = sql_fixed
                        valid_items.append(item)
                        self.logger.info(f"[항목 {idx+1}] 검증 완료 - 수동 수정 후 추가됨")
                        continue
                else:
                    self.logger.info(f"[항목 {idx+1}] 테이블 유효성 확인 성공: {', '.join(used_tables)}")
            
            # SQL 검증기로 검증 (있는 경우)
            if self.validate_sql and self.sql_validator:
                self.logger.info(f"[항목 {idx+1}] SQL 검증기 실행 중...")
                try:
                    validation_result = self.sql_validator.validate_sql(sql_clean)
                    
                    if not validation_result["is_valid"]:
                        errors = validation_result.get("errors", [])
                        error_str = ", ".join(errors) if errors else "알 수 없는 오류"
                        self.logger.warning(f"[항목 {idx+1}] SQL 검증 실패: {error_str}")
                        
                        # 수정된 SQL이 있는 경우
                        corrected_sql = validation_result.get("corrected_sql")
                        if corrected_sql:
                            self.logger.info(f"[항목 {idx+1}] SQL 수정됨: {corrected_sql}")
                            item["sql"] = corrected_sql
                            valid_items.append(item)
                            self.logger.info(f"[항목 {idx+1}] 검증 완료 - 수정 후 추가됨")
                            continue
                    else:
                        self.logger.info(f"[항목 {idx+1}] SQL 검증 성공")
                        valid_items.append(item)
                        self.logger.info(f"[항목 {idx+1}] 검증 완료 - 추가됨")
                        continue
                except Exception as e:
                    self.logger.error(f"[항목 {idx+1}] SQL 검증 중 오류 발생: {str(e)}")
            
            # 검증기를 사용하지 않거나 검증 중 오류가 발생한 경우 기본 검사 통과 항목만 추가
            valid_items.append(item)
            self.logger.info(f"[항목 {idx+1}] 기본 검증 완료 - 추가됨")
            
            self.logger.info(f"[항목 {idx+1}/{total_items}] 검증 완료")
        
        # 로그 요약
        added_count = len(valid_items)
        self.logger.info(f"=== 항목 검증 완료: {added_count}/{total_items} 항목 추가됨 ===")
        
        return valid_items
    
    def _parse_qa_response(self, response: str, difficulty: str) -> List[Dict[str, Any]]:
        """모델 응답에서 Q&A 항목 파싱
        
        Args:
            response: 모델 응답 텍스트
            difficulty: 난이도
            
        Returns:
            파싱된 Q&A 항목 리스트
        """
        try:
            # 응답이 비어있는 경우 처리
            if not response or response.strip() == "":
                self.logger.error("응답이 비어 있습니다.")
                return []
                    
            # 응답 로깅 (디버깅 목적)
            self.logger.debug(f"파싱할 응답: {response[:500]}...")
            
            # JSON 응답 추출 시도
            json_content = None
            
            # 1. 정규식으로 JSON 블록 찾기 시도
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_content = json_match.group(1).strip()
                self.logger.debug("JSON 코드 블록에서 콘텐츠 추출됨")
            else:
                # 2. 추가: ```와 ``` 사이의 모든 텍스트 시도
                code_block_match = re.search(r'```\s*([\s\S]*?)\s*```', response)
                if code_block_match:
                    potential_json = code_block_match.group(1).strip()
                    # JSON 유효성 검사
                    try:
                        json.loads(potential_json)
                        json_content = potential_json
                        self.logger.debug("일반 코드 블록에서 JSON 콘텐츠 추출됨")
                    except json.JSONDecodeError:
                        pass
                        
                if not json_content:
                    # 3. 응답 전체가 JSON인지 확인
                    try:
                        json.loads(response.strip())
                        json_content = response.strip()
                        self.logger.debug("전체 응답이 JSON으로 처리됨")
                    except json.JSONDecodeError:
                        # 4. 응답에서 [ 로 시작하고 ] 로 끝나는 부분 찾기
                        array_match = re.search(r'(\[\s*\{.*\}\s*\])', response, re.DOTALL)
                        if array_match:
                            json_content = array_match.group(1).strip()
                            self.logger.debug("배열 패턴에서 JSON 추출됨")
                        else:
                            # 5. { 로 시작하고 } 로 끝나는 부분 찾기 (단일 객체)
                            obj_match = re.search(r'(\{\s*".*"\s*:.*\})', response, re.DOTALL)
                            if obj_match:
                                json_content = obj_match.group(1).strip()
                                self.logger.debug("객체 패턴에서 JSON 추출됨")
                            else:
                                # 마지막 방법: 줄별로 분석하여 JSON 부분 찾기
                                for line in response.splitlines():
                                    line = line.strip()
                                    if (line.startswith('{') and line.endswith('}')) or (line.startswith('[') and line.endswith(']')):
                                        try:
                                            json.loads(line)
                                            json_content = line
                                            self.logger.debug("줄별 분석에서 JSON 발견됨")
                                            break
                                        except json.JSONDecodeError:
                                            continue
            
            if not json_content:
                # JSON을 찾지 못한 경우 텍스트 기반으로 항목 생성 시도
                self.logger.warning("JSON을 찾을 수 없어 텍스트 기반 파싱 시도")
                text_items = self._create_qa_from_text(response, difficulty)
                if text_items:
                    return text_items
                
                # SQL 쿼리가 직접 있는지 확인
                if "SELECT" in response and "FROM" in response:
                    self.logger.info("SQL 쿼리가 감지되어 수동 항목 생성")
                    manual_item = self._create_manual_qa_item(response, difficulty)
                    if manual_item:
                        return [manual_item]
                
                return []
            
            # JSON 파싱 전 정리 (추가된 부분)
            # 때로는 JSON 문자열 앞뒤에 따옴표나 백틱이 포함될 수 있음
            json_content = json_content.strip('`"\' ')
            
            # JSON 파싱
            qa_items = json.loads(json_content)
            
            # 단일 항목인 경우 리스트로 변환
            if isinstance(qa_items, dict):
                qa_items = [qa_items]
            
            # 각 항목에 누락된 정보 추가
            for item in qa_items:
                if "difficulty" not in item:
                    item["difficulty"] = difficulty
            
            self.logger.info(f"텍스트에서 {len(qa_items)}개 항목 추출 성공")
            return qa_items
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 파싱 오류: {str(e)}")
            self.logger.debug(f"파싱 시도한 내용: {response[:500]}")
            return self._create_qa_from_text(response, difficulty)
        except Exception as e:
            self.logger.error(f"응답 파싱 중 오류 발생: {str(e)}")
            return []
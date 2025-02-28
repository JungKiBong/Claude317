import json
import time
import concurrent.futures
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import random

from ..models.base_model import BaseModel
from ..data.schema_loader import SchemaLoader
from ..data.qa_loader import QALoader
from .prompt_builder import PromptBuilder
from .sql_validator import SQLValidator
from ..utils.logger import get_logger

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
        
        # SQL 검증기 초기화
        self.sql_validator = SQLValidator(schema_loader) if validate_sql else None
        
        # 초기 Q&A 데이터 로드 (제공된 경우)
        self.initial_qa = []
        if qa_loader:
            self.initial_qa = qa_loader.load_qa_data()
    
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
        
        # 병렬 처리 또는 순차 처리 선택
        if parallel and count > 1:
            return self._generate_qa_parallel(
                prompt_builder=prompt_builder,
                difficulty=difficulty,
                count=count,
                max_workers=max_workers,
                batch_size=batch_size
            )
        else:
            return self._generate_qa_sequential(
                prompt_builder=prompt_builder,
                difficulty=difficulty,
                count=count
            )
    
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
        
        # 배치 크기 계산 (API 제한 고려)
        batch_size = min(5, count)
        remaining = count
        
        while remaining > 0:
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
            self.logger.info(f"{current_batch_size}개 Q&A 생성 중...")
            response, success = self.model.generate_with_retry(
                prompt=model_inputs.get("prompt", ""),
                system_prompt=model_inputs.get("system_prompt"),
                max_retries=self.max_retries
            )
            
            if not success:
                self.logger.error(f"생성 실패: {response}")
                continue
            
            # 응답 파싱
            try:
                qa_items = self._parse_qa_response(response, difficulty)
                if qa_items:
                    # 생성된 항목 검증 및 추가
                    valid_items = self._validate_qa_items(qa_items)
                    all_qa_items.extend(valid_items)
                    
                    # 충분한 수량이 생성되었는지 확인
                    remaining -= len(valid_items)
                    self.logger.info(f"{len(valid_items)}개 유효한 Q&A 생성 완료 (남은 수량: {remaining})")
                    
                    # 잠시 대기 (API 제한 고려)
                    if remaining > 0:
                        time.sleep(1)
                else:
                    self.logger.warning("생성된 Q&A 항목이 없습니다.")
            except Exception as e:
                self.logger.error(f"응답 파싱 오류: {str(e)}")
        
        return all_qa_items
    
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
        all_qa_items = []
        
        # 작업 분할
        total_batches = (count + batch_size - 1) // batch_size  # 올림 나눗셈
        batch_counts = [batch_size] * (total_batches - 1) + [count - batch_size * (total_batches - 1)]
        
        # 작업 함수 정의
        def generate_batch(batch_size: int, batch_idx: int) -> List[Dict[str, Any]]:
            self.logger.info(f"배치 {batch_idx+1}/{total_batches} 시작 (크기: {batch_size})")
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
                
                if not success:
                    self.logger.error(f"배치 {batch_idx+1} 생성 실패: {response}")
                    return []
                
                # 응답 파싱
                qa_items = self._parse_qa_response(response, difficulty)
                if qa_items:
                    # 생성된 항목 검증
                    valid_items = self._validate_qa_items(qa_items)
                    self.logger.info(f"배치 {batch_idx+1} 완료: {len(valid_items)}/{batch_size} 유효 항목 생성")
                    return valid_items
                else:
                    self.logger.warning(f"배치 {batch_idx+1}: 생성된 Q&A 항목이 없습니다.")
                    return []
            except Exception as e:
                self.logger.error(f"배치 {batch_idx+1} 처리 중 오류 발생: {str(e)}")
                return []
        
        # 병렬 실행
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(generate_batch, batch_count, i)
                for i, batch_count in enumerate(batch_counts)
            ]
            
            # 결과 수집
            for future in concurrent.futures.as_completed(futures):
                try:
                    batch_items = future.result()
                    all_qa_items.extend(batch_items)
                except Exception as e:
                    self.logger.error(f"작업 실행 중 오류: {str(e)}")
        
        # 결과 출력
        self.logger.info(f"병렬 생성 완료: {len(all_qa_items)}/{count} 항목 생성")
        
        return all_qa_items
    
    def _parse_qa_response(self, response: str, difficulty: str) -> List[Dict[str, Any]]:
        """모델 응답에서 Q&A 항목 파싱
        
        Args:
            response: 모델 응답 텍스트
            difficulty: 난이도
            
        Returns:
            파싱된 Q&A 항목 리스트
        """
        try:
            # JSON 응답 추출
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_content = json_match.group(1).strip()
            else:
                # JSON 코드 블록이 없으면 전체 응답에서 시도
                json_content = response.strip()
            
            # JSON 파싱
            qa_items = json.loads(json_content)
            
            # 단일 항목인 경우 리스트로 변환
            if isinstance(qa_items, dict):
                qa_items = [qa_items]
            
            # 각 항목에 누락된 정보 추가
            for item in qa_items:
                if "difficulty" not in item:
                    item["difficulty"] = difficulty
            
            return qa_items
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 파싱 오류: {str(e)}")
            self.logger.debug(f"파싱 시도한 내용: {response}")
            return []
        except Exception as e:
            self.logger.error(f"응답 파싱 중 오류 발생: {str(e)}")
            return []
    
    def _validate_qa_items(self, qa_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """생성된 Q&A 항목 검증
        
        Args:
            qa_items: 검증할 Q&A 항목 리스트
            
        Returns:
            유효한 Q&A 항목 리스트
        """
        valid_items = []
        
        for item in qa_items:
            # 필수 필드 확인
            if not all(key in item for key in ["question", "sql", "answer"]):
                self.logger.warning(f"필수 필드 누락: {item}")
                continue
            
            # SQL 쿼리 유효성 검증 (설정된 경우)
            if self.validate_sql and self.sql_validator:
                validation_result = self.sql_validator.validate_sql(item["sql"])
                
                if not validation_result["is_valid"]:
                    self.logger.warning(f"유효하지 않은 SQL: {item['sql']}")
                    self.logger.debug(f"SQL 오류: {validation_result['errors']}")
                    
                    # 수정 시도
                    if validation_result.get("corrected_sql"):
                        item["sql"] = validation_result["corrected_sql"]
                        self.logger.info(f"SQL 수정됨: {item['sql']}")
                    else:
                        # SQL 생성 재시도 (필요시 구현)
                        continue
            
            # 모든 검증 통과한 항목 추가
            valid_items.append(item)
        
        return valid_items
    
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
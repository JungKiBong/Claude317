import os
import sys
import argparse
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import time

from config import AppConfig, ModelConfig, get_default_config
from models import create_model
from data.schema_loader import SchemaLoader
from data.qa_loader import QALoader
from generator.qa_generator import QAGenerator
from utils.logger import setup_logger, log_success, log_progress

def parse_args():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(description="LLM 기반 Q&A 및 SQL 생성기")
    
    # 기본 설정
    parser.add_argument("--schema", type=str, help="데이터베이스 스키마 파일 경로")
    parser.add_argument("--output", type=str, help="출력 파일 경로")
    parser.add_argument("--qa", type=str, help="초기 Q&A 데이터 파일 경로")
    
    # 생성 설정
    parser.add_argument("--easy", type=int, default=10, help="생성할 쉬운 난이도 항목 수")
    parser.add_argument("--medium", type=int, default=10, help="생성할 중간 난이도 항목 수")
    parser.add_argument("--hard", type=int, default=10, help="생성할 어려운 난이도 항목 수")
    
    # 모델 설정
    parser.add_argument("--model-type", type=str, choices=["ollama", "openai", "huggingface", "claude"],
                        help="사용할 모델 타입")
    parser.add_argument("--model-name", type=str, help="사용할 모델 이름")
    parser.add_argument("--temperature", type=float, help="모델 온도 설정 (0~1)")
    parser.add_argument("--api-key", type=str, help="API 키")
    parser.add_argument("--api-base", type=str, help="API 기본 URL")
    
    # 성능 설정
    parser.add_argument("--parallel", action="store_true", help="병렬 처리 활성화")
    parser.add_argument("--sequential", dest="parallel", action="store_false", help="순차 처리 활성화")
    parser.add_argument("--workers", type=int, default=4, help="최대 작업자 수")
    parser.add_argument("--batch-size", type=int, default=5, help="배치 크기")
    
    # 추가 설정
    parser.add_argument("--no-validate", dest="validate_sql", action="store_false", 
                        help="SQL 유효성 검증 비활성화")
    parser.add_argument("--format", type=str, choices=["json", "csv", "excel"], default="json",
                        help="출력 파일 형식")
    parser.add_argument("--config", type=str, help="설정 파일 경로")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                        default="INFO", help="로그 레벨")
    
    return parser.parse_args()

def create_config_from_args(args) -> AppConfig:
    """명령줄 인자에서 설정 객체 생성
    
    Args:
        args: 파싱된 명령줄 인자
        
    Returns:
        AppConfig 객체
    """
    # 기본 설정 가져오기
    config = get_default_config()
    
    # 명령줄 인자로 설정 업데이트
    if args.schema:
        config.schema_path = Path(args.schema)
    
    if args.output:
        config.output_path = Path(args.output)
    
    if args.qa:
        config.initial_qa_path = Path(args.qa)
    
    # 난이도별 생성 수량
    if args.easy is not None:
        config.easy_count = args.easy
        
    if args.medium is not None:
        config.medium_count = args.medium
        
    if args.hard is not None:
        config.hard_count = args.hard
    
    # 모델 설정
    if args.model_type or args.model_name:
        # 기존 모델 설정 가져오기
        model_config = config.model_config
        
        if args.model_type:
            model_config.model_type = args.model_type
            
        if args.model_name:
            model_config.model_name = args.model_name
            
        if args.temperature is not None:
            model_config.temperature = args.temperature
            
        if args.api_key:
            model_config.api_key = args.api_key
            
        if args.api_base:
            model_config.api_base = args.api_base
    
    # 병렬 처리 설정
    if hasattr(args, 'parallel'):
        config.parallel = args.parallel
        
    if args.workers:
        config.max_workers = args.workers
        
    if args.batch_size:
        config.batch_size = args.batch_size
    
    # SQL 유효성 검증 설정
    if hasattr(args, 'validate_sql'):
        config.validate_sql = args.validate_sql
    
    # 출력 형식 설정
    if args.format:
        config.output_format = args.format
    
    # 로그 레벨 설정
    if args.log_level:
        config.log_level = args.log_level
    
    return config

def main():
    """메인 함수"""
    # 명령줄 인자 파싱
    args = parse_args()
    
    # 설정 로드
    if args.config:
        try:
            config = AppConfig.from_json(args.config)
        except Exception as e:
            print(f"설정 파일 로드 오류: {str(e)}")
            sys.exit(1)
    else:
        config = create_config_from_args(args)
    
    # 로거 설정
    logger = setup_logger(
        name="rag_qa_generator",
        level=config.log_level,
        log_file=Path("logs/generator.log")
    )
    logger.info("Q&A 생성기 시작")
    
    try:
        # 모델 초기화
        logger.info(f"모델 초기화: {config.model_config.model_type} - {config.model_config.model_name}")
        model = create_model(
            model_type=config.model_config.model_type,
            model_name=config.model_config.model_name,
            temperature=config.model_config.temperature,
            max_tokens=config.model_config.max_tokens,
            api_key=config.model_config.api_key,
            api_base=config.model_config.api_base
        )
        
        # 모델 사용 가능 여부 확인
        if not model.is_available():
            logger.error(f"모델을 사용할 수 없습니다: {config.model_config.model_name}")
            sys.exit(1)
            
        logger.info("모델 초기화 완료")
        
        # 데이터 로더 초기화
        schema_loader = SchemaLoader(config.schema_path)
        schema_loader.load_schema()
        logger.info(f"스키마 로드 완료: {config.schema_path}")
        
        # 초기 Q&A 데이터 로더 초기화 (있는 경우)
        qa_loader = None
        if config.initial_qa_path:
            qa_loader = QALoader(config.initial_qa_path)
            qa_loader.load_qa_data()
            logger.info(f"초기 Q&A 데이터 로드 완료: {config.initial_qa_path}")
        
        # 생성기 초기화
        generator = QAGenerator(
            model=model,
            schema_loader=schema_loader,
            qa_loader=qa_loader,
            validate_sql=config.validate_sql,
            max_retries=config.max_retries,
            logger=logger
        )
        
        # 결과 저장 경로 생성
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_filename = f"qa_results_{timestamp}.{config.output_format}"
        output_path = config.output_path / output_filename
        
        # 각 난이도별 생성
        all_qa_items = []
        
        if config.easy_count > 0:
            logger.info(f"쉬운 난이도 Q&A {config.easy_count}개 생성 시작")
            easy_items = generator.generate_qa(
                difficulty="easy",
                count=config.easy_count,
                parallel=config.parallel,
                max_workers=config.max_workers,
                batch_size=config.batch_size
            )
            all_qa_items.extend(easy_items)
            log_success(logger, f"쉬운 난이도 Q&A {len(easy_items)}개 생성 완료")
        
        if config.medium_count > 0:
            logger.info(f"중간 난이도 Q&A {config.medium_count}개 생성 시작")
            medium_items = generator.generate_qa(
                difficulty="medium",
                count=config.medium_count,
                parallel=config.parallel,
                max_workers=config.max_workers,
                batch_size=config.batch_size
            )
            all_qa_items.extend(medium_items)
            log_success(logger, f"중간 난이도 Q&A {len(medium_items)}개 생성 완료")
        
        if config.hard_count > 0:
            logger.info(f"어려운 난이도 Q&A {config.hard_count}개 생성 시작")
            hard_items = generator.generate_qa(
                difficulty="hard",
                count=config.hard_count,
                parallel=config.parallel,
                max_workers=config.max_workers,
                batch_size=config.batch_size
            )
            all_qa_items.extend(hard_items)
            log_success(logger, f"어려운 난이도 Q&A {len(hard_items)}개 생성 완료")
        
        # 결과 저장
        if all_qa_items:
            saved_path = generator.save_results(
                qa_items=all_qa_items,
                output_path=output_path,
                format=config.output_format
            )
            log_success(logger, f"전체 {len(all_qa_items)}개 Q&A 항목이 {saved_path}에 저장되었습니다.")
        else:
            logger.error("생성된 Q&A 항목이 없습니다.")
        
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {str(e)}", exc_info=True)
        sys.exit(1)
    
    logger.info("Q&A 생성기 종료")

if __name__ == "__main__":
    main()
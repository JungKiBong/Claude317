import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import json
from pathlib import Path

@dataclass
class ModelConfig:
    """LLM 모델 설정을 위한 클래스"""
    model_type: str  # ollama, huggingface, openai, claude 등
    model_name: str  # llama3, mistral, gpt-4 등
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.95
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    streaming: bool = False
    
    def __post_init__(self):
        """환경 변수에서 API 키 로드 및 설정값 검증"""
        # 대소문자 구분 없이 모델 타입 표준화
        self.model_type = self.model_type.lower()
        
        # 환경 변수에서 API 키 로드 (설정되지 않은 경우)
        if self.api_key is None:
            env_var_name = f"{self.model_type.upper()}_API_KEY"
            self.api_key = os.environ.get(env_var_name)
        
        # API 키가 필요한 모델인지 확인
        api_key_required = self.model_type in ["openai", "claude", "huggingface"]
        if api_key_required and not self.api_key:
            raise ValueError(f"{self.model_type} 모델을 사용하려면 API 키가 필요합니다.")
        
        # API 베이스 URL이 설정되지 않은 경우 기본값 설정
        if self.api_base is None:
            if self.model_type == "ollama":
                self.api_base = "http://localhost:11434/api"
            elif self.model_type == "openai":
                self.api_base = "https://api.openai.com/v1"
            elif self.model_type == "claude":
                self.api_base = "https://api.anthropic.com/v1"
        
        # 온도 범위 검증
        if not 0 <= self.temperature <= 1:
            raise ValueError("온도는 0과 1 사이의 값이어야 합니다.")

    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환 (API 키 제외)"""
        config_dict = {
            "model_type": self.model_type,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "api_base": self.api_base,
            "streaming": self.streaming
        }
        return config_dict

@dataclass
class AppConfig:
    """애플리케이션 전체 설정을 위한 클래스"""
    schema_path: Path  # 데이터베이스 스키마 파일 경로
    output_path: Path  # 결과 출력 경로
    model_config: ModelConfig  # 모델 설정
    initial_qa_path: Optional[Path] = None  # 초기 Q&A 데이터 파일 경로
    
    # 난이도별 생성 수량
    easy_count: int = 10
    medium_count: int = 10
    hard_count: int = 10
    
    # 병렬 처리 관련 설정
    parallel: bool = True
    max_workers: int = 4
    batch_size: int = 5
    
    # 생성 관련 설정
    validate_sql: bool = True
    max_retries: int = 3
    timeout: int = 60
    
    # 출력 설정
    output_format: str = "json"  # json, csv, excel
    log_level: str = "INFO"
    
    def __post_init__(self):
        """경로 변환 및 설정값 검증"""
        # 문자열 경로를 Path 객체로 변환
        if isinstance(self.schema_path, str):
            self.schema_path = Path(self.schema_path)
        
        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)
        
        if self.initial_qa_path and isinstance(self.initial_qa_path, str):
            self.initial_qa_path = Path(self.initial_qa_path)
        
        # 설정값 검증
        if not self.schema_path.exists():
            raise FileNotFoundError(f"스키마 파일이 존재하지 않습니다: {self.schema_path}")
        
        if self.initial_qa_path and not self.initial_qa_path.exists():
            raise FileNotFoundError(f"초기 Q&A 파일이 존재하지 않습니다: {self.initial_qa_path}")
        
        # 출력 디렉토리가 없으면 생성
        if not self.output_path.exists():
            self.output_path.mkdir(parents=True)
        
        # 출력 형식 검증
        valid_formats = ["json", "csv", "excel"]
        if self.output_format.lower() not in valid_formats:
            raise ValueError(f"지원되지 않는 출력 형식입니다. 다음 중 하나를 사용하세요: {', '.join(valid_formats)}")
        
        # 로그 레벨 검증
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"유효하지 않은 로그 레벨입니다. 다음 중 하나를 사용하세요: {', '.join(valid_log_levels)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        config_dict = {
            "schema_path": str(self.schema_path),
            "output_path": str(self.output_path),
            "model_config": self.model_config.to_dict(),
            "initial_qa_path": str(self.initial_qa_path) if self.initial_qa_path else None,
            "easy_count": self.easy_count,
            "medium_count": self.medium_count,
            "hard_count": self.hard_count,
            "parallel": self.parallel,
            "max_workers": self.max_workers,
            "batch_size": self.batch_size,
            "validate_sql": self.validate_sql,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "output_format": self.output_format,
            "log_level": self.log_level
        }
        return config_dict
    
    @classmethod
    def from_json(cls, json_path: str) -> 'AppConfig':
        """JSON 파일에서 설정 로드"""
        with open(json_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # ModelConfig 객체 생성
        model_data = config_data.pop('model_config')
        model_config = ModelConfig(**model_data)
        
        # AppConfig 객체 생성 (model_config를 별도 처리)
        config_data['model_config'] = model_config
        
        return cls(**config_data)

    def save_json(self, json_path: str) -> None:
        """설정을 JSON 파일로 저장"""
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

# 기본 설정 가져오기 
def get_default_config() -> AppConfig:
    """기본 애플리케이션 설정 생성"""
    model_config = ModelConfig(
        model_type="ollama",
        model_name="llama3",
        temperature=0.7
    )
    
    app_config = AppConfig(
        schema_path=Path("examples/schemas/ecommerce_schema.json"),
        output_path=Path("output"),
        model_config=model_config
    )
    
    return app_config
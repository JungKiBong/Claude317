from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Generator, Union, Tuple
import time

class BaseModel(ABC):
    """모든 LLM 모델의 기본 인터페이스를 정의하는 추상 클래스"""
    
    def __init__(self, model_name: str, **kwargs):
        """
        Args:
            model_name: 모델 이름
            **kwargs: 추가 설정 (온도, max_tokens 등)
        """
        self.model_name = model_name
        self.kwargs = kwargs
    
    @abstractmethod
    def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """텍스트 생성 메서드
        
        Args:
            prompt: 모델에 전달할 프롬프트 
            system_prompt: 시스템 프롬프트 (지원하는 모델만)
            **kwargs: 생성 시 추가 파라미터
            
        Returns:
            생성된 텍스트
        """
        pass
    
    @abstractmethod
    def generate_stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """스트리밍 텍스트 생성 메서드
        
        Args:
            prompt: 모델에 전달할 프롬프트
            system_prompt: 시스템 프롬프트 (지원하는 모델만)
            **kwargs: 생성 시 추가 파라미터
            
        Returns:
            생성된 텍스트 조각의 제너레이터
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 계산
        
        Args:
            text: 토큰 수를 계산할 텍스트
            
        Returns:
            토큰 수
        """
        pass
    
    def generate_with_retry(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs
    ) -> Tuple[str, bool]:
        """재시도 로직이 포함된 텍스트 생성
        
        Args:
            prompt: 모델에 전달할 프롬프트
            system_prompt: 시스템 프롬프트 (지원하는 모델만)
            max_retries: 최대 재시도 횟수
            retry_delay: 재시도 간 대기 시간(초)
            **kwargs: 생성 시 추가 파라미터
            
        Returns:
            (생성된 텍스트, 성공 여부) 튜플
        """
        attempts = 0
        error = None
        
        while attempts < max_retries:
            try:
                response = self.generate(
                    prompt=prompt, 
                    system_prompt=system_prompt,
                    **kwargs
                )
                return response, True
            except Exception as e:
                error = e
                attempts += 1
                if attempts < max_retries:
                    # 지수 백오프 적용
                    delay = retry_delay * (2 ** (attempts - 1))
                    time.sleep(delay)
        
        # 모든 재시도 실패 시 빈 문자열 반환하고 실패 표시
        return str(error), False
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환
        
        Returns:
            모델 정보를 담은 딕셔너리
        """
        return {
            "model_name": self.model_name,
            "model_type": self.__class__.__name__,
            **self.kwargs
        }
    
    @abstractmethod
    def is_available(self) -> bool:
        """모델 사용 가능 여부 확인
        
        Returns:
            사용 가능 여부 (True/False)
        """
        pass
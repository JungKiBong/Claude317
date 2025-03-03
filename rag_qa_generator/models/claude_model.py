import os
from typing import Dict, Optional, Generator, Any, List
import time

from .base_model import BaseModel

# Anthropic API를 위한 임포트
try:
    import anthropic
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

class ClaudeModel(BaseModel):
    """Anthropic Claude 모델 구현 클래스"""
    
    def __init__(
        self, 
        model_name: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        **kwargs
    ):
        """
        Args:
            model_name: Claude 모델 이름 (claude-3-opus, claude-3-sonnet 등)
            api_key: Anthropic API 키
            api_base: Anthropic API 기본 URL
            temperature: 생성 온도 (0~1)
            max_tokens: 최대 생성 토큰 수
            top_p: Top-p 샘플링 값
            **kwargs: 추가 파라미터
        """
        super().__init__(model_name=model_name)
        
        # Anthropic 패키지 사용 가능 여부 확인
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Claude 사용을 위해 'anthropic' 패키지를 설치하세요.")
        
        # API 키 설정
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API 키가 필요합니다. (ANTHROPIC_API_KEY 환경 변수 또는 api_key 파라미터로 제공)")
        
        # API 기본 URL 설정 (기본적으로 필요 없음)
        self.api_base = api_base
        
        # 모델 설정
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.kwargs = kwargs
        
        # Claude 클라이언트 초기화
        client_kwargs = {"api_key": self.api_key}
        if self.api_base:
            client_kwargs["base_url"] = self.api_base
        
        self.client = Anthropic(**client_kwargs)
    
    def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """텍스트 생성
        
        Args:
            prompt: 모델에 전달할 프롬프트
            system_prompt: 시스템 프롬프트
            **kwargs: 추가 파라미터
            
        Returns:
            생성된 텍스트
        """
        # 생성 설정 구성
        generation_params = {
            "model": self.model_name,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
        }
        
        # 시스템 프롬프트 추가
        if system_prompt:
            generation_params["system"] = system_prompt
        
        # stop 토큰 처리
        stop_sequences = kwargs.get("stop", [])
        if stop_sequences:
            generation_params["stop_sequences"] = stop_sequences if isinstance(stop_sequences, list) else [stop_sequences]
        
        try:
            # API 호출 (메시지 기반)
            response = self.client.messages.create(
                messages=[{"role": "user", "content": prompt}],
                **generation_params
            )
            
            # 응답에서 텍스트 추출
            if response.content and len(response.content) > 0:
                text_content = [block.text for block in response.content if hasattr(block, 'text')]
                return "\n".join(text_content)
            return ""
                
        except Exception as e:
            raise RuntimeError(f"Claude API 오류: {str(e)}")
    
    def generate_stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """스트리밍 텍스트 생성
        
        Args:
            prompt: 모델에 전달할 프롬프트
            system_prompt: 시스템 프롬프트
            **kwargs: 추가 파라미터
            
        Yields:
            생성된 텍스트 조각
        """
        # 생성 설정 구성
        generation_params = {
            "model": self.model_name,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
            "stream": True,  # 스트리밍 활성화
        }
        
        # 시스템 프롬프트 추가
        if system_prompt:
            generation_params["system"] = system_prompt
        
        # stop 토큰 처리
        stop_sequences = kwargs.get("stop", [])
        if stop_sequences:
            generation_params["stop_sequences"] = stop_sequences if isinstance(stop_sequences, list) else [stop_sequences]
        
        try:
            # 스트리밍 API 호출
            stream = self.client.messages.create(
                messages=[{"role": "user", "content": prompt}],
                **generation_params
            )
            
            # 스트리밍 응답 처리
            for chunk in stream:
                # 각 메시지 조각에서 텍스트 추출
                if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                    text = chunk.delta.text
                    if text:
                        yield text
                    
        except Exception as e:
            raise RuntimeError(f"Claude 스트리밍 API 오류: {str(e)}")
    
    def count_tokens(self, text: str) -> int:
        """텍스트 토큰 수 계산
        
        Args:
            text: 토큰 수를 계산할 텍스트
            
        Returns:
            토큰 수
        """
        try:
            # Anthropic의 토큰 계산 함수 사용
            token_count = self.client.count_tokens(text)
            return token_count
            
        except Exception:
            # 대체 방법
            try:
                import tiktoken
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
            except ImportError:
                # 대략적인 토큰 수 추정
                return len(text) // 4
    
    def is_available(self) -> bool:
        """Claude 모델 사용 가능 여부 확인
        
        Returns:
            사용 가능 여부 (True/False)
        """
        try:
            # 간단한 토큰 카운트로 API 연결 확인
            self.client.count_tokens("test")
            return True
        except Exception:
            return False
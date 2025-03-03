import os
from typing import Dict, Optional, Generator, Any, List
import time

from .base_model import BaseModel

# OpenAI API를 위한 임포트
try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

class OpenAIModel(BaseModel):
    """OpenAI 모델 구현 클래스"""
    
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
            model_name: OpenAI 모델 이름 (gpt-4, gpt-3.5-turbo 등)
            api_key: OpenAI API 키
            api_base: OpenAI API 기본 URL (기본값: https://api.openai.com/v1)
            temperature: 생성 온도 (0~1)
            max_tokens: 최대 생성 토큰 수
            top_p: Top-p 샘플링 값
            **kwargs: 추가 파라미터
        """
        super().__init__(model_name=model_name)
        
        # OpenAI 패키지 사용 가능 여부 확인
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI 사용을 위해 'openai' 패키지를 설치하세요.")
        
        # API 키 설정
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API 키가 필요합니다. (OPENAI_API_KEY 환경 변수 또는 api_key 파라미터로 제공)")
        
        # API 기본 URL 설정
        self.api_base = api_base
        
        # 모델 설정
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.kwargs = kwargs
        
        # OpenAI 클라이언트 초기화
        client_kwargs = {"api_key": self.api_key}
        if self.api_base:
            client_kwargs["base_url"] = self.api_base
        
        self.client = OpenAI(**client_kwargs)
    
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
        # 메시지 구성
        messages = self._prepare_messages(prompt, system_prompt)
        
        # 생성 설정 구성
        generation_params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "top_p": kwargs.get("top_p", self.top_p),
        }
        
        # stop 토큰 처리
        stop_sequences = kwargs.get("stop", [])
        if stop_sequences:
            generation_params["stop"] = stop_sequences
        
        try:
            # API 호출
            response = self.client.chat.completions.create(**generation_params)
            
            # 응답에서 텍스트 추출
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            return ""
                
        except Exception as e:
            raise RuntimeError(f"OpenAI API 오류: {str(e)}")
    
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
        # 메시지 구성
        messages = self._prepare_messages(prompt, system_prompt)
        
        # 생성 설정 구성
        generation_params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "top_p": kwargs.get("top_p", self.top_p),
            "stream": True,  # 스트리밍 활성화
        }
        
        # stop 토큰 처리
        stop_sequences = kwargs.get("stop", [])
        if stop_sequences:
            generation_params["stop"] = stop_sequences
        
        try:
            # 스트리밍 API 호출
            stream = self.client.chat.completions.create(**generation_params)
            
            # 스트리밍 응답 처리
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                    
        except Exception as e:
            raise RuntimeError(f"OpenAI 스트리밍 API 오류: {str(e)}")
    
    def count_tokens(self, text: str) -> int:
        """텍스트 토큰 수 계산
        
        Args:
            text: 토큰 수를 계산할 텍스트
            
        Returns:
            토큰 수
        """
        try:
            # tiktoken 라이브러리를 사용하여 토큰 수 계산
            import tiktoken
            
            # 모델에 맞는 인코딩 선택
            encoding_name = "cl100k_base"  # gpt-4, gpt-3.5-turbo 등에 사용
            if "gpt-3.5-turbo" in self.model_name or "gpt-4" in self.model_name:
                encoding_name = "cl100k_base"
            elif "text-davinci" in self.model_name:
                encoding_name = "p50k_base"
            elif "davinci" in self.model_name:
                encoding_name = "r50k_base"
            
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
            
        except ImportError:
            # tiktoken이 설치되어 있지 않은 경우 대략적인 토큰 수 추정
            return len(text) // 4
    
    def is_available(self) -> bool:
        """OpenAI 모델 사용 가능 여부 확인
        
        Returns:
            사용 가능 여부 (True/False)
        """
        try:
            # 간단한 요청으로 API 연결 확인
            self.client.models.list(limit=1)
            return True
        except Exception:
            return False
    
    def _prepare_messages(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """OpenAI API용 메시지 형식 구성
        
        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트
            
        Returns:
            메시지 리스트
        """
        messages = []
        
        # 시스템 메시지 추가 (제공된 경우)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 사용자 메시지 추가
        messages.append({"role": "user", "content": prompt})
        
        return messages
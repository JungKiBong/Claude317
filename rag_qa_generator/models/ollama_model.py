import json
import requests
from typing import Dict, Optional, Generator, Any
import tiktoken

from .base_model import BaseModel

class OllamaModel(BaseModel):
    """Ollama 모델 구현 클래스"""
    
    def __init__(
        self, 
        model_name: str,
        api_base: str = "http://localhost:11434/api",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        **kwargs
    ):
        """
        Args:
            model_name: Ollama 모델 이름 (llama3, mistral 등)
            api_base: Ollama API 기본 URL
            temperature: 생성 온도 (0~1)
            max_tokens: 최대 생성 토큰 수
            top_p: Top-p 샘플링 값
            **kwargs: 추가 파라미터
        """
        super().__init__(model_name=model_name)
        self.api_base = api_base.rstrip("/")  # 후행 슬래시 제거
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.kwargs = kwargs
        
        # Tiktoken을 사용한 토큰 카운팅을 위한 인코더 초기화 (fallback)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except:
            self.tokenizer = None
    
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
        # API 엔드포인트 설정
        endpoint = f"{self.api_base}/generate"
        
        # 요청 본문 구성
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "top_p": kwargs.get("top_p", self.top_p),
            "stop": kwargs.get("stop", None),
        }
        
        # 시스템 프롬프트가 제공된 경우 추가
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()  # HTTP 오류 발생 시 예외 처리
            
            # 응답 처리
            result = response.json()
            return result.get("response", "")
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Ollama API 연결 오류: {str(e)}")
    
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
        # API 엔드포인트 설정
        endpoint = f"{self.api_base}/generate"
        
        # 요청 본문 구성
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "top_p": kwargs.get("top_p", self.top_p),
            "stop": kwargs.get("stop", None),
            "stream": True,  # 스트리밍 활성화
        }
        
        # 시스템 프롬프트가 제공된 경우 추가
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            response = requests.post(
                endpoint, 
                json=payload, 
                stream=True,  # 스트리밍 응답 설정
                timeout=60
            )
            response.raise_for_status()
            
            # 스트리밍 응답 처리
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        line_json = line_text[6:]  # 'data: ' 제거
                        if line_json == "[DONE]":
                            break
                            
                        try:
                            chunk = json.loads(line_json)
                            if 'response' in chunk:
                                yield chunk['response']
                        except json.JSONDecodeError:
                            continue
                            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Ollama API 스트리밍 연결 오류: {str(e)}")
    
    def count_tokens(self, text: str) -> int:
        """텍스트 토큰 수 계산
        
        Args:
            text: 토큰 수를 계산할 텍스트
            
        Returns:
            토큰 수
        """
        # Ollama API를 통한 토큰 수 계산 시도
        try:
            endpoint = f"{self.api_base}/tokenize"
            payload = {
                "model": self.model_name,
                "prompt": text
            }
            response = requests.post(endpoint, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            return len(result.get("tokens", []))
            
        except requests.exceptions.RequestException:
            # API 호출 실패 시 tiktoken 사용 (fallback)
            if self.tokenizer:
                return len(self.tokenizer.encode(text))
            else:
                # 대략적인 토큰 수 추정 (4자당 1토큰)
                return len(text) // 4
    
    def is_available(self) -> bool:
        """Ollama 서비스 사용 가능 여부 확인
        
        Returns:
            사용 가능 여부 (True/False)
        """
        try:
            # Ollama 서버 연결 확인
            endpoint = f"{self.api_base}/version"
            response = requests.get(endpoint, timeout=5)
            response.raise_for_status()
            
            # 특정 모델 사용 가능 여부 확인
            # 특정 모델 사용 가능 여부 확인
            models_endpoint = f"{self.api_base}/tags"
            models_response = requests.get(models_endpoint, timeout=5)
            models_response.raise_for_status()
            
            models_data = models_response.json()
            available_models = [model["name"] for model in models_data.get("models", [])]
            
            # 요청된 모델이 사용 가능한지 확인
            return self.model_name in available_models
            
        except requests.exceptions.RequestException:
            return False
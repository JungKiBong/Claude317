import os
from typing import Dict, Optional, Generator, Any
import tiktoken
import time

from .base_model import BaseModel

# HuggingFace API를 위한 임포트
try:
    from huggingface_hub import InferenceClient
    from huggingface_hub.inference._text_generation import TextGenerationStreamOutput
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

class HuggingFaceModel(BaseModel):
    """HuggingFace 모델 구현 클래스"""
    
    def __init__(
        self, 
        model_name: str,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        **kwargs
    ):
        """
        Args:
            model_name: HuggingFace 모델 이름 (Hugging Face Hub에 등록된 모델 ID)
            api_key: HuggingFace API 키
            temperature: 생성 온도 (0~1)
            max_tokens: 최대 생성 토큰 수
            top_p: Top-p 샘플링 값
            **kwargs: 추가 파라미터
        """
        super().__init__(model_name=model_name)
        
        # HuggingFace 패키지 사용 가능 여부 확인
        if not HF_AVAILABLE:
            raise ImportError("HuggingFace 사용을 위해 'huggingface_hub' 패키지를 설치하세요.")
        
        # API 키 설정
        self.api_key = api_key or os.environ.get("HUGGINGFACE_API_KEY")
        if not self.api_key:
            raise ValueError("HuggingFace API 키가 필요합니다. (HUGGINGFACE_API_KEY 환경 변수 또는 api_key 파라미터로 제공)")
        
        # 모델 설정
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.kwargs = kwargs
        
        # HuggingFace 클라이언트 초기화
        self.client = InferenceClient(token=self.api_key)
        
        # 토큰 카운팅을 위한 tiktoken 인코더 초기화
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
        # 시스템 프롬프트가 있으면 합치기
        final_prompt = prompt
        if system_prompt:
            # Chat completion 또는 text completion에 따라 적절한 형식 사용
            if self._is_chat_model():
                # 모델별 적절한 시스템 메시지 포맷 사용
                final_prompt = self._format_chat_prompt(system_prompt, prompt)
            else:
                # 텍스트 모델용 포맷
                final_prompt = f"{system_prompt}\n\n{prompt}"
        
        # 생성 설정 구성
        generation_params = {
            "max_new_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
            "do_sample": True,
        }
        
        # stop 토큰 처리
        stop_sequences = kwargs.get("stop", [])
        if stop_sequences:
            if isinstance(stop_sequences, str):
                stop_sequences = [stop_sequences]
            generation_params["stop_sequences"] = stop_sequences
        
        try:
            # 모델 타입에 따라 다른 메서드 호출
            if self._is_chat_model():
                response = self.client.chat_completion(
                    model=self.model_name,
                    messages=[{"role": "user", "content": final_prompt}],
                    **generation_params
                )
                # 응답에서 텍스트 추출
                return response.choices[0].message.content
            else:
                # 일반 텍스트 생성
                response = self.client.text_generation(
                    model=self.model_name,
                    prompt=final_prompt,
                    **generation_params
                )
                return response
                
        except Exception as e:
            raise RuntimeError(f"HuggingFace API 오류: {str(e)}")
    
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
        # 시스템 프롬프트가 있으면 합치기
        final_prompt = prompt
        if system_prompt:
            if self._is_chat_model():
                final_prompt = self._format_chat_prompt(system_prompt, prompt)
            else:
                final_prompt = f"{system_prompt}\n\n{prompt}"
        
        # 생성 설정 구성
        generation_params = {
            "max_new_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
            "do_sample": True,
        }
        
        # stop 토큰 처리
        stop_sequences = kwargs.get("stop", [])
        if stop_sequences:
            if isinstance(stop_sequences, str):
                stop_sequences = [stop_sequences]
            generation_params["stop_sequences"] = stop_sequences
        
        try:
            # 모델 타입에 따라 다른 스트리밍 메서드 호출
            if self._is_chat_model():
                stream = self.client.chat_completion(
                    model=self.model_name,
                    messages=[{"role": "user", "content": final_prompt}],
                    stream=True,
                    **generation_params
                )
                
                # 스트리밍 응답 처리
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                # 일반 텍스트 생성 스트리밍
                stream = self.client.text_generation(
                    model=self.model_name,
                    prompt=final_prompt,
                    stream=True,
                    **generation_params
                )
                
                # 응답 처리
                for response in stream:
                    yield response.token.text
                    
        except Exception as e:
            raise RuntimeError(f"HuggingFace 스트리밍 API 오류: {str(e)}")
    
    def count_tokens(self, text: str) -> int:
        """텍스트 토큰 수 계산
        
        Args:
            text: 토큰 수를 계산할 텍스트
            
        Returns:
            토큰 수
        """
        try:
            # HuggingFace 토큰화 API 사용
            token_info = self.client.tokenize(text=text, model=self.model_name)
            return len(token_info.tokens)
            
        except Exception:
            # API 호출 실패 시 대체 방법 사용
            if self.tokenizer:
                return len(self.tokenizer.encode(text))
            else:
                # 대략적인 토큰 수 추정 (4자당 1토큰)
                return len(text) // 4
    
    def is_available(self) -> bool:
        """HuggingFace 모델 사용 가능 여부 확인
        
        Returns:
            사용 가능 여부 (True/False)
        """
        try:
            # 간단한 요청으로 API 연결 확인
            self.client.tokenize(text="test", model=self.model_name)
            return True
        except Exception:
            return False
    
    def _is_chat_model(self) -> bool:
        """현재 모델이 채팅 모델인지 확인
        
        Returns:
            채팅 모델 여부 (True/False)
        """
        # 일반적으로 알려진 채팅 모델 목록 (확장 가능)
        chat_models = [
            "meta-llama", "llama", "mistral", "gemma", 
            "mpt-chat", "falcon-chat", "chatglm", "mixtral"
        ]
        
        # 모델 이름에 채팅 관련 키워드가 포함되어 있는지 확인
        model_name_lower = self.model_name.lower()
        for chat_model in chat_models:
            if chat_model in model_name_lower:
                return True
                
        return "chat" in model_name_lower or "instruct" in model_name_lower
    
    def _format_chat_prompt(self, system_prompt: str, user_prompt: str) -> str:
        """채팅 모델용 프롬프트 포맷 지정
        
        Args:
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트
            
        Returns:
            포맷팅된 프롬프트
        """
        # 기본 Llama 스타일 포맷
        return f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{user_prompt} [/INST]"
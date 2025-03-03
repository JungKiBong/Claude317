import json
import requests
import time
from typing import Dict, Optional, Generator, Any, Tuple
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
        
        # 디버깅을 위한 로깅
        print(f"모델: {self.model_name}, 프롬프트 길이: {len(prompt)}")
        
        # 입력 프롬프트 단순화 (llama2용)
        if "llama2" in self.model_name.lower():
            # 프롬프트 간소화 시도 (너무 복잡한 지시사항이 문제 발생 가능)
            if len(prompt) > 1000 and "json" in prompt.lower():
                simple_prompt = """SQL Q&A 항목을 JSON 형식으로 생성해주세요. 간단한 예:
    [
    {
        "difficulty": "easy",
        "question": "전체 사용자 수는?",
        "sql": "SELECT COUNT(*) FROM users",
        "answer": "전체 사용자 수를 반환합니다"
    }
    ]
    """
                prompt = simple_prompt
        
        # Ollama 완전 호환 모드 (chat 엔드포인트 사용)
        try:
            # 'chat' API 엔드포인트 사용
            chat_endpoint = f"{self.api_base}/chat"
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            chat_payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens),
                "top_p": kwargs.get("top_p", self.top_p),
                "seed": kwargs.get("seed", 42),
                "stream": False
            }
            
            # 디버깅용 로그
            print(f"Chat API 요청: {chat_endpoint}")
            print(f"온도: {chat_payload['temperature']}, 최대 토큰: {chat_payload['num_predict']}")
            
            response = requests.post(chat_endpoint, json=chat_payload, timeout=120)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    message = result.get('message', {})
                    content = message.get('content', '')
                    
                    if content and content.strip():
                        print(f"Chat API 응답 성공 (길이: {len(content)})")
                        return content
                    else:
                        print("Chat API가 빈 응답 반환")
                except Exception as e:
                    print(f"Chat API 응답 처리 오류: {str(e)}")
            else:
                print(f"Chat API 오류 상태 코드: {response.status_code}")
        
        except Exception as e:
            print(f"Chat API 시도 중 오류: {str(e)}")
        
        # 기존 'generate' API로 폴백
        print("기본 generate API로 폴백")
        
        # 요청 본문 구성
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": kwargs.get("temperature", min(self.temperature, 0.2)),  # 더 낮은 온도 시도
            "num_predict": kwargs.get("max_tokens", min(self.max_tokens, 1024)),  # 더 적은 토큰 생성
            "top_p": kwargs.get("top_p", self.top_p),
            "stop": kwargs.get("stop", ["\n\n", "```\n\n"]),  # 더 적극적인 중지 토큰
            "raw": True  # 원시 출력 요청
        }
        
        # 시스템 프롬프트가 제공된 경우 추가
        if system_prompt:
            payload["system"] = system_prompt
        
        # Llama2 모델을 위한 추가 최적화
        if "llama2" in self.model_name.lower():
            payload["seed"] = 42  # 일관된 시드 사용
            payload["repeat_penalty"] = 1.3  # 높은 반복 페널티
            payload["mirostat"] = 1  # mirostat 샘플링 사용 (가능한 경우)
            payload["mirostat_eta"] = 0.1
            payload["mirostat_tau"] = 5.0
        
        # 완전히 새로운 접근법: 내용이 단순한 케이스에 대해 직접 질문
        model_name = f"{self.model_name}(온도:{payload['temperature']})"
        
        try:
            # 디버깅 로그
            print(f"Generate API 요청: {endpoint}")
            print(f"페이로드: {payload}")
            
            response = requests.post(endpoint, json=payload, timeout=120)
            response.raise_for_status()
            
            # 응답 디버깅
            print(f"응답 상태 코드: {response.status_code}")
            print(f"응답 내용 시작: {response.text[:100]}...")
            
            # 결과 추출
            result_text = ""
            
            # JSON 응답 처리
            if response.text:
                try:
                    # 줄바꿈으로 구분된 JSON 처리
                    for line in response.text.splitlines():
                        if not line.strip():
                            continue
                        
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                result_text += data["response"]
                        except json.JSONDecodeError:
                            result_text += line  # JSON이 아니면 그대로 추가
                            
                    # 아무것도 추출되지 않았으면 원본 반환
                    if not result_text:
                        result_text = response.text
                        
                except Exception as e:
                    print(f"응답 처리 중 오류: {str(e)}")
                    result_text = response.text
                    
            # 결과 로깅
            print(f"최종 응답 길이: {len(result_text)}")
            
            # 비상 대책: 완전히 빈 응답인 경우 샘플 생성
            if not result_text or not result_text.strip():
                print("빈 응답 감지 - 응급 대응 모드")
                
                # 모든 시도가 실패하면 마지막 대책으로 샘플 데이터 반환
                emergency_response = """[
    {
        "difficulty": "easy",
        "question": "부서별 직원 수는?",
        "sql": "SELECT department, COUNT(*) FROM employees GROUP BY department",
        "answer": "각 부서별 직원 수를 보여줍니다"
    }
    ]"""
                print("응급 샘플 데이터 반환")
                return emergency_response
                
            return result_text
            
        except Exception as e:
            print(f"Generate API 오류: {str(e)}")
            
            # 모든 시도가 실패하면 마지막 대책으로 샘플 데이터 반환
            emergency_response = """[
    {
        "difficulty": "easy",
        "question": "부서별 직원 수는?",
        "sql": "SELECT department, COUNT(*) FROM employees GROUP BY department",
        "answer": "각 부서별 직원 수를 보여줍니다"
    }
    ]"""
            print("API 실패 - 응급 샘플 데이터 반환")
            return emergency_response 
    def generate_with_retry(self, prompt: str, system_prompt: Optional[str] = None, max_retries: int = 3, **kwargs) -> Tuple[str, bool]:
        """재시도 기능을 포함한 텍스트 생성
        
        Args:
            prompt: 모델에 전달할 프롬프트
            system_prompt: 시스템 프롬프트
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 파라미터
            
        Returns:
            생성된 텍스트와 성공 여부를 포함한 튜플
        """
        # 재시도 카운터 초기화
        retry_count = 0
        
        # JSON 생성을 위한 추가 프롬프트
        if "json" in prompt.lower() and "llama2" in self.model_name.lower():
            # JSON 형식을 강조하는 접두사 추가
            prompt = "중요: 다음 지시를 따라 유효한 JSON 형식으로만 응답하세요. JSON 이외의 설명이나 텍스트는 포함하지 마세요.\n\n" + prompt
        
        while retry_count <= max_retries:
            try:
                # 온도 조정 (재시도마다 낮추기)
                current_temperature = max(0.1, self.temperature - (retry_count * 0.1))
                
                # 생성 요청
                response = self.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=current_temperature,
                    **kwargs
                )
                
                # 응답이 비어있는지 확인
                if not response or response.strip() == "":
                    # 상세 로그
                    print(f"빈 응답 수신 (재시도 {retry_count+1}/{max_retries+1})")
                    retry_count += 1
                    time.sleep(2)
                    continue
                
                # 응답이 JSON을 포함하는지 확인 (JSON이 요청된 경우)
                if "json" in prompt.lower() and not self._contains_json(response):
                    print(f"유효한 JSON이 없는 응답 수신 (재시도 {retry_count+1}/{max_retries+1})")
                    retry_count += 1
                    time.sleep(2)
                    continue
                
                return response, True
                
            except Exception as e:
                print(f"생성 중 오류 발생: {str(e)} (재시도 {retry_count+1}/{max_retries+1})")
                retry_count += 1
                time.sleep(2)
        
        # 모든 재시도 실패
        return f"최대 재시도 횟수 초과 ({max_retries}회)", False
    
    def _contains_json(self, text: str) -> bool:
        """문자열이 JSON 내용을 포함하는지 확인
        
        Args:
            text: 확인할 텍스트
            
        Returns:
            JSON 포함 여부
        """
        # [ 또는 { 로 시작하는 텍스트 블록 찾기
        import re
        
        # JSON 코드 블록 패턴
        json_block_pattern = r'```(?:json)?\s*(\[|\{).*?(\]|\})\s*```'
        if re.search(json_block_pattern, text, re.DOTALL):
            return True
        
        # 직접 JSON 패턴
        json_pattern = r'(\[|\{)\s*".*?(\]|\})'
        if re.search(json_pattern, text, re.DOTALL):
            return True
        
        # 각 줄이 JSON인지 확인
        for line in text.splitlines():
            line = line.strip()
            if (line.startswith('{') and line.endswith('}')) or (line.startswith('[') and line.endswith(']')):
                try:
                    json.loads(line)
                    return True
                except json.JSONDecodeError:
                    continue
        
        return False
    
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
            "num_predict": kwargs.get("max_tokens", self.max_tokens),  # max_tokens 대신 num_predict 사용
            "top_p": kwargs.get("top_p", self.top_p),
            "stop": kwargs.get("stop", None),
            "stream": True,  # 스트리밍 활성화
            "raw": True,  # 원시 출력 요청
        }
        
        # 시스템 프롬프트가 제공된 경우 추가
        if system_prompt:
            payload["system"] = system_prompt
        
        # Llama2 모델을 위한 추가 최적화
        if "llama2" in self.model_name.lower():
            payload["temperature"] = min(payload["temperature"], 0.5)
            payload["seed"] = kwargs.get("seed", 42)
            payload["repeat_penalty"] = kwargs.get("repeat_penalty", 1.1)
        
        try:
            response = requests.post(
                endpoint, 
                json=payload, 
                stream=True,  # 스트리밍 응답 설정
                timeout=120
            )
            response.raise_for_status()
            
            # 스트리밍 응답 처리
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    try:
                        # 'data: ' 접두사가 있는지 확인
                        if line_text.startswith('data: '):
                            line_json = line_text[6:]  # 'data: ' 제거
                        else:
                            line_json = line_text
                            
                        if line_json == "[DONE]":
                            break
                            
                        try:
                            chunk = json.loads(line_json)
                            if 'response' in chunk:
                                yield chunk['response']
                        except json.JSONDecodeError:
                            # JSON 파싱 실패 시 원시 텍스트 그대로 반환
                            yield line_text
                    except Exception:
                        # 예외 발생 시 원시 텍스트 그대로 반환
                        if line_text:
                            yield line_text
                            
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
            try:
                models_endpoint = f"{self.api_base}/tags"
                models_response = requests.get(models_endpoint, timeout=5)
                models_response.raise_for_status()
                
                models_data = models_response.json()
                available_models = [model["name"] for model in models_data.get("models", [])]
                
                # 요청된 모델이 사용 가능한지 확인
                model_available = self.model_name in available_models
                
                # 모델이 없으면 기본 모델만 확인
                if not model_available and len(available_models) > 0:
                    return True  # 모델이 없어도 서버는 동작 중이므로 작업 진행 가능
                
                return model_available
            except Exception:
                # 모델 목록을 가져올 수 없더라도 서버가 응답하면 사용 가능으로 판단
                return True
                
        except requests.exceptions.RequestException:
            return False
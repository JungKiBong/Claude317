from typing import Dict, Optional, Type, List
from .base_model import BaseModel

# 모델 클래스들을 동적으로 가져오기 (필요할 때만 임포트)
_MODEL_REGISTRY: Dict[str, Type[BaseModel]] = {}

def register_model(model_type: str, model_class: Type[BaseModel]) -> None:
    """모델 타입과 클래스를 레지스트리에 등록
    
    Args:
        model_type: 모델 타입 (ollama, huggingface 등)
        model_class: 모델 클래스
    """
    _MODEL_REGISTRY[model_type.lower()] = model_class

def get_model_class(model_type: str) -> Type[BaseModel]:
    """모델 타입에 해당하는 클래스 반환
    
    Args:
        model_type: 모델 타입 (ollama, huggingface 등)
        
    Returns:
        해당 모델 클래스
        
    Raises:
        ValueError: 지원되지 않는 모델 타입인 경우
    """
    model_type = model_type.lower()
    
    # 이미 등록된 모델인지 확인
    if model_type in _MODEL_REGISTRY:
        return _MODEL_REGISTRY[model_type]
    
    # 등록되지 않은 경우 임포트 후 등록
    try:
        if model_type == "ollama":
            from .ollama_model import OllamaModel
            register_model("ollama", OllamaModel)
            return OllamaModel
        elif model_type == "huggingface":
            from .huggingface_model import HuggingFaceModel
            register_model("huggingface", HuggingFaceModel)
            return HuggingFaceModel
        elif model_type == "openai":
            from .openai_model import OpenAIModel
            register_model("openai", OpenAIModel)
            return OpenAIModel
        elif model_type == "claude":
            from .claude_model import ClaudeModel
            register_model("claude", ClaudeModel)
            return ClaudeModel
        else:
            raise ValueError(f"지원되지 않는 모델 타입: {model_type}")
    except ImportError as e:
        raise ImportError(f"{model_type} 모델을 로드하는 데 실패했습니다. 필요한 패키지가 설치되어 있는지 확인하세요: {str(e)}")

def create_model(
    model_type: str,
    model_name: str,
    **kwargs
) -> BaseModel:
    """모델 타입과 이름에 따라 모델 인스턴스 생성
    
    Args:
        model_type: 모델 타입 (ollama, huggingface 등)
        model_name: 모델 이름 (llama3, mistral 등)
        **kwargs: 모델에 전달할 추가 파라미터
        
    Returns:
        생성된 모델 인스턴스
    """
    model_class = get_model_class(model_type)
    return model_class(model_name=model_name, **kwargs)

def get_available_model_types() -> List[str]:
    """사용 가능한 모델 타입 목록 반환
    
    Returns:
        사용 가능한 모델 타입 리스트
    """
    # 기본 지원 모델 타입
    model_types = ["ollama", "huggingface", "openai", "claude"]
    
    # 각 모델 타입의 사용 가능 여부 확인을 통해 필터링
    available_types = []
    for model_type in model_types:
        try:
            get_model_class(model_type)
            available_types.append(model_type)
        except (ImportError, ValueError):
            pass
    
    return available_types
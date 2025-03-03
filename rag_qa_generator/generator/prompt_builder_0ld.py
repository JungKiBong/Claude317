import re
from typing import Dict, List, Optional, Any
import json

class PromptBuilder:
    """LLM 프롬프트 생성 유틸리티 클래스"""
    
    def __init__(
        self, 
        model_type: str,
        schema_formatted: str,
        examples: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Args:
            model_type: 모델 타입 ('ollama', 'huggingface', 'openai', 'claude')
            schema_formatted: 형식화된 스키마 텍스트
            examples: 예시 Q&A 데이터 (생성 가이드로 사용)
        """
        self.model_type = model_type.lower()
        self.schema = schema_formatted
        self.examples = examples or []
    
    def build_qa_generation_prompt(
        self, 
        difficulty: str, 
        count: int = 1
    ) -> Dict[str, str]:
        """Q&A 생성을 위한 프롬프트 구성"""
        return {
            "system_prompt": self._get_base_system_prompt(),
            "user_prompt": self._build_qa_user_prompt(difficulty, count)
        }
    
    def build_sql_validation_prompt(
        self, 
        question: str, 
        sql: str
    ) -> Dict[str, str]:
        """SQL 유효성 검증을 위한 프롬프트 구성"""
        user_prompt = f"""다음 질문과 SQL 쿼리를 검증하세요:
## 질문
{question}
## SQL 쿼리
```sql
{sql}
```
## 데이터베이스 스키마
{self.schema}
이 SQL 쿼리가 다음 기준에 맞는지 검증하세요:
1. 문법적으로 올바른가?
2. 모든 테이블과 컬럼이 스키마에 존재하는가?
3. 질문에 대한 답을 제공하는가?
검증 결과를 다음 JSON 형식으로 반환하세요:
```json
{{
  "is_valid": true 또는 false,
  "errors": ["오류 메시지 1", "오류 메시지 2", ...],
  "corrected_sql": "수정된 SQL 쿼리 (필요한 경우)"
}}
```"""
        return {
            "system_prompt": self._get_sql_validation_system_prompt(),
            "user_prompt": user_prompt
        }
    
    def build_answer_generation_prompt(
        self, 
        question: str, 
        sql: str
    ) -> Dict[str, str]:
        """질문에 대한 답변 생성을 위한 프롬프트 구성"""
        user_prompt = f"""다음 질문과 SQL 쿼리를 바탕으로 답변을 작성하세요:
## 질문
{question}
## SQL 쿼리
```sql
{sql}
```
## 데이터베이스 스키마
{self.schema}
SQL 쿼리를 분석하고, 어떤 결과를 반환할지 설명하는 자연스러운 답변을 작성하세요."""
        return {
            "system_prompt": "당신은 SQL 전문가이며 데이터 분석가입니다. ...",
            "user_prompt": user_prompt
        }
    
    def _get_base_system_prompt(self) -> str:
        """기본 시스템 프롬프트 구성"""
        return "당신은 데이터베이스 전문가이자 SQL 튜터입니다. ..."
    
    def _get_sql_validation_system_prompt(self) -> str:
        """SQL 유효성 검증용 시스템 프롬프트 구성"""
        return "당신은 SQL 검증 전문가입니다. ..."
    
    def _build_qa_user_prompt(self, difficulty: str, count: int) -> str:
        """Q&A 생성용 사용자 프롬프트 구성"""
        difficulty_descriptions = {
            "easy": "- 단일 테이블 쿼리 ...",
            "medium": "- 2-3개 테이블 조인 ...",
            "hard": "- 3개 이상 테이블 조인 ..."
        }
        difficulty_desc = difficulty_descriptions.get(
            difficulty.lower(), difficulty_descriptions["medium"]
        )
        return f"""다음 데이터베이스 스키마를 바탕으로 {difficulty} 난이도의 Q&A를 {count}개 생성하세요.
## 데이터베이스 스키마
{self.schema}
## 난이도: {difficulty.upper()}
{difficulty_desc}
## 출력 형식
```json
[ {{ "difficulty": "{difficulty}", "question": "질문 내용", "sql": "SQL 쿼리", "answer": "답변 내용" }} ]
```"""
    
    def format_output_for_model(self, prompt_dict: Dict[str, str]) -> Dict[str, Any]:
        """모델 타입에 따라 프롬프트 포맷팅"""
        system_prompt = prompt_dict.get("system_prompt", "")
        user_prompt = prompt_dict.get("user_prompt", "")
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        if self.model_type in {"openai", "claude", "ollama"}:
            return {"system_prompt": system_prompt, "prompt": user_prompt}
        elif self.model_type == "huggingface":
            return {"prompt": f"시스템: {system_prompt}\n\n사용자: {user_prompt}"}
        return {"prompt": combined_prompt}

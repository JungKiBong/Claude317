import re
from typing import Dict, List, Optional, Any, Union
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
            "system_prompt": "당신은 SQL 전문가이며 데이터 분석가입니다. SQL 쿼리의 결과를 명확하고 이해하기 쉬운 자연어로 설명해야 합니다.",
            "user_prompt": user_prompt
        }
    
    def _get_base_system_prompt(self) -> str:
        """기본 시스템 프롬프트 구성"""
        return """당신은 데이터베이스 전문가이자 SQL 튜터입니다. 
주어진 데이터베이스 스키마를 바탕으로 정확한 SQL 질문과 답변을 생성해야 합니다.
항상 유효하고 실행 가능한 SQL 쿼리를 작성하세요."""
    
    def _get_sql_validation_system_prompt(self) -> str:
        """SQL 유효성 검증용 시스템 프롬프트 구성"""
        return """당신은 SQL 검증 전문가입니다.
주어진 데이터베이스 스키마와 SQL 쿼리를 검토하고 오류를 찾아 수정하세요."""
    
    def _build_qa_user_prompt(self, difficulty: str, count: int) -> str:
        """Q&A 생성용 사용자 프롬프트 구성 - 스키마 정보 강조
        
        Args:
            difficulty: 난이도 ('easy', 'medium', 'hard')
            count: 생성할 질문 수
            
        Returns:
            사용자 프롬프트 문자열
        """
        # 테이블 목록 추출 (스키마 정보가 있는 경우)
        schema_tables = []
        schema_summary = ""
        
        # 스키마에서 정보 추출 시도
        try:
            schema_str = self.schema
            if not isinstance(schema_str, str) and hasattr(schema_str, 'get'):
                # 사전 형태의 스키마
                tables = schema_str.get('tables', [])
                for table in tables:
                    table_name = table.get('name', '')
                    if table_name:
                        schema_tables.append(table_name)
                        
                        # 컬럼 정보 요약
                        columns = table.get('columns', [])
                        col_names = [col.get('name', '') for col in columns if col.get('name', '')]
                        
                        if col_names:
                            schema_summary += f"테이블 {table_name}: {', '.join(col_names)}\n"
            else:
                # 문자열 형태의 스키마에서 테이블명 추출 시도
                table_pattern = r'CREATE\s+TABLE\s+(?:\w+\.)?(\w+)'
                schema_tables = re.findall(table_pattern, schema_str, re.IGNORECASE)
                
                # 스키마 요약은 원본 스키마 그대로 사용
                schema_summary = schema_str
        except Exception:
            # 추출 실패 시 빈 목록 사용
            schema_tables = []
            schema_summary = self.schema  # 원본 스키마 유지
        
        # 난이도별 설명 (더 간결하게 제공)
        difficulty_descriptions = {
            "easy": "단일 테이블 쿼리와 기본 조건만 사용",
            "medium": "2개 테이블 JOIN과 GROUP BY 사용",
            "hard": "다중 테이블 JOIN, 서브쿼리, 윈도우 함수 사용"
        }
        
        # 난이도에 맞는 설명 선택
        difficulty_desc = difficulty_descriptions.get(
            difficulty.lower(), difficulty_descriptions["medium"]
        )
        
        # Ollama 모델용 최적화
        if "ollama" in self.model_type.lower():
            # 스키마 정보 강조 버전
            tables_str = ", ".join(schema_tables) if schema_tables else "제공된 스키마의 테이블"
            
            # 사용 가능한 테이블 강조
            tables_instruction = ""
            if schema_tables:
                tables_instruction = f"\n\n사용 가능한 테이블: {tables_str}\n다음 테이블들만 사용하여 SQL을 작성하세요."
            
            prompt = f"""다음 데이터베이스 스키마를 바탕으로 {difficulty} 난이도의 SQL 질문을 {count}개 생성하세요.

    ## 데이터베이스 스키마
    {schema_summary}{tables_instruction}

    ## 중요: 위의 스키마에 있는 테이블과 컬럼만 사용하세요. 가상의 테이블이나 컬럼을 사용하지 마세요.

    난이도: {difficulty.upper()} ({difficulty_desc})

    각 질문에 대해 다음 정보를 포함하는 JSON 형식으로 응답하세요:
    1. 질문 (question): 데이터베이스에 관한 질문
    2. SQL 쿼리 (sql): 질문에 답하는 유효한 SQL 쿼리
    3. 답변 (answer): SQL 쿼리가 반환할 결과에 대한 설명

    JSON 응답 형식:
    ```json
    [
    {{
        "difficulty": "{difficulty}",
        "question": "질문 내용",
        "sql": "SQL 쿼리",
        "answer": "답변 내용"
    }}
    ]
    ```

    정확히 {count}개의 항목을 생성하고, JSON 형식만 반환하세요. 다른 설명이나 텍스트는 추가하지 마세요."""

            return prompt
        
        # 다른 모델용 기존 프롬프트 (스키마 정보 강조)
        # 예시 추가 (있는 경우)
        examples_text = ""
        if self.examples:
            examples_text = "\n## 예시\n"
            for i, example in enumerate(self.examples, 1):
                if example.get('difficulty', '').lower() == difficulty.lower():
                    examples_text += f"### 예시 {i}\n"
                    examples_text += f"질문: {example.get('question', '')}\n"
                    examples_text += f"SQL: ```sql\n{example.get('sql', '')}\n```\n"
                    examples_text += f"답변: {example.get('answer', '')}\n\n"
        
        # 스키마 정보 강조
        tables_str = ", ".join(schema_tables) if schema_tables else "제공된 스키마의 테이블"
        tables_instruction = ""
        if schema_tables:
            tables_instruction = f"\n\n사용 가능한 테이블: {tables_str}\n위의 테이블들만 사용하여 SQL을 작성하세요."
        
        # 프롬프트 구성 - 명확한 지시 및 출력 형식 강조
        prompt = f"""다음 데이터베이스 스키마를 바탕으로 {difficulty} 난이도의 SQL Q&A를 {count}개 생성하세요.

    ## 데이터베이스 스키마
    {schema_summary}{tables_instruction}

    ## 중요: 위의 스키마에 있는 테이블과 컬럼만 사용하세요. 가상의 테이블이나 컬럼을 사용하지 마세요.

    ## 난이도: {difficulty.upper()}
    {difficulty_desc}

    {examples_text}

    ## 지침
    1. 각 Q&A는 질문, SQL 쿼리, 답변으로 구성합니다.
    2. 질문은 명확하고 구체적이어야 합니다.
    3. SQL 쿼리는 정확하고 실행 가능해야 합니다.
    4. 답변은 SQL 쿼리의 예상 결과를 자연어로 설명해야 합니다.
    5. 답변에 SQL 쿼리를 포함하지 마세요.

    ## 중요: 출력 형식
    아래 JSON 형식으로만 응답하세요. 다른 설명이나 텍스트를 추가하지 마세요:

    ```json
    [
    {{
        "difficulty": "{difficulty}",
        "question": "질문 내용",
        "sql": "SQL 쿼리",
        "answer": "답변 내용"
    }}
    ]
    ```

    정확히 {count}개의 Q&A를 생성하세요. 유효한 JSON만 반환하세요."""
        
        return prompt
    def format_output_for_model(self, prompt_dict: Dict[str, str]) -> Dict[str, Any]:
        """모델 타입에 따라 프롬프트 포맷팅"""
        system_prompt = prompt_dict.get("system_prompt", "")
        user_prompt = prompt_dict.get("user_prompt", "")
        
        # 모델별 포맷팅
        if "ollama" in self.model_type.lower():
            # Ollama 모델 최적화: llama2 모델은 특히 JSON 생성에 어려움을 겪음
            if "llama" in self.model_type.lower() and "json" in user_prompt.lower():
                # JSON 형식을 강조하는 시스템 프롬프트
                json_system = """당신은 항상 유효한 JSON 형식으로만 응답하는 SQL 및 데이터베이스 전문가입니다.
    다른 설명이나 텍스트는 절대 추가하지 마세요. 
    오직 요청된 JSON 형식으로만 응답하세요."""
                
                # 시스템 프롬프트와 사용자 프롬프트 결합
                combined_prompt = f"{json_system}\n\n{user_prompt}"
                
                # JSON 형식을 강조하는 접두사 추가
                combined_prompt = """중요: 다음 형식의 유효한 JSON만 출력하세요:
    ```json
    [
    {
        "difficulty": "난이도",
        "question": "질문",
        "sql": "SQL 쿼리",
        "answer": "답변"
    }
    ]
    ```
    다른 텍스트나 설명을 추가하지 마세요. 오직 위 형식의 JSON만 반환하세요.

    """ + combined_prompt
                
                return {"prompt": combined_prompt}
            else:
                # 일반 Ollama 요청
                combined_prompt = f"시스템: {system_prompt}\n\n사용자 요청:\n{user_prompt}"
                return {"prompt": combined_prompt}
        elif self.model_type.lower() == "openai":
            return {
                "system_prompt": system_prompt,
                "prompt": user_prompt
            }
        elif self.model_type.lower() == "claude":
            return {
                "system_prompt": system_prompt, 
                "prompt": user_prompt
            }
        elif self.model_type.lower() == "huggingface":
            return {"prompt": f"시스템: {system_prompt}\n\n사용자: {user_prompt}"}
        else:
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            return {"prompt": combined_prompt}

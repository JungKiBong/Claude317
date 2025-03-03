# LLM RAG Q&A 및 SQL 자동 생성기

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10-blue)

대규모 언어 모델(LLM)을 활용하여 RAG(Retrieval-Augmented Generation) 시스템을 검증하기 위한 Q&A 데이터셋과 관련 SQL을 자동으로 생성하는 강력한 도구입니다.

<p align="center">
  <img src="https://github.com/yourusername/rag_qa_generator/raw/main/assets/banner.png" alt="RAG Q&A Generator Banner" width="600">
</p>

## 주요 기능

- 📊 **데이터베이스 스키마 기반 질문 생성**: 데이터베이스 스키마를 분석하여 실제 사용자 질문 시나리오를 자동 생성
- 🎯 **다양한 난이도**: 쉬움, 중간, 어려움 등 다양한 난이도의 질문 생성
- 💻 **SQL 쿼리 자동 생성**: 질문에 대응하는 정확한 SQL 쿼리 생성
- ✅ **SQL 유효성 검증**: 생성된 SQL의 문법 및 스키마 적합성 검증
- 🚀 **성능 최적화**: 병렬 처리, 캐싱, 오류 시 자동 재시도 지원
- 🖥️ **다양한 인터페이스**: CLI와 웹 기반 GUI(Streamlit) 인터페이스 모두 지원
- 🤖 **다양한 LLM 지원**: Ollama API 및 Hugging Face 로컬 모델 지원

## 설치 방법

### 요구 사항

- Python 3.8 이상
- 선택 사항: CUDA 지원 GPU (HuggingFace 모델 사용 시 권장)

### 기본 설치

```bash
# 저장소 복제
git clone https://github.com/yourusername/rag_qa_generator.git
cd rag_qa_generator

# 의존성 패키지 설치
pip install -e .
```

### 특정 모델 유형에 따른 설치

```bash
# Ollama 모델만 사용하려는 경우
pip install -e ".[ollama]"

# HuggingFace 모델만 사용하려는 경우
pip install -e ".[huggingface]"

# Streamlit UI를 사용하려는 경우
pip install -e ".[ui]"

# 모든 기능 설치
pip install -e ".[all]"
```

## 사용 방법

### CLI 모드

명령줄에서 다음과 같이 실행합니다:

```bash
# 기본 사용법
python run.py cli --schema examples/schemas/ecommerce_schema.json --qa examples/qa/ecommerce_qa.json --output generated_qa.json

# 고급 설정
python run.py cli \
  --schema examples/schemas/ecommerce_schema.json \
  --qa examples/qa/ecommerce_qa.json \
  --output generated_qa.json \
  --model-type ollama \
  --model-name llama3 \
  --temperature 0.7 \
  --easy 10 \
  --medium 20 \
  --hard 10 \
  --parallel \
  --max-workers 3 \
  --validate-sql
```

### GUI 모드 (Streamlit)

웹 기반 인터페이스를 통해 사용하려면:

```bash
python run.py gui
```

브라우저에서 자동으로 http://localhost:8501 이 열립니다.

<p align="center">
  <img src="https://github.com/yourusername/rag_qa_generator/raw/main/assets/streamlit_ui.png" alt="Streamlit UI Screenshot" width="800">
</p>

## 입력 파일 형식

### 데이터베이스 스키마 (JSON)

```json
{
  "database_name": "ecommerce_db",
  "tables": {
    "customers": {
      "description": "고객 정보를 저장하는 테이블",
      "columns": [
        {"name": "customer_id", "type": "INT", "description": "고객 고유 식별자", "primary_key": true},
        {"name": "name", "type": "VARCHAR(100)", "description": "고객 이름"}
      ]
    }
  },
  "relationships": [
    {"from_table": "orders", "from_column": "customer_id", "to_table": "customers", "to_column": "customer_id"}
  ]
}
```

### Cold Start Q&A (JSON)

```json
[
  {
    "question": "2023년에 가장 많이 판매된 상품은 무엇인가요?",
    "answer": "2023년에 가장 많이 판매된 상품은 '스마트폰 XYZ 프로'로, 총 1,245개가 판매되었습니다.",
    "sql": "SELECT p.name, SUM(oi.quantity) as total_quantity FROM products p JOIN order_items oi ON p.product_id = oi.product_id JOIN orders o ON oi.order_id = o.order_id WHERE EXTRACT(YEAR FROM o.order_date) = 2023 GROUP BY p.product_id, p.name ORDER BY total_quantity DESC LIMIT 1;",
    "difficulty": "easy"
  }
]
```

## 출력 데이터셋

```json
[
  {
    "question": "가장 많은 주문을 한 고객 5명의 이름과 주문 횟수는 무엇인가요?",
    "answer": "가장 많은 주문을 한 상위 5명의 고객은 '홍길동'(32회), '김영희'(28회), '이철수'(25회), '박지영'(23회), '최민준'(19회)입니다.",
    "sql": "SELECT c.name, COUNT(o.order_id) AS order_count FROM customers c JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.customer_id, c.name ORDER BY order_count DESC LIMIT 5;",
    "difficulty": "medium",
    "sql_valid": true
  }
]
```

## 프로젝트 구조

```
rag_qa_generator/
├── run.py                      # 메인 실행 스크립트 (CLI/GUI)
├── main.py                     # CLI 모드 메인 실행 파일
├── streamlit_app.py            # Streamlit GUI 인터페이스
├── config.py                   # 설정 관련 클래스
├── models/                     # 모델 관련 모듈
├── data/                       # 데이터 처리 관련 모듈
├── generator/                  # 생성 관련 모듈
├── utils/                      # 유틸리티 모듈
└── examples/                   # 예제 데이터
```

## 성능 및 최적화

- **병렬 처리**: 다중 스레드를 사용하여 생성 속도 향상
- **LRU 캐싱**: 중복 쿼리 최소화로 성능 향상
- **오류 자동 재시도**: 네트워크 오류나 API 제한 시 자동 재시도
- **메모리 최적화**: 대량의 데이터셋 생성 시에도 안정적인 메모리 사용

## 라이선스

MIT 라이선스에 따라 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 기여하기

1. 저장소 포크 (https://github.com/yourusername/rag_qa_generator/fork)
2. 새 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -am 'Add some amazing feature'`)
4. 브랜치에 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 제출

## 연락처

프로젝트 관리자 - [@yourusername](https://github.com/yourusername)

프로젝트 링크: [https://github.com/yourusername/rag_qa_generator](https://github.com/yourusername/rag_qa_generator)

















# RAG Q&A 및 SQL 자동 생성기

데이터베이스 스키마와 초기 Q&A 데이터를 기반으로 다양한 난이도의 질문, 답변, SQL 쿼리를 자동으로 생성하는 도구입니다.

## 주요 기능

- 데이터베이스 스키마 기반으로 질문 생성
- 다양한 난이도(쉬움, 중간, 어려움)의 Q&A 생성
- 질문에 대응하는 SQL 쿼리 자동 생성
- SQL 유효성 검증
- 병렬 처리 지원으로 생성 성능 최적화
- CLI와 Streamlit 기반 GUI 인터페이스 제공
- Ollama, HuggingFace, OpenAI, Claude 등 다양한 LLM 지원

## 설치 방법
 
# 저장소 클론
git clone https://github.com/yourusername/rag_qa_generator.git
cd rag_qa_generator

# 필요 패키지 설치
pip install -e .



## 사용 방법
# CLI 모드


# 기본 사용법
python run.py --schema examples/schemas/ecommerce_schema.json --output output --model-type ollama --model-name llama3

# 상세 옵션
python run.py --schema examples/schemas/ecommerce_schema.json \
              --output output \
              --qa examples/qa/ecommerce_qa.json \
              --easy 5 --medium 10 --hard 5 \
              --model-type openai --model-name gpt-4 \
              --temperature 0.7 --api-key YOUR_API_KEY \
              --parallel --workers 4 --batch-size 5 \
              --format json



# Streamlit 인터페이스 실행
python run.py --gui
or
streamlit run streamlit_app.py


설정 옵션
옵션설명--schema데이터베이스 스키마 파일 경로--output결과 출력 경로--qa초기 Q&A 데이터 파일 경로 (선택사항)--easy생성할 쉬운 난이도 항목 수 (기본값: 10)--medium생성할 중간 난이도 항목 수 (기본값: 10)--hard생성할 어려운 난이도 항목 수 (기본값: 10)--model-type사용할 모델 타입 (ollama, openai, huggingface, claude)--model-name사용할 모델 이름--temperature모델 온도 설정 (0~1)--api-keyAPI 키 (필요한 경우)--parallel병렬 처리 활성화--workers최대 작업자 수 (기본값: 4)--batch-size배치 크기 (기본값: 5)--format출력 형식 (json, csv, excel)--config설정 파일 경로
예제 파일
프로젝트에는 다음과 같은 예제 파일이 포함되어 있습니다:

examples/schemas/ecommerce_schema.json: 이커머스 데이터베이스 스키마 예제
examples/schemas/hospital_schema.json: 병원 데이터베이스 스키마 예제
examples/qa/ecommerce_qa.json: 이커머스 관련 초기 Q&A 예제
examples/qa/hospital_qa.json: 병원 관련 초기 Q&A 예제



지원하는 모델
Ollama

llama3, mistral, gemma, codegemma 등
API 엔드포인트: 기본값 http://localhost:11434/api

OpenAI

gpt-4, gpt-4-0125-preview, gpt-3.5-turbo, gpt-3.5-turbo-0125 등
API 키 필요

Claude

claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307 등
API 키 필요

HuggingFace

meta-llama/Meta-Llama-3-8B-Instruct, mistralai/Mistral-7B-Instruct-v0.2 등
API 키 필요

라이선스
MIT License




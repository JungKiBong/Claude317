# LLM RAG Q&A 및 SQL 자동 생성기

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10-blue)
![Version](https://img.shields.io/badge/version-1.0.0-green)

대규모 언어 모델(LLM)을 활용하여 RAG(Retrieval-Augmented Generation) 시스템을 검증하기 위한 Q&A 데이터셋과 관련 SQL을 자동으로 생성하는 강력한 도구입니다.

<p align="center">
  <img src="https://github.com/yourusername/rag_qa_generator/raw/main/assets/banner.png" alt="RAG Q&A Generator Banner" width="600">
</p>

## 🚀 주요 기능

- 📊 **데이터베이스 스키마 기반 질문 생성**: 데이터베이스 스키마를 분석하여 실제 사용자 질문 시나리오를 자동 생성
- 🎯 **다양한 난이도**: 쉬움, 중간, 어려움 등 다양한 난이도의 질문 생성
- 💻 **SQL 쿼리 자동 생성**: 질문에 대응하는 정확한 SQL 쿼리 생성
- ✅ **SQL 유효성 검증**: 생성된 SQL의 문법 및 스키마 적합성 검증
- 🚀 **성능 최적화**: 병렬 처리, 캐싱, 오류 시 자동 재시도 지원
- 🖥️ **다양한 인터페이스**: CLI와 웹 기반 GUI(Streamlit) 인터페이스 모두 지원
- 🤖 **다양한 LLM 지원**: Ollama, Hugging Face, OpenAI 및 Claude 모델 지원

## 🔌 지원 모델

| 모델 유형 | 설명 | 필요 사항 |
|----------|------|----------|
| **Ollama** | 로컬에서 실행되는 오픈소스 모델 | Ollama 설치 필요 |
| **Hugging Face** | 로컬 또는 API 기반 다양한 모델 | 선택적으로 CUDA 가속 |
| **OpenAI** | GPT-4, GPT-3.5 등 OpenAI 모델 | OpenAI API 키 필요 |
| **Claude** | Anthropic Claude 시리즈 모델 | Anthropic API 키 필요 |

## 📋 설치 방법

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

# OpenAI 모델만 사용하려는 경우
pip install -e ".[openai]"

# Claude 모델만 사용하려는 경우
pip install -e ".[claude]"

# Streamlit UI를 사용하려는 경우
pip install -e ".[ui]"

# 모든 기능 설치
pip install -e ".[all]"
```

## 🛠️ 사용 방법

### CLI 모드

명령줄에서 다음과 같이 실행합니다:

```bash
# 기본 사용법
python run.py cli --schema examples/schemas/ecommerce_schema.json --qa examples/qa/ecommerce_qa.json --output generated_qa.json

# OpenAI 모델 사용
python run.py cli \
  --schema examples/schemas/ecommerce_schema.json \
  --qa examples/qa/ecommerce_qa.json \
  --output generated_qa.json \
  --model-type openai \
  --model-name gpt-3.5-turbo \
  --temperature 0.7 \
  --easy 10 \
  --medium 20 \
  --hard 10

# Claude 모델 사용
python run.py cli \
  --schema examples/schemas/ecommerce_schema.json \
  --qa examples/qa/ecommerce_qa.json \
  --output generated_qa.json \
  --model-type claude \
  --model-name claude-3-sonnet \
  --temperature 0.7
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

## 📂 입력 파일 형식

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

## 📊 출력 데이터셋

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

## 🗂️ 프로젝트 구조

```
rag_qa_generator/
├── run.py                      # 메인 실행 스크립트 (CLI/GUI)
├── cli.py                      # 향상된 CLI 인터페이스
├── streamlit_app.py            # 개선된 Streamlit GUI 인터페이스
├── config/                     # 설정 관련 모듈
├── models/                     # 모델 관련 모듈
├── data/                       # 데이터 처리 관련 모듈
├── generator/                  # 생성 관련 모듈
├── utils/                      # 유틸리티 모듈
├── ui/                         # UI 관련 모듈
└── examples/                   # 예제 데이터
```

## ⚡ 성능 및 최적화

- **병렬 처리**: 다중 스레드를 사용하여 생성 속도 향상
- **LRU 캐싱**: 중복 쿼리 최소화로 성능 향상
- **오류 자동 재시도**: 네트워크 오류나 API 제한 시 자동 재시도
- **메모리 최적화**: 대량의 데이터셋 생성 시에도 안정적인 메모리 사용
- **응답 스트리밍**: 지원하는 모델(OpenAI, Claude)에서 스트리밍 응답 활용

## 🔧 환경 변수

환경 변수를 사용하여 API 키와 기타 설정을 관리할 수 있습니다:

```bash
# OpenAI API 키 설정
export OPENAI_API_KEY=your-api-key-here

# Anthropic API 키 설정
export ANTHROPIC_API_KEY=your-api-key-here

# 기본 출력 디렉토리 설정
export RAG_OUTPUT_DIR=/path/to/output/directory

# 로깅 레벨 설정
export RAG_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

또는 `.env` 파일을 사용할 수 있습니다 (dotenv 패키지 필요):

```bash
# .env 파일
OPENAI_API_KEY=your-api-key-here
ANTHROPIC_API_KEY=your-api-key-here
RAG_OUTPUT_DIR=/path/to/output/directory
RAG_LOG_LEVEL=INFO
```

## 🔄 API 사용 예제

Python 코드에서 직접 사용하는 예제:

```python
from config.model_config import ModelConfig
from models.model_factory import ModelFactory
from generator.qa_generator import QAGenerator
from data.schema_loader import DatabaseSchema
from data.qa_loader import QACollection

# 모델 설정
model_config = ModelConfig(
    model_type="openai",  # 'ollama', 'huggingface', 'openai', 'claude'
    model_name="gpt-3.5-turbo", 
    temperature=0.7
)

# 스키마 및 QA 데이터 로드
db_schema = DatabaseSchema("examples/schemas/ecommerce_schema.json")
qa_collection = QACollection("examples/qa/ecommerce_qa.json")

# 생성 옵션
options = {
    'output_file': 'generated_qa.json',
    'num_easy': 5,
    'num_medium': 10,
    'num_hard': 5,
    'use_parallel': True,
    'max_workers': 3,
    'validate_sql': True
}

# 생성기 초기화 및 실행
generator = QAGenerator(
    model_config=model_config,
    db_schema=db_schema,
    qa_collection=qa_collection,
    options=options
)

# 데이터셋 생성
results = generator.generate_dataset()

# 결과 출력
print(f"생성된 항목 수: {len(results)}")
```

## 📝 앞으로 개발 계획

- [ ] 생성된 SQL 쿼리 실제 실행 및 검증 기능
- [ ] 특정 도메인이나 산업 분야별 템플릿 지원
- [ ] 다국어 Q&A 생성 지원
- [ ] 벡터 검색을 포함한 고급 RAG 테스트 시나리오 생성
- [ ] Docker 컨테이너화 및 클라우드 배포 옵션
- [ ] 분산 처리 지원으로 대규모 데이터셋 생성 성능 향상

## 📜 라이선스

MIT 라이선스에 따라 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 🤝 기여하기

1. 저장소 포크 (https://github.com/yourusername/rag_qa_generator/fork)
2. 새 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -am 'Add some amazing feature'`)
4. 브랜치에 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 제출

## 📮 연락처

프로젝트 관리자 - [@yourusername](https://github.com/yourusername)

프로젝트 링크: [https://github.com/yourusername/rag_qa_generator](https://github.com/yourusername/rag_qa_generator)

---

<p align="center">
  <img src="https://github.com/yourusername/rag_qa_generator/raw/main/assets/logo-small.png" alt="RAG Q&A Generator" width="100">
  <br>
  <em>RAG Q&A 및 SQL 자동 생성기로 데이터 기반 검증의 새로운 지평을 열어보세요!</em>
</p>
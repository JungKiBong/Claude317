rag_qa_generator/
├── run.py                      # 메인 실행 스크립트 (CLI/GUI)
├── cli.py                      # 향상된 CLI 인터페이스
├── streamlit_app.py            # 개선된 Streamlit GUI 인터페이스
├── setup.py                    # 패키지 설치 스크립트
├── requirements.txt            # 핵심 의존성 패키지
├── requirements-dev.txt        # 개발용 의존성 패키지
├── README.md                   # 프로젝트 설명서
├── CHANGELOG.md                # 변경 이력
├── LICENSE                     # 라이선스 파일
├── .env.example                # 환경 변수 예제 파일
├── .gitignore                  # Git 무시 파일 목록
│
├── config/                     # 설정 관련 모듈
│   ├── __init__.py             # 패키지 초기화
│   ├── app_config.py           # 애플리케이션 설정
│   ├── model_config.py         # 모델 설정
│   └── settings.py             # 전역 설정 및 환경 변수
│
├── models/                     # 모델 관련 모듈
│   ├── __init__.py             # 패키지 초기화
│   ├── base_model.py           # 기본 모델 인터페이스
│   ├── model_factory.py        # 모델 생성 팩토리
│   ├── ollama_model.py         # Ollama 모델 구현
│   ├── huggingface_model.py    # HuggingFace 모델 구현
│   ├── openai_model.py         # OpenAI 모델 구현 (추가)
│   └── claude_model.py         # Claude 모델 구현 (추가)
│
├── data/                       # 데이터 처리 관련 모듈
│   ├── __init__.py             # 패키지 초기화
│   ├── schema_loader.py        # 데이터베이스 스키마 로더
│   ├── qa_loader.py            # Q&A 데이터 로더
│   └── dataset_manager.py      # 데이터셋 관리 (확장)
│
├── generator/                  # 생성 관련 모듈
│   ├── __init__.py             # 패키지 초기화
│   ├── prompt_builder.py       # 개선된 프롬프트 생성 유틸리티
│   ├── qa_generator.py         # 향상된 Q&A 생성기 클래스
│   ├── sql_validator.py        # 강화된 SQL 검증 유틸리티
│   └── sql_executor.py         # SQL 실행기 (새 기능)
│
├── utils/                      # 유틸리티 모듈
│   ├── __init__.py             # 패키지 초기화
│   ├── logger.py               # 로깅 유틸리티
│   ├── file_handler.py         # 파일 처리 유틸리티
│   ├── caching.py              # 캐싱 시스템
│   ├── progress.py             # 진행률 표시 유틸리티
│   └── errors.py               # 오류 처리 유틸리티
│
├── ui/                         # UI 관련 모듈 (새 디렉토리)
│   ├── __init__.py             # 패키지 초기화
│   ├── streamlit_helpers.py    # Streamlit 헬퍼 함수
│   ├── components.py           # 재사용 가능한 UI 컴포넌트
│   └── pages/                  # Streamlit 멀티페이지 구조
│       ├── __init__.py         # 패키지 초기화
│       ├── home.py             # 홈페이지
│       ├── generator.py        # 생성 페이지
│       ├── results.py          # 결과 페이지
│       └── settings.py         # 설정 페이지
│
└── examples/                   # 예제 데이터
    ├── schemas/                # 예제 스키마 파일
    │   ├── ecommerce_schema.json       # 이커머스 데이터베이스 스키마
    │   ├── hospital_schema.json        # 병원 데이터베이스 스키마
    │   └── finance_schema.json         # 금융 데이터베이스 스키마 (추가)
    │
    └── qa/                     # 예제 Q&A 파일
        ├── ecommerce_qa.json           # 이커머스 초기 Q&A
        ├── hospital_qa.json            # 병원 초기 Q&A
        └── finance_qa.json             # 금융 초기 Q&A (추가)
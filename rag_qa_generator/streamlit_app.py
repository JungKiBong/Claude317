import streamlit as st
import os
import sys
import json
from pathlib import Path
import time
from typing import Dict, List, Any, Optional
import pandas as pd

from data_catalog_connectors import DatahubConnector, CollibraConnector, AuthenticationError
from data.extended_schema_loader import ExtendedSchemaLoader
from generator.enhanced_schema_adapter import EnhancedSchemaAdapter


# 상위 디렉토리를 sys.path에 추가하여 모듈 임포트 가능하게 함
parent_dir = Path(__file__).parent.absolute()
sys.path.append(str(parent_dir))

# 프로젝트 모듈 임포트
from config import AppConfig, ModelConfig, get_default_config
from models import create_model, get_available_model_types
from data.schema_loader import SchemaLoader
from data.qa_loader import QALoader
from generator.qa_generator import QAGenerator
from utils.logger import get_logger

# 로거 설정
logger = get_logger(name="streamlit_app", level="INFO")

# 세션 상태 초기화
def init_session_state():
    """Streamlit 세션 상태 초기화"""
    if 'config' not in st.session_state:
        st.session_state.config = get_default_config()
    
    if 'schema_loader' not in st.session_state:
        st.session_state.schema_loader = None
    
    if 'qa_loader' not in st.session_state:
        st.session_state.qa_loader = None
    
    if 'model' not in st.session_state:
        st.session_state.model = None
    
    if 'generator' not in st.session_state:
        st.session_state.generator = None
    
    if 'qa_results' not in st.session_state:
        st.session_state.qa_results = []
    
    if 'is_generating' not in st.session_state:
        st.session_state.is_generating = False

# 스키마 업로드 및 처리
def handle_schema_upload(uploaded_file):
    """스키마 파일 업로드 처리
    
    Args:
        uploaded_file: Streamlit 업로드 파일 객체
    """
    if uploaded_file is not None:
        try:
            # 임시 파일로 저장
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            file_path = temp_dir / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # 설정 업데이트
            st.session_state.config.schema_path = file_path
            
            # 스키마 로더 초기화
            st.session_state.schema_loader = SchemaLoader(file_path)
            schema = st.session_state.schema_loader.load_schema()
            
            st.success(f"스키마 파일 '{uploaded_file.name}'이 업로드되었습니다.")
            return True
            
        except Exception as e:
            st.error(f"스키마 파일 처리 중 오류 발생: {str(e)}")
            return False
    
    return False

# 초기 Q&A 데이터 업로드 및 처리
def handle_qa_upload(uploaded_file):
    """Q&A 데이터 파일 업로드 처리
    
    Args:
        uploaded_file: Streamlit 업로드 파일 객체
    """
    if uploaded_file is not None:
        try:
            # 임시 파일로 저장
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            file_path = temp_dir / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # 설정 업데이트
            st.session_state.config.initial_qa_path = file_path
            
            # Q&A 로더 초기화
            st.session_state.qa_loader = QALoader(file_path)
            qa_data = st.session_state.qa_loader.load_qa_data()
            
            st.success(f"Q&A 데이터 파일 '{uploaded_file.name}'이 업로드되었습니다. {len(qa_data)}개 항목 로드됨.")
            return True
            
        except Exception as e:
            st.error(f"Q&A 데이터 파일 처리 중 오류 발생: {str(e)}")
            return False
    
    return False

# 모델 초기화
def initialize_model(model_type, model_name, temperature, api_key, api_base):
    """LLM 모델 초기화
    
    Args:
        model_type: 모델 타입
        model_name: 모델 이름
        temperature: 온도 설정
        api_key: API 키
        api_base: API 기본 URL
        
    Returns:
        초기화 성공 여부
    """
    try:
        # 모델 설정 업데이트
        st.session_state.config.model_config.model_type = model_type
        st.session_state.config.model_config.model_name = model_name
        st.session_state.config.model_config.temperature = temperature
        st.session_state.config.model_config.api_key = api_key
        st.session_state.config.model_config.api_base = api_base
        
        # 모델 생성
        model = create_model(
            model_type=model_type,
            model_name=model_name,
            temperature=temperature,
            api_key=api_key,
            api_base=api_base
        )
        
        # 모델 사용 가능 여부 확인
        if not model.is_available():
            st.error(f"모델을 사용할 수 없습니다: {model_name}")
            return False
        
        # 모델 저장
        st.session_state.model = model
        return True
        
    except Exception as e:
        st.error(f"모델 초기화 중 오류 발생: {str(e)}")
        return False

# 생성기 초기화
def initialize_generator():
    """Q&A 생성기 초기화
    
    Returns:
        초기화 성공 여부
    """
    try:
        if not st.session_state.model:
            st.error("모델이 초기화되지 않았습니다.")
            return False
            
        if not st.session_state.schema_loader:
            st.error("스키마가 로드되지 않았습니다.")
            return False
        
        # 생성기 생성
        st.session_state.generator = QAGenerator(
            model=st.session_state.model,
            schema_loader=st.session_state.schema_loader,
            qa_loader=st.session_state.qa_loader,
            validate_sql=st.session_state.config.validate_sql,
            max_retries=st.session_state.config.max_retries,
            logger=logger
        )
        
        return True
        
    except Exception as e:
        st.error(f"생성기 초기화 중 오류 발생: {str(e)}")
        return False

# Q&A 생성 실행
# generate_qa 함수 수정 (탭1에서 결과를 실시간으로 표시)
def generate_qa(difficulty, count, parallel, max_workers, batch_size):
    """Q&A 생성 작업 실행 - 실시간 결과 표시
    
    Args:
        difficulty: 난이도
        count: 생성할 항목 수
        parallel: 병렬 처리 여부
        max_workers: 최대 작업자 수
        batch_size: 배치 크기
        
    Returns:
        생성된 Q&A 항목 리스트
    """
    try:
        if not st.session_state.generator:
            if not initialize_generator():
                return []
        
        # 생성 시작
        st.session_state.is_generating = True
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 실시간 결과 표시를 위한 컨테이너
        result_container = st.empty()
        
        status_text.text(f"{difficulty} 난이도의 Q&A {count}개 생성 중...")
        
        # 결과 저장용 리스트
        result_items = []
        
        # 단일 배치 생성 (병렬 비활성화)
        if not parallel:
            # 생성 함수 호출
            result_items = st.session_state.generator.generate_qa(
                difficulty=difficulty,
                count=count,
                parallel=False,
                max_workers=1,
                batch_size=1
            )
            
            # 결과 표시
            progress_bar.progress(100)
            status_text.text(f"{difficulty} 난이도의 Q&A {len(result_items)}개 생성 완료")
            
            # 실시간 결과 표시
            if result_items:
                display_results(result_items, result_container)
        else:
            # 병렬 처리는 그대로 유지
            result_items = st.session_state.generator.generate_qa(
                difficulty=difficulty,
                count=count,
                parallel=parallel,
                max_workers=max_workers,
                batch_size=batch_size
            )
            
            # 결과 표시
            progress_bar.progress(100)
            status_text.text(f"{difficulty} 난이도의 Q&A {len(result_items)}개 생성 완료")
            
            # 생성 후 결과 표시
            if result_items:
                display_results(result_items, result_container)
        
        st.session_state.is_generating = False
        return result_items
        
    except Exception as e:
        st.error(f"Q&A 생성 중 오류 발생: {str(e)}")
        st.session_state.is_generating = False
        return []

# 실시간 결과 표시를 위한 함수 추가
def display_results(result_items, container):
    """생성된 결과를 실시간으로 표시
    
    Args:
        result_items: 표시할 결과 항목
        container: 표시할 Streamlit 컨테이너
    """
    with container.container():
        st.subheader("생성된 Q&A")
        
        # 응급 생성 항목 여부 확인
        emergency_items = [item for item in result_items if item.get("is_emergency", False)]
        if emergency_items:
            st.warning(f"⚠️ {len(emergency_items)}개 항목이 오류로 인해 자동 생성되었습니다. 품질이 낮을 수 있습니다.")
        
        # 데이터프레임 구성
        df_data = []
        for idx, item in enumerate(result_items, start=1):
            df_data.append({
                "번호": idx,
                "난이도": item.get("difficulty", ""),
                "질문": item.get("question", ""),
                "SQL": item.get("sql", ""),
                "답변": item.get("answer", "")
            })
        
        # 데이터프레임 표시
        if df_data:
            results_df = pd.DataFrame(df_data)
            st.dataframe(results_df, use_container_width=True)
            
            # 첫 항목 상세 표시
            if len(result_items) > 0:
                with st.expander("첫 번째 항목 상세", expanded=True):
                    item = result_items[0]
                    st.markdown(f"**질문**: {item.get('question', '')}")
                    st.markdown("**SQL**:")
                    st.code(item.get("sql", ""), language="sql")
                    st.markdown("**답변**:")
                    st.markdown(item.get("answer", ""))

# 결과 저장
def save_results(qa_items, output_format):
    """생성된 Q&A 결과 저장
    
    Args:
        qa_items: 저장할 Q&A 항목 리스트
        output_format: 출력 형식
        
    Returns:
        저장된 파일 경로
    """
    if not qa_items:
        st.error("저장할 Q&A 항목이 없습니다.")
        return None
    
    try:
        # 출력 디렉토리 생성
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # 파일명 생성
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_path = output_dir / f"qa_results_{timestamp}.{output_format}"
        
        # 생성기를 통해 저장
        if st.session_state.generator:
            saved_path = st.session_state.generator.save_results(
                qa_items=qa_items,
                output_path=output_path,
                format=output_format
            )
            return saved_path
        else:
            # QALoader를 사용하여 저장
            qa_loader = QALoader()
            qa_loader.save_qa_data(qa_items, output_path, output_format)
            return output_path
            
    except Exception as e:
        st.error(f"결과 저장 중 오류 발생: {str(e)}")
        return None

# 앱 구성 (메인 페이지)
def main():
    """Streamlit 앱 메인 함수"""
    st.set_page_config(
        page_title="LLM RAG Q&A 및 SQL 생성기",
        page_icon="📊",
        layout="wide"
    )
    
    # 세션 상태 초기화
    init_session_state()
    
    # 사이드바: 설정
    with st.sidebar:
        st.title("⚙️ 설정")
        # 탭으로 구분하여 파일 업로드와 데이터 카탈로그 연동 구분
        source_tab1, source_tab2 = st.tabs(["파일 업로드", "데이터 카탈로그"])
    
        ## 스키마 업로드
        #st.header("데이터베이스 스키마")
        #schema_file = st.file_uploader("스키마 파일 업로드 (JSON)", type=["json"], key="schema_uploader")
        #if schema_file and handle_schema_upload(schema_file):
        #    # 스키마 요약 표시
        #    if st.session_state.schema_loader:
        #        st.info(st.session_state.schema_loader.get_schema_summary())
        
        ## 초기 Q&A 업로드 (선택사항)
        #st.header("초기 Q&A 데이터 (선택사항)")
        #qa_file = st.file_uploader("Q&A 데이터 파일 업로드", type=["json", "csv", "xlsx"], key="qa_uploader")
        #if qa_file:
        #    handle_qa_upload(qa_file)
        with source_tab1:
        # 기존 스키마 업로드 코드
            st.header("데이터베이스 스키마")
            schema_file = st.file_uploader("스키마 파일 업로드 (JSON)", type=["json"], key="schema_uploader")
            if schema_file and handle_schema_upload(schema_file):
                # 스키마 요약 표시
                if st.session_state.schema_loader:
                    st.info(st.session_state.schema_loader.get_schema_summary())
            
            # 초기 Q&A 업로드 (선택사항)
            st.header("초기 Q&A 데이터 (선택사항)")
            qa_file = st.file_uploader("Q&A 데이터 파일 업로드", type=["json", "csv", "xlsx"], key="qa_uploader")
            if qa_file:
                handle_qa_upload(qa_file)
        
        with source_tab2:
            st.header("데이터 카탈로그 연동")
            use_catalog = st.checkbox("데이터 카탈로그 사용", value=False, key="use_catalog")
            
            if use_catalog:
                catalog_type = st.selectbox("카탈로그 유형", 
                                        ["DataHub", "Collibra"], 
                                        key="catalog_type")
                
                # DataHub 접속 정보 입력 섹션
                if catalog_type == "DataHub":
                    catalog_url = st.text_input("DataHub API URL", 
                                            value="http://localhost:8080/api/gms", 
                                            help="DataHub GMS API 엔드포인트 주소",
                                            key="datahub_url")
                    
                    catalog_token = st.text_input("API 토큰", 
                                                type="password",
                                                help="DataHub 인증 토큰",
                                                key="datahub_token")
                    
                    # 추가 설정 (선택 사항)
                    with st.expander("고급 설정"):
                        api_timeout = st.number_input("API 타임아웃(초)", 
                                                    min_value=5, 
                                                    max_value=120,
                                                    value=30,
                                                    key="api_timeout")
                        
                        cache_ttl = st.number_input("캐시 유효 기간(초)", 
                                                min_value=60,
                                                max_value=3600,
                                                value=300,
                                                key="cache_ttl")
                    
                    # 연결 테스트 버튼
                    if st.button("연결 테스트", key="test_connection"):
                        if not catalog_url or not catalog_token:
                            st.error("API URL과 토큰을 모두 입력해주세요.")
                        else:
                            try:
                                with st.spinner("DataHub 연결 테스트 중..."):
                                    # 연결 테스트
                                    connector = DatahubConnector(
                                        base_url=catalog_url,
                                        api_token=catalog_token,
                                        timeout=api_timeout
                                    )
                                    
                                    # 간단한 API 호출로 연결 테스트
                                    datasets = connector.list_datasets(limit=1)
                                    
                                    # 성공 메시지
                                    st.success(f"DataHub 연결 성공! {len(datasets)}개의 데이터셋이 있습니다.")
                                    
                                    # 세션 상태에 연결 정보 저장
                                    st.session_state.catalog_connector = connector
                                    st.session_state.connector_type = "datahub"
                                    
                            except AuthenticationError:
                                st.error("인증 실패. API 토큰을 확인하세요.")
                            except TimeoutError:
                                st.error(f"요청 시간 초과. API URL이 올바른지 확인하거나 타임아웃 값을 늘려보세요.")
                            except Exception as e:
                                st.error(f"연결 오류: {str(e)}")
                    
                    # 연결이 성공적으로 이루어진 경우에만 데이터셋 목록 표시
                    if "catalog_connector" in st.session_state and st.session_state.connector_type == "datahub":
                        try:
                            with st.spinner("데이터셋 목록 가져오는 중..."):
                                # 데이터셋 목록 가져오기
                                datasets = st.session_state.catalog_connector.list_datasets(limit=100)
                                
                                if datasets:
                                    # 데이터셋 선택 드롭다운 생성
                                    dataset_options = [f"{d['name']} ({d['platform']})" for d in datasets]
                                    selected_dataset_idx = st.selectbox(
                                        "사용할 데이터셋 선택", 
                                        options=range(len(dataset_options)),
                                        format_func=lambda i: dataset_options[i],
                                        key="selected_dataset"
                                    )
                                    
                                    # 선택된 데이터셋 정보
                                    selected_dataset = datasets[selected_dataset_idx]
                                    dataset_urn = selected_dataset["urn"]
                                    
                                    # 선택된 데이터셋의 스키마 로드 버튼
                                    if st.button("스키마 로드", key="load_schema_btn"):
                                        with st.spinner("스키마 정보 로드 중..."):
                                            # 확장된 스키마 로더 사용
                                            schema_loader = ExtendedSchemaLoader(
                                                data_catalog_connector=st.session_state.catalog_connector
                                            )
                                            
                                            # 데이터셋 URN 설정 및 스키마 로드
                                            try:
                                                schema = schema_loader.load_schema_from_catalog(dataset_urn)
                                                
                                                # 세션 상태에 스키마 로더 저장
                                                st.session_state.schema_loader = schema_loader
                                                st.session_state.dataset_urn = dataset_urn
                                                
                                                # 성공 메시지
                                                st.success(f"스키마 로드 성공: {selected_dataset['name']}")
                                                
                                                # 스키마 요약 정보 표시
                                                st.info(schema_loader.get_schema_summary())
                                                
                                            except Exception as e:
                                                st.error(f"스키마 로드 오류: {str(e)}")
                                else:
                                    st.info("사용 가능한 데이터셋이 없습니다.")
                                    
                        except Exception as e:
                            st.error(f"데이터셋 목록 가져오기 오류: {str(e)}")
                    
        # 모델 설정
        st.header("LLM 모델 설정")
        
        # 모델 타입 선택
        available_model_types = get_available_model_types()
        model_type = st.selectbox(
            "모델 타입",
            options=available_model_types,
            index=0 if "ollama" in available_model_types else 0,
            help="사용할 LLM 모델 타입을 선택하세요.",
            key="model_type_select"
        )
        
        # 모델별 추가 설정
        if model_type == "ollama":
            model_name = st.text_input("모델 이름", value="llama2:7b", help="Ollama 모델 이름 (llama3, mistral 등)", key="ollama_model_name")
            api_base = st.text_input("API 기본 URL", value="http://localhost:11434/api", help="Ollama API 기본 URL", key="ollama_api_base")
            api_key = None
        elif model_type == "openai":
            model_name = st.selectbox("모델 이름", options=["gpt-4", "gpt-4-0125-preview", "gpt-3.5-turbo", "gpt-3.5-turbo-0125"], key="openai_model_name")
            api_key = st.text_input("API 키", type="password", help="OpenAI API 키", key="openai_api_key")
            api_base = st.text_input("API 기본 URL (선택사항)", help="기본 OpenAI URL이 아닌 경우 입력", key="openai_api_base")
        elif model_type == "claude":
            model_name = st.selectbox("모델 이름", options=["claude-3-7-sonnet-20250219","claude-3-5-haiku-20241022"], key="claude_model_name")
            api_key = st.text_input("API 키", type="password", help="Anthropic API 키", key="claude_api_key")
            api_base = None
        elif model_type == "huggingface":
            model_name = st.text_input("모델 이름", value="meta-llama/Meta-Llama-3-8B-Instruct", help="HuggingFace 모델 ID", key="hf_model_name")
            api_key = st.text_input("API 키", type="password", help="HuggingFace API 키", key="hf_api_key")
            api_base = None
        
        # 공통 설정
        temperature = st.slider("온도", min_value=0.0, max_value=1.0, value=0.7, step=0.1, help="높을수록 다양한 응답, 낮을수록 일관된 응답", key="temperature_slider")
        
        # 모델 초기화 버튼
        if st.button("모델 초기화", key="init_model_btn"):
            if initialize_model(model_type, model_name, temperature, api_key, api_base):
                st.success("모델이 성공적으로 초기화되었습니다.")
    
    # 메인 컨텐츠
    st.title("LLM RAG Q&A 및 SQL 생성기")
    st.markdown("데이터베이스 스키마를 기반으로 다양한 난이도의 Q&A 및 SQL 쿼리를 생성합니다.")
    
    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["생성", "결과", "설정 내보내기"])
    
    # 탭 1: 생성
    with tab1:
        st.header("Q&A 생성")
        
        # 난이도별 생성 설정
        col1, col2, col3 = st.columns(3)
        
        with col1:
            easy_count = st.number_input("쉬운 난이도 항목 수", min_value=0, max_value=50, value=5, key="easy_count")
        
        with col2:
            medium_count = st.number_input("중간 난이도 항목 수", min_value=0, max_value=50, value=5, key="medium_count")
        
        with col3:
            hard_count = st.number_input("어려운 난이도 항목 수", min_value=0, max_value=50, value=5, key="hard_count")
        
        # 고급 설정
        with st.expander("고급 설정"):
            parallel = st.checkbox("병렬 처리", value=True, help="병렬 처리를 사용하여 성능 향상", key="parallel_checkbox")
            
            col1, col2 = st.columns(2)
            with col1:
                max_workers = st.number_input("최대 작업자 수", min_value=1, max_value=16, value=4, help="병렬 처리 시 최대 작업자 수", key="max_workers")
            
            with col2:
                batch_size = st.number_input("배치 크기", min_value=1, max_value=10, value=5, help="각 작업자가 처리할 항목 수", key="batch_size")
            
            validate_sql = st.checkbox("SQL 유효성 검증", value=True, help="생성된 SQL 쿼리의 유효성 검증", key="validate_sql")
            
            # 설정 적용
            st.session_state.config.parallel = parallel
            st.session_state.config.max_workers = max_workers
            st.session_state.config.batch_size = batch_size
            st.session_state.config.validate_sql = validate_sql
            
         # 생성 결과 저장 옵션
        auto_save = st.checkbox("생성 완료 후 자동 저장", value=False, help="생성이 완료된 후 자동으로 파일 저장", key="auto_save")
        if auto_save:
            save_format = st.selectbox("저장 형식", options=["json", "csv", "excel"], index=0, key="auto_save_format")
            
        # 생성 버튼
        if st.button("Q&A 생성 시작", disabled=st.session_state.is_generating, key="generate_btn"):
            if not st.session_state.schema_loader:
                st.error("데이터베이스 스키마를 먼저 업로드하세요.")
            elif not st.session_state.model:
                st.error("모델을 먼저 초기화하세요.")
            elif easy_count + medium_count + hard_count == 0:
                st.error("최소한 하나의 난이도에서 생성할 항목 수를 지정하세요.")
            else:
                # 생성기 초기화
                if initialize_generator():
                    # 결과 초기화
                    st.session_state.qa_results = []
                    
                    # 각 난이도별로 생성
                    all_results = []
                    
                    if easy_count > 0:
                        easy_results = generate_qa("easy", easy_count, parallel, max_workers, batch_size)
                        all_results.extend(easy_results)
                    
                    if medium_count > 0:
                        medium_results = generate_qa("medium", medium_count, parallel, max_workers, batch_size)
                        all_results.extend(medium_results)
                    
                    if hard_count > 0:
                        hard_results = generate_qa("hard", hard_count, parallel, max_workers, batch_size)
                        all_results.extend(hard_results)
                    
                    # 결과 저장
                    st.session_state.qa_results = all_results
                    
                    if all_results:
                        st.success(f"총 {len(all_results)}개의 Q&A가 생성되었습니다.")
                        
                        # 자동 저장 옵션이 켜져 있으면 파일로 저장
                        if auto_save:
                            saved_path = save_results(all_results, save_format)
                            if saved_path:
                                st.success(f"결과가 {saved_path}에 자동 저장되었습니다.")
                    else:
                        st.warning("생성된 Q&A가 없습니다.")
    
    # 탭 2: 결과
    with tab2:
        st.header("생성 결과")
        
        if not st.session_state.qa_results:
            st.info("아직 생성된 Q&A가 없습니다. '생성' 탭에서 Q&A를 생성하세요.")
        else:
            # 결과 출력 형식 선택
            output_format = st.selectbox("저장 형식", options=["json", "csv", "excel"], index=0, key="results_format")
            
            # 저장 버튼
            if st.button("결과 저장", key="save_results_btn"):
                saved_path = save_results(st.session_state.qa_results, output_format)
                if saved_path:
                    st.success(f"결과가 {saved_path}에 저장되었습니다.")
            
            # 난이도별 필터
            difficulties = ["전체"] + list(set(item.get("difficulty", "medium") for item in st.session_state.qa_results))
            selected_difficulty = st.selectbox("난이도 필터", options=difficulties, index=0, key="difficulty_filter")
            
            # 결과 테이블 (데이터프레임) 생성
            filtered_results = st.session_state.qa_results
            if selected_difficulty != "전체":
                filtered_results = [item for item in st.session_state.qa_results 
                                    if item.get("difficulty", "medium") == selected_difficulty]
            
            # 데이터프레임 생성 및 표시
            if filtered_results:
                # 표시할 컬럼 구성
                df_data = []
                for idx, item in enumerate(filtered_results, start=1):
                    df_data.append({
                        "번호": idx,
                        "난이도": item.get("difficulty", ""),
                        "질문": item.get("question", ""),
                        "SQL": item.get("sql", ""),
                        "답변": item.get("answer", "")
                    })
                
                results_df = pd.DataFrame(df_data)
                st.dataframe(results_df, use_container_width=True)
                
                # 개별 항목 상세 보기
                with st.expander("항목 상세 보기"):
                    item_idx = st.number_input("항목 번호", min_value=1, max_value=len(filtered_results), value=1, step=1, key="item_idx")
                    if 1 <= item_idx <= len(filtered_results):
                        item = filtered_results[item_idx - 1]
                        
                        st.subheader(f"질문 {item_idx}")
                        st.markdown(f"**난이도**: {item.get('difficulty', '')}")
                        st.markdown(f"**질문**: {item.get('question', '')}")
                        
                        st.markdown("**SQL**:")
                        st.code(item.get("sql", ""), language="sql")
                        
                        st.markdown("**답변**:")
                        st.markdown(item.get("answer", ""))
            else:
                st.info("선택된 난이도의 결과가 없습니다.")
    
    # 탭 3: 설정 내보내기
    with tab3:
        st.header("설정 내보내기")
        
        st.markdown("현재 설정을 JSON 파일로 저장하여 나중에 다시 사용할 수 있습니다.")
        
        if st.button("현재 설정 내보내기", key="export_btn"):
            try:
                # 설정 JSON 생성
                config_dict = st.session_state.config.to_dict()
                config_json = json.dumps(config_dict, indent=2, ensure_ascii=False)
                
                # 다운로드 버튼 생성
                st.download_button(
                    label="설정 파일 다운로드",
                    data=config_json,
                    file_name="qa_generator_config.json",
                    mime="application/json",
                    key="download_config_btn"
                )
                
                st.success("설정이 JSON으로 내보내기되었습니다.")
                
            except Exception as e:
                st.error(f"설정 내보내기 중 오류 발생: {str(e)}")
        
        # 설정 가져오기
        st.markdown("---")
        st.subheader("설정 가져오기")
        
        config_file = st.file_uploader("설정 파일 업로드 (JSON)", type=["json"], key="config_uploader")
        if config_file is not None:
            try:
                # 임시 파일로 저장
                temp_dir = Path("temp")
                temp_dir.mkdir(exist_ok=True)
                
                file_path = temp_dir / config_file.name
                with open(file_path, "wb") as f:
                    f.write(config_file.getbuffer())
                
                # 설정 로드
                loaded_config = AppConfig.from_json(str(file_path))
                st.session_state.config = loaded_config
                
                st.success("설정이 성공적으로 로드되었습니다.")
                
                # 설정 요약 표시
                st.markdown("### 로드된 설정 요약")
                st.markdown(f"- **모델 타입**: {loaded_config.model_config.model_type}")
                st.markdown(f"- **모델 이름**: {loaded_config.model_config.model_name}")
                st.markdown(f"- **스키마 경로**: {loaded_config.schema_path}")
                st.markdown(f"- **초기 Q&A 경로**: {loaded_config.initial_qa_path or '없음'}")
                
            except Exception as e:
                st.error(f"설정 로드 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()
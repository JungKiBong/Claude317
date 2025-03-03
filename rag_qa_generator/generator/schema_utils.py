import logging
import json
import os
import re
from typing import Dict, List, Any, Optional, Union

def setup_enhanced_logging():
    """향상된 로깅 설정"""
    # 로그 디렉토리 생성
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # 로거 설정
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # 기존 핸들러 제거 (중복 방지)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 핸들러 설정
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)-8s %(message)s')
    console_handler.setFormatter(console_format)
    
    # 파일 핸들러 (상세 로그)
    file_handler = logging.FileHandler(os.path.join(log_dir, "detailed_qa_generation.log"))
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    
    # SQL 검증 관련 로그만 저장하는 파일 핸들러
    sql_handler = logging.FileHandler(os.path.join(log_dir, "sql_validation.log"))
    sql_handler.setLevel(logging.DEBUG)
    sql_handler.setFormatter(file_format)
    
    # SQL 검증 로그 필터
    class SQLFilter(logging.Filter):
        def filter(self, record):
            return "SQL" in record.getMessage() or "sql" in record.getMessage()
    
    sql_handler.addFilter(SQLFilter())
    
    # 로거에 핸들러 추가
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(sql_handler)
    
    return logger

def extract_schema_info(db_path: str) -> Dict[str, Any]:
    """데이터베이스 스키마 정보 추출 및 저장
    
    Args:
        db_path: 데이터베이스 파일 경로
        
    Returns:
        스키마 정보를 담은 딕셔너리
    """
    logger = logging.getLogger(__name__)
    logger.info(f"데이터베이스 스키마 추출 시작: {db_path}")
    
    schema = {"tables": []}
    
    try:
        # SQLite 데이터베이스 연결
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 목록 가져오기
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            
            # 시스템 테이블 제외
            if table_name.startswith('sqlite_'):
                continue
                
            logger.debug(f"테이블 정보 추출 중: {table_name}")
            
            # 테이블 스키마 가져오기
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns_info = cursor.fetchall()
            
            columns = []
            for col in columns_info:
                # SQLite PRAGMA table_info() 컬럼 순서:
                # 0: cid, 1: name, 2: type, 3: notnull, 4: dflt_value, 5: pk
                column = {
                    "name": col[1],
                    "type": col[2],
                    "primary_key": col[5] == 1,
                    "nullable": col[3] == 0,
                    "default": col[4]
                }
                columns.append(column)
            
            # 테이블 추가
            schema["tables"].append({
                "name": table_name,
                "columns": columns
            })
        
        conn.close()
        logger.info(f"스키마 추출 완료: {len(schema['tables'])} 테이블")
        
        # 스키마를 파일로 저장 (디버깅 및 참조용)
        schema_file = "schema_info.json"
        with open(schema_file, 'w') as f:
            json.dump(schema, f, indent=2)
            
        logger.info(f"스키마 정보 저장됨: {schema_file}")
        
    except Exception as e:
        logger.error(f"스키마 추출 중 오류 발생: {str(e)}")
        # 샘플 스키마 사용
        schema = {
            "tables": [
                {
                    "name": "sample_table",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "primary_key": True},
                        {"name": "name", "type": "TEXT", "primary_key": False},
                        {"name": "value", "type": "INTEGER", "primary_key": False}
                    ]
                }
            ]
        }
        logger.warning("오류로 인해 샘플 스키마를 사용합니다.")
    
    return schema

class SchemaAdapter:
    """스키마 적응형 SQL 생성 및 검증 클래스"""
    
    def __init__(self, schema_loader=None, db_path=None):
        """
        Args:
            schema_loader: 스키마 로더 인스턴스
            db_path: 데이터베이스 파일 경로
        """
        self.logger = logging.getLogger(__name__)
        self.schema = None
        self.schema_tables = {}
        self.table_relationships = []
        
        # 스키마 로더나 DB 경로 중 하나 사용
        if schema_loader:
            try:
                self.schema = schema_loader.load_schema()
                self.logger.info("스키마 로더로부터 스키마 로드됨")
            except Exception as e:
                self.logger.error(f"스키마 로더 오류: {str(e)}")
        elif db_path:
            self.schema = extract_schema_info(db_path)
            self.logger.info(f"DB 파일로부터 스키마 추출됨: {db_path}")
        
        # 스키마 분석
        if self.schema:
            self._analyze_schema()
    
    def _analyze_schema(self):
        """스키마 분석 및 테이블 관계 추출"""
        if not self.schema:
            self.logger.warning("스키마가 없습니다. 분석을 건너뜁니다.")
            return
            
        self.logger.info("스키마 분석 시작")
        
        # 테이블 및 컬럼 정보 구성
        for table in self.schema.get('tables', []):
            table_name = table.get('name')
            if not table_name:
                continue
                
            columns = []
            primary_keys = []
            foreign_keys = []
            
            for column in table.get('columns', []):
                if isinstance(column, dict):
                    col_name = column.get('name')
                    if not col_name:
                        continue
                        
                    columns.append(col_name)
                    
                    # 기본키 식별
                    if column.get('primary_key'):
                        primary_keys.append(col_name)
                    
                    # 외래키 추정 (이름으로)
                    if '_id' in col_name.lower() and not column.get('primary_key'):
                        # 가능한 참조 테이블 추정
                        ref_table = col_name.lower().replace('_id', '')
                        foreign_keys.append({
                            'column': col_name,
                            'ref_table': ref_table,
                            'ref_column': 'id'  # 가정
                        })
                elif isinstance(column, str):
                    # 문자열인 경우 컬럼 이름으로 처리
                    columns.append(column)
                    if column.lower() == 'id':
                        primary_keys.append(column)
                    if '_id' in column.lower():
                        ref_table = column.lower().replace('_id', '')
                        foreign_keys.append({
                            'column': column,
                            'ref_table': ref_table,
                            'ref_column': 'id'
                        })
            
            # 테이블 정보 저장
            self.schema_tables[table_name] = {
                'columns': columns,
                'primary_keys': primary_keys,
                'foreign_keys': foreign_keys
            }
            
            # 관계 추출
            for fk in foreign_keys:
                self.table_relationships.append({
                    'from_table': table_name,
                    'from_column': fk['column'],
                    'to_table': fk['ref_table'],
                    'to_column': fk['ref_column']
                })
        
        self.logger.info(f"스키마 분석 완료: {len(self.schema_tables)} 테이블, {len(self.table_relationships)} 관계")
    
    def format_schema_for_prompt(self) -> str:
        """프롬프트용 스키마 정보 포맷팅"""
        if not self.schema_tables:
            return "사용 가능한 스키마 정보가 없습니다."
            
        # 간결한 형식으로 포맷팅
        formatted = "## 데이터베이스 스키마\n\n"
        
        for table_name, table_info in self.schema_tables.items():
            columns = table_info['columns']
            primary_keys = table_info['primary_keys']
            
            formatted += f"### {table_name}\n"
            for col in columns:
                pk_mark = " (PK)" if col in primary_keys else ""
                formatted += f"- {col}{pk_mark}\n"
            formatted += "\n"
        
        # 테이블 관계 추가
        if self.table_relationships:
            formatted += "### 테이블 관계\n"
            for rel in self.table_relationships:
                formatted += f"- {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}\n"
        
        return formatted
    
    def generate_valid_samples(self, difficulty: str, count: int) -> List[Dict[str, Any]]:
        """유효한 스키마 기반 샘플 생성
        
        Args:
            difficulty: 난이도 ('easy', 'medium', 'hard')
            count: 생성할 샘플 수
            
        Returns:
            생성된 샘플 목록
        """
        self.logger.info(f"{difficulty} 난이도 샘플 {count}개 생성 시작")
        
        # 스키마가 없거나 빈 경우 기본 스키마 사용
        schema_to_use = self.schema
        if not schema_to_use or not schema_to_use.get('tables'):
            self.logger.warning("유효한 스키마가 없습니다. 기본 스키마를 사용합니다.")
            schema_to_use = {
                "tables": [
                    {
                        "name": "customers",
                        "columns": [
                            {"name": "id", "type": "INTEGER", "primary_key": True},
                            {"name": "name", "type": "TEXT", "primary_key": False},
                            {"name": "email", "type": "TEXT", "primary_key": False},
                            {"name": "age", "type": "INTEGER", "primary_key": False}
                        ]
                    },
                    {
                        "name": "orders",
                        "columns": [
                            {"name": "id", "type": "INTEGER", "primary_key": True},
                            {"name": "customer_id", "type": "INTEGER", "primary_key": False},
                            {"name": "order_date", "type": "DATE", "primary_key": False},
                            {"name": "amount", "type": "REAL", "primary_key": False}
                        ]
                    }
                ]
            }
        
        # 샘플 생성
        samples = create_schema_samples(schema_to_use, difficulty, count)
        
        return samples
        
    def validate_sql(self, sql: str) -> Dict[str, Any]:
        """SQL 유효성 검증 (스키마 기반)
        
        Args:
            sql: 검증할 SQL 쿼리
            
        Returns:
            유효성 검증 결과
        """
        result = {
            "is_valid": False,
            "errors": []
        }
        
        # SQL이 비어있는 경우
        if not sql or not sql.strip():
            result["errors"].append("SQL 쿼리가 비어 있습니다.")
            return result
        
        # 기본 문법 확인
        if not sql.upper().startswith("SELECT"):
            result["errors"].append("SQL 쿼리는 SELECT로 시작해야 합니다.")
        
        if "FROM" not in sql.upper():
            result["errors"].append("FROM 절이 필요합니다.")
        
        # 테이블 및 컬럼 유효성 검사
        if self.schema_tables:
            # SQL에서 사용된 테이블 추출
            used_tables = []
            from_match = re.findall(r'FROM\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
            join_match = re.findall(r'JOIN\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
            
            if from_match:
                used_tables.extend(from_match)
            if join_match:
                used_tables.extend(join_match)
            
            # 테이블 존재 여부 확인
            invalid_tables = [table for table in used_tables if table not in self.schema_tables]
            if invalid_tables:
                tables_str = ", ".join(invalid_tables)
                result["errors"].append(f"테이블이 스키마에 존재하지 않습니다: {tables_str}")
                
                # 테이블명 제안
                if self.schema_tables:
                    available_tables = ", ".join(list(self.schema_tables.keys())[:5])
                    result["errors"].append(f"사용 가능한 테이블: {available_tables}{' 외 더 많은 테이블' if len(self.schema_tables) > 5 else ''}")
                    
                    # SQL 수정 시도
                    corrected_sql = sql
                    for bad_table in invalid_tables:
                        if self.schema_tables:
                            # 가장 유사한 테이블명 찾기
                            import difflib
                            similar = difflib.get_close_matches(bad_table, self.schema_tables.keys(), n=1)
                            if similar:
                                replacement = similar[0]
                                corrected_sql = re.sub(r'\b{0}\b'.format(re.escape(bad_table)), replacement, corrected_sql, flags=re.IGNORECASE)
                    
                    if corrected_sql != sql:
                        result["corrected_sql"] = corrected_sql
        
        # 오류가 없으면 유효한 것으로 간주
        if not result["errors"]:
            result["is_valid"] = True
        
        return result
    
    def create_schema_samples(schema: Dict[str, Any], difficulty: str, count: int) -> List[Dict[str, Any]]:
        """스키마를 기반으로 사용자 친화적인 샘플 데이터 생성
        
        Args:
            schema: 데이터베이스 스키마
            difficulty: 난이도 ('easy', 'medium', 'hard')
            count: 생성할 샘플 수
            
        Returns:
            생성된 샘플 목록
        """
        logger = logging.getLogger(__name__)
        logger.info(f"스키마 기반 {difficulty} 난이도 샘플 {count}개 생성")
        
        samples = []
        tables = []
        table_descriptions = {}  # 테이블 설명 저장
        table_relationships = []  # 테이블 관계 정보 저장
        
        # 스키마에서 테이블 정보와 설명 추출
        try:
            #for table in schema['tables']:
            #    table_name = table.get('name', '')
            #    if table_name:
            #        tables.append(table_name)
                    
            #        # 테이블 설명 추출 (있는 경우)
            #        description = table.get('description', '')
            #        if description:
            #            table_descriptions[table_name] = description
            #        else:
            #            # 설명이 없으면 테이블명을 사용자 친화적으로 변환
            #            user_friendly_name = table_name.replace('_', ' ').title()
            #            table_descriptions[table_name] = user_friendly_name
             # 테이블 및 컬럼 정보 추출
            for table in schema['tables']:
                table_name = table.get('name', '')
                if table_name:
                    tables.append(table_name)
                    
                    # 테이블 설명 추출
                    description = table.get('description', '')
                    if description:
                        table_descriptions[table_name] = description
                    else:
                        user_friendly_name = table_name.replace('_', ' ').title()
                        table_descriptions[table_name] = user_friendly_name
                    
                    # 외래 키 및 관계 정보 추출
                    if 'relationships' in table:
                        for rel in table.get('relationships', []):
                            table_relationships.append({
                                'from_table': table_name,
                                'from_column': rel.get('from_column', ''),
                                'to_table': rel.get('to_table', ''),
                                'to_column': rel.get('to_column', ''),
                                'type': rel.get('type', 'foreign_key')  # 관계 유형
                            })
                    # 컬럼에서 외래 키 추정
                    for col in table.get('columns', []):
                        col_name = col.get('name', '')
                        if '_id' in col_name.lower():
                            ref_table = col_name.lower().replace('_id', '')
                            if ref_table in tables:
                                table_relationships.append({
                                    'from_table': table_name,
                                    'from_column': col_name,
                                    'to_table': ref_table,
                                    'to_column': 'id',
                                    'type': 'inferred'  # 추정된 관계
                                })
        except:
            tables = ['customers', 'orders']
            table_descriptions = {
                'customers': '고객',
                'orders': '주문'
            }
        
        # 테이블이 없으면 기본값 사용
        if not tables:
            tables = ['customers', 'orders']
            table_descriptions = {
                'customers': '고객',
                'orders': '주문'
            }
        
        # 난이도별 템플릿, 여기서 관계 정보를 활용하여 조인 쿼리 생성
        templates = {
            'easy': [
                # 기존 템플릿...
            ],
            'medium': [
                # 관계 정보를 활용한 조인 템플릿 추가
                ("SELECT {table1}.{col1}, {table2}.{col2} FROM {table1} JOIN {table2} ON {table1}.{join_col1} = {table2}.{join_col2} LIMIT 10",
                "{table1}과 {table2} 테이블을 조인하여 {col1}과 {col2}를 조회하는 쿼리는?",
                "{table1_desc}과 {table2_desc} 간의 관계에서 {col1_desc}와 {col2_desc}는 무엇인가요?",
                "{table1_desc}과 {table2_desc}의 관계에서 처음 10개의 {col1_desc}와 {col2_desc} 정보를 보여줍니다.")
            ],
            'hard': [
                # 복잡한 다중 조인 템플릿 추가
                ("SELECT {table1}.{col1}, {table2}.{col2}, {table3}.{col3} FROM {table1} " +
                "JOIN {table2} ON {table1}.{join_col1} = {table2}.{join_col2} " +
                "JOIN {table3} ON {table2}.{join_col3} = {table3}.{join_col4} " +
                "WHERE {table1}.{filter_col} > 100 GROUP BY {table1}.{group_col} LIMIT 5",
                "세 개의 테이블({table1}, {table2}, {table3})을 조인하고 {filter_col} 기준으로 필터링하는 쿼리는?",
                "{table1_desc}, {table2_desc}, {table3_desc} 간의 관계에서 {filter_col_desc}가 100보다 큰 {group_col_desc}별 {col1_desc}, {col2_desc}, {col3_desc} 정보를 어떻게 찾을 수 있나요?",
                "{table1_desc}, {table2_desc}, {table3_desc} 간의 관계에서 {filter_col_desc}가 100보다 큰 처음 5개의 결과를 {group_col_desc}별로 그룹화하여 보여줍니다.")
            ]
        }
        
        # 선택된 난이도의 템플릿 목록
        selected_templates = templates.get(difficulty.lower(), templates['easy'])
        
        # 샘플 생성 시 관계 정보 활용
        for i in range(count):
            # 랜덤하게 템플릿 선택
            template, tech_question, user_question, answer_template = random.choice(selected_templates)
            
            # 관계 정보가 필요한 템플릿인 경우 (조인 쿼리)
            if "{table1}" in template and "{table2}" in template:
                # 관계 있는 테이블 쌍 선택
                if table_relationships and difficulty in ['medium', 'hard'] and random.random() < 0.7:
                    # 관계 있는 테이블 선택
                    relationship = random.choice(table_relationships)
                    table1 = relationship['from_table']
                    table2 = relationship['to_table']
                    join_col1 = relationship['from_column']
                    join_col2 = relationship['to_column']
                    
                    # 세 번째 테이블이 필요한 경우 (hard 난이도)
                    if "{table3}" in template:
                        # 두 번째, 세 번째 테이블 간 관계 찾기
                        related_rels = [rel for rel in table_relationships 
                                    if (rel['from_table'] == table2 or rel['to_table'] == table2) 
                                    and rel['from_table'] != table1 and rel['to_table'] != table1]
                        
                        if related_rels:
                            rel2 = random.choice(related_rels)
                            if rel2['from_table'] == table2:
                                table3 = rel2['to_table']
                                join_col3 = rel2['from_column']
                                join_col4 = rel2['to_column']
                            else:
                                table3 = rel2['from_table']
                                join_col3 = rel2['to_column']
                                join_col4 = rel2['from_column']
                        else:
                            # 관계가 없으면 랜덤 선택
                            available_tables = [t for t in tables if t != table1 and t != table2]
                            table3 = random.choice(available_tables) if available_tables else table2
                            join_col3 = "id"
                            join_col4 = table2 + "_id"
                    
                    # 설명 가져오기
                    table1_desc = table_descriptions.get(table1, table1.replace('_', ' ').title())
                    table2_desc = table_descriptions.get(table2, table2.replace('_', ' ').title())
                    
                    # 다른 필드 랜덤 선택 (col1, col2 등)
                    # ...
                
                # SQL 쿼리 및 질문 생성
                # ...
            
            # 최종 항목 추가
            samples.append({
                "difficulty": difficulty,
                "question": question,
                "sql": sql,
                "answer": answer
            })
        
        return samples
import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
import sqlparse
from pathlib import Path

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.schema_loader import SchemaLoader

class SQLValidator:
    """SQL 쿼리 유효성 검증 클래스"""
    
    def __init__(self, schema_loader: SchemaLoader):
        """
        Args:
            schema_loader: 스키마 로더 인스턴스
        """
        self.schema_loader = schema_loader
        self.tables = {}
        self.columns = {}
        self.aliases = {}
        
        # 로거 초기화 추가
        self.logger = logging.getLogger(__name__)
        
        # 스키마 정보 초기화
        self._initialize_schema_info()
    
    def _initialize_schema_info(self) -> None:
        """스키마 정보 초기화 및 캐싱"""
        # 테이블 정보 가져오기
        try:
            self.tables = self.schema_loader.get_tables()
        except AttributeError:
            # get_tables 메서드가 없는 경우 대체 로직
            self.logger.warning("get_tables 메서드를 찾을 수 없습니다. 스키마에서 직접 테이블 정보를 추출합니다.")
            schema = self.schema_loader.load_schema()
            self.tables = {}
            
            if isinstance(schema, dict) and 'tables' in schema:
                for table in schema['tables']:
                    table_name = table.get('name')
                    if table_name:
                        self.tables[table_name] = table
            elif isinstance(schema, str):
                # 문자열 형식의 스키마에서 테이블 추출 시도
                table_pattern = r'CREATE\s+TABLE\s+(?:\w+\.)?(\w+)'
                table_names = re.findall(table_pattern, schema, re.IGNORECASE)
                
                for table_name in table_names:
                    self.tables[table_name] = {"name": table_name, "columns": []}
                    
                    # 컬럼 추출 시도
                    column_pattern = r'CREATE\s+TABLE\s+(?:\w+\.)?{0}\s*\((.*?)\)'.format(re.escape(table_name))
                    column_matches = re.search(column_pattern, schema, re.IGNORECASE | re.DOTALL)
                    
                    if column_matches:
                        column_text = column_matches.group(1)
                        column_defs = column_text.split(',')
                        for col_def in column_defs:
                            col_def = col_def.strip()
                            if col_def:
                                col_name_match = re.match(r'(\w+)', col_def)
                                if col_name_match:
                                    col_name = col_name_match.group(1)
                                    self.tables[table_name].setdefault("columns", []).append(
                                        {"name": col_name}
                                    )
                            
        # 각 테이블의 컬럼 정보 캐싱
        self.columns = {}
        for table_name, table_info in self.tables.items():
            self.columns[table_name] = {}
            for column in table_info.get("columns", []):
                if isinstance(column, dict) and "name" in column:
                    column_name = column["name"]
                    self.columns[table_name][column_name] = column
                elif isinstance(column, str):
                    self.columns[table_name][column] = {"name": column}
    
    def validate_sql(self, sql: str) -> Dict[str, Any]:
        """SQL 쿼리 유효성 검증 - 로깅 추가
        
        Args:
            sql: 검증할 SQL 쿼리
            
        Returns:
            유효성 검증 결과
        """
        # 로깅 레벨 확인
        is_debug = self.logger.getEffectiveLevel() <= logging.DEBUG
        
        if is_debug:
            self.logger.debug(f"SQL 검증 시작: {sql}")
        
        # 기본 결과
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
        tables_in_schema = []
        try:
            # 스키마에서 테이블 목록 추출
            tables_in_schema = list(self.tables.keys())
            
            if is_debug:
                self.logger.debug(f"스키마에서 추출한 테이블: {tables_in_schema}")
            
            # SQL에서 사용된 테이블 추출
            used_tables = []
            from_match = re.findall(r'FROM\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
            join_match = re.findall(r'JOIN\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
            
            if from_match:
                used_tables.extend(from_match)
            if join_match:
                used_tables.extend(join_match)
            
            if is_debug:
                self.logger.debug(f"SQL에서 사용된 테이블: {used_tables}")
            
            # 테이블 존재 여부 확인
            invalid_tables = [table for table in used_tables if table not in tables_in_schema]
            if invalid_tables:
                tables_str = ", ".join(invalid_tables)
                result["errors"].append(f"테이블이 스키마에 존재하지 않습니다: {tables_str}")
                
                # 테이블명 제안
                if tables_in_schema:
                    available_tables = ", ".join(tables_in_schema[:5])
                    result["errors"].append(f"사용 가능한 테이블: {available_tables}{' 외 더 많은 테이블' if len(tables_in_schema) > 5 else ''}")
                    
                    # SQL 수정 시도
                    corrected_sql = sql
                    for bad_table in invalid_tables:
                        if tables_in_schema:
                            # 가장 유사한 테이블명 찾기
                            import difflib
                            similar = difflib.get_close_matches(bad_table, tables_in_schema, n=1)
                            if similar:
                                replacement = similar[0]
                                corrected_sql = re.sub(r'\b{0}\b'.format(re.escape(bad_table)), replacement, corrected_sql, flags=re.IGNORECASE)
                                
                                if is_debug:
                                    self.logger.debug(f"테이블 수정: {bad_table} -> {replacement}")
                    
                    if corrected_sql != sql:
                        result["corrected_sql"] = corrected_sql
        
        except Exception as e:
            if is_debug:
                self.logger.debug(f"스키마 확인 중 오류: {str(e)}")
            result["errors"].append(f"스키마 확인 오류: {str(e)}")
        
        # 오류가 없으면 유효한 것으로 간주
        if not result["errors"]:
            result["is_valid"] = True
        
        return result 
    
    def _validate_tables(self, stmt, sql: str) -> List[str]:
        """SQL 쿼리에서 테이블 참조 유효성 검증
        
        Args:
            stmt: 파싱된 SQL 문장
            sql: 원본 SQL 쿼리
            
        Returns:
            오류 메시지 리스트
        """
        errors = []
        
        # FROM 절에서 테이블 이름 추출
        tables_in_query = self._extract_tables_from_query(sql)
        
        # 테이블 별칭 수집
        self.aliases = self._collect_table_aliases(sql)
        
        # 각 테이블 존재 여부 확인
        for table in tables_in_query:
            # 별칭인 경우 원래 테이블 이름으로 변환
            real_table = table
            if table in self.aliases:
                real_table = self.aliases[table]
            
            # 테이블 존재 여부 확인
            if real_table not in self.tables:
                errors.append(f"테이블 '{real_table}'이 스키마에 존재하지 않습니다.")
        
        # 컬럼 참조 유효성 검증
        column_errors = self._validate_columns(sql, tables_in_query)
        errors.extend(column_errors)
        
        return errors
    
    def _extract_tables_from_query(self, sql: str) -> Set[str]:
        """SQL 쿼리에서 테이블 이름 추출
        
        Args:
            sql: SQL 쿼리
            
        Returns:
            테이블 이름 집합
        """
        tables = set()
        
        # 정규식을 사용하여 FROM 및 JOIN 절에서 테이블 추출
        # FROM 절 패턴
        from_pattern = r'FROM\s+([a-zA-Z0-9_\.]+)(?:\s+AS\s+([a-zA-Z0-9_]+))?'
        from_matches = re.finditer(from_pattern, sql, re.IGNORECASE)
        for match in from_matches:
            table_name = match.group(1)
            tables.add(table_name)
        
        # JOIN 절 패턴
        join_pattern = r'JOIN\s+([a-zA-Z0-9_\.]+)(?:\s+AS\s+([a-zA-Z0-9_]+))?'
        join_matches = re.finditer(join_pattern, sql, re.IGNORECASE)
        for match in join_matches:
            table_name = match.group(1)
            tables.add(table_name)
        
        return tables
    
    def _collect_table_aliases(self, sql: str) -> Dict[str, str]:
        """SQL 쿼리에서 테이블 별칭 수집
        
        Args:
            sql: SQL 쿼리
            
        Returns:
            별칭에서 실제 테이블 이름으로의 매핑 딕셔너리
        """
        aliases = {}
        
        # FROM 절의 별칭 패턴
        from_alias_pattern = r'FROM\s+([a-zA-Z0-9_\.]+)(?:\s+AS\s+|\s+)([a-zA-Z0-9_]+)'
        from_matches = re.finditer(from_alias_pattern, sql, re.IGNORECASE)
        for match in from_matches:
            table_name = match.group(1)
            alias = match.group(2)
            aliases[alias] = table_name
        
        # JOIN 절의 별칭 패턴
        join_alias_pattern = r'JOIN\s+([a-zA-Z0-9_\.]+)(?:\s+AS\s+|\s+)([a-zA-Z0-9_]+)'
        join_matches = re.finditer(join_alias_pattern, sql, re.IGNORECASE)
        for match in join_matches:
            table_name = match.group(1)
            alias = match.group(2)
            aliases[alias] = table_name
        
        return aliases
    
    def _validate_columns(self, sql: str, tables_in_query: Set[str]) -> List[str]:
        """SQL 쿼리에서 컬럼 참조 유효성 검증
        
        Args:
            sql: SQL 쿼리
            tables_in_query: 쿼리에 사용된 테이블 집합
            
        Returns:
            오류 메시지 리스트
        """
        errors = []
        
        # 정규식으로 컬럼 참조 추출
        # SELECT 절 패턴
        select_pattern = r'SELECT\s+(.*?)\s+FROM'
        select_match = re.search(select_pattern, sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_columns = select_match.group(1)
            # AS 키워드, 괄호, 집계 함수 등을 고려하여 처리 필요
            # 여기서는 간단한 구현만 제공
        
        # WHERE 절 패턴
        where_pattern = r'WHERE\s+(.*?)(?:GROUP BY|ORDER BY|LIMIT|$)'
        where_match = re.search(where_pattern, sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            # 조건 구문 처리
        
        # 복잡한 SQL 검증은 LLM 기반 검증으로 위임
        # 이 클래스는 기본적인 구문 및 참조 확인만 수행
        
        return errors
    
    def fix_sql(self, sql: str, errors: List[str]) -> Optional[str]:
        """오류가 있는 SQL 쿼리 수정 시도
        
        Args:
            sql: 원본 SQL 쿼리
            errors: 발견된 오류 메시지 리스트
            
        Returns:
            수정된 SQL 쿼리 또는 None (수정 불가능한 경우)
        """
        # 간단한 오류만 수정 시도
        corrected_sql = sql
        
        # 테이블 이름 오류 수정
        for error in errors:
            if "테이블" in error and "존재하지 않습니다" in error:
                # 오류 메시지에서 테이블 이름 추출
                match = re.search(r"'([^']+)'", error)
                if match:
                    wrong_table = match.group(1)
                    # 가장 유사한 테이블 이름 찾기
                    similar_table = self._find_similar_table(wrong_table)
                    if similar_table:
                        # 잘못된 테이블 이름을 유사한 이름으로 대체
                        corrected_sql = re.sub(
                            fr'\b{re.escape(wrong_table)}\b', 
                            similar_table, 
                            corrected_sql
                        )
        
        # 수정이 없었으면 None 반환
        if corrected_sql == sql:
            return None
            
        return corrected_sql
    
    def _find_similar_table(self, table_name: str) -> Optional[str]:
        """유사한 테이블 이름 찾기
        
        Args:
            table_name: 잘못된 테이블 이름
            
        Returns:
            가장 유사한 테이블 이름 또는 None
        """
        if not self.tables:
            return None
            
        # difflib 라이브러리를 사용하여 가장 유사한 테이블 이름 찾기
        import difflib
        similar_tables = difflib.get_close_matches(table_name, list(self.tables.keys()), n=1)
        if similar_tables:
            return similar_tables[0]
                
        return None
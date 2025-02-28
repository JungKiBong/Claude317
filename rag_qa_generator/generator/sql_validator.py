import re
import json
from typing import Dict, List, Any, Optional, Tuple, Set
import sqlparse
from pathlib import Path

from ..data.schema_loader import SchemaLoader

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
        
        # 스키마 정보 초기화
        self._initialize_schema_info()
    
    def _initialize_schema_info(self) -> None:
        """스키마 정보 초기화 및 캐싱"""
        # 테이블 정보 가져오기
        self.tables = self.schema_loader.get_tables()
        
        # 각 테이블의 컬럼 정보 캐싱
        self.columns = {}
        for table_name, table_info in self.tables.items():
            self.columns[table_name] = {}
            for column in table_info.get("columns", []):
                column_name = column["name"]
                self.columns[table_name][column_name] = column
    
    def validate_sql(self, sql: str) -> Dict[str, Any]:
        """SQL 쿼리 유효성 검증
        
        Args:
            sql: 검증할 SQL 쿼리
            
        Returns:
            검증 결과 (유효성, 오류 메시지 등)
        """
        # 초기 결과 설정
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "corrected_sql": None
        }
        
        # 빈 쿼리 확인
        if not sql or sql.strip() == "":
            result["is_valid"] = False
            result["errors"].append("SQL 쿼리가 비어 있습니다.")
            return result
        
        try:
            # 구문 분석
            parsed = sqlparse.parse(sql)
            if not parsed:
                result["is_valid"] = False
                result["errors"].append("SQL 쿼리를 파싱할 수 없습니다.")
                return result
            
            # 분석된 쿼리의 첫 번째 문장 사용
            stmt = parsed[0]
            
            # 테이블 및 컬럼 참조 검증
            table_errors = self._validate_tables(stmt, sql)
            if table_errors:
                result["is_valid"] = False
                result["errors"].extend(table_errors)
            
            # 추가 검증 (필요에 따라 확장)
            
        except Exception as e:
            result["is_valid"] = False
            result["errors"].append(f"검증 중 오류 발생: {str(e)}")
        
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
            
        # 간단한 유사도 측정 (레벤슈타인 거리 등을 사용할 수 있음)
        # 여기서는 간단한 접두사 매칭만 구현
        table_name_lower = table_name.lower()
        for real_table in self.tables.keys():
            if real_table.lower().startswith(table_name_lower) or table_name_lower.startswith(real_table.lower()):
                return real_table
                
        return None
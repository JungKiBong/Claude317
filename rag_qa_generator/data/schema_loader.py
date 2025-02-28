import json
import os
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import re

class SchemaLoader:
    """데이터베이스 스키마 파일 로드 및 처리를 위한 클래스"""
    
    def __init__(self, schema_path: Union[str, Path]):
        """
        Args:
            schema_path: 스키마 파일 경로 (JSON 형식)
        """
        self.schema_path = Path(schema_path)
        self.schema = None
        self.tables = {}
        self.references = {}
    
    def load_schema(self) -> Dict[str, Any]:
        """스키마 파일 로드 및 검증
        
        Returns:
            파싱된 스키마 데이터
            
        Raises:
            FileNotFoundError: 스키마 파일이 존재하지 않는 경우
            ValueError: 스키마 파일 형식이 잘못된 경우
        """
        # 파일 존재 여부 확인
        if not self.schema_path.exists():
            raise FileNotFoundError(f"스키마 파일이 존재하지 않습니다: {self.schema_path}")
        
        # 파일 로드
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                self.schema = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"스키마 파일 형식이 잘못되었습니다: {str(e)}")
        
        # 스키마 검증
        self._validate_schema()
        
        # 테이블 및 참조 정보 추출
        self._extract_tables_and_references()
        
        return self.schema
    
    def _validate_schema(self) -> None:
        """스키마 형식 검증
        
        Raises:
            ValueError: 필수 필드가 누락되었거나 형식이 잘못된 경우
        """
        if not self.schema:
            raise ValueError("스키마가 로드되지 않았습니다.")
        
        # 필수 필드 확인
        if not isinstance(self.schema.get("tables"), list):
            raise ValueError("스키마에 'tables' 배열이 필요합니다.")
        
        # 각 테이블 확인
        for table in self.schema["tables"]:
            # 테이블 이름 확인
            if "name" not in table:
                raise ValueError("모든 테이블에 'name' 필드가 필요합니다.")
            
            # 컬럼 확인
            if "columns" not in table or not isinstance(table["columns"], list):
                raise ValueError(f"테이블 '{table['name']}'에 'columns' 배열이 필요합니다.")
            
            # 각 컬럼 확인
            for column in table["columns"]:
                if "name" not in column:
                    raise ValueError(f"테이블 '{table['name']}'의 모든 컬럼에 'name' 필드가 필요합니다.")
                if "type" not in column:
                    raise ValueError(f"테이블 '{table['name']}'의 컬럼 '{column['name']}'에 'type' 필드가 필요합니다.")
    
    def _extract_tables_and_references(self) -> None:
        """테이블 및 외래 키 참조 정보 추출"""
        if not self.schema:
            return
        
        # 테이블 정보 추출
        for table in self.schema["tables"]:
            table_name = table["name"]
            self.tables[table_name] = table
            
            # 외래 키 참조 추출
            for column in table["columns"]:
                if "references" in column:
                    ref_table = column["references"].get("table")
                    ref_column = column["references"].get("column")
                    
                    if ref_table and ref_column:
                        # 참조 정보 저장
                        if table_name not in self.references:
                            self.references[table_name] = []
                        
                        self.references[table_name].append({
                            "column": column["name"],
                            "ref_table": ref_table,
                            "ref_column": ref_column
                        })
    
    def get_tables(self) -> Dict[str, Any]:
        """테이블 정보 반환
        
        Returns:
            테이블 이름과 정보가 담긴 딕셔너리
        """
        if not self.schema:
            self.load_schema()
        
        return self.tables
    
    def get_table(self, table_name: str) -> Optional[Dict[str, Any]]:
        """지정된 테이블 정보 반환
        
        Args:
            table_name: 테이블 이름
            
        Returns:
            테이블 정보 또는 None (테이블이 없는 경우)
        """
        if not self.schema:
            self.load_schema()
        
        return self.tables.get(table_name)
    
    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """지정된 테이블의 컬럼 정보 반환
        
        Args:
            table_name: 테이블 이름
            
        Returns:
            컬럼 정보 리스트
            
        Raises:
            ValueError: 테이블이 존재하지 않는 경우
        """
        table = self.get_table(table_name)
        if not table:
            raise ValueError(f"테이블이 존재하지 않습니다: {table_name}")
        
        return table.get("columns", [])
    
    def get_relationships(self) -> Dict[str, List[Dict[str, str]]]:
        """테이블 간 관계 정보 반환
        
        Returns:
            테이블별 외래 키 참조 정보
        """
        if not self.schema:
            self.load_schema()
        
        return self.references
    
    def format_for_prompt(self, include_relationships: bool = True) -> str:
        """프롬프트에 사용할 수 있는 형식으로 스키마 정보 변환
        
        Args:
            include_relationships: 관계 정보 포함 여부
            
        Returns:
            텍스트 형식의 스키마 정보
        """
        if not self.schema:
            self.load_schema()
        
        formatted_schema = []
        
        # 각 테이블 정보 포맷팅
        for table_name, table in self.tables.items():
            table_info = [f"Table: {table_name}"]
            
            # 컬럼 정보 추가
            columns_info = []
            for column in table["columns"]:
                col_name = column["name"]
                col_type = column["type"]
                is_primary = column.get("primary_key", False)
                is_nullable = not column.get("not_null", False)
                
                # 컬럼 정보 문자열 구성
                col_info = f"{col_name} ({col_type})"
                if is_primary:
                    col_info += " PRIMARY KEY"
                if not is_nullable:
                    col_info += " NOT NULL"
                
                columns_info.append(col_info)
            
            # 테이블에 컬럼 정보 추가
            table_info.append("Columns:")
            table_info.extend([f"  - {col}" for col in columns_info])
            
            # 관계 정보 추가 (요청된 경우)
            if include_relationships and table_name in self.references:
                table_info.append("Foreign Keys:")
                for ref in self.references[table_name]:
                    ref_info = f"  - {ref['column']} references {ref['ref_table']}({ref['ref_column']})"
                    table_info.append(ref_info)
            
            # 테이블 구분선 추가
            formatted_schema.append("\n".join(table_info))
        
        # 전체 스키마 조합
        return "\n\n".join(formatted_schema)
    
    def get_schema_summary(self) -> str:
        """스키마 요약 정보 생성
        
        Returns:
            스키마 요약 정보 문자열
        """
        if not self.schema:
            self.load_schema()
        
        summary = []
        
        # 데이터베이스 이름 추가 (있는 경우)
        db_name = self.schema.get("database_name", "Database")
        summary.append(f"Database: {db_name}")
        
        # 테이블 수 추가
        table_count = len(self.tables)
        summary.append(f"Tables: {table_count}")
        
        # 테이블 이름 목록 추가
        table_names = list(self.tables.keys())
        summary.append(f"Table list: {', '.join(table_names)}")
        
        # 관계 수 추가
        relation_count = sum(len(refs) for refs in self.references.values())
        summary.append(f"Relationships: {relation_count}")
        
        return "\n".join(summary)
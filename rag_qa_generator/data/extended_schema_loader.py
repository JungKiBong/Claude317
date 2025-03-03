# data/extended_schema_loader.py
from typing import Dict, Any, Optional
import json
import logging
from pathlib import Path

from data.schema_loader import SchemaLoader
from data_catalog_connectors import DataCatalogConnector

logger = logging.getLogger(__name__)

class ExtendedSchemaLoader(SchemaLoader):
    """외부 데이터 카탈로그에서 스키마를 로드할 수 있는 확장 스키마 로더"""
    
    def __init__(self, schema_path: Optional[str] = None, 
                 data_catalog_connector: Optional[DataCatalogConnector] = None):
        """
        Args:
            schema_path: 로컬 스키마 파일 경로
            data_catalog_connector: 데이터 카탈로그 커넥터 인스턴스
        """
        super().__init__(schema_path)
        self.data_catalog_connector = data_catalog_connector
        self.dataset_urn = None
        self.use_catalog = data_catalog_connector is not None
    
    def load_schema_from_catalog(self, dataset_urn: str) -> Dict[str, Any]:
        """데이터 카탈로그에서 스키마 로드
        
        Args:
            dataset_urn: 데이터셋 식별자
            
        Returns:
            스키마 정보 딕셔너리
        """
        if not self.data_catalog_connector:
            raise ValueError("Data catalog connector is not initialized")
        
        try:
            logger.info(f"Loading schema from data catalog for: {dataset_urn}")
            
            # 데이터셋 스키마 가져오기
            catalog_schema = self.data_catalog_connector.get_dataset_schema(dataset_urn)
            
            # 내부 형식으로 변환
            internal_schema = self.data_catalog_connector.convert_to_internal_schema(catalog_schema)
            
            # 캐싱
            self.schema = internal_schema
            self.dataset_urn = dataset_urn
            
            # 디버깅을 위해 파일로 저장 (선택적)
            try:
                temp_dir = Path("temp")
                temp_dir.mkdir(exist_ok=True)
                
                schema_file = temp_dir / f"catalog_schema_{dataset_urn.split(':')[-1]}.json"
                with open(schema_file, 'w', encoding='utf-8') as f:
                    json.dump(internal_schema, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Saved catalog schema to: {schema_file}")
            except Exception as e:
                logger.warning(f"Failed to save catalog schema to file: {e}")
            
            return internal_schema
            
        except Exception as e:
            logger.error(f"Error loading schema from catalog: {e}")
            raise
    
    def load_schema(self) -> Dict[str, Any]:
        """파일 또는 데이터 카탈로그에서 스키마 로드
        
        Returns:
            스키마 정보 딕셔너리
        """
        # 이미 로드된 스키마가 있으면 반환
        if self.schema:
            return self.schema
        
        # 데이터 카탈로그 연결이 있고 dataset_urn이 설정된 경우 카탈로그에서 로드
        if self.use_catalog and self.dataset_urn:
            return self.load_schema_from_catalog(self.dataset_urn)
        
        # 그렇지 않으면 파일에서 로드
        return super().load_schema()
    
    def get_schema_summary(self) -> str:
        """스키마 정보 요약 문자열 생성"""
        schema = self.load_schema()
        
        if not schema:
            return "스키마 정보가 없습니다."
        
        summary = []
        
        # 데이터베이스 이름
        db_name = schema.get("database_name", "Unknown Database")
        summary.append(f"데이터베이스: {db_name}")
        
        # 테이블 정보
        tables = schema.get("tables", [])
        summary.append(f"테이블 수: {len(tables)}")
        
        for table in tables:
            table_name = table.get("name", "Unknown Table")
            table_desc = table.get("description", "")
            columns = table.get("columns", [])
            
            summary.append(f"\n테이블: {table_name}")
            if table_desc:
                summary.append(f"설명: {table_desc}")
            
            summary.append(f"컬럼 수: {len(columns)}")
            if columns:
                col_list = [f"{col.get('name')} ({col.get('type')})" for col in columns[:5]]
                summary.append(f"주요 컬럼: {', '.join(col_list)}")
                if len(columns) > 5:
                    summary.append(f"외 {len(columns) - 5}개 컬럼")
        
        # 출처 정보 추가
        if self.use_catalog and self.dataset_urn:
            summary.append(f"\n출처: 데이터 카탈로그 (URN: {self.dataset_urn})")
        else:
            summary.append(f"\n출처: 로컬 파일 ({self.schema_path})")
        
        return "\n".join(summary)
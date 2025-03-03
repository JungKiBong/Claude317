# generator/enhanced_schema_adapter.py
from typing import Dict, List, Any, Optional
import logging
import random

from generator.schema_utils import SchemaAdapter
from data_catalog_connectors import DataCatalogConnector

logger = logging.getLogger(__name__)

class EnhancedSchemaAdapter(SchemaAdapter):
    """데이터 카탈로그 메타데이터를 활용하는 스키마 어댑터"""
    
    def __init__(self, schema_loader=None, data_catalog_connector=None):
        """
        Args:
            schema_loader: 스키마 로더 인스턴스
            data_catalog_connector: 데이터 카탈로그 커넥터 인스턴스
        """
        super().__init__(schema_loader=schema_loader)
        self.data_catalog_connector = data_catalog_connector
        self.popularity_cache = {}  # 인기도 정보 캐시
        
    def get_popular_fields(self, dataset_urn: str, limit: int = 10) -> List[Dict[str, Any]]:
        """데이터셋에서 가장 많이 사용되는 필드 정보 가져오기"""
        if not self.data_catalog_connector:
            return []
            
        try:
            # DataHub API에 맞게 구현 필요 (인기 필드 API가 있는 경우)
            # 일부 데이터 카탈로그는 이러한 기능을 제공하지 않을 수 있음
            
            # 예시 구현 (실제로는 API를 통해 가져와야 함)
            fields = []
            schema = self.schema_loader.load_schema()
            
            for table in schema.get("tables", []):
                for column in table.get("columns", []):
                    # 임의의 인기도 점수 생성 (실제로는 API에서 가져와야 함)
                    popularity = random.randint(1, 100)
                    fields.append({
                        "table": table.get("name"),
                        "field": column.get("name"),
                        "popularity": popularity,
                        "description": column.get("description", "")
                    })
            
            # 인기도순 정렬
            fields.sort(key=lambda x: x["popularity"], reverse=True)
            return fields[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular fields: {e}")
            return []
    
    def get_join_suggestions(self, dataset_urn: str) -> List[Dict[str, Any]]:
        """테이블 간 조인 제안 가져오기"""
        if not self.data_catalog_connector:
            return []
            
        try:
            # 관계 정보 가져오기 (DataHub API에서 관계 정보 조회)
            relationships = []
            schema = self.schema_loader.load_schema()
            
            # 스키마에서 관계 정보 추출
            for table in schema.get("tables", []):
                for rel in table.get("relationships", []):
                    relationships.append({
                        "from_table": rel.get("from_table", table.get("name")),
                        "from_column": rel.get("from_column"),
                        "to_table": rel.get("to_table"),
                        "to_column": rel.get("to_column"),
                        "description": rel.get("description", "")
                    })
            
            return relationships
            
        except Exception as e:
            logger.error(f"Error getting join suggestions: {e}")
            return []
    
    def generate_enhanced_samples(self, difficulty: str, count: int) -> List[Dict[str, Any]]:
        """데이터 카탈로그 메타데이터를 활용한 향상된 샘플 생성"""
        # 기본 샘플 생성 (기존 함수 호출)
        samples = super().generate_valid_samples(difficulty, count)
        
        # 데이터 카탈로그 메타데이터 활용 가능하면 샘플 향상
        if self.data_catalog_connector and hasattr(self.schema_loader, 'dataset_urn'):
            dataset_urn = self.schema_loader.dataset_urn
            
            # 인기 필드 기반 질문 추가
            popular_fields = self.get_popular_fields(dataset_urn)
            
            if popular_fields and difficulty in ['medium', 'hard']:
                try:
                    # 인기 필드를 활용한 질문 생성
                    for i, field in enumerate(popular_fields[:3]):  # 상위 3개 필드만 사용
                        if i >= len(samples):  # 샘플 개수 초과하면 중단
                            break
                            
                        # 인기 필드 관련 질문으로 대체
                        table_name = field["table"]
                        field_name = field["field"]
                        
                        if difficulty == 'medium':
                            # 중간 난이도 질문 예시
                            sql = f"SELECT {field_name}, COUNT(*) as count FROM {table_name} GROUP BY {field_name} ORDER BY count DESC LIMIT 10;"
                            question = f"{field['description'] or field_name}별 분포를 확인하세요."
                            answer = f"{table_name} 테이블에서 {field['description'] or field_name}별 빈도를 계산하여 상위 10개를 보여줍니다."
                        else:
                            # 어려운 난이도 질문 예시
                            sql = f"SELECT {field_name}, COUNT(*) as count, AVG(price) as avg_price FROM {table_name} GROUP BY {field_name} ORDER BY count DESC LIMIT 10;"
                            question = f"{field['description'] or field_name}별 빈도 및 평균 가격을 분석하세요."
                            answer = f"{table_name} 테이블에서 {field['description'] or field_name}별 빈도와 평균 가격을 계산하여 상위 10개를 보여줍니다."
                        
                        samples[i]["question"] = question
                        samples[i]["sql"] = sql
                        samples[i]["answer"] = answer
                
                except Exception as e:
                    logger.error(f"Error enhancing samples with popular fields: {e}")
            
            # 조인 제안 기반 질문 추가
            join_suggestions = self.get_join_suggestions(dataset_urn)
            
            if join_suggestions and difficulty in ['medium', 'hard']:
                try:
                    # 조인 제안을 활용한 질문 생성
                    for i, join in enumerate(join_suggestions[:2]):  # 최대 2개의 조인만 활용
                        idx = len(samples) // 2 + i  # 샘플의 중간부터 대체
                        if idx >= len(samples):  # 샘플 개수 초과하면 중단
                            break
                            
                        # 조인 관련 질문으로 대체
                        from_table = join["from_table"]
                        from_column = join["from_column"]
                        to_table = join["to_table"]
                        to_column = join["to_column"]
                        
                        if difficulty == 'medium':
                            # 중간 난이도 조인 질문
                            sql = f"SELECT t1.*, t2.* FROM {from_table} t1 JOIN {to_table} t2 ON t1.{from_column} = t2.{to_column} LIMIT 10;"
                            question = f"{from_table}과 {to_table}의 관계를 조회하세요."
                            answer = f"{from_table}과 {to_table}을 {from_column}과 {to_column} 컬럼을 기준으로 조인하여 관련 정보를 조회합니다."
                        else:
                            # 어려운 난이도 조인 질문
                            sql = f"""
                            SELECT 
                                t1.*, 
                                t2.*, 
                                (SELECT COUNT(*) FROM {to_table} t3 WHERE t3.{to_column} = t1.{from_column}) as related_count
                            FROM {from_table} t1 
                            LEFT JOIN {to_table} t2 ON t1.{from_column} = t2.{to_column} 
                            GROUP BY t1.{from_column}
                            ORDER BY related_count DESC
                            LIMIT 10;"""
                            question = f"각 {from_table}에 연결된 {to_table}의 수를 계산하세요."
                            answer = f"각 {from_table}에 연결된 {to_table}의 수를 계산하고, 연결된 항목이 많은 순으로 정렬하여 상위 10개를 보여줍니다."
                        
                        samples[idx]["question"] = question
                        samples[idx]["sql"] = sql.strip()
                        samples[idx]["answer"] = answer
                
                except Exception as e:
                    logger.error(f"Error enhancing samples with join suggestions: {e}")
        
        return samples
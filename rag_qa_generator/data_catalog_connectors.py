# data_catalog_connectors.py
import requests
import json
import time
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

class DataCatalogConnector(ABC):
    """데이터 카탈로그 연결을 위한 기본 추상 클래스"""
    
    def __init__(self, base_url: str, api_token: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.timeout = timeout
        self.cache = {}  # 간단한 메모리 캐시
        self.cache_ttl = 300  # 캐시 TTL (초)
        self.cache_timestamp = {}
    
    @abstractmethod
    def list_datasets(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """데이터셋 목록 가져오기"""
        pass
    
    @abstractmethod
    def get_dataset_schema(self, dataset_urn: str) -> Dict[str, Any]:
        """특정 데이터셋의 스키마 정보 가져오기"""
        pass
    
    @abstractmethod
    def convert_to_internal_schema(self, external_schema: Dict[str, Any]) -> Dict[str, Any]:
        """외부 스키마를 내부 스키마 형식으로 변환"""
        pass
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """캐시에서 데이터 가져오기"""
        if key in self.cache:
            # 캐시 TTL 확인
            if time.time() - self.cache_timestamp.get(key, 0) < self.cache_ttl:
                logger.debug(f"Cache hit for key: {key}")
                return self.cache[key]
            else:
                # 캐시 만료
                del self.cache[key]
                if key in self.cache_timestamp:
                    del self.cache_timestamp[key]
        return None
    
    def _store_in_cache(self, key: str, data: Any) -> None:
        """데이터를 캐시에 저장"""
        self.cache[key] = data
        self.cache_timestamp[key] = time.time()
        logger.debug(f"Stored in cache: {key}")
    
    def _make_api_request(self, endpoint: str, method: str = "GET", 
                          params: Optional[Dict[str, Any]] = None, 
                          data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """API 요청 수행"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # 응답 상태 확인
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise AuthenticationError("API 인증 실패. 토큰을 확인하세요.")
            elif response.status_code == 403:
                raise PermissionError("API 접근 권한이 없습니다.")
            elif response.status_code == 429:
                raise RateLimitError("API 요청 한도 초과. 잠시 후 다시 시도하세요.")
            else:
                logger.error(f"HTTP error: {e}")
                raise
        except requests.exceptions.Timeout:
            raise TimeoutError(f"API 요청 타임아웃 ({self.timeout}초)")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise ConnectionError(f"API 연결 오류: {str(e)}")

# 예외 클래스 정의
class AuthenticationError(Exception):
    pass

class PermissionError(Exception):
    pass

class RateLimitError(Exception):
    pass

class DatahubConnector(DataCatalogConnector):
    """DataHub API와 연동하여 스키마 정보를 가져오는 클래스"""
    
    def list_datasets(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """데이터셋 목록 가져오기"""
        cache_key = f"datahub_datasets_{limit}_{offset}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        params = {
            "limit": limit,
            "offset": offset,
            "type": "DATASET"
        }
        
        result = self._make_api_request("/entities", params=params)
        datasets = result.get("entities", [])
        
        # 응답 변환 - DataHub 특화 형식을 일반적인 형식으로 변환
        formatted_datasets = []
        for dataset in datasets:
            formatted_datasets.append({
                "name": dataset.get("name", ""),
                "urn": dataset.get("urn", ""),
                "platform": self._extract_platform_from_urn(dataset.get("urn", "")),
                "description": dataset.get("description", "")
            })
        
        self._store_in_cache(cache_key, formatted_datasets)
        return formatted_datasets
    
    def get_dataset_schema(self, dataset_urn: str) -> Dict[str, Any]:
        """특정 데이터셋의 스키마 정보 가져오기"""
        cache_key = f"datahub_schema_{dataset_urn}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        endpoint = f"/aspects/{dataset_urn}?aspects=schemaMetadata"
        result = self._make_api_request(endpoint)
        
        schema = result.get("aspects", {}).get("schemaMetadata", {})
        if not schema:
            raise ValueError(f"Schema not found for dataset: {dataset_urn}")
        
        self._store_in_cache(cache_key, schema)
        return schema
    
    def get_dataset_relationships(self, dataset_urn: str) -> List[Dict[str, Any]]:
        """데이터셋의 관계 정보 가져오기"""
        cache_key = f"datahub_relationships_{dataset_urn}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        endpoint = f"/relationships?urn={dataset_urn}"
        result = self._make_api_request(endpoint)
        
        relationships = result.get("relationships", [])
        self._store_in_cache(cache_key, relationships)
        return relationships
    
    def convert_to_internal_schema(self, datahub_schema: Dict[str, Any]) -> Dict[str, Any]:
        """DataHub 스키마를 내부 스키마 형식으로 변환"""
        # 필드 추출
        fields = datahub_schema.get("fields", [])
        
        # 데이터셋 이름 및 플랫폼 추출
        dataset_name = datahub_schema.get("dataset", "unknown")
        platform = "unknown"
        if "platformUrn" in datahub_schema:
            platform = self._extract_platform_from_urn(datahub_schema["platformUrn"])
        
        # 테이블 생성
        table = {
            "name": dataset_name,
            "description": datahub_schema.get("description", ""),
            "columns": [],
            "indexes": [],
            "relationships": []
        }
        
        # 컬럼 추가
        for field in fields:
            column = {
                "name": field.get("fieldPath", ""),
                "type": field.get("type", {}).get("type", ""),
                "description": field.get("description", ""),
                "primary_key": any(tag.get("tag", "") == "primaryKey" for tag in field.get("globalTags", {}).get("tags", [])),
                "not_null": any(tag.get("tag", "") == "nonnull" for tag in field.get("globalTags", {}).get("tags", []))
            }
            table["columns"].append(column)
        
        # 관계 정보 추출 및 인덱스 추정 (DataHub는 직접적인 인덱스 정보를 제공하지 않음)
        # 기본 키를 인덱스로 추가
        primary_keys = [col["name"] for col in table["columns"] if col["primary_key"]]
        if primary_keys:
            table["indexes"].append({
                "name": f"pk_{table['name']}",
                "type": "PRIMARY KEY",
                "columns": ",".join(primary_keys),
                "description": "Primary Key Index"
            })
        
        # 최종 스키마 구성
        internal_schema = {
            "database_name": platform,
            "tables": [table]
        }
        
        return internal_schema
    
    def _extract_platform_from_urn(self, urn: str) -> str:
        """URN에서 플랫폼 이름 추출"""
        if not urn:
            return "unknown"
        
        # 예: urn:li:dataset:(urn:li:dataPlatform:mysql,mydb.schema.table,PROD)
        parts = urn.split(",")
        if len(parts) > 0:
            platform_part = parts[0]
            if "dataPlatform:" in platform_part:
                return platform_part.split("dataPlatform:")[1]
        return "unknown"

class CollibraConnector(DataCatalogConnector):
    """Collibra API 연동 클래스"""
    
    def list_datasets(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Collibra API에서 데이터셋 목록 가져오기"""
        # Collibra API 구현
        pass
    
    def get_dataset_schema(self, dataset_id: str) -> Dict[str, Any]:
        """Collibra에서 스키마 정보 가져오기"""
        # Collibra API 구현
        pass
    
    def convert_to_internal_schema(self, collibra_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Collibra 스키마를 내부 형식으로 변환"""
        # Collibra 스키마 변환 로직
        pass

# 필요에 따라 다른 데이터 카탈로그 커넥터 추가
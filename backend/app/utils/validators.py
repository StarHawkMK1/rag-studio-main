# rag-studio/backend/app/utils/validators.py
"""
데이터 검증 유틸리티

다양한 데이터 타입과 비즈니스 로직에 대한 검증 함수들을 제공합니다.
"""

import re
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from pathlib import Path
from urllib.parse import urlparse
import uuid

from app.utils.exceptions import ValidationError


class PipelineValidator:
    """파이프라인 관련 검증"""
    
    @staticmethod
    def validate_pipeline_name(name: str) -> bool:
        """
        파이프라인 이름 검증
        
        Args:
            name: 파이프라인 이름
            
        Returns:
            bool: 유효성 여부
            
        Raises:
            ValidationError: 이름이 유효하지 않은 경우
        """
        if not name or not name.strip():
            raise ValidationError("Pipeline name cannot be empty")
        
        if len(name) > 255:
            raise ValidationError("Pipeline name cannot exceed 255 characters")
        
        # 특수문자 제한 (기본적인 문자, 숫자, 공백, 하이픈, 언더스코어만 허용)
        if not re.match(r'^[a-zA-Z0-9가-힣\s\-_]+$', name):
            raise ValidationError("Pipeline name contains invalid characters")
        
        return True
    
    @staticmethod
    def validate_pipeline_config(config: Dict[str, Any]) -> bool:
        """
        파이프라인 설정 검증
        
        Args:
            config: 파이프라인 설정 딕셔너리
            
        Returns:
            bool: 유효성 여부
        """
        if not isinstance(config, dict):
            raise ValidationError("Pipeline config must be a dictionary")
        
        # 필수 설정 확인
        required_fields = ["retrieval_top_k", "temperature", "max_tokens"]
        for field in required_fields:
            if field not in config:
                raise ValidationError(f"Missing required config field: {field}")
        
        # 값 범위 검증
        top_k = config.get("retrieval_top_k")
        if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
            raise ValidationError("retrieval_top_k must be an integer between 1 and 100")
        
        temperature = config.get("temperature")
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            raise ValidationError("temperature must be a number between 0 and 2")
        
        max_tokens = config.get("max_tokens")
        if not isinstance(max_tokens, int) or max_tokens < 100 or max_tokens > 32000:
            raise ValidationError("max_tokens must be an integer between 100 and 32000")
        
        return True


class QueryValidator:
    """쿼리 관련 검증"""
    
    @staticmethod
    def validate_query_text(query: str) -> bool:
        """
        쿼리 텍스트 검증
        
        Args:
            query: 쿼리 텍스트
            
        Returns:
            bool: 유효성 여부
        """
        if not query or not query.strip():
            raise ValidationError("Query text cannot be empty")
        
        if len(query) > 10000:
            raise ValidationError("Query text cannot exceed 10000 characters")
        
        # 최소 길이 체크
        if len(query.strip()) < 3:
            raise ValidationError("Query text must be at least 3 characters long")
        
        return True
    
    @staticmethod
    def validate_query_parameters(params: Dict[str, Any]) -> bool:
        """
        쿼리 파라미터 검증
        
        Args:
            params: 쿼리 파라미터
            
        Returns:
            bool: 유효성 여부
        """
        if "top_k" in params:
            top_k = params["top_k"]
            if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
                raise ValidationError("top_k must be an integer between 1 and 100")
        
        if "filters" in params and params["filters"] is not None:
            if not isinstance(params["filters"], dict):
                raise ValidationError("filters must be a dictionary")
        
        return True


class IndexValidator:
    """인덱스 관련 검증"""
    
    @staticmethod
    def validate_index_name(name: str) -> bool:
        """
        인덱스 이름 검증 (OpenSearch 규칙에 따름)
        
        Args:
            name: 인덱스 이름
            
        Returns:
            bool: 유효성 여부
        """
        if not name or not name.strip():
            raise ValidationError("Index name cannot be empty")
        
        # OpenSearch 인덱스 이름 규칙
        if len(name) > 255:
            raise ValidationError("Index name cannot exceed 255 characters")
        
        # 소문자, 숫자, 하이픈만 허용
        if not re.match(r'^[a-z0-9\-_]+$', name):
            raise ValidationError("Index name can only contain lowercase letters, numbers, hyphens, and underscores")
        
        # 하이픈으로 시작하거나 끝날 수 없음
        if name.startswith('-') or name.endswith('-'):
            raise ValidationError("Index name cannot start or end with a hyphen")
        
        # 예약된 이름 체크
        reserved_names = ['.', '..']
        if name in reserved_names:
            raise ValidationError(f"Index name '{name}' is reserved")
        
        # 시스템 인덱스 패턴 체크 (점으로 시작)
        if name.startswith('.') and not name.startswith('.rag-'):
            raise ValidationError("Index names starting with '.' are reserved for system indices")
        
        return True
    
    @staticmethod
    def validate_index_config(config: Dict[str, Any]) -> bool:
        """
        인덱스 설정 검증
        
        Args:
            config: 인덱스 설정
            
        Returns:
            bool: 유효성 여부
        """
        if not isinstance(config, dict):
            raise ValidationError("Index config must be a dictionary")
        
        # 샤드 수 검증
        if "number_of_shards" in config:
            shards = config["number_of_shards"]
            if not isinstance(shards, int) or shards < 1 or shards > 10:
                raise ValidationError("number_of_shards must be an integer between 1 and 10")
        
        # 복제본 수 검증
        if "number_of_replicas" in config:
            replicas = config["number_of_replicas"]
            if not isinstance(replicas, int) or replicas < 0 or replicas > 5:
                raise ValidationError("number_of_replicas must be an integer between 0 and 5")
        
        # 임베딩 차원 검증
        if "embedding_dimension" in config:
            dimension = config["embedding_dimension"]
            if not isinstance(dimension, int) or dimension < 128 or dimension > 4096:
                raise ValidationError("embedding_dimension must be an integer between 128 and 4096")
        
        return True


class FileValidator:
    """파일 관련 검증"""
    
    @staticmethod
    def validate_file_upload(
        filename: str,
        file_size: int,
        allowed_extensions: List[str],
        max_size: int
    ) -> bool:
        """
        파일 업로드 검증
        
        Args:
            filename: 파일명
            file_size: 파일 크기 (바이트)
            allowed_extensions: 허용된 확장자 목록
            max_size: 최대 파일 크기 (바이트)
            
        Returns:
            bool: 유효성 여부
        """
        if not filename or not filename.strip():
            raise ValidationError("Filename cannot be empty")
        
        # 파일 확장자 검증
        file_path = Path(filename)
        extension = file_path.suffix.lower().lstrip('.')
        
        if extension not in allowed_extensions:
            raise ValidationError(
                f"File extension '{extension}' not allowed. "
                f"Allowed extensions: {', '.join(allowed_extensions)}"
            )
        
        # 파일 크기 검증
        if file_size <= 0:
            raise ValidationError("File size must be greater than 0")
        
        if file_size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise ValidationError(f"File size exceeds maximum limit of {max_size_mb:.1f}MB")
        
        # 파일명 안전성 검증 (경로 순회 공격 방지)
        if '..' in filename or '/' in filename or '\\' in filename:
            raise ValidationError("Filename contains invalid path characters")
        
        return True
    
    @staticmethod
    def validate_document_content(content: str) -> bool:
        """
        문서 내용 검증
        
        Args:
            content: 문서 내용
            
        Returns:
            bool: 유효성 여부
        """
        if not content or not content.strip():
            raise ValidationError("Document content cannot be empty")
        
        if len(content) > 10_000_000:  # 10MB 텍스트 제한
            raise ValidationError("Document content too large (max 10MB)")
        
        # 최소 내용 길이
        if len(content.strip()) < 10:
            raise ValidationError("Document content too short (minimum 10 characters)")
        
        return True


class BenchmarkValidator:
    """벤치마크 관련 검증"""
    
    @staticmethod
    def validate_benchmark_config(config: Dict[str, Any]) -> bool:
        """
        벤치마크 설정 검증
        
        Args:
            config: 벤치마크 설정
            
        Returns:
            bool: 유효성 여부
        """
        if not isinstance(config, dict):
            raise ValidationError("Benchmark config must be a dictionary")
        
        # 파이프라인 ID 목록 검증
        if "pipeline_ids" not in config:
            raise ValidationError("Missing required field: pipeline_ids")
        
        pipeline_ids = config["pipeline_ids"]
        if not isinstance(pipeline_ids, list) or len(pipeline_ids) == 0:
            raise ValidationError("pipeline_ids must be a non-empty list")
        
        # UUID 형식 검증
        for pipeline_id in pipeline_ids:
            if not UUIDValidator.is_valid_uuid(pipeline_id):
                raise ValidationError(f"Invalid pipeline ID format: {pipeline_id}")
        
        # 반복 횟수 검증
        if "iterations" in config:
            iterations = config["iterations"]
            if not isinstance(iterations, int) or iterations < 1 or iterations > 10:
                raise ValidationError("iterations must be an integer between 1 and 10")
        
        # 타임아웃 검증
        if "timeout_seconds" in config:
            timeout = config["timeout_seconds"]
            if not isinstance(timeout, int) or timeout < 60 or timeout > 3600:
                raise ValidationError("timeout_seconds must be an integer between 60 and 3600")
        
        return True


class URLValidator:
    """URL 관련 검증"""
    
    @staticmethod
    def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> bool:
        """
        URL 형식 검증
        
        Args:
            url: 검증할 URL
            allowed_schemes: 허용된 스키마 목록 (기본값: ['http', 'https'])
            
        Returns:
            bool: 유효성 여부
        """
        if not url or not url.strip():
            raise ValidationError("URL cannot be empty")
        
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        try:
            parsed = urlparse(url)
        except Exception:
            raise ValidationError("Invalid URL format")
        
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(f"URL scheme must be one of: {', '.join(allowed_schemes)}")
        
        if not parsed.netloc:
            raise ValidationError("URL must include a domain")
        
        return True


class UUIDValidator:
    """UUID 관련 검증"""
    
    @staticmethod
    def is_valid_uuid(uuid_string: str, version: Optional[int] = None) -> bool:
        """
        UUID 형식 검증
        
        Args:
            uuid_string: UUID 문자열
            version: UUID 버전 (기본값: None, 모든 버전 허용)
            
        Returns:
            bool: 유효성 여부
        """
        try:
            uuid_obj = uuid.UUID(uuid_string)
            
            # 버전 검증
            if version is not None and uuid_obj.version != version:
                return False
                
            return True
        except (ValueError, AttributeError):
            return False
    
    @staticmethod
    def validate_uuid(uuid_string: str, field_name: str = "UUID") -> bool:
        """
        UUID 검증 (예외 발생)
        
        Args:
            uuid_string: UUID 문자열
            field_name: 필드명 (에러 메시지용)
            
        Returns:
            bool: 유효성 여부
            
        Raises:
            ValidationError: UUID가 유효하지 않은 경우
        """
        if not UUIDValidator.is_valid_uuid(uuid_string):
            raise ValidationError(f"Invalid {field_name} format")
        
        return True


class JSONValidator:
    """JSON 관련 검증"""
    
    @staticmethod
    def validate_json_string(json_string: str) -> bool:
        """
        JSON 문자열 검증
        
        Args:
            json_string: JSON 문자열
            
        Returns:
            bool: 유효성 여부
        """
        if not json_string or not json_string.strip():
            raise ValidationError("JSON string cannot be empty")
        
        try:
            json.loads(json_string)
            return True
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format: {str(e)}")
    
    @staticmethod
    def validate_json_schema(
        data: Dict[str, Any],
        required_fields: List[str],
        optional_fields: Optional[List[str]] = None
    ) -> bool:
        """
        JSON 스키마 검증
        
        Args:
            data: 검증할 데이터
            required_fields: 필수 필드 목록
            optional_fields: 선택적 필드 목록
            
        Returns:
            bool: 유효성 여부
        """
        if not isinstance(data, dict):
            raise ValidationError("Data must be a dictionary")
        
        # 필수 필드 확인
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
        
        # 허용되지 않은 필드 확인
        if optional_fields is not None:
            allowed_fields = set(required_fields + optional_fields)
            extra_fields = set(data.keys()) - allowed_fields
            
            if extra_fields:
                raise ValidationError(f"Unknown fields: {', '.join(extra_fields)}")
        
        return True


# 종합 검증 클래스
class DataValidator:
    """종합 데이터 검증 클래스"""
    
    def __init__(self):
        self.pipeline = PipelineValidator()
        self.query = QueryValidator()
        self.index = IndexValidator()
        self.file = FileValidator()
        self.benchmark = BenchmarkValidator()
        self.url = URLValidator()
        self.uuid = UUIDValidator()
        self.json = JSONValidator()
    
    def validate_all(self, data_type: str, data: Any, **kwargs) -> bool:
        """
        데이터 타입에 따른 종합 검증
        
        Args:
            data_type: 데이터 타입
            data: 검증할 데이터
            **kwargs: 추가 검증 파라미터
            
        Returns:
            bool: 유효성 여부
        """
        validators_map = {
            "pipeline_name": self.pipeline.validate_pipeline_name,
            "pipeline_config": self.pipeline.validate_pipeline_config,
            "query_text": self.query.validate_query_text,
            "index_name": self.index.validate_index_name,
            "uuid": self.uuid.validate_uuid,
            "url": self.url.validate_url,
            "json": self.json.validate_json_string,
        }
        
        validator = validators_map.get(data_type)
        if not validator:
            raise ValidationError(f"Unknown data type: {data_type}")
        
        return validator(data, **kwargs)


# 전역 검증기 인스턴스
validator = DataValidator()
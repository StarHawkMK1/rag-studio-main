# rag-studio/backend/app/utils/exceptions.py
"""
커스텀 예외 클래스 정의

애플리케이션에서 사용하는 구체적인 예외들을 정의합니다.
"""

from typing import Any, Dict, Optional, List


class RAGStudioException(Exception):
    """RAGStudio 기본 예외 클래스"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(RAGStudioException):
    """데이터 검증 실패 예외"""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        self.field = field
        self.value = value
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)


class ConfigurationError(RAGStudioException):
    """설정 오류 예외"""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        **kwargs
    ):
        self.config_key = config_key
        super().__init__(message, error_code="CONFIGURATION_ERROR", **kwargs)


class PipelineError(RAGStudioException):
    """파이프라인 관련 예외"""
    
    def __init__(
        self,
        message: str,
        pipeline_id: Optional[str] = None,
        stage: Optional[str] = None,
        **kwargs
    ):
        self.pipeline_id = pipeline_id
        self.stage = stage
        super().__init__(message, error_code="PIPELINE_ERROR", **kwargs)


class OpenSearchError(RAGStudioException):
    """OpenSearch 관련 예외"""
    
    def __init__(
        self,
        message: str,
        index_name: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        self.index_name = index_name
        self.operation = operation
        super().__init__(message, error_code="OPENSEARCH_ERROR", **kwargs)


class LLMError(RAGStudioException):
    """LLM 관련 예외"""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs
    ):
        self.model_name = model_name
        self.provider = provider
        super().__init__(message, error_code="LLM_ERROR", **kwargs)


class AuthenticationError(RAGStudioException):
    """인증 실패 예외"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, error_code="AUTHENTICATION_ERROR", **kwargs)


class AuthorizationError(RAGStudioException):
    """권한 부족 예외"""
    
    def __init__(
        self,
        message: str = "Access denied",
        required_permissions: Optional[List[str]] = None,
        **kwargs
    ):
        self.required_permissions = required_permissions or []
        super().__init__(message, error_code="AUTHORIZATION_ERROR", **kwargs)


class ResourceNotFoundError(RAGStudioException):
    """리소스 없음 예외"""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(message, error_code="RESOURCE_NOT_FOUND", **kwargs)


class ResourceConflictError(RAGStudioException):
    """리소스 충돌 예외"""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        conflicting_field: Optional[str] = None,
        **kwargs
    ):
        self.resource_type = resource_type
        self.conflicting_field = conflicting_field
        super().__init__(message, error_code="RESOURCE_CONFLICT", **kwargs)


class ServiceUnavailableError(RAGStudioException):
    """서비스 이용 불가 예외"""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(message, error_code="SERVICE_UNAVAILABLE", **kwargs)


class RateLimitError(RAGStudioException):
    """요청 제한 초과 예외"""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        reset_time: Optional[int] = None,
        **kwargs
    ):
        self.limit = limit
        self.reset_time = reset_time
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED", **kwargs)


class BenchmarkError(RAGStudioException):
    """벤치마크 관련 예외"""
    
    def __init__(
        self,
        message: str,
        benchmark_id: Optional[str] = None,
        stage: Optional[str] = None,
        **kwargs
    ):
        self.benchmark_id = benchmark_id
        self.stage = stage
        super().__init__(message, error_code="BENCHMARK_ERROR", **kwargs)


class FileProcessingError(RAGStudioException):
    """파일 처리 관련 예외"""
    
    def __init__(
        self,
        message: str,
        filename: Optional[str] = None,
        file_type: Optional[str] = None,
        **kwargs
    ):
        self.filename = filename
        self.file_type = file_type
        super().__init__(message, error_code="FILE_PROCESSING_ERROR", **kwargs)


class EmbeddingError(RAGStudioException):
    """임베딩 관련 예외"""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        text_length: Optional[int] = None,
        **kwargs
    ):
        self.model_name = model_name
        self.text_length = text_length
        super().__init__(message, error_code="EMBEDDING_ERROR", **kwargs)


# 예외 매핑 (HTTP 상태 코드)
EXCEPTION_STATUS_MAP = {
    ValidationError: 400,
    ConfigurationError: 400,
    AuthenticationError: 401,
    AuthorizationError: 403,
    ResourceNotFoundError: 404,
    ResourceConflictError: 409,
    RateLimitError: 429,
    ServiceUnavailableError: 503,
    PipelineError: 500,
    OpenSearchError: 500,
    LLMError: 500,
    BenchmarkError: 500,
    FileProcessingError: 500,
    EmbeddingError: 500,
    RAGStudioException: 500,
}


def get_http_status_code(exception: Exception) -> int:
    """
    예외 타입에 따른 HTTP 상태 코드 반환
    
    Args:
        exception: 예외 인스턴스
        
    Returns:
        int: HTTP 상태 코드
    """
    for exc_type, status_code in EXCEPTION_STATUS_MAP.items():
        if isinstance(exception, exc_type):
            return status_code
    
    return 500  # 기본값


def format_error_response(exception: RAGStudioException) -> Dict[str, Any]:
    """
    예외를 API 에러 응답 형식으로 변환
    
    Args:
        exception: RAGStudio 예외 인스턴스
        
    Returns:
        Dict[str, Any]: 에러 응답 딕셔너리
    """
    response = {
        "error": True,
        "error_code": exception.error_code or "UNKNOWN_ERROR",
        "message": exception.message,
        "details": exception.details
    }
    
    # 추가 필드들 포함
    if hasattr(exception, 'field') and exception.field:
        response["field"] = exception.field
    
    if hasattr(exception, 'resource_type') and exception.resource_type:
        response["resource_type"] = exception.resource_type
        
    if hasattr(exception, 'resource_id') and exception.resource_id:
        response["resource_id"] = exception.resource_id
    
    return response


class ExceptionHandler:
    """예외 처리 헬퍼 클래스"""
    
    @staticmethod
    def handle_validation_errors(errors: List[Dict[str, Any]]) -> ValidationError:
        """
        Pydantic 검증 에러를 커스텀 예외로 변환
        
        Args:
            errors: Pydantic 에러 리스트
            
        Returns:
            ValidationError: 변환된 예외
        """
        if not errors:
            return ValidationError("Unknown validation error")
        
        # 첫 번째 에러를 기준으로 예외 생성
        first_error = errors[0]
        field = ".".join(str(loc) for loc in first_error.get("loc", []))
        message = first_error.get("msg", "Validation failed")
        
        return ValidationError(
            message=f"Validation failed for field '{field}': {message}",
            field=field,
            details={"all_errors": errors}
        )
    
    @staticmethod
    def handle_database_errors(error: Exception) -> RAGStudioException:
        """
        데이터베이스 에러를 커스텀 예외로 변환
        
        Args:
            error: 데이터베이스 예외
            
        Returns:
            RAGStudioException: 변환된 예외
        """
        error_str = str(error).lower()
        
        if "unique" in error_str or "duplicate" in error_str:
            return ResourceConflictError(
                message="Resource already exists",
                details={"original_error": str(error)}
            )
        
        if "foreign key" in error_str:
            return ValidationError(
                message="Referenced resource does not exist",
                details={"original_error": str(error)}
            )
        
        if "not null" in error_str:
            return ValidationError(
                message="Required field is missing",
                details={"original_error": str(error)}
            )
        
        # 기본 예외 반환
        return RAGStudioException(
            message="Database operation failed",
            error_code="DATABASE_ERROR",
            details={"original_error": str(error)}
        )
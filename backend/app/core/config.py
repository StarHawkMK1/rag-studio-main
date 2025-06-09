# rag-studio/backend/app/core/config.py
"""
애플리케이션 설정 관리 모듈

환경 변수를 읽어와 Pydantic 모델로 검증하고,
애플리케이션 전체에서 사용할 설정값을 제공합니다.
"""

from typing import List, Optional, Union
from pathlib import Path
from functools import lru_cache

from pydantic import AnyHttpUrl, Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스
    
    환경 변수를 자동으로 읽어와 타입 검증을 수행합니다.
    .env 파일을 지원하며, 환경 변수가 우선순위를 가집니다.
    """
    
    # 애플리케이션 기본 설정
    APP_NAME: str = Field(default="RAGStudio", description="애플리케이션 이름")
    APP_VERSION: str = Field(default="1.0.0", description="애플리케이션 버전")
    DEBUG: bool = Field(default=False, description="디버그 모드 활성화 여부")
    LOG_LEVEL: str = Field(default="INFO", description="로깅 레벨")
    
    # API 서버 설정
    API_HOST: str = Field(default="0.0.0.0", description="API 서버 호스트")
    API_PORT: int = Field(default=8000, description="API 서버 포트")
    API_PREFIX: str = Field(default="/api/v1", description="API 경로 접두사")
    
    # CORS 설정
    CORS_ORIGINS: List[AnyHttpUrl] = Field(
        default=["http://localhost:3000", "http://localhost:9002"],
        description="허용된 CORS 오리진 목록"
    )
    
    # 데이터베이스 설정
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://ragstudio:password@localhost:5432/ragstudio",
        description="PostgreSQL 연결 URL"
    )
    DATABASE_ECHO: bool = Field(default=False, description="SQL 쿼리 로깅 여부")
    
    # Redis 설정
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 연결 URL"
    )
    
    # OpenSearch 설정
    OPENSEARCH_HOST: str = Field(default="localhost", description="OpenSearch 호스트")
    OPENSEARCH_PORT: int = Field(default=9200, description="OpenSearch 포트")
    OPENSEARCH_USER: Optional[str] = Field(default="admin", description="OpenSearch 사용자명")
    OPENSEARCH_PASSWORD: Optional[str] = Field(default="admin", description="OpenSearch 비밀번호")
    OPENSEARCH_USE_SSL: bool = Field(default=False, description="SSL 사용 여부")
    
    # OpenAI 설정
    OPENAI_API_KEY: str = Field(description="OpenAI API 키")
    OPENAI_MODEL: str = Field(default="gpt-4-turbo-preview", description="사용할 OpenAI 모델")
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small", 
        description="임베딩 생성에 사용할 모델"
    )
    
    # JWT 보안 설정
    SECRET_KEY: str = Field(
        default="your-secret-key-here-change-this-in-production",
        description="JWT 토큰 서명에 사용할 비밀 키"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT 알고리즘")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30, 
        description="액세스 토큰 만료 시간 (분)"
    )
    
    # Celery 설정
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        description="Celery 브로커 URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/2",
        description="Celery 결과 백엔드 URL"
    )
    
    # 파일 업로드 설정
    MAX_UPLOAD_SIZE: int = Field(
        default=104857600,  # 100MB
        description="최대 업로드 파일 크기 (바이트)"
    )
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=["pdf", "txt", "docx", "csv", "json"],
        description="허용된 파일 확장자 목록"
    )
    UPLOAD_DIR: Path = Field(
        default=Path("uploads"),
        description="업로드 파일 저장 디렉토리"
    )
    
    # 벤치마킹 설정
    BENCHMARK_TIMEOUT: int = Field(
        default=300,  # 5분
        description="벤치마크 실행 제한 시간 (초)"
    )
    BENCHMARK_MAX_QUERIES: int = Field(
        default=1000,
        description="벤치마크 최대 쿼리 수"
    )
    
    # RAG 파이프라인 설정
    CHUNK_SIZE: int = Field(default=1000, description="텍스트 청크 크기")
    CHUNK_OVERLAP: int = Field(default=200, description="청크 오버랩 크기")
    TOP_K_RETRIEVAL: int = Field(default=5, description="검색 결과 상위 K개")
    
    # 모델 설정
    DEFAULT_TEMPERATURE: float = Field(
        default=0.7, 
        description="LLM 기본 temperature 값"
    )
    MAX_TOKENS: int = Field(
        default=2000, 
        description="LLM 최대 토큰 수"
    )
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """
        CORS 오리진 문자열을 리스트로 파싱
        
        환경 변수에서 콤마로 구분된 문자열로 전달되는 경우를 처리합니다.
        """
        if isinstance(v, str):
            # 콤마로 구분된 문자열을 리스트로 변환
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("UPLOAD_DIR")
    def create_upload_dir(cls, v: Path) -> Path:
        """
        업로드 디렉토리가 없으면 생성
        
        애플리케이션 시작 시 업로드 디렉토리의 존재를 보장합니다.
        """
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    @property
    def opensearch_url(self) -> str:
        """OpenSearch 연결 URL 생성"""
        protocol = "https" if self.OPENSEARCH_USE_SSL else "http"
        
        if self.OPENSEARCH_USER and self.OPENSEARCH_PASSWORD:
            return f"{protocol}://{self.OPENSEARCH_USER}:{self.OPENSEARCH_PASSWORD}@{self.OPENSEARCH_HOST}:{self.OPENSEARCH_PORT}"
        
        return f"{protocol}://{self.OPENSEARCH_HOST}:{self.OPENSEARCH_PORT}"
    
    @property
    def database_url_sync(self) -> str:
        """동기 데이터베이스 URL (Alembic 마이그레이션용)"""
        return self.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
    
    class Config:
        """Pydantic 설정"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # 필드 설명을 스키마에 포함
        json_schema_extra = {
            "example": {
                "APP_NAME": "RAGStudio",
                "DEBUG": True,
                "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
                "OPENAI_API_KEY": "sk-..."
            }
        }


@lru_cache()
def get_settings() -> Settings:
    """
    설정 인스턴스를 반환하는 함수
    
    @lru_cache 데코레이터를 사용하여 설정 객체를 캐싱합니다.
    애플리케이션 생명주기 동안 동일한 설정 인스턴스를 재사용합니다.
    """
    return Settings()


# 전역 설정 인스턴스
settings = get_settings()
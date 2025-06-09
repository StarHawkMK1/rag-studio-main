# rag-studio/backend/tests/conftest.py
"""
pytest 설정 및 공통 픽스처

모든 테스트에서 사용할 공통 설정과 픽스처들을 정의합니다.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings
from app.models.user import User
from app.models.pipeline import Pipeline
from app.models.rag_config import PromptTemplate, LLMConfiguration
from app.core.security import get_password_hash, create_access_token


# 테스트용 비동기 데이터베이스 엔진
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)

TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """세션 수준의 이벤트 루프 생성"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    테스트용 데이터베이스 세션 픽스처
    
    각 테스트마다 새로운 인메모리 데이터베이스를 생성합니다.
    """
    # 테이블 생성
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 세션 생성
    async with TestAsyncSessionLocal() as session:
        yield session
    
    # 테이블 삭제
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    테스트용 HTTP 클라이언트 픽스처
    
    FastAPI 앱과 테스트 데이터베이스를 연결합니다.
    """
    def get_test_db():
        return db
    
    app.dependency_overrides[get_db] = get_test_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db: AsyncSession) -> User:
    """테스트 사용자 픽스처"""
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        is_superuser=False
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    """관리자 사용자 픽스처"""
    admin = User(
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        hashed_password=get_password_hash("adminpassword123"),
        is_active=True,
        is_superuser=True
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """인증 헤더 픽스처"""
    access_token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def admin_auth_headers(admin_user: User) -> dict:
    """관리자 인증 헤더 픽스처"""
    access_token = create_access_token(subject=str(admin_user.id))
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture
async def test_pipeline(db: AsyncSession, test_user: User) -> Pipeline:
    """테스트 파이프라인 픽스처"""
    from app.schemas.pipeline import PipelineType, PipelineStatus
    
    pipeline = Pipeline(
        name="Test Pipeline",
        description="테스트용 파이프라인",
        pipeline_type=PipelineType.NAIVE_RAG,
        status=PipelineStatus.INACTIVE,
        index_name="test_index",
        config={
            "retrieval_top_k": 5,
            "temperature": 0.7,
            "max_tokens": 2000
        },
        created_by=test_user.id
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return pipeline


@pytest_asyncio.fixture
async def test_prompt_template(db: AsyncSession, test_user: User) -> PromptTemplate:
    """테스트 프롬프트 템플릿 픽스처"""
    template = PromptTemplate(
        name="Test Template",
        description="테스트용 프롬프트 템플릿",
        template_text="Question: {question}\nAnswer:",
        template_format="f-string",
        variables=[
            {"name": "question", "type": "string", "required": True}
        ],
        category="test",
        is_active=True,
        created_by=test_user.id
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@pytest_asyncio.fixture
async def test_llm_config(db: AsyncSession, test_user: User) -> LLMConfiguration:
    """테스트 LLM 설정 픽스처"""
    config = LLMConfiguration(
        name="Test LLM Config",
        provider="openai",
        model_name="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=1000,
        description="테스트용 LLM 설정",
        is_active=True,
        created_by=test_user.id
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@pytest.fixture
def mock_opensearch_service():
    """OpenSearch 서비스 모킹 픽스처"""
    mock_service = MagicMock()
    
    # check_connection 모킹
    mock_service.check_connection = AsyncMock(return_value=True)
    
    # search 모킹
    mock_search_result = {
        "query": "test query",
        "total_hits": 3,
        "hits": [
            {
                "document_id": "doc1",
                "title": "Test Document 1",
                "chunk_text": "This is test content 1",
                "chunk_index": 0,
                "score": 0.95,
                "metadata": {"category": "test"}
            },
            {
                "document_id": "doc2", 
                "title": "Test Document 2",
                "chunk_text": "This is test content 2",
                "chunk_index": 0,
                "score": 0.87,
                "metadata": {"category": "test"}
            },
            {
                "document_id": "doc3",
                "title": "Test Document 3", 
                "chunk_text": "This is test content 3",
                "chunk_index": 0,
                "score": 0.82,
                "metadata": {"category": "test"}
            }
        ],
        "took_ms": 50
    }
    mock_service.search = AsyncMock(return_value=mock_search_result)
    
    # index_documents 모킹
    mock_index_result = {
        "total_documents": 1,
        "total_chunks": 3,
        "successful": 3,
        "failed": 0,
        "failed_items": []
    }
    mock_service.index_documents = AsyncMock(return_value=mock_index_result)
    
    # get_cluster_health 모킹
    from app.schemas.opensearch import ClusterHealth
    mock_health = ClusterHealth(
        cluster_name="test-cluster",
        status="green",
        node_count=1,
        active_shards=1,
        relocating_shards=0,
        initializing_shards=0,
        unassigned_shards=0,
        delayed_unassigned_shards=0,
        active_shards_percent=100.0
    )
    mock_service.get_cluster_health = AsyncMock(return_value=mock_health)
    
    # get_index_stats 모킹
    from app.schemas.opensearch import IndexStats
    mock_stats = IndexStats(
        index_name="test_index",
        document_count=10,
        size_in_bytes=1024,
        size_human="1.0KB",
        primary_shards=1,
        total_shards=1
    )
    mock_service.get_index_stats = AsyncMock(return_value=mock_stats)
    
    return mock_service


@pytest.fixture
def mock_llm():
    """LLM 모킹 픽스처"""
    mock_llm = MagicMock()
    
    # agenerate 모킹
    from langchain.schema import LLMResult, Generation
    mock_generation = Generation(text="This is a test response from the LLM.")
    mock_result = LLMResult(generations=[[mock_generation]])
    mock_llm.agenerate = AsyncMock(return_value=mock_result)
    
    # apredict 모킹
    mock_llm.apredict = AsyncMock(return_value="This is a test prediction.")
    
    return mock_llm


@pytest.fixture
def mock_settings():
    """설정 모킹 픽스처"""
    mock_settings = MagicMock()
    mock_settings.OPENAI_API_KEY = "test-api-key"
    mock_settings.OPENAI_MODEL = "gpt-3.5-turbo"
    mock_settings.EMBEDDING_MODEL = "text-embedding-3-small"
    mock_settings.CHUNK_SIZE = 1000
    mock_settings.CHUNK_OVERLAP = 200
    mock_settings.TOP_K_RETRIEVAL = 5
    mock_settings.DEFAULT_TEMPERATURE = 0.7
    mock_settings.MAX_TOKENS = 2000
    mock_settings.OPENSEARCH_HOST = "localhost"
    mock_settings.OPENSEARCH_PORT = 9200
    mock_settings.MAX_UPLOAD_SIZE = 104857600
    mock_settings.ALLOWED_EXTENSIONS = ["pdf", "txt", "docx", "csv", "json"]
    return mock_settings


@pytest.fixture
def sample_documents():
    """샘플 문서 픽스처"""
    from app.schemas.opensearch import DocumentInput
    
    return [
        DocumentInput(
            document_id="test_doc_1",
            title="Test Document 1",
            content="This is the content of test document 1. It contains information about testing.",
            source="test",
            metadata={"category": "test", "priority": "high"}
        ),
        DocumentInput(
            document_id="test_doc_2",
            title="Test Document 2", 
            content="This is the content of test document 2. It contains different information for testing.",
            source="test",
            metadata={"category": "test", "priority": "medium"}
        )
    ]


@pytest.fixture
def sample_query_input():
    """샘플 쿼리 입력 픽스처"""
    from app.schemas.pipeline import QueryInput
    
    return QueryInput(
        query_id="test_query_123",
        query_text="What is testing?",
        top_k=5,
        filters={"category": "test"}
    )


@pytest.fixture
def sample_benchmark_config():
    """샘플 벤치마크 설정 픽스처"""
    from app.schemas.benchmark import BenchmarkCreate
    
    return BenchmarkCreate(
        name="Test Benchmark",
        description="테스트용 벤치마크",
        pipeline_ids=["pipeline1", "pipeline2"],
        auto_generate_cases=True,
        num_test_cases=10,
        iterations=1,
        timeout_seconds=300
    )


# 모킹 유틸리티
class MockAsyncContext:
    """비동기 컨텍스트 매니저 모킹"""
    
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# 테스트 데이터 생성 헬퍼
def create_test_user_data(
    email: str = "test@example.com",
    username: str = "testuser",
    is_superuser: bool = False
) -> dict:
    """테스트 사용자 데이터 생성 헬퍼"""
    return {
        "email": email,
        "username": username,
        "full_name": f"Test User {username}",
        "password": "testpassword123",
        "is_active": True,
        "is_superuser": is_superuser
    }


def create_test_pipeline_data(
    name: str = "Test Pipeline",
    index_name: str = "test_index"
) -> dict:
    """테스트 파이프라인 데이터 생성 헬퍼"""
    return {
        "name": name,
        "description": f"Description for {name}",
        "pipeline_type": "naive_rag",
        "index_name": index_name,
        "config": {
            "retrieval_top_k": 5,
            "temperature": 0.7,
            "max_tokens": 2000
        }
    }


# pytest 설정
pytest_plugins = ["pytest_asyncio"]

# 테스트 설정
pytestmark = pytest.mark.asyncio
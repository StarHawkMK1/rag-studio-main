# rag-studio/backend/tests/test_pipelines.py
"""
파이프라인 API 테스트

파이프라인 관련 엔드포인트의 테스트 케이스를 포함합니다.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.models.pipeline import Pipeline
from app.schemas.pipeline import PipelineType, PipelineStatus
from app.core.security import create_access_token


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    """테스트 사용자 픽스처"""
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password="hashed_password",
        is_active=True,
        is_superuser=False
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def auth_headers(test_user: User) -> dict:
    """인증 헤더 픽스처"""
    access_token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def test_pipeline(db: AsyncSession, test_user: User) -> Pipeline:
    """테스트 파이프라인 픽스처"""
    pipeline = Pipeline(
        name="Test Pipeline",
        description="Test description",
        pipeline_type=PipelineType.NAIVE_RAG,
        status=PipelineStatus.INACTIVE,
        index_name="test_index",
        config={"temperature": 0.7},
        created_by=test_user.id
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return pipeline


class TestPipelineAPI:
    """파이프라인 API 테스트 클래스"""
    
    async def test_create_pipeline(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """파이프라인 생성 테스트"""
        pipeline_data = {
            "name": "New Test Pipeline",
            "description": "A test pipeline",
            "pipeline_type": "naive_rag",
            "index_name": "test_index"
        }
        
        response = await client.post(
            "/api/v1/pipelines",
            json=pipeline_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == pipeline_data["name"]
        assert data["pipeline_type"] == pipeline_data["pipeline_type"]
        assert data["status"] == "inactive"
    
    async def test_list_pipelines(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline,
        auth_headers: dict
    ):
        """파이프라인 목록 조회 테스트"""
        response = await client.get(
            "/api/v1/pipelines",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1
        assert data["total"] >= 1
    
    async def test_get_pipeline(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline,
        auth_headers: dict
    ):
        """특정 파이프라인 조회 테스트"""
        response = await client.get(
            f"/api/v1/pipelines/{test_pipeline.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_pipeline.id)
        assert data["name"] == test_pipeline.name
    
    async def test_update_pipeline(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline,
        auth_headers: dict
    ):
        """파이프라인 수정 테스트"""
        update_data = {
            "name": "Updated Pipeline Name",
            "description": "Updated description"
        }
        
        response = await client.put(
            f"/api/v1/pipelines/{test_pipeline.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
    
    async def test_execute_pipeline(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline,
        auth_headers: dict,
        mocker
    ):
        """파이프라인 실행 테스트"""
        # RAG 실행을 모킹
        mock_result = {
            "query_id": "test_query_123",
            "query_text": "What is machine learning?",
            "answer": "Machine learning is...",
            "retrieved_documents": [],
            "latency_ms": 250,
            "pipeline_type": "naive_rag"
        }
        
        mocker.patch(
            "app.services.rag_executor.NaiveRAGPipeline.process_query",
            return_value=mock_result
        )
        
        query_data = {
            "query_text": "What is machine learning?",
            "top_k": 5
        }
        
        response = await client.post(
            f"/api/v1/pipelines/{test_pipeline.id}/execute",
            json=query_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["query_text"] == query_data["query_text"]
        assert "answer" in data
        assert "latency_ms" in data
    
    async def test_delete_pipeline(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline,
        auth_headers: dict
    ):
        """파이프라인 삭제 테스트"""
        response = await client.delete(
            f"/api/v1/pipelines/{test_pipeline.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # 삭제 확인
        response = await client.get(
            f"/api/v1/pipelines/{test_pipeline.id}",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    async def test_activate_pipeline(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline,
        auth_headers: dict
    ):
        """파이프라인 활성화 테스트"""
        response = await client.post(
            f"/api/v1/pipelines/{test_pipeline.id}/activate",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
    
    async def test_deactivate_pipeline(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline,
        auth_headers: dict,
        db: AsyncSession
    ):
        """파이프라인 비활성화 테스트"""
        # 먼저 활성화
        test_pipeline.status = PipelineStatus.ACTIVE
        await db.commit()
        
        response = await client.post(
            f"/api/v1/pipelines/{test_pipeline.id}/deactivate",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "inactive"
    
    async def test_pipeline_metrics(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline,
        auth_headers: dict
    ):
        """파이프라인 메트릭 조회 테스트"""
        response = await client.get(
            f"/api/v1/pipelines/{test_pipeline.id}/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_queries" in data
        assert "successful_queries" in data
        assert "failed_queries" in data
        assert "average_latency" in data
    
    async def test_unauthorized_access(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline
    ):
        """인증되지 않은 접근 테스트"""
        response = await client.get(f"/api/v1/pipelines/{test_pipeline.id}")
        assert response.status_code == 401
    
    async def test_invalid_pipeline_type(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """잘못된 파이프라인 타입 테스트"""
        pipeline_data = {
            "name": "Invalid Pipeline",
            "pipeline_type": "invalid_type",
            "index_name": "test_index"
        }
        
        response = await client.post(
            "/api/v1/pipelines",
            json=pipeline_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error


class TestPipelineExecution:
    """파이프라인 실행 관련 테스트"""
    
    async def test_naive_rag_execution(
        self,
        client: AsyncClient,
        test_pipeline: Pipeline,
        auth_headers: dict,
        mocker
    ):
        """Naive RAG 파이프라인 실행 테스트"""
        # OpenSearch 검색 결과 모킹
        mock_search_result = {
            "query": "test query",
            "total_hits": 5,
            "hits": [
                {
                    "document_id": "doc1",
                    "title": "Test Document",
                    "chunk_text": "This is a test document",
                    "chunk_index": 0,
                    "score": 0.95,
                    "metadata": {}
                }
            ],
            "took_ms": 50
        }
        
        mocker.patch(
            "app.services.opensearch_service.OpenSearchService.search",
            return_value=mock_search_result
        )
        
        # LLM 응답 모킹
        mocker.patch(
            "langchain.chat_models.ChatOpenAI.agenerate",
            return_value=mocker.Mock(
                generations=[[mocker.Mock(text="This is the answer")]]
            )
        )
        
        query_data = {
            "query_text": "test query",
            "top_k": 5
        }
        
        response = await client.post(
            f"/api/v1/pipelines/{test_pipeline.id}/execute",
            json=query_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_type"] == "naive_rag"
        assert len(data["retrieved_documents"]) > 0
        assert data["answer"] == "This is the answer"
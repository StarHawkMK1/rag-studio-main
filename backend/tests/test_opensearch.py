# rag-studio/backend/tests/test_opensearch.py
"""
OpenSearch 관련 테스트

OpenSearch 클러스터 관리, 인덱스 작업, 문서 색인/검색 등을 테스트합니다.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.opensearch import (
    IndexConfig, 
    DocumentInput, 
    SearchQuery,
    ClusterHealth,
    IndexStats
)


class TestOpenSearchAPI:
    """OpenSearch API 테스트 클래스"""
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_get_cluster_health(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict,
        mock_opensearch_service
    ):
        """클러스터 상태 조회 테스트"""
        mock_get_service.return_value = mock_opensearch_service
        
        response = await client.get(
            "/api/v1/opensearch/health",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "cluster_name" in data
        assert "status" in data
        assert "node_count" in data
        assert "active_shards" in data
        assert data["status"] == "green"
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_cluster_connection_failed(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict
    ):
        """클러스터 연결 실패 테스트"""
        mock_service = MagicMock()
        mock_service.check_connection = AsyncMock(return_value=False)
        mock_get_service.return_value = mock_service
        
        response = await client.get(
            "/api/v1/opensearch/health",
            headers=auth_headers
        )
        
        assert response.status_code == 503
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_list_indices(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict,
        mock_opensearch_service
    ):
        """인덱스 목록 조회 테스트"""
        # 인덱스 정보 모킹
        mock_indices_response = {
            "test_index": {
                "settings": {
                    "index": {
                        "number_of_shards": "1",
                        "number_of_replicas": "0",
                        "creation_date": "1234567890"
                    }
                }
            },
            "another_index": {
                "settings": {
                    "index": {
                        "number_of_shards": "2", 
                        "number_of_replicas": "1",
                        "creation_date": "1234567891"
                    }
                }
            }
        }
        
        mock_opensearch_service.client.indices.get = AsyncMock(
            return_value=mock_indices_response
        )
        mock_get_service.return_value = mock_opensearch_service
        
        response = await client.get(
            "/api/v1/opensearch/indices",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "indices" in data
        assert "total" in data
        assert len(data["indices"]) == 2
        assert data["total"] == 2
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_create_index(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict,
        mock_opensearch_service
    ):
        """인덱스 생성 테스트"""
        mock_opensearch_service.create_index = AsyncMock(
            return_value={
                "index": "test_new_index",
                "acknowledged": True,
                "shards_acknowledged": True
            }
        )
        mock_get_service.return_value = mock_opensearch_service
        
        index_data = {
            "number_of_shards": 2,
            "number_of_replicas": 1,
            "embedding_dimension": 384
        }
        
        response = await client.post(
            "/api/v1/opensearch/indices?index_name=test_new_index",
            json=index_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["index"] == "test_new_index"
        assert data["acknowledged"] is True
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_create_index_already_exists(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict
    ):
        """이미 존재하는 인덱스 생성 시도 테스트"""
        mock_service = MagicMock()
        mock_service.create_index = AsyncMock(
            side_effect=Exception("resource_already_exists_exception")
        )
        mock_get_service.return_value = mock_service
        
        index_data = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "embedding_dimension": 384
        }
        
        response = await client.post(
            "/api/v1/opensearch/indices?index_name=existing_index",
            json=index_data,
            headers=auth_headers
        )
        
        assert response.status_code == 409
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_get_index_stats(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict,
        mock_opensearch_service
    ):
        """인덱스 통계 조회 테스트"""
        mock_get_service.return_value = mock_opensearch_service
        
        response = await client.get(
            "/api/v1/opensearch/indices/test_index",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "index_name" in data
        assert "document_count" in data
        assert "size_in_bytes" in data
        assert data["index_name"] == "test_index"
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_get_index_stats_not_found(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict
    ):
        """존재하지 않는 인덱스 통계 조회 테스트"""
        mock_service = MagicMock()
        mock_service.get_index_stats = AsyncMock(
            side_effect=Exception("index_not_found_exception")
        )
        mock_get_service.return_value = mock_service
        
        response = await client.get(
            "/api/v1/opensearch/indices/nonexistent_index",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_delete_index(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict
    ):
        """인덱스 삭제 테스트"""
        mock_service = MagicMock()
        mock_service.client.indices.delete = AsyncMock(
            return_value={"acknowledged": True}
        )
        mock_get_service.return_value = mock_service
        
        response = await client.delete(
            "/api/v1/opensearch/indices/test_index",
            headers=auth_headers
        )
        
        assert response.status_code == 204
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_index_documents(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict,
        sample_documents,
        mock_opensearch_service
    ):
        """문서 색인 테스트"""
        mock_opensearch_service.index_documents = AsyncMock(
            return_value={
                "total_documents": len(sample_documents),
                "total_chunks": 6,
                "successful": 6,
                "failed": 0,
                "failed_items": []
            }
        )
        mock_get_service.return_value = mock_opensearch_service
        
        documents_data = [doc.dict() for doc in sample_documents]
        
        response = await client.post(
            "/api/v1/opensearch/indices/test_index/documents",
            json=documents_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_documents"] == len(sample_documents)
        assert data["successful"] == 6
        assert data["failed"] == 0
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_search_documents(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict,
        mock_opensearch_service
    ):
        """문서 검색 테스트"""
        mock_get_service.return_value = mock_opensearch_service
        
        search_data = {
            "index_name": "test_index",
            "query_text": "machine learning",
            "top_k": 5
        }
        
        response = await client.post(
            "/api/v1/opensearch/search",
            json=search_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "total_hits" in data
        assert "hits" in data
        assert "took_ms" in data
        assert data["query"] == "machine learning"
        assert len(data["hits"]) <= 5
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_upload_file(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict,
        mock_opensearch_service
    ):
        """파일 업로드 테스트"""
        mock_opensearch_service.index_documents = AsyncMock(
            return_value={
                "total_documents": 1,
                "total_chunks": 3,
                "successful": 3,
                "failed": 0,
                "file_info": {
                    "filename": "test.txt",
                    "size_bytes": 1024,
                    "extension": "txt",
                    "source": "upload"
                }
            }
        )
        mock_get_service.return_value = mock_opensearch_service
        
        # 파일 파싱 모킹
        with patch("app.utils.file_parser.parse_document_file") as mock_parse:
            mock_parse.return_value = [
                DocumentInput(
                    document_id="uploaded_doc_1",
                    title="Uploaded Document",
                    content="This is uploaded content.",
                    source="upload"
                )
            ]
            
            # 임시 파일 생성 및 삭제 모킹
            with patch("aiofiles.open"), \
                 patch("pathlib.Path.unlink"), \
                 patch("pathlib.Path.stat"):
                
                # 파일 업로드
                files = {"file": ("test.txt", b"test content", "text/plain")}
                data = {"source": "upload"}
                
                response = await client.post(
                    "/api/v1/opensearch/indices/test_index/upload",
                    files=files,
                    data=data,
                    headers=auth_headers
                )
        
        assert response.status_code == 200
        result = response.json()
        assert result["successful"] == 3
        assert "file_info" in result
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_list_models(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict
    ):
        """ML 모델 목록 조회 테스트"""
        mock_service = MagicMock()
        mock_models_response = {
            "models": [
                {
                    "model_id": "model_1",
                    "name": "Test Model 1",
                    "model_type": "embedding",
                    "model_state": "DEPLOYED",
                    "model_version": "1.0",
                    "created_time": "2024-01-01T00:00:00Z"
                }
            ]
        }
        
        mock_service.client.transport.perform_request = AsyncMock(
            return_value=mock_models_response
        )
        mock_get_service.return_value = mock_service
        
        response = await client.get(
            "/api/v1/opensearch/models",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "model_1"
        assert data[0]["status"] == "loaded"
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_list_models_no_ml_plugin(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict
    ):
        """ML 플러그인이 없는 경우 테스트"""
        mock_service = MagicMock()
        mock_service.client.transport.perform_request = AsyncMock(
            side_effect=Exception("404")
        )
        mock_get_service.return_value = mock_service
        
        response = await client.get(
            "/api/v1/opensearch/models",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0  # 빈 목록 반환
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_list_pipelines(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict
    ):
        """인제스트 파이프라인 목록 조회 테스트"""
        mock_service = MagicMock()
        mock_pipelines_response = {
            "pipeline_1": {
                "description": "Test pipeline",
                "processors": [
                    {"set": {"field": "test", "value": "test_value"}}
                ]
            }
        }
        
        mock_service.client.ingest.get_pipeline = AsyncMock(
            return_value=mock_pipelines_response
        )
        mock_get_service.return_value = mock_service
        
        response = await client.get(
            "/api/v1/opensearch/pipelines",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "pipeline_1"
        assert data[0]["processor_count"] == 1
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_reindex_data(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict
    ):
        """데이터 재색인 테스트"""
        mock_service = MagicMock()
        
        # 인덱스 매핑 및 설정 조회 모킹
        mock_service.client.indices.get_mapping = AsyncMock(
            return_value={
                "source_index": {
                    "mappings": {"properties": {"field1": {"type": "text"}}}
                }
            }
        )
        mock_service.client.indices.get_settings = AsyncMock(
            return_value={
                "source_index": {
                    "settings": {
                        "index": {
                            "number_of_shards": "1",
                            "number_of_replicas": "0"
                        }
                    }
                }
            }
        )
        
        # 인덱스 생성 모킹
        mock_service.client.indices.create = AsyncMock(
            return_value={"acknowledged": True}
        )
        
        # 재색인 실행 모킹
        mock_service.client.reindex = AsyncMock(
            return_value={"task": "task_123"}
        )
        
        mock_get_service.return_value = mock_service
        
        reindex_data = {
            "source_index": "source_index",
            "target_index": "target_index",
            "create_target": True
        }
        
        response = await client.post(
            "/api/v1/opensearch/reindex",
            json=reindex_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task_123"
        assert data["source_index"] == "source_index"
        assert data["target_index"] == "target_index"
        assert data["status"] == "started"
    
    @patch("app.services.opensearch_service.get_opensearch_service")
    async def test_get_task_status(
        self,
        mock_get_service,
        client: AsyncClient,
        auth_headers: dict
    ):
        """태스크 상태 조회 테스트"""
        mock_service = MagicMock()
        mock_task_response = {
            "completed": True,
            "task": {
                "description": "reindex from [source] to [target]",
                "start_time_in_millis": 1234567890,
                "running_time_in_nanos": 1000000000,
                "status": {
                    "total": 100,
                    "created": 100,
                    "updated": 0,
                    "deleted": 0,
                    "batches": 1
                }
            }
        }
        
        mock_service.client.tasks.get = AsyncMock(
            return_value=mock_task_response
        )
        mock_get_service.return_value = mock_service
        
        response = await client.get(
            "/api/v1/opensearch/tasks/task_123",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task_123"
        assert data["completed"] is True
        assert data["status"]["total"] == 100
    
    async def test_unauthorized_access(
        self,
        client: AsyncClient
    ):
        """인증되지 않은 접근 테스트"""
        response = await client.get("/api/v1/opensearch/health")
        assert response.status_code == 401


class TestOpenSearchService:
    """OpenSearch 서비스 단위 테스트"""
    
    @patch("app.services.opensearch_service.AsyncOpenSearch")
    @patch("app.services.opensearch_service.SentenceTransformer")
    async def test_service_initialization(
        self,
        mock_sentence_transformer,
        mock_opensearch_client
    ):
        """서비스 초기화 테스트"""
        from app.services.opensearch_service import OpenSearchService
        
        # 모킹 설정
        mock_model = MagicMock()
        mock_sentence_transformer.return_value = mock_model
        
        # 서비스 생성
        service = OpenSearchService()
        
        # 초기화 확인
        assert service.client is not None
        assert service.embedding_model is not None
        mock_sentence_transformer.assert_called_once_with('all-MiniLM-L6-v2')
    
    async def test_connection_check_success(
        self,
        mock_opensearch_service
    ):
        """연결 확인 성공 테스트"""
        # info 메서드 모킹
        mock_opensearch_service.client.info = AsyncMock(
            return_value={
                "cluster_name": "test-cluster",
                "version": {"number": "2.11.0"}
            }
        )
        
        # 연결 확인
        result = await mock_opensearch_service.check_connection()
        
        assert result is True
    
    async def test_connection_check_failure(
        self,
        mock_opensearch_service
    ):
        """연결 확인 실패 테스트"""
        # info 메서드가 예외 발생하도록 모킹
        mock_opensearch_service.client.info = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        
        # 연결 확인
        result = await mock_opensearch_service.check_connection()
        
        assert result is False
    
    async def test_text_splitting(self):
        """텍스트 분할 테스트"""
        from app.services.opensearch_service import OpenSearchService
        
        service = OpenSearchService()
        
        # 긴 텍스트
        long_text = "This is a long text. " * 100  # 2000+ 문자
        
        # 분할 실행
        chunks = service._split_text(long_text, chunk_size=500, overlap=100)
        
        # 결과 검증
        assert len(chunks) > 1
        assert all(len(chunk) <= 600 for chunk in chunks)  # 오버랩 고려
    
    async def test_text_splitting_short_text(self):
        """짧은 텍스트 분할 테스트"""
        from app.services.opensearch_service import OpenSearchService
        
        service = OpenSearchService()
        
        # 짧은 텍스트
        short_text = "This is a short text."
        
        # 분할 실행
        chunks = service._split_text(short_text, chunk_size=1000, overlap=200)
        
        # 결과 검증
        assert len(chunks) == 1
        assert chunks[0] == short_text
    
    async def test_text_splitting_empty(self):
        """빈 텍스트 분할 테스트"""
        from app.services.opensearch_service import OpenSearchService
        
        service = OpenSearchService()
        
        # 빈 텍스트
        empty_text = ""
        
        # 분할 실행
        chunks = service._split_text(empty_text)
        
        # 결과 검증
        assert len(chunks) == 0
    
    def test_bytes_to_human_readable(self):
        """바이트 크기 변환 테스트"""
        from app.services.opensearch_service import OpenSearchService
        
        service = OpenSearchService()
        
        # 다양한 크기 테스트
        assert service._bytes_to_human_readable(512) == "512B"
        assert service._bytes_to_human_readable(1024) == "1.00KB"
        assert service._bytes_to_human_readable(1048576) == "1.00MB"
        assert service._bytes_to_human_readable(1073741824) == "1.00GB"
        assert service._bytes_to_human_readable(1536) == "1.50KB"
    
    async def test_document_indexing_flow(
        self,
        mock_opensearch_service,
        sample_documents
    ):
        """문서 색인 플로우 테스트"""
        # 임베딩 모델 모킹
        mock_opensearch_service.embedding_model.encode.return_value = [0.1] * 384
        
        # async_bulk 모킹
        with patch("app.services.opensearch_service.async_bulk") as mock_bulk:
            mock_bulk.return_value = (len(sample_documents) * 3, [])  # 성공 3개, 실패 0개
            
            # 문서 색인
            result = await mock_opensearch_service.index_documents(
                "test_index",
                sample_documents
            )
        
        # 결과 검증
        assert result["total_documents"] == len(sample_documents)
        assert result["successful"] > 0
        assert result["failed"] == 0
    
    async def test_search_execution(
        self,
        mock_opensearch_service
    ):
        """검색 실행 테스트"""
        from app.schemas.opensearch import SearchQuery
        
        # 검색 쿼리 생성
        query = SearchQuery(
            index_name="test_index",
            query_text="machine learning",
            top_k=5
        )
        
        # 임베딩 생성 모킹
        mock_opensearch_service.embedding_model.encode.return_value = [0.1] * 384
        
        # 검색 실행 모킹
        mock_search_response = {
            "hits": {
                "total": {"value": 3},
                "hits": [
                    {
                        "_source": {
                            "document_id": "doc1",
                            "title": "ML Guide",
                            "chunk_text": "Machine learning basics",
                            "chunk_index": 0,
                            "metadata": {}
                        },
                        "_score": 0.95
                    }
                ]
            },
            "took": 50
        }
        
        mock_opensearch_service.client.search = AsyncMock(
            return_value=mock_search_response
        )
        
        # 검색 실행
        result = await mock_opensearch_service.search("test_index", query)
        
        # 결과 검증
        assert result.query == "machine learning"
        assert result.total_hits == 3
        assert len(result.hits) == 1
        assert result.took_ms == 50


class TestOpenSearchValidation:
    """OpenSearch 데이터 검증 테스트"""
    
    def test_index_config_validation(self):
        """인덱스 설정 검증 테스트"""
        # 유효한 설정
        valid_config = IndexConfig(
            number_of_shards=2,
            number_of_replicas=1,
            embedding_dimension=384
        )
        assert valid_config.number_of_shards == 2
        assert valid_config.number_of_replicas == 1
        assert valid_config.embedding_dimension == 384
        
        # 잘못된 설정 테스트
        with pytest.raises(ValueError):
            IndexConfig(
                number_of_shards=0,  # 최소값 위반
                number_of_replicas=1,
                embedding_dimension=384
            )
    
    def test_document_input_validation(self):
        """문서 입력 검증 테스트"""
        # 유효한 문서
        valid_doc = DocumentInput(
            document_id="doc_001",
            title="Test Document",
            content="This is test content.",
            source="test"
        )
        assert valid_doc.document_id == "doc_001"
        assert valid_doc.source == "test"
        
        # 필수 필드 누락 테스트
        with pytest.raises(ValueError):
            DocumentInput(
                title="Test Document",
                content="This is test content."
                # document_id 누락
            )
    
    def test_search_query_validation(self):
        """검색 쿼리 검증 테스트"""
        # 유효한 쿼리
        valid_query = SearchQuery(
            index_name="test_index",
            query_text="test query",
            top_k=10
        )
        assert valid_query.index_name == "test_index"
        assert valid_query.top_k == 10
        
        # top_k 범위 초과 테스트
        with pytest.raises(ValueError):
            SearchQuery(
                index_name="test_index",
                query_text="test query",
                top_k=101  # 최대값 초과
            )
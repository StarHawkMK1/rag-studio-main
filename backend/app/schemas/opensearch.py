# rag-studio/backend/app/schemas/opensearch.py
"""
OpenSearch 관련 스키마
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ClusterHealth(BaseModel):
    """클러스터 상태"""
    cluster_name: str
    status: str  # green, yellow, red
    node_count: int
    active_shards: int
    relocating_shards: int
    initializing_shards: int
    unassigned_shards: int
    delayed_unassigned_shards: int
    active_shards_percent: float


class IndexConfig(BaseModel):
    """인덱스 설정"""
    number_of_shards: int = Field(default=1, ge=1, le=10)
    number_of_replicas: int = Field(default=1, ge=0, le=5)
    embedding_dimension: int = Field(default=384, ge=128, le=4096)
    
    class Config:
        json_schema_extra = {
            "example": {
                "number_of_shards": 2,
                "number_of_replicas": 1,
                "embedding_dimension": 384
            }
        }


class IndexStats(BaseModel):
    """인덱스 통계"""
    index_name: str
    document_count: int
    size_in_bytes: int
    size_human: str
    primary_shards: int
    total_shards: int


class IndexListResponse(BaseModel):
    """인덱스 목록 응답"""
    indices: List[Dict[str, Any]]
    total: int


class DocumentInput(BaseModel):
    """문서 입력"""
    document_id: str
    title: str
    content: str
    source: Optional[str] = "manual"
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_001",
                "title": "User Manual",
                "content": "This is the content of the document...",
                "source": "upload",
                "metadata": {"category": "manual", "version": "1.0"}
            }
        }


class DocumentBulkUpload(BaseModel):
    """문서 일괄 업로드"""
    documents: List[DocumentInput]


class SearchQuery(BaseModel):
    """검색 쿼리"""
    index_name: str
    query_text: str
    top_k: int = Field(default=10, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "index_name": "documents",
                "query_text": "machine learning",
                "top_k": 10
            }
        }


class SearchResult(BaseModel):
    """검색 결과"""
    query: str
    total_hits: int
    hits: List[Dict[str, Any]]
    took_ms: int


class ModelInfo(BaseModel):
    """ML 모델 정보"""
    id: str
    name: str
    type: str
    status: str
    version: Optional[str]
    created_at: Optional[str]


class PipelineInfo(BaseModel):
    """인제스트 파이프라인 정보"""
    id: str
    name: str
    description: str
    processor_count: int
    processors: Optional[List[Dict[str, Any]]] = None
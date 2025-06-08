# rag-studio/backend/app/schemas/pipeline.py
"""
파이프라인 관련 스키마
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator


class PipelineType(str, Enum):
    """파이프라인 타입"""
    NAIVE_RAG = "naive_rag"
    GRAPH_RAG = "graph_rag"


class PipelineStatus(str, Enum):
    """파이프라인 상태"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class PipelineConfig(BaseModel):
    """파이프라인 설정"""
    name: str
    pipeline_type: PipelineType
    index_name: str
    retrieval_top_k: Optional[int] = Field(default=5, ge=1, le=100)
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=2000, ge=100, le=8000)
    search_filters: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Customer Support Pipeline",
                "pipeline_type": "graph_rag",
                "index_name": "customer_docs",
                "retrieval_top_k": 5,
                "temperature": 0.7,
                "max_tokens": 2000
            }
        }


class PipelineCreate(BaseModel):
    """파이프라인 생성 요청"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    pipeline_type: PipelineType
    index_name: str = Field(..., min_length=1, max_length=255)
    config: Optional[PipelineConfig] = None


class PipelineUpdate(BaseModel):
    """파이프라인 수정 요청"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[PipelineStatus] = None
    config: Optional[Dict[str, Any]] = None


class PipelineMetrics(BaseModel):
    """파이프라인 성능 메트릭"""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    average_latency: float = 0.0
    average_retrieval_score: float = 0.0


class PipelineResponse(BaseModel):
    """파이프라인 응답"""
    id: str
    name: str
    description: Optional[str]
    pipeline_type: PipelineType
    status: PipelineStatus
    index_name: str
    config: Dict[str, Any]
    metrics: Optional[PipelineMetrics]
    created_at: datetime
    updated_at: datetime
    last_run: Optional[datetime]


class PipelineListResponse(BaseModel):
    """파이프라인 목록 응답"""
    items: List[PipelineResponse]
    total: int
    skip: int
    limit: int


class QueryInput(BaseModel):
    """쿼리 입력"""
    query_id: Optional[str] = None
    query_text: str = Field(..., min_length=1, max_length=1000)
    top_k: Optional[int] = Field(default=5, ge=1, le=50)
    filters: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_text": "How do I reset my password?",
                "top_k": 5
            }
        }


class QueryResult(BaseModel):
    """쿼리 실행 결과"""
    query_id: str
    query_text: str
    answer: str
    retrieved_documents: List[Dict[str, Any]]
    latency_ms: int
    pipeline_type: PipelineType
    metadata: Optional[Dict[str, Any]] = None
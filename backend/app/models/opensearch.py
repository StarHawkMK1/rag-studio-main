# rag-studio/backend/app/models/opensearch.py
"""
OpenSearch 관련 모델

OpenSearch 인덱스, 문서, 검색 등과 관련된 데이터베이스 모델을 정의합니다.
"""

from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base, TimestampMixin


class IndexConfiguration(Base, TimestampMixin):
    """OpenSearch 인덱스 설정 모델"""
    
    __tablename__ = "index_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text)
    
    # 인덱스 설정
    number_of_shards = Column(Integer, default=1)
    number_of_replicas = Column(Integer, default=1)
    embedding_dimension = Column(Integer, default=384)
    
    # 매핑 설정
    mapping_config = Column(JSON, default={})
    analyzer_config = Column(JSON, default={})
    
    # 상태
    is_active = Column(Boolean, default=True)
    index_created = Column(Boolean, default=False)
    
    # 메타데이터
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # 관계
    documents = relationship("DocumentRecord", back_populates="index_config")
    
    def __repr__(self):
        return f"<IndexConfiguration(id={self.id}, name='{self.name}')>"


class DocumentRecord(Base, TimestampMixin):
    """문서 색인 기록 모델"""
    
    __tablename__ = "document_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String(255), nullable=False, index=True)
    title = Column(String(500))
    content_hash = Column(String(64))  # SHA-256 해시
    
    # 파일 정보
    original_filename = Column(String(255))
    file_size = Column(Integer)
    file_type = Column(String(50))
    
    # 색인 정보
    index_config_id = Column(UUID(as_uuid=True), ForeignKey("index_configurations.id"))
    chunk_count = Column(Integer, default=0)
    embedding_model = Column(String(100))
    
    # 처리 상태
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    
    # 메타데이터
    source = Column(String(100), default="upload")
    metadata = Column(JSON, default={})
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # 관계
    index_config = relationship("IndexConfiguration", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document")
    
    def __repr__(self):
        return f"<DocumentRecord(id={self.id}, document_id='{self.document_id}')>"


class DocumentChunk(Base, TimestampMixin):
    """문서 청크 모델"""
    
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_record_id = Column(UUID(as_uuid=True), ForeignKey("document_records.id"))
    
    # 청크 정보
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_hash = Column(String(64))  # 청크 내용 해시
    
    # 임베딩 정보
    embedding_vector = Column(JSON)  # 임베딩 벡터 (저장용)
    embedding_model = Column(String(100))
    
    # OpenSearch 정보
    opensearch_doc_id = Column(String(255))  # OpenSearch 문서 ID
    indexed_at = Column(DateTime)
    
    # 메타데이터
    metadata = Column(JSON, default={})
    
    # 관계
    document = relationship("DocumentRecord", back_populates="chunks")
    
    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, chunk_index={self.chunk_index})>"


class SearchQuery(Base, TimestampMixin):
    """검색 쿼리 기록 모델"""
    
    __tablename__ = "search_queries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_text = Column(Text, nullable=False)
    query_hash = Column(String(64), index=True)  # 쿼리 해시 (중복 검색 감지용)
    
    # 검색 설정
    index_name = Column(String(255))
    top_k = Column(Integer, default=10)
    filters = Column(JSON, default={})
    
    # 검색 결과
    total_hits = Column(Integer, default=0)
    took_ms = Column(Integer)  # 검색 소요 시간
    results = Column(JSON, default=[])  # 검색 결과 (요약)
    
    # 사용자 정보
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    session_id = Column(String(255))
    
    # 메타데이터
    source = Column(String(50), default="manual")  # manual, pipeline, benchmark
    metadata = Column(JSON, default={})
    
    def __repr__(self):
        return f"<SearchQuery(id={self.id}, query_text='{self.query_text[:50]}...')>"


class IndexStats(Base, TimestampMixin):
    """인덱스 통계 모델"""
    
    __tablename__ = "index_stats"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    index_name = Column(String(255), nullable=False, index=True)
    
    # 통계 정보
    document_count = Column(Integer, default=0)
    size_in_bytes = Column(Integer, default=0)
    primary_shards = Column(Integer, default=1)
    total_shards = Column(Integer, default=1)
    
    # 성능 메트릭
    avg_search_time_ms = Column(Float, default=0.0)
    total_searches = Column(Integer, default=0)
    
    # 수집 시간
    collected_at = Column(DateTime, nullable=False)
    
    # 추가 메트릭
    metrics = Column(JSON, default={})
    
    def __repr__(self):
        return f"<IndexStats(index_name='{self.index_name}', collected_at={self.collected_at})>"


class EmbeddingModel(Base, TimestampMixin):
    """임베딩 모델 정보"""
    
    __tablename__ = "embedding_models"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    provider = Column(String(100))  # openai, huggingface, local
    model_id = Column(String(255))  # 실제 모델 식별자
    
    # 모델 정보
    dimension = Column(Integer, nullable=False)
    max_input_length = Column(Integer, default=512)
    
    # 설정
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    config = Column(JSON, default={})
    
    # 사용 통계
    usage_count = Column(Integer, default=0)
    avg_processing_time_ms = Column(Float, default=0.0)
    
    # 메타데이터
    description = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    def __repr__(self):
        return f"<EmbeddingModel(name='{self.name}', dimension={self.dimension})>"


class ClusterHealth(Base, TimestampMixin):
    """클러스터 상태 기록 모델"""
    
    __tablename__ = "cluster_health_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_name = Column(String(255))
    status = Column(String(20))  # green, yellow, red
    
    # 노드 정보
    node_count = Column(Integer, default=0)
    data_node_count = Column(Integer, default=0)
    
    # 샤드 정보
    active_shards = Column(Integer, default=0)
    relocating_shards = Column(Integer, default=0)
    initializing_shards = Column(Integer, default=0)
    unassigned_shards = Column(Integer, default=0)
    
    # 성능 메트릭
    active_shards_percent = Column(Float, default=0.0)
    
    # 체크 시간
    checked_at = Column(DateTime, nullable=False)
    
    # 추가 정보
    details = Column(JSON, default={})
    
    def __repr__(self):
        return f"<ClusterHealth(status='{self.status}', checked_at={self.checked_at})>"
# rag-studio/backend/app/models/rag_config.py
"""
RAG 설정 관련 모델

RAG 파이프라인의 다양한 설정과 구성 요소를 관리하는 모델들을 정의합니다.
"""

from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.models.base import Base, TimestampMixin


class ComponentType(str, enum.Enum):
    """RAG 컴포넌트 타입"""
    LOADER = "loader"
    SPLITTER = "splitter"
    EMBEDDER = "embedder"
    RETRIEVER = "retriever"
    GENERATOR = "generator"
    POSTPROCESSOR = "postprocessor"


class PromptTemplate(Base, TimestampMixin):
    """프롬프트 템플릿 모델"""
    
    __tablename__ = "prompt_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    
    # 템플릿 내용
    template_text = Column(Text, nullable=False)
    template_format = Column(String(50), default="f-string")  # f-string, jinja2, custom
    
    # 변수 정의
    variables = Column(JSON, default=[])  # [{"name": "context", "type": "string", "required": true}]
    
    # 카테고리
    category = Column(String(100))  # qa, summarization, extraction, etc.
    use_case = Column(String(100))  # naive_rag, graph_rag, etc.
    
    # 설정
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # 성능 메트릭
    usage_count = Column(Integer, default=0)
    avg_quality_score = Column(Float, default=0.0)
    
    # 메타데이터
    tags = Column(JSON, default=[])
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # 관계
    configurations = relationship("RAGConfiguration", back_populates="prompt_template")
    
    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, name='{self.name}')>"


class RAGConfiguration(Base, TimestampMixin):
    """RAG 파이프라인 전체 설정 모델"""
    
    __tablename__ = "rag_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    version = Column(String(50), default="1.0.0")
    
    # 파이프라인 연결
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id"))
    
    # 구성 요소 설정
    prompt_template_id = Column(UUID(as_uuid=True), ForeignKey("prompt_templates.id"))
    
    # 검색 설정
    retrieval_config = Column(JSON, default={})  # top_k, similarity_threshold, etc.
    
    # 생성 설정
    generation_config = Column(JSON, default={})  # temperature, max_tokens, etc.
    
    # 후처리 설정
    postprocessing_config = Column(JSON, default={})  # filtering, ranking, etc.
    
    # 전체 설정
    global_config = Column(JSON, default={})
    
    # 상태
    is_active = Column(Boolean, default=True)
    is_validated = Column(Boolean, default=False)
    
    # 성능 정보
    avg_latency_ms = Column(Float, default=0.0)
    avg_quality_score = Column(Float, default=0.0)
    total_executions = Column(Integer, default=0)
    
    # 메타데이터
    tags = Column(JSON, default=[])
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # 관계
    prompt_template = relationship("PromptTemplate", back_populates="configurations")
    component_configs = relationship("ComponentConfiguration", back_populates="rag_config")
    
    def __repr__(self):
        return f"<RAGConfiguration(id={self.id}, name='{self.name}')>"


class ComponentConfiguration(Base, TimestampMixin):
    """개별 컴포넌트 설정 모델"""
    
    __tablename__ = "component_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rag_config_id = Column(UUID(as_uuid=True), ForeignKey("rag_configurations.id"))
    
    # 컴포넌트 정보
    component_type = Column(Enum(ComponentType), nullable=False)
    component_name = Column(String(255), nullable=False)
    order_index = Column(Integer, default=0)  # 실행 순서
    
    # 설정
    config = Column(JSON, default={})
    is_enabled = Column(Boolean, default=True)
    
    # 성능 메트릭
    avg_execution_time_ms = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)
    
    # 메타데이터
    description = Column(Text)
    version = Column(String(50), default="1.0.0")
    
    # 관계
    rag_config = relationship("RAGConfiguration", back_populates="component_configs")
    
    def __repr__(self):
        return f"<ComponentConfiguration(type={self.component_type}, name='{self.component_name}')>"


class LLMConfiguration(Base, TimestampMixin):
    """LLM 설정 모델"""
    
    __tablename__ = "llm_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    provider = Column(String(100), nullable=False)  # openai, anthropic, local, etc.
    model_name = Column(String(255), nullable=False)
    
    # 생성 파라미터
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)
    top_p = Column(Float, default=1.0)
    frequency_penalty = Column(Float, default=0.0)
    presence_penalty = Column(Float, default=0.0)
    
    # 설정
    system_prompt = Column(Text)
    stop_sequences = Column(JSON, default=[])
    
    # API 설정
    api_key_ref = Column(String(255))  # 키 참조 (실제 키는 저장하지 않음)
    api_base_url = Column(String(500))
    api_version = Column(String(50))
    
    # 상태
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # 성능 메트릭
    avg_latency_ms = Column(Float, default=0.0)
    total_tokens_used = Column(Integer, default=0)
    cost_per_token = Column(Float, default=0.0)
    
    # 메타데이터
    description = Column(Text)
    tags = Column(JSON, default=[])
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    def __repr__(self):
        return f"<LLMConfiguration(name='{self.name}', model='{self.model_name}')>"


class RetrievalConfiguration(Base, TimestampMixin):
    """검색 설정 모델"""
    
    __tablename__ = "retrieval_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    
    # 기본 검색 설정
    top_k = Column(Integer, default=5)
    similarity_threshold = Column(Float, default=0.7)
    max_distance = Column(Float)
    
    # 고급 검색 설정
    search_strategy = Column(String(100), default="semantic")  # semantic, hybrid, keyword
    reranking_enabled = Column(Boolean, default=False)
    reranking_top_k = Column(Integer, default=20)
    
    # 필터링
    metadata_filters = Column(JSON, default={})
    content_filters = Column(JSON, default={})
    
    # 다이버시티 설정
    diversity_enabled = Column(Boolean, default=False)
    diversity_threshold = Column(Float, default=0.8)
    
    # 시간 가중치
    time_decay_enabled = Column(Boolean, default=False)
    time_decay_factor = Column(Float, default=0.9)
    
    # 상태
    is_active = Column(Boolean, default=True)
    
    # 성능 메트릭
    avg_retrieval_time_ms = Column(Float, default=0.0)
    avg_relevance_score = Column(Float, default=0.0)
    
    # 메타데이터
    description = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    def __repr__(self):
        return f"<RetrievalConfiguration(name='{self.name}', top_k={self.top_k})>"


class ChunkingConfiguration(Base, TimestampMixin):
    """청킹 설정 모델"""
    
    __tablename__ = "chunking_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    
    # 청킹 전략
    strategy = Column(String(100), default="recursive")  # recursive, semantic, fixed, sentence
    
    # 크기 설정
    chunk_size = Column(Integer, default=1000)
    chunk_overlap = Column(Integer, default=200)
    min_chunk_size = Column(Integer, default=100)
    max_chunk_size = Column(Integer, default=2000)
    
    # 구분자 설정
    separators = Column(JSON, default=["\n\n", "\n", " ", ""])
    keep_separator = Column(Boolean, default=False)
    
    # 특수 설정
    respect_sentence_boundary = Column(Boolean, default=True)
    respect_word_boundary = Column(Boolean, default=True)
    
    # 메타데이터 보존
    preserve_metadata = Column(Boolean, default=True)
    metadata_keys = Column(JSON, default=[])
    
    # 상태
    is_active = Column(Boolean, default=True)
    
    # 메타데이터
    description = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    def __repr__(self):
        return f"<ChunkingConfiguration(name='{self.name}', strategy='{self.strategy}')>"


class QualityMetrics(Base, TimestampMixin):
    """RAG 품질 메트릭 기록"""
    
    __tablename__ = "quality_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rag_config_id = Column(UUID(as_uuid=True), ForeignKey("rag_configurations.id"))
    
    # 메트릭 타입
    metric_type = Column(String(100))  # relevance, coherence, faithfulness, etc.
    
    # 점수
    score = Column(Float, nullable=False)
    max_score = Column(Float, default=1.0)
    
    # 측정 정보
    measurement_method = Column(String(100))  # human, automatic, hybrid
    evaluator = Column(String(255))  # 평가자 또는 평가 모델
    
    # 컨텍스트
    query_text = Column(Text)
    generated_answer = Column(Text)
    reference_answer = Column(Text)
    retrieved_context = Column(JSON)
    
    # 메타데이터
    evaluation_date = Column(DateTime, nullable=False)
    metadata = Column(JSON, default={})
    
    def __repr__(self):
        return f"<QualityMetrics(type='{self.metric_type}', score={self.score})>"
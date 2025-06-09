# rag-studio/backend/app/schemas/rag_config.py
"""
RAG 설정 관련 스키마

RAG 파이프라인 설정을 위한 Pydantic 스키마들을 정의합니다.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator


class ComponentType(str, Enum):
    """RAG 컴포넌트 타입"""
    LOADER = "loader"
    SPLITTER = "splitter"  
    EMBEDDER = "embedder"
    RETRIEVER = "retriever"
    GENERATOR = "generator"
    POSTPROCESSOR = "postprocessor"


class TemplateFormat(str, Enum):
    """프롬프트 템플릿 형식"""
    F_STRING = "f-string"
    JINJA2 = "jinja2"
    CUSTOM = "custom"


class SearchStrategy(str, Enum):
    """검색 전략"""
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    KEYWORD = "keyword"
    GRAPH = "graph"


class ChunkingStrategy(str, Enum):
    """청킹 전략"""
    RECURSIVE = "recursive"
    SEMANTIC = "semantic"
    FIXED = "fixed"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"


# 기본 스키마들

class PromptTemplateBase(BaseModel):
    """프롬프트 템플릿 기본 스키마"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    template_text: str = Field(..., min_length=1)
    template_format: TemplateFormat = TemplateFormat.F_STRING
    variables: List[Dict[str, Any]] = Field(default_factory=list)
    category: Optional[str] = None
    use_case: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PromptTemplateCreate(PromptTemplateBase):
    """프롬프트 템플릿 생성 스키마"""
    pass


class PromptTemplateUpdate(BaseModel):
    """프롬프트 템플릿 수정 스키마"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    template_text: Optional[str] = Field(None, min_length=1)
    template_format: Optional[TemplateFormat] = None
    variables: Optional[List[Dict[str, Any]]] = None
    category: Optional[str] = None
    use_case: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class PromptTemplateResponse(PromptTemplateBase):
    """프롬프트 템플릿 응답 스키마"""
    id: str
    is_active: bool
    is_default: bool
    usage_count: int
    avg_quality_score: float
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True


# LLM 설정 스키마

class LLMConfigurationBase(BaseModel):
    """LLM 설정 기본 스키마"""
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., min_length=1, max_length=100)
    model_name: str = Field(..., min_length=1, max_length=255)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=1, le=32000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    system_prompt: Optional[str] = None
    stop_sequences: List[str] = Field(default_factory=list)
    api_base_url: Optional[str] = None
    api_version: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class LLMConfigurationCreate(LLMConfigurationBase):
    """LLM 설정 생성 스키마"""
    api_key: Optional[str] = Field(None, description="API 키 (저장 시 참조로 변환)")


class LLMConfigurationUpdate(BaseModel):
    """LLM 설정 수정 스키마"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    provider: Optional[str] = Field(None, min_length=1, max_length=100)
    model_name: Optional[str] = Field(None, min_length=1, max_length=255)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    system_prompt: Optional[str] = None
    stop_sequences: Optional[List[str]] = None
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    api_version: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class LLMConfigurationResponse(LLMConfigurationBase):
    """LLM 설정 응답 스키마"""
    id: str
    is_active: bool
    is_default: bool
    avg_latency_ms: float
    total_tokens_used: int
    cost_per_token: float
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True


# 검색 설정 스키마

class RetrievalConfigurationBase(BaseModel):
    """검색 설정 기본 스키마"""
    name: str = Field(..., min_length=1, max_length=255)
    top_k: int = Field(default=5, ge=1, le=100)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_distance: Optional[float] = Field(None, ge=0.0)
    search_strategy: SearchStrategy = SearchStrategy.SEMANTIC
    reranking_enabled: bool = False
    reranking_top_k: int = Field(default=20, ge=1, le=200)
    metadata_filters: Dict[str, Any] = Field(default_factory=dict)
    content_filters: Dict[str, Any] = Field(default_factory=dict)
    diversity_enabled: bool = False
    diversity_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    time_decay_enabled: bool = False
    time_decay_factor: float = Field(default=0.9, ge=0.0, le=1.0)
    description: Optional[str] = None


class RetrievalConfigurationCreate(RetrievalConfigurationBase):
    """검색 설정 생성 스키마"""
    pass


class RetrievalConfigurationUpdate(BaseModel):
    """검색 설정 수정 스키마"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    top_k: Optional[int] = Field(None, ge=1, le=100)
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_distance: Optional[float] = Field(None, ge=0.0)
    search_strategy: Optional[SearchStrategy] = None
    reranking_enabled: Optional[bool] = None
    reranking_top_k: Optional[int] = Field(None, ge=1, le=200)
    metadata_filters: Optional[Dict[str, Any]] = None
    content_filters: Optional[Dict[str, Any]] = None
    diversity_enabled: Optional[bool] = None
    diversity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    time_decay_enabled: Optional[bool] = None
    time_decay_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None
    description: Optional[str] = None


class RetrievalConfigurationResponse(RetrievalConfigurationBase):
    """검색 설정 응답 스키마"""
    id: str
    is_active: bool
    avg_retrieval_time_ms: float
    avg_relevance_score: float
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True


# 청킹 설정 스키마

class ChunkingConfigurationBase(BaseModel):
    """청킹 설정 기본 스키마"""
    name: str = Field(..., min_length=1, max_length=255)
    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE
    chunk_size: int = Field(default=1000, ge=100, le=10000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    min_chunk_size: int = Field(default=100, ge=10, le=1000)
    max_chunk_size: int = Field(default=2000, ge=500, le=20000)
    separators: List[str] = Field(default=["\n\n", "\n", " ", ""])
    keep_separator: bool = False
    respect_sentence_boundary: bool = True
    respect_word_boundary: bool = True
    preserve_metadata: bool = True
    metadata_keys: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    
    @validator('chunk_overlap')
    def validate_overlap(cls, v, values):
        if 'chunk_size' in values and v >= values['chunk_size']:
            raise ValueError('chunk_overlap must be less than chunk_size')
        return v


class ChunkingConfigurationCreate(ChunkingConfigurationBase):
    """청킹 설정 생성 스키마"""
    pass


class ChunkingConfigurationUpdate(BaseModel):
    """청킹 설정 수정 스키마"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    strategy: Optional[ChunkingStrategy] = None
    chunk_size: Optional[int] = Field(None, ge=100, le=10000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000)
    min_chunk_size: Optional[int] = Field(None, ge=10, le=1000)
    max_chunk_size: Optional[int] = Field(None, ge=500, le=20000)
    separators: Optional[List[str]] = None
    keep_separator: Optional[bool] = None
    respect_sentence_boundary: Optional[bool] = None
    respect_word_boundary: Optional[bool] = None
    preserve_metadata: Optional[bool] = None
    metadata_keys: Optional[List[str]] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class ChunkingConfigurationResponse(ChunkingConfigurationBase):
    """청킹 설정 응답 스키마"""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True


# 컴포넌트 설정 스키마

class ComponentConfigurationBase(BaseModel):
    """컴포넌트 설정 기본 스키마"""
    component_type: ComponentType
    component_name: str = Field(..., min_length=1, max_length=255)
    order_index: int = Field(default=0, ge=0)
    config: Dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    description: Optional[str] = None
    version: str = Field(default="1.0.0", max_length=50)


class ComponentConfigurationCreate(ComponentConfigurationBase):
    """컴포넌트 설정 생성 스키마"""
    pass


class ComponentConfigurationUpdate(BaseModel):
    """컴포넌트 설정 수정 스키마"""
    component_name: Optional[str] = Field(None, min_length=1, max_length=255)
    order_index: Optional[int] = Field(None, ge=0)
    config: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None
    description: Optional[str] = None
    version: Optional[str] = Field(None, max_length=50)


class ComponentConfigurationResponse(ComponentConfigurationBase):
    """컴포넌트 설정 응답 스키마"""
    id: str
    avg_execution_time_ms: float
    success_rate: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# RAG 전체 설정 스키마

class RAGConfigurationBase(BaseModel):
    """RAG 설정 기본 스키마"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    version: str = Field(default="1.0.0", max_length=50)
    retrieval_config: Dict[str, Any] = Field(default_factory=dict)
    generation_config: Dict[str, Any] = Field(default_factory=dict)
    postprocessing_config: Dict[str, Any] = Field(default_factory=dict)
    global_config: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class RAGConfigurationCreate(RAGConfigurationBase):
    """RAG 설정 생성 스키마"""
    pipeline_id: Optional[str] = None
    prompt_template_id: Optional[str] = None
    component_configs: List[ComponentConfigurationCreate] = Field(default_factory=list)


class RAGConfigurationUpdate(BaseModel):
    """RAG 설정 수정 스키마"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    version: Optional[str] = Field(None, max_length=50)
    prompt_template_id: Optional[str] = None
    retrieval_config: Optional[Dict[str, Any]] = None
    generation_config: Optional[Dict[str, Any]] = None
    postprocessing_config: Optional[Dict[str, Any]] = None
    global_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None


class RAGConfigurationResponse(RAGConfigurationBase):
    """RAG 설정 응답 스키마"""
    id: str
    pipeline_id: Optional[str] = None
    prompt_template_id: Optional[str] = None
    is_active: bool
    is_validated: bool
    avg_latency_ms: float
    avg_quality_score: float
    total_executions: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    component_configs: List[ComponentConfigurationResponse] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


# 품질 메트릭 스키마

class QualityMetricsBase(BaseModel):
    """품질 메트릭 기본 스키마"""
    metric_type: str = Field(..., min_length=1, max_length=100)
    score: float = Field(..., ge=0.0)
    max_score: float = Field(default=1.0, gt=0.0)
    measurement_method: str = Field(..., min_length=1, max_length=100)
    evaluator: str = Field(..., min_length=1, max_length=255)
    query_text: Optional[str] = None
    generated_answer: Optional[str] = None
    reference_answer: Optional[str] = None
    retrieved_context: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QualityMetricsCreate(QualityMetricsBase):
    """품질 메트릭 생성 스키마"""
    rag_config_id: str
    evaluation_date: datetime = Field(default_factory=datetime.utcnow)


class QualityMetricsResponse(QualityMetricsBase):
    """품질 메트릭 응답 스키마"""
    id: str
    rag_config_id: str
    evaluation_date: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# 목록 응답 스키마

class PromptTemplateListResponse(BaseModel):
    """프롬프트 템플릿 목록 응답"""
    items: List[PromptTemplateResponse]
    total: int
    skip: int = 0
    limit: int = 100


class LLMConfigurationListResponse(BaseModel):
    """LLM 설정 목록 응답"""
    items: List[LLMConfigurationResponse]
    total: int
    skip: int = 0
    limit: int = 100


class RetrievalConfigurationListResponse(BaseModel):
    """검색 설정 목록 응답"""
    items: List[RetrievalConfigurationResponse]
    total: int
    skip: int = 0
    limit: int = 100


class ChunkingConfigurationListResponse(BaseModel):
    """청킹 설정 목록 응답"""
    items: List[ChunkingConfigurationResponse]
    total: int
    skip: int = 0
    limit: int = 100


class RAGConfigurationListResponse(BaseModel):
    """RAG 설정 목록 응답"""
    items: List[RAGConfigurationResponse]
    total: int
    skip: int = 0
    limit: int = 100


# 설정 템플릿 스키마

class ConfigurationTemplate(BaseModel):
    """설정 템플릿"""
    name: str
    description: str
    category: str
    config: Dict[str, Any]
    is_default: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Basic QA Pipeline",
                "description": "기본 질의응답 파이프라인 설정",
                "category": "qa",
                "config": {
                    "retrieval": {"top_k": 5, "similarity_threshold": 0.7},
                    "generation": {"temperature": 0.7, "max_tokens": 2000}
                },
                "is_default": True
            }
        }


class ConfigurationValidation(BaseModel):
    """설정 검증 결과"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_valid": False,
                "errors": ["temperature must be between 0.0 and 2.0"],
                "warnings": ["high max_tokens may increase latency"],
                "suggestions": ["consider using retrieval reranking for better results"]
            }
        }
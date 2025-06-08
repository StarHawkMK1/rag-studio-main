# rag-studio/backend/app/models/pipeline.py
"""
파이프라인 모델
"""

from sqlalchemy import Column, String, Enum, JSON, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base, TimestampMixin
from app.schemas.pipeline import PipelineType, PipelineStatus


class Pipeline(Base, TimestampMixin):
    """RAG 파이프라인 모델"""
    
    __tablename__ = "pipelines"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    pipeline_type = Column(Enum(PipelineType), nullable=False)
    status = Column(Enum(PipelineStatus), default=PipelineStatus.INACTIVE)
    index_name = Column(String(255), nullable=False)
    config = Column(JSON, default={})
    
    # 메타데이터
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    last_run = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Pipeline(id={self.id}, name='{self.name}', type={self.pipeline_type})>"

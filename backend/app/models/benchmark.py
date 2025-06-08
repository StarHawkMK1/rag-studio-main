# rag-studio/backend/app/models/benchmark.py
"""
벤치마크 모델
"""

from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base, TimestampMixin


class Benchmark(Base, TimestampMixin):
    """벤치마크 실행 모델"""
    
    __tablename__ = "benchmarks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    
    # 설정
    config = Column(JSON, nullable=False)
    
    # 실행 정보
    total_queries = Column(Integer, default=0)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # 결과
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    # 메타데이터
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    def __repr__(self):
        return f"<Benchmark(id={self.id}, name='{self.name}', status={self.status})>"
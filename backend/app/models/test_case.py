# rag-studio/backend/app/models/test_case.py
"""
테스트 케이스 모델
"""

from sqlalchemy import Column, String, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base, TimestampMixin


class TestCase(Base, TimestampMixin):
    """벤치마크 테스트 케이스 모델"""
    
    __tablename__ = "test_cases"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(String(255), unique=True, nullable=False)
    query = Column(Text, nullable=False)
    query_type = Column(String(50))  # factual, analytical, comparative, explanatory
    expected_answer = Column(Text, nullable=True)
    test_metadata = Column(JSON, default={})
    
    # 메타데이터
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    def __repr__(self):
        return f"<TestCase(id={self.id}, query_id='{self.query_id}', type={self.query_type})>"

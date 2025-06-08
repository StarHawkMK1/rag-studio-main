# rag-studio/backend/app/models/base.py
"""
베이스 모델 클래스
"""

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime
from datetime import datetime

Base = declarative_base()


class TimestampMixin:
    """타임스탬프 믹스인"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

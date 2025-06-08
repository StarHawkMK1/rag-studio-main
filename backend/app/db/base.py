# rag-studio/backend/app/db/base.py
"""
데이터베이스 베이스 설정
"""

# 모든 모델을 import하여 Base.metadata에 등록
from app.models.base import Base
from app.models.pipeline import Pipeline
from app.models.benchmark import Benchmark
from app.models.test_case import TestCase
from app.models.user import User

__all__ = ["Base", "Pipeline", "Benchmark", "TestCase", "User"]
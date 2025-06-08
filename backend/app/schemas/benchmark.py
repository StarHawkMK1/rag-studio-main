# rag-studio/backend/app/schemas/benchmark.py
"""
벤치마킹 관련 스키마
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class QueryTestCase(BaseModel):
    """테스트 케이스"""
    query_id: str
    query: str
    query_type: Optional[str] = None
    expected_answer: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BenchmarkConfig(BaseModel):
    """벤치마크 설정"""
    pipeline_ids: List[str]
    test_case_ids: Optional[List[str]] = None
    iterations: int = Field(default=1, ge=1, le=10)
    warmup_queries: int = Field(default=0, ge=0, le=10)
    timeout_seconds: Optional[int] = Field(default=300, ge=60, le=3600)
    top_k: int = Field(default=5, ge=1, le=50)
    parallel_execution: bool = False


class BenchmarkCreate(BaseModel):
    """벤치마크 생성 요청"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    pipeline_ids: List[str] = Field(..., min_items=1)
    test_case_ids: Optional[List[str]] = None
    auto_generate_cases: bool = True
    num_test_cases: Optional[int] = Field(default=50, ge=10, le=1000)
    query_types: Optional[List[str]] = None
    iterations: int = Field(default=1, ge=1, le=10)
    warmup_queries: int = Field(default=5, ge=0, le=20)
    timeout_seconds: Optional[int] = Field(default=300, ge=60, le=3600)
    top_k: int = Field(default=5, ge=1, le=50)
    parallel_execution: bool = False


class BenchmarkMetrics(BaseModel):
    """파이프라인 벤치마크 메트릭"""
    pipeline_id: str
    latency_ms: Dict[str, float]  # mean, median, std, min, max, p95, p99
    retrieval_score: Dict[str, float]  # mean, median, std, min, max
    success_rate: float
    throughput_qps: float
    total_queries: int
    failed_queries: int
    error_rate: float


class ComparisonResult(BaseModel):
    """파이프라인 비교 결과"""
    pipeline_a: str
    pipeline_b: str
    metrics_comparison: Dict[str, float]
    winner: str
    winner_criteria: Dict[str, str]
    summary: str


class BenchmarkResult(BaseModel):
    """벤치마크 실행 결과"""
    benchmark_id: str
    config: BenchmarkConfig
    metrics: Dict[str, BenchmarkMetrics]
    comparisons: List[ComparisonResult]
    total_queries: int
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    status: str
    error: Optional[str] = None


class BenchmarkListResponse(BaseModel):
    """벤치마크 목록 응답"""
    items: List[Dict[str, Any]]
    total: int
    skip: int
    limit: int


class TestCaseUpload(BaseModel):
    """테스트 케이스 업로드"""
    test_cases: List[QueryTestCase]
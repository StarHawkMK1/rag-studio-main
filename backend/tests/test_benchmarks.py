# rag-studio/backend/tests/test_benchmarks.py
"""
벤치마크 관련 테스트

벤치마크 생성, 실행, 결과 조회 등의 기능을 테스트합니다.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.pipeline import Pipeline
from app.models.benchmark import Benchmark as BenchmarkModel
from app.schemas.benchmark import BenchmarkCreate, QueryTestCase
from app.schemas.pipeline import PipelineType, PipelineStatus


@pytest.fixture
async def test_pipelines(db: AsyncSession, test_user: User):
    """테스트용 파이프라인들 생성"""
    pipelines = []
    
    for i in range(2):
        pipeline = Pipeline(
            name=f"Test Pipeline {i+1}",
            description=f"테스트 파이프라인 {i+1}",
            pipeline_type=PipelineType.NAIVE_RAG,
            status=PipelineStatus.INACTIVE,
            index_name="test_index",
            config={
                "retrieval_top_k": 5 + i,
                "temperature": 0.7 + (i * 0.1),
                "max_tokens": 2000
            },
            created_by=test_user.id
        )
        db.add(pipeline)
        pipelines.append(pipeline)
    
    await db.commit()
    
    for pipeline in pipelines:
        await db.refresh(pipeline)
    
    return pipelines


@pytest.fixture
async def test_benchmark(db: AsyncSession, test_user: User, test_pipelines):
    """테스트용 벤치마크 생성"""
    benchmark = BenchmarkModel(
        name="Test Benchmark",
        description="테스트용 벤치마크",
        status="pending",
        config={
            "pipeline_ids": [str(p.id) for p in test_pipelines],
            "iterations": 1,
            "timeout_seconds": 300,
            "top_k": 5
        },
        total_queries=10,
        created_by=test_user.id
    )
    db.add(benchmark)
    await db.commit()
    await db.refresh(benchmark)
    return benchmark


class TestBenchmarkAPI:
    """벤치마크 API 테스트 클래스"""
    
    async def test_list_benchmarks(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_benchmark: BenchmarkModel
    ):
        """벤치마크 목록 조회 테스트"""
        response = await client.get(
            "/api/v1/benchmarks/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1
        assert data["total"] >= 1
        
        # 첫 번째 벤치마크 확인
        benchmark_item = data["items"][0]
        assert "id" in benchmark_item
        assert "name" in benchmark_item
        assert "status" in benchmark_item
        assert "pipeline_count" in benchmark_item
    
    async def test_create_benchmark_auto_generate(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_pipelines
    ):
        """자동 테스트 케이스 생성으로 벤치마크 생성 테스트"""
        benchmark_data = {
            "name": "Auto Generated Benchmark",
            "description": "자동 생성된 테스트 케이스로 벤치마크",
            "pipeline_ids": [str(p.id) for p in test_pipelines],
            "auto_generate_cases": True,
            "num_test_cases": 5,
            "iterations": 1,
            "timeout_seconds": 300
        }
        
        with patch("app.services.benchmark_service.benchmark_service") as mock_service:
            # 테스트 케이스 생성 모킹
            mock_test_cases = [
                QueryTestCase(
                    query_id=f"test_{i}",
                    query=f"Test query {i}",
                    query_type="factual"
                ) for i in range(5)
            ]
            mock_service.generate_test_cases.return_value = mock_test_cases
            
            response = await client.post(
                "/api/v1/benchmarks/",
                json=benchmark_data,
                headers=auth_headers
            )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == benchmark_data["name"]
        assert data["status"] == "running"
        assert "id" in data
        assert data["pipeline_count"] == len(test_pipelines)
        assert data["test_case_count"] == 5
    
    async def test_create_benchmark_with_test_cases(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_pipelines
    ):
        """기존 테스트 케이스로 벤치마크 생성 테스트"""
        benchmark_data = {
            "name": "Manual Test Cases Benchmark", 
            "description": "수동으로 제공된 테스트 케이스로 벤치마크",
            "pipeline_ids": [str(p.id) for p in test_pipelines],
            "test_case_ids": ["case_1", "case_2", "case_3"],
            "auto_generate_cases": False,
            "iterations": 2,
            "timeout_seconds": 600
        }
        
        with patch("app.api.v1.benchmarks._load_test_cases") as mock_load:
            # 테스트 케이스 로드 모킹
            mock_test_cases = [
                QueryTestCase(
                    query_id=case_id,
                    query=f"Query for {case_id}",
                    query_type="factual"
                ) for case_id in benchmark_data["test_case_ids"]
            ]
            mock_load.return_value = mock_test_cases
            
            response = await client.post(
                "/api/v1/benchmarks/",
                json=benchmark_data,
                headers=auth_headers
            )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == benchmark_data["name"]
        assert data["status"] == "running"
    
    async def test_get_benchmark_result_pending(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_benchmark: BenchmarkModel
    ):
        """진행 중인 벤치마크 결과 조회 테스트"""
        response = await client.get(
            f"/api/v1/benchmarks/{test_benchmark.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["benchmark_id"] == str(test_benchmark.id)
        assert data["status"] == "pending"
        assert "message" in data
    
    async def test_get_benchmark_result_completed(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_benchmark: BenchmarkModel,
        db: AsyncSession
    ):
        """완료된 벤치마크 결과 조회 테스트"""
        # 벤치마크 결과 설정
        mock_result = {
            "benchmark_id": str(test_benchmark.id),
            "status": "completed",
            "metrics": {
                "pipeline_1": {
                    "latency_ms": {"mean": 250.5, "median": 245.0},
                    "retrieval_score": {"mean": 0.85},
                    "success_rate": 0.95,
                    "throughput_qps": 4.2
                }
            },
            "total_queries": 10,
            "duration_seconds": 30.5
        }
        
        test_benchmark.status = "completed"
        test_benchmark.result = mock_result
        await db.commit()
        
        response = await client.get(
            f"/api/v1/benchmarks/{test_benchmark.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "metrics" in data
        assert data["total_queries"] == 10
    
    async def test_get_benchmark_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """존재하지 않는 벤치마크 조회 테스트"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        
        response = await client.get(
            f"/api/v1/benchmarks/{fake_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    async def test_delete_benchmark(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_benchmark: BenchmarkModel,
        db: AsyncSession
    ):
        """벤치마크 삭제 테스트"""
        # 벤치마크를 완료 상태로 변경
        test_benchmark.status = "completed"
        await db.commit()
        
        response = await client.delete(
            f"/api/v1/benchmarks/{test_benchmark.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # 삭제 확인
        response = await client.get(
            f"/api/v1/benchmarks/{test_benchmark.id}",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    async def test_delete_running_benchmark(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_benchmark: BenchmarkModel,
        db: AsyncSession
    ):
        """실행 중인 벤치마크 삭제 시도 테스트"""
        # 벤치마크를 실행 중 상태로 변경
        test_benchmark.status = "running"
        await db.commit()
        
        response = await client.delete(
            f"/api/v1/benchmarks/{test_benchmark.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    async def test_export_benchmark_result_json(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_benchmark: BenchmarkModel,
        db: AsyncSession
    ):
        """벤치마크 결과 JSON 내보내기 테스트"""
        # 완료된 벤치마크 결과 설정
        mock_result = {
            "benchmark_id": str(test_benchmark.id),
            "status": "completed",
            "metrics": {"pipeline_1": {"latency_ms": {"mean": 250.5}}},
            "total_queries": 10
        }
        
        test_benchmark.status = "completed"
        test_benchmark.result = mock_result
        await db.commit()
        
        response = await client.get(
            f"/api/v1/benchmarks/{test_benchmark.id}/export?format=json",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers["content-disposition"]
    
    async def test_export_benchmark_result_csv(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_benchmark: BenchmarkModel,
        db: AsyncSession
    ):
        """벤치마크 결과 CSV 내보내기 테스트"""
        # 완료된 벤치마크 결과 설정
        mock_result = {
            "benchmark_id": str(test_benchmark.id),
            "status": "completed",
            "metrics": {
                "pipeline_1": {
                    "latency_ms": {"mean": 250.5},
                    "retrieval_score": {"mean": 0.85},
                    "success_rate": 0.95,
                    "throughput_qps": 4.2
                }
            }
        }
        
        test_benchmark.status = "completed"
        test_benchmark.result = mock_result
        await db.commit()
        
        response = await client.get(
            f"/api/v1/benchmarks/{test_benchmark.id}/export?format=csv",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"
    
    async def test_compare_benchmarks(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_pipelines,
        db: AsyncSession
    ):
        """벤치마크 비교 테스트"""
        # 두 개의 완료된 벤치마크 생성
        benchmark1 = BenchmarkModel(
            name="Benchmark 1",
            status="completed",
            result={
                "metrics": {
                    "pipeline_1": {
                        "latency_ms": {"mean": 250.0},
                        "retrieval_score": {"mean": 0.8},
                        "success_rate": 0.9
                    }
                }
            },
            total_queries=10
        )
        
        benchmark2 = BenchmarkModel(
            name="Benchmark 2", 
            status="completed",
            result={
                "metrics": {
                    "pipeline_1": {
                        "latency_ms": {"mean": 200.0},
                        "retrieval_score": {"mean": 0.85},
                        "success_rate": 0.95
                    }
                }
            },
            total_queries=10
        )
        
        db.add(benchmark1)
        db.add(benchmark2)
        await db.commit()
        await db.refresh(benchmark1)
        await db.refresh(benchmark2)
        
        response = await client.get(
            f"/api/v1/benchmarks/compare/{benchmark1.id}/{benchmark2.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "benchmark_1" in data
        assert "benchmark_2" in data
        assert "pipeline_comparison" in data
        assert "common_pipelines" in data
    
    async def test_upload_test_cases(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """테스트 케이스 업로드 테스트"""
        test_cases_data = {
            "test_cases": [
                {
                    "query_id": "tc_001",
                    "query": "What is machine learning?",
                    "query_type": "factual",
                    "expected_answer": "Machine learning is...",
                    "metadata": {"category": "ai"}
                },
                {
                    "query_id": "tc_002",
                    "query": "How does neural network work?",
                    "query_type": "explanatory",
                    "metadata": {"category": "ai", "difficulty": "intermediate"}
                }
            ]
        }
        
        response = await client.post(
            "/api/v1/benchmarks/test-cases",
            json=test_cases_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_cases"] == 2
        assert "cases" in data
        assert len(data["cases"]) <= 10  # 최대 10개만 반환
    
    async def test_generate_test_cases(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """테스트 케이스 자동 생성 테스트"""
        with patch("app.services.benchmark_service.benchmark_service") as mock_service:
            # 테스트 케이스 생성 모킹
            mock_test_cases = [
                {
                    "query_id": f"generated_{i}",
                    "query": f"Generated query {i}",
                    "query_type": "factual",
                    "metadata": {"auto_generated": True}
                } for i in range(3)
            ]
            mock_service.generate_test_cases.return_value = mock_test_cases
            
            response = await client.get(
                "/api/v1/benchmarks/test-cases/generate?num_cases=3&query_types=factual",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("query_id" in case for case in data)
        assert all("query" in case for case in data)
    
    async def test_benchmark_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db: AsyncSession
    ):
        """벤치마크 목록 페이지네이션 테스트"""
        # 여러 벤치마크 생성
        for i in range(5):
            benchmark = BenchmarkModel(
                name=f"Benchmark {i}",
                description=f"Test benchmark {i}",
                status="completed",
                config={"pipeline_ids": ["test"]},
                total_queries=10,
                created_by=test_user.id
            )
            db.add(benchmark)
        
        await db.commit()
        
        # 첫 번째 페이지 (2개씩)
        response = await client.get(
            "/api/v1/benchmarks/?skip=0&limit=2",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["skip"] == 0
        assert data["limit"] == 2
        assert data["total"] >= 5
        
        # 두 번째 페이지
        response = await client.get(
            "/api/v1/benchmarks/?skip=2&limit=2", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 2
        assert data["limit"] == 2
    
    async def test_benchmark_status_filter(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db: AsyncSession
    ):
        """벤치마크 상태별 필터링 테스트"""
        # 다양한 상태의 벤치마크 생성
        statuses = ["pending", "running", "completed", "failed"]
        
        for status in statuses:
            benchmark = BenchmarkModel(
                name=f"Benchmark {status}",
                status=status,
                config={"pipeline_ids": ["test"]},
                total_queries=10,
                created_by=test_user.id
            )
            db.add(benchmark)
        
        await db.commit()
        
        # 완료된 벤치마크만 조회
        response = await client.get(
            "/api/v1/benchmarks/?status=completed",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 모든 항목이 completed 상태인지 확인
        for item in data["items"]:
            assert item["status"] == "completed"
    
    async def test_unauthorized_access(
        self,
        client: AsyncClient,
        test_benchmark: BenchmarkModel
    ):
        """인증되지 않은 접근 테스트"""
        response = await client.get(f"/api/v1/benchmarks/{test_benchmark.id}")
        assert response.status_code == 401
    
    async def test_invalid_benchmark_config(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """잘못된 벤치마크 설정 테스트"""
        invalid_data = {
            "name": "",  # 빈 이름
            "pipeline_ids": [],  # 빈 파이프라인 리스트
            "iterations": 0,  # 잘못된 반복 횟수
            "timeout_seconds": 10  # 너무 짧은 타임아웃
        }
        
        response = await client.post(
            "/api/v1/benchmarks/",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error


class TestBenchmarkService:
    """벤치마크 서비스 단위 테스트"""
    
    @patch("app.services.benchmark_service.benchmark_service")
    async def test_benchmark_execution_flow(
        self,
        mock_service
    ):
        """벤치마크 실행 플로우 테스트"""
        from app.schemas.benchmark import BenchmarkConfig, QueryTestCase
        
        # 모킹 설정
        mock_config = BenchmarkConfig(
            pipeline_ids=["pipeline_1", "pipeline_2"],
            iterations=1,
            timeout_seconds=300,
            top_k=5
        )
        
        mock_test_cases = [
            QueryTestCase(
                query_id="test_1",
                query="Test query 1",
                query_type="factual"
            )
        ]
        
        # 벤치마크 서비스 실행 모킹
        from app.schemas.benchmark import BenchmarkResult
        mock_result = BenchmarkResult(
            benchmark_id="test_benchmark",
            config=mock_config,
            metrics={},
            comparisons=[],
            total_queries=1,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_seconds=10.0,
            status="completed"
        )
        
        mock_service.run_benchmark.return_value = mock_result
        
        # 벤치마크 실행
        result = await mock_service.run_benchmark(
            "test_benchmark",
            mock_config,
            mock_test_cases
        )
        
        # 결과 검증
        assert result.benchmark_id == "test_benchmark"
        assert result.status == "completed"
        assert result.total_queries == 1
        assert result.duration_seconds == 10.0
    
    async def test_test_case_generation(self):
        """테스트 케이스 생성 테스트"""
        from app.services.benchmark_service import benchmark_service
        
        # 테스트 케이스 생성
        test_cases = benchmark_service.generate_test_cases(
            num_cases=5,
            query_types=["factual", "analytical"]
        )
        
        assert len(test_cases) == 5
        assert all(case.query_id for case in test_cases)
        assert all(case.query for case in test_cases)
        assert all(case.query_type in ["factual", "analytical"] for case in test_cases)
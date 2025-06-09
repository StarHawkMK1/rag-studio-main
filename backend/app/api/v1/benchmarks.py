# rag-studio/backend/app/api/v1/benchmarks.py
"""
벤치마킹 API 엔드포인트

RAG 파이프라인 성능 벤치마킹 기능을 제공합니다.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.utils.logger import logger
from app.db.session import get_db
from app.services.benchmark_service import benchmark_service
from app.schemas.benchmark import (
    BenchmarkCreate,
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkListResponse,
    QueryTestCase,
    TestCaseUpload
)
from app.models.benchmark import Benchmark as BenchmarkModel
from app.core.dependencies import get_current_user

# API 라우터 생성
router = APIRouter(
    prefix="/benchmarks",
    tags=["benchmarks"],
    responses={
        404: {"description": "Benchmark not found"},
        500: {"description": "Internal server error"}
    }
)


@router.get("/", response_model=BenchmarkListResponse)
async def list_benchmarks(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> BenchmarkListResponse:
    """
    벤치마크 목록 조회
    
    Args:
        skip: 건너뛸 항목 수
        limit: 조회할 최대 항목 수
        status: 필터링할 상태
        db: 데이터베이스 세션
        
    Returns:
        BenchmarkListResponse: 벤치마크 목록
    """
    try:
        # 쿼리 구성
        query = db.query(BenchmarkModel)
        
        # 상태 필터 적용
        if status:
            query = query.filter(BenchmarkModel.status == status)
        
        # 최신순 정렬
        query = query.order_by(BenchmarkModel.created_at.desc())
        
        # 페이지네이션 적용
        query = query.offset(skip).limit(limit)
        
        # 쿼리 실행
        result = await db.execute(query)
        benchmarks = result.scalars().all()
        
        # 전체 개수 조회
        count_query = db.query(BenchmarkModel)
        if status:
            count_query = count_query.filter(BenchmarkModel.status == status)
        
        total_result = await db.execute(count_query.count())
        total_count = total_result.scalar()
        
        # 응답 구성
        items = []
        for benchmark in benchmarks:
            item = {
                "id": str(benchmark.id),
                "name": benchmark.name,
                "description": benchmark.description,
                "status": benchmark.status,
                "pipeline_count": len(benchmark.config.get("pipeline_ids", [])),
                "total_queries": benchmark.total_queries,
                "created_at": benchmark.created_at,
                "completed_at": benchmark.completed_at,
                "duration_seconds": benchmark.duration_seconds
            }
            items.append(item)
        
        return BenchmarkListResponse(
            items=items,
            total=total_count,
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"벤치마크 목록 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="벤치마크 목록 조회에 실패했습니다."
        )


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_benchmark(
    benchmark_data: BenchmarkCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    새 벤치마크 생성 및 실행
    
    Args:
        benchmark_data: 벤치마크 생성 데이터
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션
        current_user: 현재 사용자
        
    Returns:
        Dict[str, Any]: 생성된 벤치마크 정보
    """
    try:
        # 벤치마크 ID 생성
        benchmark_id = str(uuid.uuid4())
        
        # 벤치마크 설정 생성
        config = BenchmarkConfig(
            pipeline_ids=benchmark_data.pipeline_ids,
            test_case_ids=benchmark_data.test_case_ids,
            iterations=benchmark_data.iterations,
            warmup_queries=benchmark_data.warmup_queries,
            timeout_seconds=benchmark_data.timeout_seconds,
            top_k=benchmark_data.top_k,
            parallel_execution=benchmark_data.parallel_execution
        )
        
        # 테스트 케이스 생성 또는 로드
        if benchmark_data.auto_generate_cases:
            # 자동 생성
            test_cases = benchmark_service.generate_test_cases(
                num_cases=benchmark_data.num_test_cases or 50,
                query_types=benchmark_data.query_types
            )
        else:
            # 기존 테스트 케이스 로드
            test_cases = await _load_test_cases(
                benchmark_data.test_case_ids,
                db
            )
        
        # 데이터베이스 모델 생성
        db_benchmark = BenchmarkModel(
            id=benchmark_id,
            name=benchmark_data.name,
            description=benchmark_data.description,
            status="running",
            config=config.dict(),
            total_queries=len(test_cases) * len(benchmark_data.pipeline_ids),
            created_by=current_user.get("id") if current_user else None,
            created_at=datetime.utcnow()
        )
        
        # 데이터베이스 저장
        db.add(db_benchmark)
        await db.commit()
        
        # 백그라운드에서 벤치마크 실행
        background_tasks.add_task(
            _run_benchmark_task,
            benchmark_id,
            config,
            test_cases,
            db
        )
        
        logger.info(f"벤치마크 생성 및 실행 시작: {benchmark_id}")
        
        return {
            "id": benchmark_id,
            "name": benchmark_data.name,
            "status": "running",
            "message": "벤치마크가 백그라운드에서 실행 중입니다.",
            "pipeline_count": len(benchmark_data.pipeline_ids),
            "test_case_count": len(test_cases)
        }
        
    except Exception as e:
        logger.error(f"벤치마크 생성 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"벤치마크 생성에 실패했습니다: {str(e)}"
        )


@router.get("/{benchmark_id}", response_model=BenchmarkResult)
async def get_benchmark_result(
    benchmark_id: str,
    db: AsyncSession = Depends(get_db)
) -> BenchmarkResult:
    """
    벤치마크 결과 조회
    
    Args:
        benchmark_id: 벤치마크 ID
        db: 데이터베이스 세션
        
    Returns:
        BenchmarkResult: 벤치마크 결과
    """
    try:
        # 데이터베이스에서 조회
        result = await db.execute(
            db.query(BenchmarkModel).filter(BenchmarkModel.id == benchmark_id)
        )
        benchmark = result.scalar_one_or_none()
        
        if not benchmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"벤치마크를 찾을 수 없습니다: {benchmark_id}"
            )
        
        # 결과가 아직 없는 경우
        if not benchmark.result:
            return {
                "benchmark_id": benchmark_id,
                "status": benchmark.status,
                "message": "벤치마크가 아직 실행 중입니다.",
                "created_at": benchmark.created_at
            }
        
        # 결과 반환
        return BenchmarkResult(**benchmark.result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"벤치마크 결과 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="벤치마크 결과 조회에 실패했습니다."
        )


@router.get("/{benchmark_id}/export")
async def export_benchmark_result(
    benchmark_id: str,
    format: str = Query(default="json", enum=["json", "csv", "html"]),
    db: AsyncSession = Depends(get_db)
):
    """
    벤치마크 결과 내보내기
    
    Args:
        benchmark_id: 벤치마크 ID
        format: 출력 형식
        db: 데이터베이스 세션
        
    Returns:
        파일 응답
    """
    try:
        # 벤치마크 조회
        result = await db.execute(
            db.query(BenchmarkModel).filter(BenchmarkModel.id == benchmark_id)
        )
        benchmark = result.scalar_one_or_none()
        
        if not benchmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"벤치마크를 찾을 수 없습니다: {benchmark_id}"
            )
        
        if not benchmark.result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="벤치마크 결과가 아직 생성되지 않았습니다."
            )
        
        # 결과 객체 생성
        benchmark_result = BenchmarkResult(**benchmark.result)
        
        # 결과 내보내기
        exported_content = await benchmark_service.export_results(
            benchmark_result,
            format=format
        )
        
        # 파일명 생성
        filename = f"benchmark_{benchmark_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        # 응답 생성
        if format == "json":
            media_type = "application/json"
        elif format == "csv":
            media_type = "text/csv"
        elif format == "html":
            media_type = "text/html"
        
        return StreamingResponse(
            io.StringIO(exported_content),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"벤치마크 결과 내보내기 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="벤치마크 결과 내보내기에 실패했습니다."
        )


@router.post("/test-cases", response_model=Dict[str, Any])
async def upload_test_cases(
    test_case_data: TestCaseUpload,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    테스트 케이스 업로드
    
    Args:
        test_case_data: 테스트 케이스 데이터
        db: 데이터베이스 세션
        
    Returns:
        Dict[str, Any]: 업로드 결과
    """
    try:
        # 테스트 케이스 저장
        saved_cases = []
        
        for case in test_case_data.test_cases:
            # TODO: 데이터베이스에 테스트 케이스 저장
            saved_cases.append({
                "query_id": case.query_id,
                "query": case.query,
                "query_type": case.query_type
            })
        
        return {
            "message": "테스트 케이스가 성공적으로 업로드되었습니다.",
            "total_cases": len(saved_cases),
            "cases": saved_cases[:10]  # 처음 10개만 반환
        }
        
    except Exception as e:
        logger.error(f"테스트 케이스 업로드 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"테스트 케이스 업로드에 실패했습니다: {str(e)}"
        )


@router.get("/test-cases/generate", response_model=List[QueryTestCase])
async def generate_test_cases(
    num_cases: int = Query(default=50, ge=1, le=1000),
    query_types: Optional[List[str]] = Query(default=None)
) -> List[QueryTestCase]:
    """
    테스트 케이스 자동 생성
    
    Args:
        num_cases: 생성할 테스트 케이스 수
        query_types: 쿼리 유형 필터
        
    Returns:
        List[QueryTestCase]: 생성된 테스트 케이스
    """
    try:
        # 테스트 케이스 생성
        test_cases = benchmark_service.generate_test_cases(
            num_cases=num_cases,
            query_types=query_types
        )
        
        return test_cases
        
    except Exception as e:
        logger.error(f"테스트 케이스 생성 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"테스트 케이스 생성에 실패했습니다: {str(e)}"
        )


@router.delete("/{benchmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_benchmark(
    benchmark_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    벤치마크 삭제
    
    Args:
        benchmark_id: 벤치마크 ID
        db: 데이터베이스 세션
    """
    try:
        # 벤치마크 조회
        result = await db.execute(
            db.query(BenchmarkModel).filter(BenchmarkModel.id == benchmark_id)
        )
        benchmark = result.scalar_one_or_none()
        
        if not benchmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"벤치마크를 찾을 수 없습니다: {benchmark_id}"
            )
        
        # 실행 중인 벤치마크는 삭제 불가
        if benchmark.status == "running":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="실행 중인 벤치마크는 삭제할 수 없습니다."
            )
        
        # 데이터베이스에서 삭제
        await db.delete(benchmark)
        await db.commit()
        
        logger.info(f"벤치마크 삭제 완료: {benchmark_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"벤치마크 삭제 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="벤치마크 삭제에 실패했습니다."
        )


@router.get("/compare/{benchmark_id_1}/{benchmark_id_2}", response_model=Dict[str, Any])
async def compare_benchmarks(
    benchmark_id_1: str,
    benchmark_id_2: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    두 벤치마크 결과 비교
    
    Args:
        benchmark_id_1: 첫 번째 벤치마크 ID
        benchmark_id_2: 두 번째 벤치마크 ID
        db: 데이터베이스 세션
        
    Returns:
        Dict[str, Any]: 비교 결과
    """
    try:
        # 두 벤치마크 조회
        result1 = await db.execute(
            db.query(BenchmarkModel).filter(BenchmarkModel.id == benchmark_id_1)
        )
        benchmark1 = result1.scalar_one_or_none()
        
        result2 = await db.execute(
            db.query(BenchmarkModel).filter(BenchmarkModel.id == benchmark_id_2)
        )
        benchmark2 = result2.scalar_one_or_none()
        
        if not benchmark1 or not benchmark2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="하나 이상의 벤치마크를 찾을 수 없습니다."
            )
        
        if not benchmark1.result or not benchmark2.result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="두 벤치마크 모두 완료되어야 비교할 수 있습니다."
            )
        
        # 결과 비교
        comparison = {
            "benchmark_1": {
                "id": benchmark_id_1,
                "name": benchmark1.name,
                "total_queries": benchmark1.total_queries,
                "duration_seconds": benchmark1.duration_seconds
            },
            "benchmark_2": {
                "id": benchmark_id_2,
                "name": benchmark2.name,
                "total_queries": benchmark2.total_queries,
                "duration_seconds": benchmark2.duration_seconds
            },
            "pipeline_comparison": {}
        }
        
        # 공통 파이프라인 찾기
        pipelines1 = set(benchmark1.result.get("metrics", {}).keys())
        pipelines2 = set(benchmark2.result.get("metrics", {}).keys())
        common_pipelines = pipelines1.intersection(pipelines2)
        
        for pipeline_id in common_pipelines:
            metrics1 = benchmark1.result["metrics"][pipeline_id]
            metrics2 = benchmark2.result["metrics"][pipeline_id]
            
            comparison["pipeline_comparison"][pipeline_id] = {
                "latency_improvement": (
                    (metrics2["latency_ms"]["mean"] - metrics1["latency_ms"]["mean"]) 
                    / metrics1["latency_ms"]["mean"] * 100
                ),
                "retrieval_score_improvement": (
                    (metrics2["retrieval_score"]["mean"] - metrics1["retrieval_score"]["mean"]) 
                    / metrics1["retrieval_score"]["mean"] * 100
                ),
                "success_rate_difference": metrics2["success_rate"] - metrics1["success_rate"]
            }
        
        comparison["common_pipelines"] = list(common_pipelines)
        comparison["unique_to_benchmark_1"] = list(pipelines1 - pipelines2)
        comparison["unique_to_benchmark_2"] = list(pipelines2 - pipelines1)
        
        return comparison
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"벤치마크 비교 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="벤치마크 비교에 실패했습니다."
        )


# 헬퍼 함수들

async def _load_test_cases(
    test_case_ids: List[str],
    db: AsyncSession
) -> List[QueryTestCase]:
    """
    데이터베이스에서 테스트 케이스 로드
    
    임시 구현 - 실제로는 DB에서 조회해야 함
    """
    # TODO: 실제 데이터베이스 조회 구현
    test_cases = []
    
    for i, case_id in enumerate(test_case_ids):
        test_case = QueryTestCase(
            query_id=case_id,
            query=f"Sample query for test case {case_id}",
            query_type="factual",
            expected_answer=None,
            metadata={"loaded_from_db": True}
        )
        test_cases.append(test_case)
    
    return test_cases


async def _run_benchmark_task(
    benchmark_id: str,
    config: BenchmarkConfig,
    test_cases: List[QueryTestCase],
    db: AsyncSession
):
    """
    백그라운드에서 벤치마크 실행
    """
    try:
        logger.info(f"백그라운드 벤치마크 실행 시작: {benchmark_id}")
        
        # 벤치마크 실행
        result = await benchmark_service.run_benchmark(
            benchmark_id,
            config,
            test_cases
        )
        
        # 결과 저장
        benchmark_query = await db.execute(
            db.query(BenchmarkModel).filter(BenchmarkModel.id == benchmark_id)
        )
        benchmark = benchmark_query.scalar_one_or_none()
        
        if benchmark:
            benchmark.result = result.dict()
            benchmark.status = result.status
            benchmark.completed_at = result.end_time
            benchmark.duration_seconds = result.duration_seconds
            
            await db.commit()
            
            logger.info(f"벤치마크 완료 및 저장: {benchmark_id}")
        
    except Exception as e:
        logger.error(f"벤치마크 실행 중 오류: {str(e)}")
        
        # 오류 상태 업데이트
        try:
            benchmark_query = await db.execute(
                db.query(BenchmarkModel).filter(BenchmarkModel.id == benchmark_id)
            )
            benchmark = benchmark_query.scalar_one_or_none()
            
            if benchmark:
                benchmark.status = "failed"
                benchmark.error = str(e)
                await db.commit()
        except Exception as save_error:
            logger.error(f"벤치마크 오류 상태 저장 실패: {str(save_error)}")
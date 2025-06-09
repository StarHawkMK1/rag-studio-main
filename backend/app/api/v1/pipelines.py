# rag-studio/backend/app/api/v1/pipelines.py
"""
RAG 파이프라인 관리 API 엔드포인트

파이프라인 생성, 조회, 실행, 삭제 등의 기능을 제공합니다.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logger import logger
from app.db.session import get_db
from app.services.rag_executor import pipeline_manager, PipelineConfig, PipelineType
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineUpdate,
    PipelineResponse,
    PipelineListResponse,
    QueryInput,
    QueryResult,
    PipelineMetrics,
    PipelineStatus
)
from app.models.pipeline import Pipeline as PipelineModel
from app.core.dependencies import get_current_user

# API 라우터 생성
router = APIRouter(
    prefix="/pipelines",
    tags=["pipelines"],
    responses={
        404: {"description": "Pipeline not found"},
        500: {"description": "Internal server error"}
    }
)


@router.get("/", response_model=PipelineListResponse)
async def list_pipelines(
    skip: int = 0,
    limit: int = 100,
    pipeline_type: Optional[PipelineType] = None,
    status: Optional[PipelineStatus] = None,
    db: AsyncSession = Depends(get_db)
) -> PipelineListResponse:
    """
    파이프라인 목록 조회
    
    Args:
        skip: 건너뛸 항목 수 (페이지네이션)
        limit: 조회할 최대 항목 수
        pipeline_type: 필터링할 파이프라인 타입
        status: 필터링할 파이프라인 상태
        db: 데이터베이스 세션
        
    Returns:
        PipelineListResponse: 파이프라인 목록
    """
    try:
        # 쿼리 구성
        query = db.query(PipelineModel)
        
        # 필터 적용
        if pipeline_type:
            query = query.filter(PipelineModel.pipeline_type == pipeline_type)
        if status:
            query = query.filter(PipelineModel.status == status)
        
        # 페이지네이션 적용
        query = query.offset(skip).limit(limit)
        
        # 쿼리 실행
        result = await db.execute(query)
        pipelines = result.scalars().all()
        
        # 응답 데이터 구성
        pipeline_responses = []
        for pipeline in pipelines:
            # 메트릭 조회
            metrics = pipeline_manager.get_metrics(str(pipeline.id))
            
            # 파이프라인 응답 객체 생성
            response = PipelineResponse(
                id=str(pipeline.id),
                name=pipeline.name,
                description=pipeline.description,
                pipeline_type=pipeline.pipeline_type,
                status=pipeline.status,
                index_name=pipeline.index_name,
                config=pipeline.config,
                metrics=metrics,
                created_at=pipeline.created_at,
                updated_at=pipeline.updated_at,
                last_run=pipeline.last_run
            )
            pipeline_responses.append(response)
        
        # 전체 개수 조회
        count_query = db.query(PipelineModel)
        if pipeline_type:
            count_query = count_query.filter(PipelineModel.pipeline_type == pipeline_type)
        if status:
            count_query = count_query.filter(PipelineModel.status == status)
        
        total_result = await db.execute(count_query.count())
        total_count = total_result.scalar()
        
        # 목록 응답 생성
        list_response = PipelineListResponse(
            items=pipeline_responses,
            total=total_count,
            skip=skip,
            limit=limit
        )
        
        return list_response
        
    except Exception as e:
        logger.error(f"파이프라인 목록 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파이프라인 목록 조회에 실패했습니다."
        )


@router.post("/", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    pipeline_data: PipelineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)  # 인증 사용 시
) -> PipelineResponse:
    """
    새로운 파이프라인 생성
    
    Args:
        pipeline_data: 파이프라인 생성 데이터
        db: 데이터베이스 세션
        current_user: 현재 사용자 정보
        
    Returns:
        PipelineResponse: 생성된 파이프라인 정보
    """
    try:
        # 파이프라인 ID 생성
        pipeline_id = str(uuid.uuid4())
        
        # 데이터베이스 모델 생성
        db_pipeline = PipelineModel(
            id=pipeline_id,
            name=pipeline_data.name,
            description=pipeline_data.description,
            pipeline_type=pipeline_data.pipeline_type,
            status=PipelineStatus.INACTIVE,
            index_name=pipeline_data.index_name,
            config=pipeline_data.config.dict() if pipeline_data.config else {},
            created_by=current_user.get("id") if current_user else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # 데이터베이스에 저장
        db.add(db_pipeline)
        await db.commit()
        await db.refresh(db_pipeline)
        
        # 파이프라인 설정 객체 생성
        config = PipelineConfig(
            name=db_pipeline.name,
            pipeline_type=db_pipeline.pipeline_type,
            index_name=db_pipeline.index_name,
            **db_pipeline.config
        )
        
        # 파이프라인 인스턴스 생성 (캐싱)
        await pipeline_manager.get_pipeline(pipeline_id, config)
        
        # 응답 생성
        created_pipeline = PipelineResponse(
            id=pipeline_id,
            name=db_pipeline.name,
            description=db_pipeline.description,
            pipeline_type=db_pipeline.pipeline_type,
            status=db_pipeline.status,
            index_name=db_pipeline.index_name,
            config=db_pipeline.config,
            metrics=None,  # 새로 생성된 파이프라인은 메트릭이 없음
            created_at=db_pipeline.created_at,
            updated_at=db_pipeline.updated_at,
            last_run=None
        )
        
        logger.info(f"파이프라인 생성 완료: {pipeline_id} - {db_pipeline.name}")
        
        return created_pipeline
        
    except Exception as e:
        logger.error(f"파이프라인 생성 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"파이프라인 생성에 실패했습니다: {str(e)}"
        )


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db)
) -> PipelineResponse:
    """
    특정 파이프라인 조회
    
    Args:
        pipeline_id: 파이프라인 ID
        db: 데이터베이스 세션
        
    Returns:
        PipelineResponse: 파이프라인 정보
    """
    try:
        # 데이터베이스에서 조회
        result = await db.execute(
            db.query(PipelineModel).filter(PipelineModel.id == pipeline_id)
        )
        pipeline = result.scalar_one_or_none()
        
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"파이프라인을 찾을 수 없습니다: {pipeline_id}"
            )
        
        # 메트릭 조회
        metrics = pipeline_manager.get_metrics(pipeline_id)
        
        # 응답 생성
        pipeline_response = PipelineResponse(
            id=str(pipeline.id),
            name=pipeline.name,
            description=pipeline.description,
            pipeline_type=pipeline.pipeline_type,
            status=pipeline.status,
            index_name=pipeline.index_name,
            config=pipeline.config,
            metrics=metrics,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
            last_run=pipeline.last_run
        )
        
        return pipeline_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파이프라인 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파이프라인 조회에 실패했습니다."
        )


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    update_data: PipelineUpdate,
    db: AsyncSession = Depends(get_db)
) -> PipelineResponse:
    """
    파이프라인 정보 업데이트
    
    Args:
        pipeline_id: 파이프라인 ID
        update_data: 업데이트할 데이터
        db: 데이터베이스 세션
        
    Returns:
        PipelineResponse: 업데이트된 파이프라인 정보
    """
    try:
        # 기존 파이프라인 조회
        result = await db.execute(
            db.query(PipelineModel).filter(PipelineModel.id == pipeline_id)
        )
        pipeline = result.scalar_one_or_none()
        
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"파이프라인을 찾을 수 없습니다: {pipeline_id}"
            )
        
        # 업데이트 적용
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(pipeline, field, value)
        
        pipeline.updated_at = datetime.utcnow()
        
        # 데이터베이스 저장
        await db.commit()
        await db.refresh(pipeline)
        
        # 파이프라인 인스턴스가 캐시에 있으면 제거 (재생성 유도)
        if pipeline.status == PipelineStatus.INACTIVE:
            await pipeline_manager.remove_pipeline(pipeline_id)
        
        # 메트릭 조회
        metrics = pipeline_manager.get_metrics(pipeline_id)
        
        # 응답 생성
        updated_pipeline = PipelineResponse(
            id=str(pipeline.id),
            name=pipeline.name,
            description=pipeline.description,
            pipeline_type=pipeline.pipeline_type,
            status=pipeline.status,
            index_name=pipeline.index_name,
            config=pipeline.config,
            metrics=metrics,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
            last_run=pipeline.last_run
        )
        
        logger.info(f"파이프라인 업데이트 완료: {pipeline_id}")
        
        return updated_pipeline
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파이프라인 업데이트 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파이프라인 업데이트에 실패했습니다."
        )


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    파이프라인 삭제
    
    Args:
        pipeline_id: 파이프라인 ID
        db: 데이터베이스 세션
    """
    try:
        # 파이프라인 조회
        result = await db.execute(
            db.query(PipelineModel).filter(PipelineModel.id == pipeline_id)
        )
        pipeline = result.scalar_one_or_none()
        
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"파이프라인을 찾을 수 없습니다: {pipeline_id}"
            )
        
        # 실행 중인 파이프라인은 삭제 불가
        if pipeline.status == PipelineStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="실행 중인 파이프라인은 삭제할 수 없습니다."
            )
        
        # 캐시에서 제거
        await pipeline_manager.remove_pipeline(pipeline_id)
        
        # 데이터베이스에서 삭제
        await db.delete(pipeline)
        await db.commit()
        
        logger.info(f"파이프라인 삭제 완료: {pipeline_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파이프라인 삭제 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파이프라인 삭제에 실패했습니다."
        )


@router.post("/{pipeline_id}/execute", response_model=QueryResult)
async def execute_pipeline(
    pipeline_id: str,
    query: QueryInput,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> QueryResult:
    """
    파이프라인 실행 (쿼리 처리)
    
    Args:
        pipeline_id: 파이프라인 ID
        query: 실행할 쿼리
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션
        
    Returns:
        QueryResult: 쿼리 실행 결과
    """
    try:
        # 파이프라인 조회
        result = await db.execute(
            db.query(PipelineModel).filter(PipelineModel.id == pipeline_id)
        )
        pipeline = result.scalar_one_or_none()
        
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"파이프라인을 찾을 수 없습니다: {pipeline_id}"
            )
        
        # 파이프라인 상태 확인
        if pipeline.status != PipelineStatus.ACTIVE:
            # 비활성 상태면 활성화
            pipeline.status = PipelineStatus.ACTIVE
            await db.commit()
        
        # 파이프라인 설정 생성
        config = PipelineConfig(
            name=pipeline.name,
            pipeline_type=pipeline.pipeline_type,
            index_name=pipeline.index_name,
            **pipeline.config
        )
        
        # 파이프라인 인스턴스 가져오기 (캐시됨)
        pipeline_instance = await pipeline_manager.get_pipeline(pipeline_id, config)
        
        # 쿼리 ID 생성 (없는 경우)
        if not query.query_id:
            query.query_id = str(uuid.uuid4())
        
        # 쿼리 실행
        query_result = await pipeline_instance.process_query(query)
        
        # 백그라운드 작업: 마지막 실행 시간 업데이트
        async def update_last_run():
            pipeline.last_run = datetime.utcnow()
            await db.commit()
        
        background_tasks.add_task(update_last_run)
        
        logger.info(
            f"파이프라인 실행 완료: {pipeline_id} - "
            f"쿼리: {query.query_text[:50]}... - "
            f"지연시간: {query_result.latency_ms}ms"
        )
        
        return query_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파이프라인 실행 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"파이프라인 실행에 실패했습니다: {str(e)}"
        )


@router.get("/{pipeline_id}/metrics", response_model=PipelineMetrics)
async def get_pipeline_metrics(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db)
) -> PipelineMetrics:
    """
    파이프라인 메트릭 조회
    
    Args:
        pipeline_id: 파이프라인 ID
        db: 데이터베이스 세션
        
    Returns:
        PipelineMetrics: 파이프라인 성능 메트릭
    """
    try:
        # 파이프라인 존재 여부 확인
        result = await db.execute(
            db.query(PipelineModel).filter(PipelineModel.id == pipeline_id)
        )
        pipeline = result.scalar_one_or_none()
        
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"파이프라인을 찾을 수 없습니다: {pipeline_id}"
            )
        
        # 메트릭 조회
        metrics = pipeline_manager.get_metrics(pipeline_id)
        
        if not metrics:
            # 메트릭이 없는 경우 기본값 반환
            default_metrics = PipelineMetrics(
                total_queries=0,
                successful_queries=0,
                failed_queries=0,
                average_latency=0.0,
                average_retrieval_score=0.0
            )
            return default_metrics
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파이프라인 메트릭 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파이프라인 메트릭 조회에 실패했습니다."
        )


@router.post("/{pipeline_id}/activate", response_model=PipelineResponse)
async def activate_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db)
) -> PipelineResponse:
    """
    파이프라인 활성화
    
    Args:
        pipeline_id: 파이프라인 ID
        db: 데이터베이스 세션
        
    Returns:
        PipelineResponse: 활성화된 파이프라인 정보
    """
    try:
        # 파이프라인 조회
        result = await db.execute(
            db.query(PipelineModel).filter(PipelineModel.id == pipeline_id)
        )
        pipeline = result.scalar_one_or_none()
        
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"파이프라인을 찾을 수 없습니다: {pipeline_id}"
            )
        
        # 이미 활성화된 경우
        if pipeline.status == PipelineStatus.ACTIVE:
            logger.info(f"파이프라인이 이미 활성화되어 있습니다: {pipeline_id}")
        else:
            # 상태 변경
            pipeline.status = PipelineStatus.ACTIVE
            pipeline.updated_at = datetime.utcnow()
            await db.commit()
            
            logger.info(f"파이프라인 활성화 완료: {pipeline_id}")
        
        # 메트릭 조회
        metrics = pipeline_manager.get_metrics(pipeline_id)
        
        # 응답 생성
        activated_pipeline = PipelineResponse(
            id=str(pipeline.id),
            name=pipeline.name,
            description=pipeline.description,
            pipeline_type=pipeline.pipeline_type,
            status=pipeline.status,
            index_name=pipeline.index_name,
            config=pipeline.config,
            metrics=metrics,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
            last_run=pipeline.last_run
        )
        
        return activated_pipeline
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파이프라인 활성화 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파이프라인 활성화에 실패했습니다."
        )


@router.post("/{pipeline_id}/deactivate", response_model=PipelineResponse)
async def deactivate_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db)
) -> PipelineResponse:
    """
    파이프라인 비활성화
    
    Args:
        pipeline_id: 파이프라인 ID
        db: 데이터베이스 세션
        
    Returns:
        PipelineResponse: 비활성화된 파이프라인 정보
    """
    try:
        # 파이프라인 조회
        result = await db.execute(
            db.query(PipelineModel).filter(PipelineModel.id == pipeline_id)
        )
        pipeline = result.scalar_one_or_none()
        
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"파이프라인을 찾을 수 없습니다: {pipeline_id}"
            )
        
        # 이미 비활성화된 경우
        if pipeline.status == PipelineStatus.INACTIVE:
            logger.info(f"파이프라인이 이미 비활성화되어 있습니다: {pipeline_id}")
        else:
            # 상태 변경
            pipeline.status = PipelineStatus.INACTIVE
            pipeline.updated_at = datetime.utcnow()
            await db.commit()
            
            # 캐시에서 제거 (리소스 절약)
            await pipeline_manager.remove_pipeline(pipeline_id)
            
            logger.info(f"파이프라인 비활성화 완료: {pipeline_id}")
        
        # 응답 생성
        deactivated_pipeline = PipelineResponse(
            id=str(pipeline.id),
            name=pipeline.name,
            description=pipeline.description,
            pipeline_type=pipeline.pipeline_type,
            status=pipeline.status,
            index_name=pipeline.index_name,
            config=pipeline.config,
            metrics=None,  # 비활성화된 파이프라인은 메트릭이 없음
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
            last_run=pipeline.last_run
        )
        
        return deactivated_pipeline
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파이프라인 비활성화 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파이프라인 비활성화에 실패했습니다."
        )
# rag-studio/backend/app/api/v1/opensearch.py
"""
OpenSearch 클러스터 관리 API 엔드포인트

클러스터 상태, 인덱스 관리, 모델 관리 등의 기능을 제공합니다.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import aiofiles

from app.core.logger import logger
from app.services.opensearch_service import get_opensearch_service, OpenSearchService
from app.schemas.opensearch import (
    ClusterHealth,
    IndexConfig,
    IndexStats,
    IndexListResponse,
    DocumentInput,
    DocumentBulkUpload,
    SearchQuery,
    SearchResult,
    ModelInfo,
    PipelineInfo
)
from app.core.config import settings
from app.utils.file_parser import parse_document_file

# API 라우터 생성
router = APIRouter(
    prefix="/opensearch",
    tags=["opensearch"],
    responses={
        500: {"description": "OpenSearch connection error"}
    }
)


@router.get("/health", response_model=ClusterHealth)
async def get_cluster_health(
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> ClusterHealth:
    """
    OpenSearch 클러스터 상태 조회
    
    Returns:
        ClusterHealth: 클러스터 상태 정보
    """
    try:
        # 연결 확인
        connected = await opensearch.check_connection()
        if not connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenSearch 클러스터에 연결할 수 없습니다."
            )
        
        # 클러스터 상태 조회
        health = await opensearch.get_cluster_health()
        
        return health
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"클러스터 상태 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="클러스터 상태 조회에 실패했습니다."
        )


@router.get("/indices", response_model=IndexListResponse)
async def list_indices(
    pattern: Optional[str] = "*",
    include_system: bool = False,
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> IndexListResponse:
    """
    인덱스 목록 조회
    
    Args:
        pattern: 인덱스 이름 패턴 (와일드카드 지원)
        include_system: 시스템 인덱스 포함 여부
        
    Returns:
        IndexListResponse: 인덱스 목록
    """
    try:
        # 인덱스 목록 조회
        indices_response = await opensearch.client.indices.get(index=pattern)
        
        indices = []
        for index_name, index_info in indices_response.items():
            # 시스템 인덱스 필터링
            if not include_system and index_name.startswith("."):
                continue
            
            # 인덱스 통계 조회
            stats = await opensearch.get_index_stats(index_name)
            
            # 인덱스 정보 구성
            index_data = {
                "name": index_name,
                "status": "open" if index_info["settings"]["index"].get("blocks", {}).get("read_only", False) == False else "closed",
                "document_count": stats.document_count,
                "size_human": stats.size_human,
                "created_at": index_info["settings"]["index"].get("creation_date"),
                "number_of_shards": int(index_info["settings"]["index"]["number_of_shards"]),
                "number_of_replicas": int(index_info["settings"]["index"]["number_of_replicas"])
            }
            
            indices.append(index_data)
        
        # 응답 구성
        response = IndexListResponse(
            indices=indices,
            total=len(indices)
        )
        
        return response
        
    except Exception as e:
        logger.error(f"인덱스 목록 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="인덱스 목록 조회에 실패했습니다."
        )


@router.post("/indices", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_index(
    index_name: str,
    config: IndexConfig,
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> Dict[str, Any]:
    """
    새 인덱스 생성
    
    Args:
        index_name: 생성할 인덱스 이름
        config: 인덱스 설정
        
    Returns:
        Dict[str, Any]: 생성 결과
    """
    try:
        # 인덱스 생성
        result = await opensearch.create_index(index_name, config)
        
        return result
        
    except Exception as e:
        logger.error(f"인덱스 생성 중 오류: {str(e)}")
        
        # 이미 존재하는 인덱스인 경우
        if "resource_already_exists_exception" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"인덱스 '{index_name}'가 이미 존재합니다."
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"인덱스 생성에 실패했습니다: {str(e)}"
        )


@router.get("/indices/{index_name}", response_model=IndexStats)
async def get_index_stats(
    index_name: str,
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> IndexStats:
    """
    특정 인덱스 통계 조회
    
    Args:
        index_name: 인덱스 이름
        
    Returns:
        IndexStats: 인덱스 통계 정보
    """
    try:
        # 인덱스 통계 조회
        stats = await opensearch.get_index_stats(index_name)
        
        return stats
        
    except Exception as e:
        logger.error(f"인덱스 통계 조회 중 오류: {str(e)}")
        
        if "index_not_found_exception" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"인덱스 '{index_name}'를 찾을 수 없습니다."
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="인덱스 통계 조회에 실패했습니다."
        )


@router.delete("/indices/{index_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_index(
    index_name: str,
    opensearch: OpenSearchService = Depends(get_opensearch_service)
):
    """
    인덱스 삭제
    
    Args:
        index_name: 삭제할 인덱스 이름
    """
    try:
        # 인덱스 삭제
        response = await opensearch.client.indices.delete(index=index_name)
        
        if response.get("acknowledged"):
            logger.info(f"인덱스 '{index_name}' 삭제 완료")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="인덱스 삭제가 확인되지 않았습니다."
            )
        
    except Exception as e:
        logger.error(f"인덱스 삭제 중 오류: {str(e)}")
        
        if "index_not_found_exception" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"인덱스 '{index_name}'를 찾을 수 없습니다."
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="인덱스 삭제에 실패했습니다."
        )


@router.post("/indices/{index_name}/documents", response_model=Dict[str, Any])
async def index_documents(
    index_name: str,
    documents: List[DocumentInput],
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> Dict[str, Any]:
    """
    문서 색인
    
    Args:
        index_name: 대상 인덱스
        documents: 색인할 문서 리스트
        
    Returns:
        Dict[str, Any]: 색인 결과
    """
    try:
        # 문서 색인
        result = await opensearch.index_documents(index_name, documents)
        
        return result
        
    except Exception as e:
        logger.error(f"문서 색인 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문서 색인에 실패했습니다: {str(e)}"
        )


@router.post("/indices/{index_name}/upload", response_model=Dict[str, Any])
async def upload_documents(
    index_name: str,
    file: UploadFile = File(...),
    source: str = Form(default="upload"),
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> Dict[str, Any]:
    """
    파일 업로드를 통한 문서 색인
    
    Args:
        index_name: 대상 인덱스
        file: 업로드 파일
        source: 문서 출처
        
    Returns:
        Dict[str, Any]: 업로드 결과
    """
    try:
        # 파일 확장자 확인
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"지원하지 않는 파일 형식입니다. 허용된 형식: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
        
        # 파일 크기 확인
        file_size = 0
        temp_file_path = settings.UPLOAD_DIR / f"temp_{file.filename}"
        
        async with aiofiles.open(temp_file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB씩 읽기
                file_size += len(chunk)
                if file_size > settings.MAX_UPLOAD_SIZE:
                    await f.close()
                    temp_file_path.unlink()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"파일 크기가 너무 큽니다. 최대 크기: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
                    )
                await f.write(chunk)
        
        # 파일 파싱
        documents = await parse_document_file(temp_file_path, file_extension, source)
        
        # 임시 파일 삭제
        temp_file_path.unlink()
        
        # 문서 색인
        result = await opensearch.index_documents(index_name, documents)
        
        # 결과에 파일 정보 추가
        result["file_info"] = {
            "filename": file.filename,
            "size_bytes": file_size,
            "extension": file_extension,
            "source": source
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파일 업로드 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"파일 업로드에 실패했습니다: {str(e)}"
        )


@router.post("/search", response_model=SearchResult)
async def search_documents(
    query: SearchQuery,
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> SearchResult:
    """
    문서 검색
    
    Args:
        query: 검색 쿼리
        
    Returns:
        SearchResult: 검색 결과
    """
    try:
        # 검색 실행
        result = await opensearch.search(query.index_name, query)
        
        return result
        
    except Exception as e:
        logger.error(f"문서 검색 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문서 검색에 실패했습니다: {str(e)}"
        )


@router.get("/models", response_model=List[ModelInfo])
async def list_models(
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> List[ModelInfo]:
    """
    등록된 ML 모델 목록 조회
    
    Returns:
        List[ModelInfo]: 모델 목록
    """
    try:
        # ML 모델 목록 조회
        response = await opensearch.client.transport.perform_request(
            method="GET",
            url="/_plugins/_ml/models"
        )
        
        models = []
        for model_data in response.get("models", []):
            model_info = ModelInfo(
                id=model_data["model_id"],
                name=model_data["name"],
                type=model_data.get("model_type", "unknown"),
                status="loaded" if model_data.get("model_state") == "DEPLOYED" else "unloaded",
                version=model_data.get("model_version", "1.0"),
                created_at=model_data.get("created_time")
            )
            models.append(model_info)
        
        return models
        
    except Exception as e:
        logger.error(f"모델 목록 조회 중 오류: {str(e)}")
        
        # ML 플러그인이 설치되지 않은 경우
        if "404" in str(e):
            return []  # 빈 목록 반환
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="모델 목록 조회에 실패했습니다."
        )


@router.get("/pipelines", response_model=List[PipelineInfo])
async def list_opensearch_pipelines(
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> List[PipelineInfo]:
    """
    OpenSearch 인제스트 파이프라인 목록 조회
    
    Returns:
        List[PipelineInfo]: 파이프라인 목록
    """
    try:
        # 인제스트 파이프라인 목록 조회
        response = await opensearch.client.ingest.get_pipeline()
        
        pipelines = []
        for pipeline_id, pipeline_data in response.items():
            # 프로세서 수 계산
            processor_count = len(pipeline_data.get("processors", []))
            
            # 설명 추출
            description = pipeline_data.get("description", "No description")
            
            pipeline_info = PipelineInfo(
                id=pipeline_id,
                name=pipeline_id,  # OpenSearch는 ID를 이름으로 사용
                description=description,
                processor_count=processor_count,
                processors=pipeline_data.get("processors", [])
            )
            pipelines.append(pipeline_info)
        
        return pipelines
        
    except Exception as e:
        logger.error(f"파이프라인 목록 조회 중 오류: {str(e)}")
        
        # 파이프라인이 없는 경우
        if "404" in str(e):
            return []  # 빈 목록 반환
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파이프라인 목록 조회에 실패했습니다."
        )


@router.post("/reindex", response_model=Dict[str, Any])
async def reindex_data(
    source_index: str,
    target_index: str,
    create_target: bool = True,
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> Dict[str, Any]:
    """
    인덱스 재색인
    
    Args:
        source_index: 원본 인덱스
        target_index: 대상 인덱스
        create_target: 대상 인덱스 자동 생성 여부
        
    Returns:
        Dict[str, Any]: 재색인 결과
    """
    try:
        # 대상 인덱스 생성 (필요한 경우)
        if create_target:
            # 원본 인덱스 매핑 조회
            source_mapping = await opensearch.client.indices.get_mapping(index=source_index)
            source_settings = await opensearch.client.indices.get_settings(index=source_index)
            
            # 대상 인덱스 생성
            await opensearch.client.indices.create(
                index=target_index,
                body={
                    "mappings": source_mapping[source_index]["mappings"],
                    "settings": {
                        "number_of_shards": source_settings[source_index]["settings"]["index"]["number_of_shards"],
                        "number_of_replicas": source_settings[source_index]["settings"]["index"]["number_of_replicas"]
                    }
                }
            )
        
        # 재색인 실행
        response = await opensearch.client.reindex(
            body={
                "source": {"index": source_index},
                "dest": {"index": target_index}
            },
            wait_for_completion=False  # 비동기 실행
        )
        
        # 태스크 ID 반환
        task_id = response.get("task")
        
        result = {
            "task_id": task_id,
            "source_index": source_index,
            "target_index": target_index,
            "status": "started",
            "message": "재색인이 시작되었습니다. 태스크 ID를 사용하여 진행 상태를 확인하세요."
        }
        
        return result
        
    except Exception as e:
        logger.error(f"재색인 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"재색인에 실패했습니다: {str(e)}"
        )


@router.get("/tasks/{task_id}", response_model=Dict[str, Any])
async def get_task_status(
    task_id: str,
    opensearch: OpenSearchService = Depends(get_opensearch_service)
) -> Dict[str, Any]:
    """
    비동기 작업 상태 조회
    
    Args:
        task_id: 작업 ID
        
    Returns:
        Dict[str, Any]: 작업 상태
    """
    try:
        # 태스크 상태 조회
        response = await opensearch.client.tasks.get(task_id=task_id)
        
        task_info = response.get("task", {})
        status = task_info.get("status", {})
        
        result = {
            "task_id": task_id,
            "completed": response.get("completed", False),
            "description": task_info.get("description", ""),
            "start_time": task_info.get("start_time_in_millis"),
            "running_time": task_info.get("running_time_in_nanos"),
            "status": {
                "total": status.get("total", 0),
                "created": status.get("created", 0),
                "updated": status.get("updated", 0),
                "deleted": status.get("deleted", 0),
                "batches": status.get("batches", 0)
            }
        }
        
        # 오류가 있는 경우
        if "error" in response:
            result["error"] = response["error"]
        
        return result
        
    except Exception as e:
        logger.error(f"태스크 상태 조회 중 오류: {str(e)}")
        
        if "404" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"태스크 '{task_id}'를 찾을 수 없습니다."
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="태스크 상태 조회에 실패했습니다."
        )
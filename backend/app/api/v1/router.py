# rag-studio/backend/app/api/v1/router.py
"""
API 라우터 통합 모듈

모든 API 엔드포인트를 하나의 라우터로 통합합니다.
"""

from fastapi import APIRouter

from app.api.v1 import pipelines, opensearch, benchmarks, rag_builder, websocket, auth

# 메인 API 라우터 생성
api_router = APIRouter()

# 각 모듈의 라우터 포함
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)

api_router.include_router(
    pipelines.router,
    prefix="/pipelines",
    tags=["pipelines"]
)

api_router.include_router(
    opensearch.router,
    prefix="/opensearch",
    tags=["opensearch"]
)

api_router.include_router(
    benchmarks.router,
    prefix="/benchmarks",
    tags=["benchmarks"]
)

api_router.include_router(
    rag_builder.router,
    prefix="/rag-builder",
    tags=["rag-builder"]
)

api_router.include_router(
    websocket.router,
    prefix="/ws",
    tags=["websocket"]
)
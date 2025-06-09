# rag-studio/backend/main.py
"""
RAGStudio 백엔드 메인 애플리케이션 파일

이 파일은 FastAPI 애플리케이션의 진입점으로, 
모든 라우터를 통합하고 미들웨어를 설정합니다.
"""

import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import settings
from app.utils.logger import logger
from app.db.session import engine
from app.db.base import Base

# Prometheus 메트릭 정의
REQUEST_COUNT = Counter(
    'ragstudio_requests_total', 
    'Total number of requests',
    ['method', 'endpoint', 'status']
)
REQUEST_DURATION = Histogram(
    'ragstudio_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 생명주기 관리
    
    시작 시: 데이터베이스 테이블 생성 및 초기화
    종료 시: 리소스 정리
    """
    # 시작 시 실행
    logger.info("🚀 RAGStudio 백엔드 서버를 시작합니다...")
    
    # 데이터베이스 테이블 생성
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("✅ 데이터베이스 초기화 완료")
    
    yield
    
    # 종료 시 실행
    logger.info("🛑 RAGStudio 백엔드 서버를 종료합니다...")
    await engine.dispose()


# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="RAG 파이프라인 관리 플랫폼 API",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    lifespan=lifespan
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Next.js 프론트엔드 URL
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)


# 요청 처리 시간 측정 미들웨어
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """
    각 요청의 처리 시간을 측정하고 헤더에 추가
    Prometheus 메트릭도 함께 기록
    """
    start_time = time.time()
    
    # 요청 처리
    response = await call_next(request)
    
    # 처리 시간 계산
    process_time = time.time() - start_time
    
    # 응답 헤더에 처리 시간 추가
    response.headers["X-Process-Time"] = str(process_time)
    
    # Prometheus 메트릭 기록
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(process_time)
    
    return response


# 전역 예외 처리기
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    처리되지 않은 예외를 캐치하고 적절한 에러 응답 반환
    """
    logger.error(
        f"처리되지 않은 예외 발생: {exc}", 
        exc_info=True,
        extra={
            "request_method": request.method,
            "request_url": str(request.url),
            "client_host": request.client.host if request.client else None
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "내부 서버 오류가 발생했습니다.",
            "type": "internal_server_error"
        }
    )


# API 라우터 등록
app.include_router(api_router, prefix=settings.API_PREFIX)


# 루트 엔드포인트
@app.get("/", response_model=Dict[str, Any])
async def root():
    """
    API 루트 엔드포인트
    서버 상태 및 기본 정보 반환
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": f"{settings.API_PREFIX}/docs",
        "health": "/health"
    }


# 헬스체크 엔드포인트
@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """
    헬스체크 엔드포인트
    Kubernetes 및 로드밸런서에서 사용
    """
    # TODO: 데이터베이스, Redis, OpenSearch 연결 상태 확인 추가
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    }


# Prometheus 메트릭 엔드포인트
@app.get("/metrics")
async def metrics():
    """
    Prometheus 메트릭 엔드포인트
    모니터링 시스템에서 사용
    """
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )


if __name__ == "__main__":
    import uvicorn
    
    # 개발 서버 실행
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
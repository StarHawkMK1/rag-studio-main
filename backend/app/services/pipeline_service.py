# rag-studio/backend/app/services/pipeline_service.py
"""
파이프라인 관리 서비스

RAG 파이프라인의 생성, 관리, 실행 등을 담당하는 서비스입니다.
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.utils.logger import logger
from app.core.config import settings
from app.models.pipeline import Pipeline as PipelineModel
from app.models.rag_config import RAGConfiguration, PromptTemplate, LLMConfiguration
from app.schemas.pipeline import (
    PipelineCreate, 
    PipelineUpdate, 
    PipelineResponse, 
    PipelineType, 
    PipelineStatus,
    QueryInput,
    QueryResult,
    PipelineMetrics
)
from app.schemas.rag_config import RAGConfigurationCreate
from app.services.rag_executor import pipeline_manager, PipelineConfig
from app.services.langgraph_service import LangGraphRAGService
from app.services.opensearch_service import OpenSearchService


@dataclass
class PipelineValidationResult:
    """파이프라인 검증 결과"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]


@dataclass
class PipelineExecutionStats:
    """파이프라인 실행 통계"""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    avg_latency_ms: float = 0.0
    avg_retrieval_score: float = 0.0
    last_executed: Optional[datetime] = None


class PipelineService:
    """
    파이프라인 관리 서비스
    
    RAG 파이프라인의 전체 생명주기를 관리합니다.
    """
    
    def __init__(self):
        """서비스 초기화"""
        self.opensearch_service = OpenSearchService()
        self._execution_stats: Dict[str, PipelineExecutionStats] = {}
        self._active_pipelines: Dict[str, Any] = {}
        
        logger.info("파이프라인 서비스 초기화 완료")
    
    async def create_pipeline(
        self,
        pipeline_data: PipelineCreate,
        db: AsyncSession,
        user_id: Optional[str] = None
    ) -> PipelineResponse:
        """
        새 파이프라인 생성
        
        Args:
            pipeline_data: 파이프라인 생성 데이터
            db: 데이터베이스 세션
            user_id: 생성자 사용자 ID
            
        Returns:
            PipelineResponse: 생성된 파이프라인 정보
        """
        try:
            # 파이프라인 ID 생성
            pipeline_id = str(uuid.uuid4())
            
            # 인덱스 존재 확인
            await self._validate_index(pipeline_data.index_name)
            
            # 설정 검증
            validation_result = await self._validate_pipeline_config(pipeline_data)
            if not validation_result.is_valid:
                raise ValueError(f"파이프라인 설정 오류: {', '.join(validation_result.errors)}")
            
            # 데이터베이스 모델 생성
            db_pipeline = PipelineModel(
                id=pipeline_id,
                name=pipeline_data.name,
                description=pipeline_data.description,
                pipeline_type=pipeline_data.pipeline_type,
                status=PipelineStatus.INACTIVE,
                index_name=pipeline_data.index_name,
                config=pipeline_data.config.dict() if pipeline_data.config else {},
                created_by=user_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # 데이터베이스 저장
            db.add(db_pipeline)
            await db.commit()
            await db.refresh(db_pipeline)
            
            # 기본 RAG 설정 생성
            if pipeline_data.config:
                await self._create_default_rag_config(
                    pipeline_id, pipeline_data.config, db, user_id
                )
            
            # 실행 통계 초기화
            self._execution_stats[pipeline_id] = PipelineExecutionStats()
            
            # 응답 생성
            response = PipelineResponse(
                id=pipeline_id,
                name=db_pipeline.name,
                description=db_pipeline.description,
                pipeline_type=db_pipeline.pipeline_type,
                status=db_pipeline.status,
                index_name=db_pipeline.index_name,
                config=db_pipeline.config,
                metrics=PipelineMetrics(),
                created_at=db_pipeline.created_at,
                updated_at=db_pipeline.updated_at,
                last_run=None
            )
            
            logger.info(f"파이프라인 생성 완료: {pipeline_id} - {db_pipeline.name}")
            
            return response
            
        except Exception as e:
            logger.error(f"파이프라인 생성 실패: {str(e)}")
            raise
    
    async def get_pipeline(
        self,
        pipeline_id: str,
        db: AsyncSession
    ) -> Optional[PipelineResponse]:
        """
        파이프라인 조회
        
        Args:
            pipeline_id: 파이프라인 ID
            db: 데이터베이스 세션
            
        Returns:
            Optional[PipelineResponse]: 파이프라인 정보
        """
        try:
            # 데이터베이스에서 조회
            stmt = select(PipelineModel).where(PipelineModel.id == pipeline_id)
            result = await db.execute(stmt)
            pipeline = result.scalar_one_or_none()
            
            if not pipeline:
                return None
            
            # 메트릭 조회
            metrics = await self._get_pipeline_metrics(pipeline_id)
            
            # 응답 생성
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
            
            return response
            
        except Exception as e:
            logger.error(f"파이프라인 조회 실패: {str(e)}")
            raise
    
    async def update_pipeline(
        self,
        pipeline_id: str,
        update_data: PipelineUpdate,
        db: AsyncSession
    ) -> Optional[PipelineResponse]:
        """
        파이프라인 수정
        
        Args:
            pipeline_id: 파이프라인 ID
            update_data: 수정 데이터
            db: 데이터베이스 세션
            
        Returns:
            Optional[PipelineResponse]: 수정된 파이프라인 정보
        """
        try:
            # 기존 파이프라인 조회
            stmt = select(PipelineModel).where(PipelineModel.id == pipeline_id)
            result = await db.execute(stmt)
            pipeline = result.scalar_one_or_none()
            
            if not pipeline:
                return None
            
            # 수정 데이터 적용
            update_dict = update_data.dict(exclude_unset=True)
            
            for field, value in update_dict.items():
                if hasattr(pipeline, field):
                    setattr(pipeline, field, value)
            
            pipeline.updated_at = datetime.utcnow()
            
            # 설정 변경 시 검증
            if "config" in update_dict:
                validation_result = await self._validate_pipeline_config_dict(
                    update_dict["config"]
                )
                if not validation_result.is_valid:
                    raise ValueError(f"설정 오류: {', '.join(validation_result.errors)}")
            
            # 데이터베이스 저장
            await db.commit()
            await db.refresh(pipeline)
            
            # 활성 파이프라인이면 캐시에서 제거 (재생성 유도)
            if pipeline_id in self._active_pipelines:
                del self._active_pipelines[pipeline_id]
                await pipeline_manager.remove_pipeline(pipeline_id)
            
            # 메트릭 조회
            metrics = await self._get_pipeline_metrics(pipeline_id)
            
            # 응답 생성
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
            
            logger.info(f"파이프라인 수정 완료: {pipeline_id}")
            
            return response
            
        except Exception as e:
            logger.error(f"파이프라인 수정 실패: {str(e)}")
            raise
    
    async def delete_pipeline(
        self,
        pipeline_id: str,
        db: AsyncSession
    ) -> bool:
        """
        파이프라인 삭제
        
        Args:
            pipeline_id: 파이프라인 ID
            db: 데이터베이스 세션
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            # 파이프라인 조회
            stmt = select(PipelineModel).where(PipelineModel.id == pipeline_id)
            result = await db.execute(stmt)
            pipeline = result.scalar_one_or_none()
            
            if not pipeline:
                return False
            
            # 실행 중인 파이프라인은 삭제 불가
            if pipeline.status == PipelineStatus.ACTIVE:
                raise ValueError("실행 중인 파이프라인은 삭제할 수 없습니다.")
            
            # 관련 데이터 정리
            await self._cleanup_pipeline_data(pipeline_id, db)
            
            # 캐시에서 제거
            if pipeline_id in self._active_pipelines:
                del self._active_pipelines[pipeline_id]
            
            if pipeline_id in self._execution_stats:
                del self._execution_stats[pipeline_id]
            
            await pipeline_manager.remove_pipeline(pipeline_id)
            
            # 데이터베이스에서 삭제
            await db.delete(pipeline)
            await db.commit()
            
            logger.info(f"파이프라인 삭제 완료: {pipeline_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"파이프라인 삭제 실패: {str(e)}")
            raise
    
    async def execute_pipeline(
        self,
        pipeline_id: str,
        query: QueryInput,
        db: AsyncSession
    ) -> QueryResult:
        """
        파이프라인 실행
        
        Args:
            pipeline_id: 파이프라인 ID
            query: 실행할 쿼리
            db: 데이터베이스 세션
            
        Returns:
            QueryResult: 실행 결과
        """
        try:
            # 파이프라인 조회
            stmt = select(PipelineModel).where(PipelineModel.id == pipeline_id)
            result = await db.execute(stmt)
            pipeline = result.scalar_one_or_none()
            
            if not pipeline:
                raise ValueError(f"파이프라인을 찾을 수 없습니다: {pipeline_id}")
            
            # 파이프라인 활성화
            if pipeline.status != PipelineStatus.ACTIVE:
                pipeline.status = PipelineStatus.ACTIVE
                await db.commit()
            
            # 쿼리 ID 생성 (없는 경우)
            if not query.query_id:
                query.query_id = f"query_{int(datetime.utcnow().timestamp())}"
            
            # 파이프라인 타입별 실행
            if pipeline.pipeline_type == PipelineType.GRAPH_RAG:
                result = await self._execute_graph_rag(pipeline, query)
            else:
                result = await self._execute_naive_rag(pipeline, query)
            
            # 실행 통계 업데이트
            await self._update_execution_stats(pipeline_id, result)
            
            # 마지막 실행 시간 업데이트
            pipeline.last_run = datetime.utcnow()
            await db.commit()
            
            logger.info(f"파이프라인 실행 완료: {pipeline_id} - {result.latency_ms}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"파이프라인 실행 실패: {str(e)}")
            
            # 실행 통계 업데이트 (실패)
            if pipeline_id in self._execution_stats:
                self._execution_stats[pipeline_id].failed_queries += 1
            
            raise
    
    async def get_pipeline_templates(self) -> List[Dict[str, Any]]:
        """
        파이프라인 템플릿 목록 조회
        
        Returns:
            List[Dict[str, Any]]: 템플릿 목록
        """
        templates = [
            {
                "id": "basic_qa",
                "name": "기본 질의응답",
                "description": "간단한 질의응답을 위한 기본 RAG 파이프라인",
                "pipeline_type": "naive_rag",
                "category": "qa",
                "config": {
                    "retrieval_top_k": 5,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "search_filters": {}
                },
                "is_default": True
            },
            {
                "id": "complex_analysis",
                "name": "복잡한 분석",
                "description": "다단계 추론이 필요한 복잡한 질의를 위한 Graph RAG 파이프라인",
                "pipeline_type": "graph_rag",
                "category": "analysis",
                "config": {
                    "retrieval_top_k": 10,
                    "temperature": 0.5,
                    "max_tokens": 3000,
                    "use_llm_filtering": True,
                    "max_context_docs": 7
                },
                "is_default": False
            },
            {
                "id": "document_summary",
                "name": "문서 요약",
                "description": "문서 요약을 위한 특화된 RAG 파이프라인",
                "pipeline_type": "naive_rag",
                "category": "summarization",
                "config": {
                    "retrieval_top_k": 3,
                    "temperature": 0.3,
                    "max_tokens": 1500,
                    "search_filters": {}
                },
                "is_default": False
            }
        ]
        
        return templates
    
    async def create_from_template(
        self,
        template_id: str,
        name: str,
        index_name: str,
        db: AsyncSession,
        user_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> PipelineResponse:
        """
        템플릿으로부터 파이프라인 생성
        
        Args:
            template_id: 템플릿 ID
            name: 파이프라인 이름
            index_name: 인덱스 이름
            db: 데이터베이스 세션
            user_id: 사용자 ID
            description: 설명
            
        Returns:
            PipelineResponse: 생성된 파이프라인
        """
        try:
            # 템플릿 조회
            templates = await self.get_pipeline_templates()
            template = next((t for t in templates if t["id"] == template_id), None)
            
            if not template:
                raise ValueError(f"템플릿을 찾을 수 없습니다: {template_id}")
            
            # 파이프라인 생성 데이터 구성
            pipeline_data = PipelineCreate(
                name=name,
                description=description or template["description"],
                pipeline_type=PipelineType(template["pipeline_type"]),
                index_name=index_name,
                config=PipelineConfig(**template["config"])
            )
            
            # 파이프라인 생성
            pipeline = await self.create_pipeline(pipeline_data, db, user_id)
            
            logger.info(f"템플릿으로부터 파이프라인 생성: {template_id} -> {pipeline.id}")
            
            return pipeline
            
        except Exception as e:
            logger.error(f"템플릿 파이프라인 생성 실패: {str(e)}")
            raise
    
    async def validate_pipeline(
        self,
        pipeline_id: str,
        db: AsyncSession
    ) -> PipelineValidationResult:
        """
        파이프라인 검증
        
        Args:
            pipeline_id: 파이프라인 ID
            db: 데이터베이스 세션
            
        Returns:
            PipelineValidationResult: 검증 결과
        """
        try:
            # 파이프라인 조회
            stmt = select(PipelineModel).where(PipelineModel.id == pipeline_id)
            result = await db.execute(stmt)
            pipeline = result.scalar_one_or_none()
            
            if not pipeline:
                return PipelineValidationResult(
                    is_valid=False,
                    errors=["파이프라인을 찾을 수 없습니다."],
                    warnings=[],
                    suggestions=[]
                )
            
            errors = []
            warnings = []
            suggestions = []
            
            # 인덱스 검증
            try:
                await self._validate_index(pipeline.index_name)
            except Exception as e:
                errors.append(f"인덱스 오류: {str(e)}")
            
            # 설정 검증
            config_validation = await self._validate_pipeline_config_dict(pipeline.config)
            errors.extend(config_validation.errors)
            warnings.extend(config_validation.warnings)
            suggestions.extend(config_validation.suggestions)
            
            # LLM 설정 검증
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-openai-api-key":
                errors.append("OpenAI API 키가 설정되지 않았습니다.")
            
            # 성능 제안
            if pipeline.pipeline_type == PipelineType.NAIVE_RAG:
                config = pipeline.config
                if config.get("retrieval_top_k", 5) > 10:
                    warnings.append("검색 문서 수가 많아 응답 시간이 늘어날 수 있습니다.")
                
                if config.get("temperature", 0.7) > 1.5:
                    warnings.append("Temperature가 높아 응답 일관성이 떨어질 수 있습니다.")
            
            result = PipelineValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions
            )
            
            return result
            
        except Exception as e:
            logger.error(f"파이프라인 검증 실패: {str(e)}")
            return PipelineValidationResult(
                is_valid=False,
                errors=[f"검증 중 오류 발생: {str(e)}"],
                warnings=[],
                suggestions=[]
            )
    
    # 내부 헬퍼 메서드들
    
    async def _validate_index(self, index_name: str):
        """인덱스 존재 확인"""
        # OpenSearch 연결 확인
        connected = await self.opensearch_service.check_connection()
        if not connected:
            raise ValueError("OpenSearch에 연결할 수 없습니다.")
        
        # 인덱스 존재 확인
        try:
            await self.opensearch_service.get_index_stats(index_name)
        except Exception:
            raise ValueError(f"인덱스 '{index_name}'를 찾을 수 없습니다.")
    
    async def _validate_pipeline_config(
        self, 
        pipeline_data: PipelineCreate
    ) -> PipelineValidationResult:
        """파이프라인 설정 검증"""
        return await self._validate_pipeline_config_dict(
            pipeline_data.config.dict() if pipeline_data.config else {}
        )
    
    async def _validate_pipeline_config_dict(
        self, 
        config: Dict[str, Any]
    ) -> PipelineValidationResult:
        """파이프라인 설정 딕셔너리 검증"""
        errors = []
        warnings = []
        suggestions = []
        
        # 필수 설정 확인
        if not config:
            warnings.append("파이프라인 설정이 비어있습니다.")
            return PipelineValidationResult(True, errors, warnings, suggestions)
        
        # 검색 설정 검증
        top_k = config.get("retrieval_top_k", 5)
        if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
            errors.append("retrieval_top_k는 1-100 사이의 정수여야 합니다.")
        
        # LLM 설정 검증
        temperature = config.get("temperature", 0.7)
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            errors.append("temperature는 0-2 사이의 숫자여야 합니다.")
        
        max_tokens = config.get("max_tokens", 2000)
        if not isinstance(max_tokens, int) or max_tokens < 100 or max_tokens > 32000:
            errors.append("max_tokens는 100-32000 사이의 정수여야 합니다.")
        
        return PipelineValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    async def _create_default_rag_config(
        self,
        pipeline_id: str,
        config: PipelineConfig,
        db: AsyncSession,
        user_id: Optional[str]
    ):
        """기본 RAG 설정 생성"""
        try:
            # RAG 설정 생성
            rag_config = RAGConfiguration(
                name=f"Config for Pipeline {pipeline_id}",
                description="자동 생성된 기본 RAG 설정",
                version="1.0.0",
                pipeline_id=pipeline_id,
                retrieval_config={
                    "top_k": config.retrieval_top_k or 5,
                    "similarity_threshold": 0.7
                },
                generation_config={
                    "temperature": config.temperature or 0.7,
                    "max_tokens": config.max_tokens or 2000
                },
                created_by=user_id
            )
            
            db.add(rag_config)
            await db.commit()
            
        except Exception as e:
            logger.warning(f"기본 RAG 설정 생성 실패: {str(e)}")
    
    async def _cleanup_pipeline_data(self, pipeline_id: str, db: AsyncSession):
        """파이프라인 관련 데이터 정리"""
        try:
            # RAG 설정 삭제
            await db.execute(
                delete(RAGConfiguration).where(RAGConfiguration.pipeline_id == pipeline_id)
            )
            await db.commit()
            
        except Exception as e:
            logger.warning(f"파이프라인 데이터 정리 실패: {str(e)}")
    
    async def _get_pipeline_metrics(self, pipeline_id: str) -> PipelineMetrics:
        """파이프라인 메트릭 조회"""
        if pipeline_id in self._execution_stats:
            stats = self._execution_stats[pipeline_id]
            return PipelineMetrics(
                total_queries=stats.total_queries,
                successful_queries=stats.successful_queries,
                failed_queries=stats.failed_queries,
                average_latency=stats.avg_latency_ms,
                average_retrieval_score=stats.avg_retrieval_score
            )
        
        return PipelineMetrics()
    
    async def _execute_naive_rag(
        self, 
        pipeline: PipelineModel, 
        query: QueryInput
    ) -> QueryResult:
        """Naive RAG 실행"""
        config = PipelineConfig(
            name=pipeline.name,
            pipeline_type=pipeline.pipeline_type,
            index_name=pipeline.index_name,
            **pipeline.config
        )
        
        # 파이프라인 인스턴스 가져오기
        pipeline_instance = await pipeline_manager.get_pipeline(str(pipeline.id), config)
        
        # 쿼리 실행
        result = await pipeline_instance.process_query(query)
        
        return result
    
    async def _execute_graph_rag(
        self, 
        pipeline: PipelineModel, 
        query: QueryInput
    ) -> QueryResult:
        """Graph RAG 실행"""
        # LangGraph 서비스 생성
        graph_service = LangGraphRAGService(
            index_name=pipeline.index_name,
            config=pipeline.config
        )
        
        # 쿼리 실행
        result = await graph_service.process_query(query)
        
        return result
    
    async def _update_execution_stats(
        self, 
        pipeline_id: str, 
        result: QueryResult
    ):
        """실행 통계 업데이트"""
        if pipeline_id not in self._execution_stats:
            self._execution_stats[pipeline_id] = PipelineExecutionStats()
        
        stats = self._execution_stats[pipeline_id]
        
        # 통계 업데이트
        stats.total_queries += 1
        stats.last_executed = datetime.utcnow()
        
        if "error" not in result.metadata.get("status", ""):
            stats.successful_queries += 1
            
            # 평균 지연시간 계산
            if stats.avg_latency_ms == 0:
                stats.avg_latency_ms = result.latency_ms
            else:
                stats.avg_latency_ms = (
                    (stats.avg_latency_ms * (stats.successful_queries - 1) + result.latency_ms)
                    / stats.successful_queries
                )
            
            # 평균 검색 점수 계산
            if result.retrieved_documents:
                avg_score = sum(doc["score"] for doc in result.retrieved_documents) / len(result.retrieved_documents)
                if stats.avg_retrieval_score == 0:
                    stats.avg_retrieval_score = avg_score
                else:
                    stats.avg_retrieval_score = (
                        (stats.avg_retrieval_score * (stats.successful_queries - 1) + avg_score)
                        / stats.successful_queries
                    )


# 전역 파이프라인 서비스 인스턴스
pipeline_service = PipelineService()
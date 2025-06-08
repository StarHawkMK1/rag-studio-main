# rag-studio/backend/app/services/rag_executor.py
"""
RAG 파이프라인 실행 엔진 모듈

GraphRAG와 Naive RAG 파이프라인을 실행하고,
질의 응답 프로세스를 관리합니다.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from abc import ABC, abstractmethod

from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.schema import Document
from langchain.chains import RetrievalQA, LLMChain
from langchain.retrievers.base import BaseRetriever
from langgraph.graph import StateGraph, END

from app.core.config import settings
from app.core.logger import logger
from app.services.opensearch_service import OpenSearchService
from app.schemas.pipeline import (
    PipelineConfig, 
    PipelineType, 
    QueryInput, 
    QueryResult,
    PipelineMetrics
)


class BaseRAGPipeline(ABC):
    """
    RAG 파이프라인 기본 추상 클래스
    
    모든 RAG 파이프라인이 구현해야 할 인터페이스를 정의합니다.
    """
    
    def __init__(self, config: PipelineConfig):
        """
        파이프라인 초기화
        
        Args:
            config: 파이프라인 설정
        """
        self.config = config
        self.opensearch_service = OpenSearchService()
        
        # LLM 초기화
        self.llm = ChatOpenAI(
            model_name=settings.OPENAI_MODEL,
            temperature=config.temperature or settings.DEFAULT_TEMPERATURE,
            max_tokens=config.max_tokens or settings.MAX_TOKENS,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # 메트릭 초기화
        self.metrics = PipelineMetrics(
            total_queries=0,
            successful_queries=0,
            failed_queries=0,
            average_latency=0.0,
            average_retrieval_score=0.0
        )
    
    @abstractmethod
    async def process_query(self, query: QueryInput) -> QueryResult:
        """
        쿼리 처리 메서드 (하위 클래스에서 구현)
        
        Args:
            query: 입력 쿼리
            
        Returns:
            QueryResult: 처리 결과
        """
        pass
    
    async def retrieve_documents(
        self, 
        query_text: str, 
        top_k: int = None
    ) -> List[Document]:
        """
        관련 문서 검색
        
        Args:
            query_text: 검색 쿼리
            top_k: 검색할 문서 수
            
        Returns:
            List[Document]: 검색된 문서 리스트
        """
        # 검색 파라미터 설정
        search_top_k = top_k or self.config.retrieval_top_k or settings.TOP_K_RETRIEVAL
        
        # OpenSearch에서 문서 검색
        search_result = await self.opensearch_service.search(
            index_name=self.config.index_name,
            query={
                "query_text": query_text,
                "top_k": search_top_k,
                "filters": self.config.search_filters
            }
        )
        
        # LangChain Document 객체로 변환
        documents = []
        for hit in search_result.hits:
            doc = Document(
                page_content=hit["chunk_text"],
                metadata={
                    "document_id": hit["document_id"],
                    "title": hit["title"],
                    "chunk_index": hit["chunk_index"],
                    "score": hit["score"],
                    **hit.get("metadata", {})
                }
            )
            documents.append(doc)
        
        return documents
    
    def _calculate_metrics(self, latency: float, retrieval_scores: List[float]):
        """
        파이프라인 메트릭 업데이트
        
        Args:
            latency: 쿼리 처리 시간
            retrieval_scores: 검색 점수 리스트
        """
        # 쿼리 카운트 증가
        self.metrics.total_queries += 1
        
        # 평균 지연 시간 계산 (이동 평균)
        self.metrics.average_latency = (
            (self.metrics.average_latency * (self.metrics.total_queries - 1) + latency) 
            / self.metrics.total_queries
        )
        
        # 평균 검색 점수 계산
        if retrieval_scores:
            avg_score = sum(retrieval_scores) / len(retrieval_scores)
            self.metrics.average_retrieval_score = (
                (self.metrics.average_retrieval_score * (self.metrics.total_queries - 1) + avg_score)
                / self.metrics.total_queries
            )


class NaiveRAGPipeline(BaseRAGPipeline):
    """
    기본 RAG 파이프라인 구현
    
    단순한 검색-생성 방식의 RAG 파이프라인입니다.
    """
    
    def __init__(self, config: PipelineConfig):
        """
        Naive RAG 파이프라인 초기화
        
        Args:
            config: 파이프라인 설정
        """
        super().__init__(config)
        
        # 프롬프트 템플릿 초기화
        self.qa_prompt = ChatPromptTemplate.from_template(
            """다음 문맥을 참고하여 질문에 답변해주세요.

문맥:
{context}

질문: {question}

답변: 문맥에 기반하여 정확하고 도움이 되는 답변을 제공하겠습니다."""
        )
        
        logger.info(f"Naive RAG 파이프라인 '{config.name}' 초기화 완료")
    
    async def process_query(self, query: QueryInput) -> QueryResult:
        """
        Naive RAG 방식으로 쿼리 처리
        
        Args:
            query: 입력 쿼리
            
        Returns:
            QueryResult: 처리 결과
        """
        start_time = time.time()
        
        try:
            # 1. 문서 검색
            retrieved_docs = await self.retrieve_documents(
                query_text=query.query_text,
                top_k=query.top_k
            )
            
            if not retrieved_docs:
                # 검색 결과가 없는 경우
                no_result = QueryResult(
                    query_id=query.query_id,
                    query_text=query.query_text,
                    answer="죄송합니다. 관련된 정보를 찾을 수 없습니다.",
                    retrieved_documents=[],
                    latency_ms=int((time.time() - start_time) * 1000),
                    pipeline_type=PipelineType.NAIVE_RAG,
                    metadata={"status": "no_results"}
                )
                return no_result
            
            # 2. 컨텍스트 구성
            context_parts = []
            retrieval_scores = []
            
            for doc in retrieved_docs:
                # 문서 내용과 메타데이터 포맷팅
                doc_text = f"[문서: {doc.metadata.get('title', 'Unknown')}]\n{doc.page_content}"
                context_parts.append(doc_text)
                
                # 검색 점수 수집
                if 'score' in doc.metadata:
                    retrieval_scores.append(doc.metadata['score'])
            
            # 컨텍스트 결합
            combined_context = "\n\n---\n\n".join(context_parts)
            
            # 3. LLM을 사용한 답변 생성
            llm_input = self.qa_prompt.format_messages(
                context=combined_context,
                question=query.query_text
            )
            
            response = await self.llm.agenerate([llm_input])
            answer_text = response.generations[0][0].text.strip()
            
            # 4. 처리 시간 계산
            processing_time = time.time() - start_time
            latency_ms = int(processing_time * 1000)
            
            # 5. 메트릭 업데이트
            self._calculate_metrics(processing_time, retrieval_scores)
            self.metrics.successful_queries += 1
            
            # 6. 결과 구성
            query_result = QueryResult(
                query_id=query.query_id,
                query_text=query.query_text,
                answer=answer_text,
                retrieved_documents=[
                    {
                        "document_id": doc.metadata["document_id"],
                        "title": doc.metadata.get("title", ""),
                        "content": doc.page_content,
                        "score": doc.metadata.get("score", 0.0),
                        "metadata": doc.metadata
                    }
                    for doc in retrieved_docs
                ],
                latency_ms=latency_ms,
                pipeline_type=PipelineType.NAIVE_RAG,
                metadata={
                    "total_documents": len(retrieved_docs),
                    "average_score": sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0.0,
                    "model": settings.OPENAI_MODEL
                }
            )
            
            return query_result
            
        except Exception as e:
            # 오류 처리
            logger.error(f"Naive RAG 처리 중 오류 발생: {str(e)}")
            self.metrics.failed_queries += 1
            
            error_result = QueryResult(
                query_id=query.query_id,
                query_text=query.query_text,
                answer=f"처리 중 오류가 발생했습니다: {str(e)}",
                retrieved_documents=[],
                latency_ms=int((time.time() - start_time) * 1000),
                pipeline_type=PipelineType.NAIVE_RAG,
                metadata={"error": str(e), "status": "failed"}
            )
            
            return error_result


class GraphRAGPipeline(BaseRAGPipeline):
    """
    LangGraph 기반 고급 RAG 파이프라인 구현
    
    상태 그래프를 사용하여 복잡한 추론 과정을 수행하는 RAG 파이프라인입니다.
    """
    
    def __init__(self, config: PipelineConfig):
        """
        Graph RAG 파이프라인 초기화
        
        Args:
            config: 파이프라인 설정
        """
        super().__init__(config)
        
        # 상태 그래프 초기화
        self._build_graph()
        
        # 프롬프트 템플릿들 초기화
        self._init_prompts()
        
        logger.info(f"Graph RAG 파이프라인 '{config.name}' 초기화 완료")
    
    def _init_prompts(self):
        """프롬프트 템플릿 초기화"""
        # 쿼리 분석 프롬프트
        self.query_analysis_prompt = PromptTemplate(
            template="""주어진 질문을 분석하고 핵심 의도와 필요한 정보를 추출하세요.

질문: {query}

분석 결과:
1. 주요 의도:
2. 필요한 정보 유형:
3. 검색 키워드:"""
        )
        
        # 문서 재순위화 프롬프트
        self.reranking_prompt = PromptTemplate(
            template="""다음 문서들을 질문과의 관련성에 따라 평가하고 순위를 매기세요.

질문: {query}

문서들:
{documents}

각 문서의 관련성 점수(0-10)와 이유를 제시하세요."""
        )
        
        # 최종 답변 생성 프롬프트
        self.answer_generation_prompt = ChatPromptTemplate.from_template(
            """질문에 대해 제공된 문맥과 분석 결과를 종합하여 상세하고 정확한 답변을 작성하세요.

질문: {query}

분석된 의도: {intent}

관련 문서:
{context}

답변:"""
        )
    
    def _build_graph(self):
        """LangGraph 상태 그래프 구축"""
        # 상태 정의
        from typing import TypedDict
        
        class GraphState(TypedDict):
            """그래프 상태 정의"""
            query: str
            analyzed_query: Dict[str, Any]
            retrieved_docs: List[Document]
            reranked_docs: List[Document]
            answer: str
            metadata: Dict[str, Any]
        
        # 워크플로우 그래프 생성
        workflow = StateGraph(GraphState)
        
        # 노드 추가
        workflow.add_node("analyze_query", self._analyze_query_node)
        workflow.add_node("retrieve_documents", self._retrieve_documents_node)
        workflow.add_node("rerank_documents", self._rerank_documents_node)
        workflow.add_node("generate_answer", self._generate_answer_node)
        
        # 엣지 추가 (실행 순서 정의)
        workflow.set_entry_point("analyze_query")
        workflow.add_edge("analyze_query", "retrieve_documents")
        workflow.add_edge("retrieve_documents", "rerank_documents")
        workflow.add_edge("rerank_documents", "generate_answer")
        workflow.add_edge("generate_answer", END)
        
        # 그래프 컴파일
        self.graph = workflow.compile()
    
    async def _analyze_query_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """쿼리 분석 노드"""
        # 쿼리 분석 실행
        analysis_chain = LLMChain(llm=self.llm, prompt=self.query_analysis_prompt)
        analysis_result = await analysis_chain.arun(query=state["query"])
        
        # 분석 결과 파싱
        analyzed_query = {
            "original": state["query"],
            "analysis": analysis_result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        state["analyzed_query"] = analyzed_query
        return state
    
    async def _retrieve_documents_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """문서 검색 노드"""
        # 분석된 쿼리를 사용하여 문서 검색
        retrieved_docs = await self.retrieve_documents(
            query_text=state["query"],
            top_k=self.config.retrieval_top_k * 2  # 재순위화를 위해 더 많이 검색
        )
        
        state["retrieved_docs"] = retrieved_docs
        return state
    
    async def _rerank_documents_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """문서 재순위화 노드"""
        # 문서 재순위화 실행
        docs_text = "\n".join([
            f"문서 {i+1}: {doc.page_content[:200]}..."
            for i, doc in enumerate(state["retrieved_docs"][:10])
        ])
        
        rerank_chain = LLMChain(llm=self.llm, prompt=self.reranking_prompt)
        rerank_result = await rerank_chain.arun(
            query=state["query"],
            documents=docs_text
        )
        
        # 상위 K개 문서만 선택
        reranked_docs = state["retrieved_docs"][:self.config.retrieval_top_k]
        state["reranked_docs"] = reranked_docs
        
        return state
    
    async def _generate_answer_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """답변 생성 노드"""
        # 컨텍스트 구성
        context = "\n\n".join([
            f"[{doc.metadata.get('title', 'Document')}]\n{doc.page_content}"
            for doc in state["reranked_docs"]
        ])
        
        # 답변 생성
        answer_messages = self.answer_generation_prompt.format_messages(
            query=state["query"],
            intent=state["analyzed_query"]["analysis"],
            context=context
        )
        
        response = await self.llm.agenerate([answer_messages])
        answer = response.generations[0][0].text.strip()
        
        state["answer"] = answer
        return state
    
    async def process_query(self, query: QueryInput) -> QueryResult:
        """
        Graph RAG 방식으로 쿼리 처리
        
        Args:
            query: 입력 쿼리
            
        Returns:
            QueryResult: 처리 결과
        """
        start_time = time.time()
        
        try:
            # 초기 상태 설정
            initial_state = {
                "query": query.query_text,
                "analyzed_query": {},
                "retrieved_docs": [],
                "reranked_docs": [],
                "answer": "",
                "metadata": {"query_id": query.query_id}
            }
            
            # 그래프 실행
            final_state = await self.graph.ainvoke(initial_state)
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            latency_ms = int(processing_time * 1000)
            
            # 메트릭 업데이트
            retrieval_scores = [
                doc.metadata.get("score", 0.0) 
                for doc in final_state["reranked_docs"]
            ]
            self._calculate_metrics(processing_time, retrieval_scores)
            self.metrics.successful_queries += 1
            
            # 결과 구성
            query_result = QueryResult(
                query_id=query.query_id,
                query_text=query.query_text,
                answer=final_state["answer"],
                retrieved_documents=[
                    {
                        "document_id": doc.metadata["document_id"],
                        "title": doc.metadata.get("title", ""),
                        "content": doc.page_content,
                        "score": doc.metadata.get("score", 0.0),
                        "metadata": doc.metadata
                    }
                    for doc in final_state["reranked_docs"]
                ],
                latency_ms=latency_ms,
                pipeline_type=PipelineType.GRAPH_RAG,
                metadata={
                    "total_documents": len(final_state["retrieved_docs"]),
                    "reranked_documents": len(final_state["reranked_docs"]),
                    "query_analysis": final_state["analyzed_query"],
                    "model": settings.OPENAI_MODEL,
                    "graph_nodes_executed": 4
                }
            )
            
            return query_result
            
        except Exception as e:
            # 오류 처리
            logger.error(f"Graph RAG 처리 중 오류 발생: {str(e)}")
            self.metrics.failed_queries += 1
            
            error_result = QueryResult(
                query_id=query.query_id,
                query_text=query.query_text,
                answer=f"처리 중 오류가 발생했습니다: {str(e)}",
                retrieved_documents=[],
                latency_ms=int((time.time() - start_time) * 1000),
                pipeline_type=PipelineType.GRAPH_RAG,
                metadata={"error": str(e), "status": "failed"}
            )
            
            return error_result


class RAGPipelineFactory:
    """
    RAG 파이프라인 팩토리 클래스
    
    파이프라인 타입에 따라 적절한 구현체를 생성합니다.
    """
    
    @staticmethod
    def create_pipeline(config: PipelineConfig) -> BaseRAGPipeline:
        """
        파이프라인 생성
        
        Args:
            config: 파이프라인 설정
            
        Returns:
            BaseRAGPipeline: 생성된 파이프라인 인스턴스
            
        Raises:
            ValueError: 지원하지 않는 파이프라인 타입인 경우
        """
        if config.pipeline_type == PipelineType.NAIVE_RAG:
            pipeline = NaiveRAGPipeline(config)
            return pipeline
            
        elif config.pipeline_type == PipelineType.GRAPH_RAG:
            pipeline = GraphRAGPipeline(config)
            return pipeline
            
        else:
            raise ValueError(f"지원하지 않는 파이프라인 타입: {config.pipeline_type}")


# 파이프라인 관리자 (싱글톤)
class PipelineManager:
    """
    파이프라인 생명주기 관리 클래스
    
    파이프라인 인스턴스를 캐싱하고 관리합니다.
    """
    
    def __init__(self):
        """파이프라인 관리자 초기화"""
        self._pipelines: Dict[str, BaseRAGPipeline] = {}
        self._lock = asyncio.Lock()
    
    async def get_pipeline(self, pipeline_id: str, config: PipelineConfig) -> BaseRAGPipeline:
        """
        파이프라인 인스턴스 조회 또는 생성
        
        Args:
            pipeline_id: 파이프라인 ID
            config: 파이프라인 설정
            
        Returns:
            BaseRAGPipeline: 파이프라인 인스턴스
        """
        async with self._lock:
            # 캐시에서 조회
            if pipeline_id in self._pipelines:
                cached_pipeline = self._pipelines[pipeline_id]
                return cached_pipeline
            
            # 새로운 파이프라인 생성
            new_pipeline = RAGPipelineFactory.create_pipeline(config)
            self._pipelines[pipeline_id] = new_pipeline
            
            logger.info(f"새로운 파이프라인 생성: {pipeline_id} ({config.pipeline_type})")
            
            return new_pipeline
    
    async def remove_pipeline(self, pipeline_id: str):
        """
        파이프라인 제거
        
        Args:
            pipeline_id: 제거할 파이프라인 ID
        """
        async with self._lock:
            if pipeline_id in self._pipelines:
                # OpenSearch 연결 종료
                pipeline = self._pipelines[pipeline_id]
                await pipeline.opensearch_service.close()
                
                # 캐시에서 제거
                del self._pipelines[pipeline_id]
                
                logger.info(f"파이프라인 제거: {pipeline_id}")
    
    def get_metrics(self, pipeline_id: str) -> Optional[PipelineMetrics]:
        """
        파이프라인 메트릭 조회
        
        Args:
            pipeline_id: 파이프라인 ID
            
        Returns:
            Optional[PipelineMetrics]: 메트릭 정보
        """
        if pipeline_id in self._pipelines:
            pipeline = self._pipelines[pipeline_id]
            metrics = pipeline.metrics
            return metrics
        
        return None


# 전역 파이프라인 관리자 인스턴스
pipeline_manager = PipelineManager()
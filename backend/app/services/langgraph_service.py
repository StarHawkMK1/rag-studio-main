# rag-studio/backend/app/services/langgraph_service.py
"""
LangGraph 기반 복잡한 RAG 파이프라인 서비스

LangGraph를 사용하여 상태 그래프 기반의 고급 RAG 파이프라인을 구현합니다.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Literal
from datetime import datetime
from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain.schema import Document, BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.tools import Tool
from langchain.schema.runnable import RunnableConfig

from app.core.config import settings
from app.utils.logger import logger
from app.services.opensearch_service import OpenSearchService
from app.schemas.pipeline import QueryInput, QueryResult


class GraphState(TypedDict):
    """그래프 상태 정의"""
    # 입력 정보
    query: str
    query_id: str
    
    # 분석 결과
    query_analysis: Dict[str, Any]
    query_intent: str
    query_complexity: str
    
    # 검색 관련
    search_queries: List[str]
    retrieved_documents: List[Document]
    filtered_documents: List[Document]
    reranked_documents: List[Document]
    
    # 생성 관련
    context: str
    initial_response: str
    refined_response: str
    final_answer: str
    
    # 메타데이터
    messages: Annotated[List[BaseMessage], add_messages]
    metadata: Dict[str, Any]
    execution_path: List[str]
    
    # 제어 플래그
    needs_clarification: bool
    needs_multiple_queries: bool
    needs_refinement: bool
    is_complete: bool


@dataclass
class NodeExecutionResult:
    """노드 실행 결과"""
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: int = 0
    metadata: Dict[str, Any] = None


class LangGraphRAGService:
    """
    LangGraph 기반 고급 RAG 서비스
    
    복잡한 질의를 처리하기 위한 다단계 추론과 검색을 수행합니다.
    """
    
    def __init__(self, index_name: str, config: Dict[str, Any] = None):
        """
        서비스 초기화
        
        Args:
            index_name: OpenSearch 인덱스 이름
            config: 파이프라인 설정
        """
        self.index_name = index_name
        self.config = config or {}
        
        # 서비스 초기화
        self.opensearch_service = OpenSearchService()
        self.llm = ChatOpenAI(
            model_name=self.config.get("model", settings.OPENAI_MODEL),
            temperature=self.config.get("temperature", 0.7),
            max_tokens=self.config.get("max_tokens", 2000),
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # 프롬프트 템플릿 초기화
        self._init_prompts()
        
        # 그래프 구축
        self.graph = self._build_graph()
        
        logger.info(f"LangGraph RAG 서비스 초기화 완료: {index_name}")
    
    def _init_prompts(self):
        """프롬프트 템플릿 초기화"""
        # 쿼리 분석 프롬프트
        self.query_analysis_prompt = PromptTemplate(
            template="""다음 질문을 분석하고 구조화된 정보를 추출하세요.

질문: {query}

다음 형식으로 분석 결과를 JSON으로 반환하세요:
{{
    "intent": "질문의 주요 의도 (factual/analytical/comparative/procedural)",
    "complexity": "질문의 복잡도 (simple/medium/complex)",
    "entities": ["추출된 핵심 엔티티들"],
    "keywords": ["검색에 사용할 키워드들"],
    "requires_multiple_steps": "다단계 처리가 필요한지 (true/false)",
    "clarification_needed": "명확화가 필요한지 (true/false)",
    "suggested_queries": ["세분화된 검색 쿼리들"]
}}""",
            input_variables=["query"]
        )
        
        # 쿼리 재작성 프롬프트
        self.query_rewrite_prompt = PromptTemplate(
            template="""원본 질문을 더 효과적인 검색을 위해 재작성하세요.

원본 질문: {original_query}
분석 결과: {analysis}

다음 원칙에 따라 1-3개의 검색 쿼리로 재작성하세요:
1. 핵심 키워드 포함
2. 구체적이고 명확한 표현
3. 검색에 최적화된 형태

재작성된 쿼리들:""",
            input_variables=["original_query", "analysis"]
        )
        
        # 문서 관련성 평가 프롬프트
        self.relevance_prompt = PromptTemplate(
            template="""다음 문서가 주어진 질문과 얼마나 관련이 있는지 평가하세요.

질문: {query}

문서:
제목: {title}
내용: {content}

0-10 점수로 관련성을 평가하고, 이유를 설명하세요.
점수가 7 미만이면 해당 문서는 제외됩니다.

평가 결과:
점수: [0-10]
이유: [평가 이유]""",
            input_variables=["query", "title", "content"]
        )
        
        # 답변 생성 프롬프트
        self.answer_generation_prompt = ChatPromptTemplate.from_template(
            """질문에 대해 제공된 문맥을 바탕으로 정확하고 도움이 되는 답변을 작성하세요.

질문: {query}

분석된 의도: {intent}

관련 문서들:
{context}

답변 작성 지침:
1. 문맥에 기반한 정확한 정보 제공
2. 논리적이고 구조화된 설명
3. 필요시 단계별 설명
4. 불확실한 정보는 명시

답변:"""
        )
        
        # 답변 개선 프롬프트
        self.refinement_prompt = PromptTemplate(
            template="""다음 답변을 개선하세요.

원본 질문: {query}
초기 답변: {initial_answer}
추가 컨텍스트: {additional_context}

개선 사항:
1. 정확성 검토
2. 완성도 향상
3. 명확성 개선
4. 누락된 중요 정보 추가

개선된 답변:""",
            input_variables=["query", "initial_answer", "additional_context"]
        )
    
    def _build_graph(self) -> StateGraph:
        """LangGraph 상태 그래프 구축"""
        # 워크플로우 그래프 생성
        workflow = StateGraph(GraphState)
        
        # 노드 추가
        workflow.add_node("analyze_query", self._analyze_query_node)
        workflow.add_node("rewrite_queries", self._rewrite_queries_node)
        workflow.add_node("retrieve_documents", self._retrieve_documents_node)
        workflow.add_node("filter_documents", self._filter_documents_node)
        workflow.add_node("rerank_documents", self._rerank_documents_node)
        workflow.add_node("generate_initial_answer", self._generate_initial_answer_node)
        workflow.add_node("refine_answer", self._refine_answer_node)
        workflow.add_node("finalize_answer", self._finalize_answer_node)
        
        # 조건부 라우팅을 위한 노드
        workflow.add_node("route_complexity", self._route_complexity_node)
        workflow.add_node("check_quality", self._check_quality_node)
        
        # 엣지 정의
        workflow.set_entry_point("analyze_query")
        
        # 기본 플로우
        workflow.add_edge("analyze_query", "route_complexity")
        
        # 복잡도에 따른 라우팅
        workflow.add_conditional_edges(
            "route_complexity",
            self._should_use_multiple_queries,
            {
                "simple": "retrieve_documents",
                "complex": "rewrite_queries"
            }
        )
        
        workflow.add_edge("rewrite_queries", "retrieve_documents")
        workflow.add_edge("retrieve_documents", "filter_documents")
        workflow.add_edge("filter_documents", "rerank_documents")
        workflow.add_edge("rerank_documents", "generate_initial_answer")
        workflow.add_edge("generate_initial_answer", "check_quality")
        
        # 품질 검사 후 라우팅
        workflow.add_conditional_edges(
            "check_quality",
            self._should_refine_answer,
            {
                "refine": "refine_answer",
                "finalize": "finalize_answer"
            }
        )
        
        workflow.add_edge("refine_answer", "finalize_answer")
        workflow.add_edge("finalize_answer", END)
        
        # 그래프 컴파일
        return workflow.compile()
    
    async def process_query(self, query_input: QueryInput) -> QueryResult:
        """
        쿼리 처리 메인 함수
        
        Args:
            query_input: 입력 쿼리
            
        Returns:
            QueryResult: 처리 결과
        """
        start_time = datetime.utcnow()
        
        try:
            # 초기 상태 설정
            initial_state = GraphState(
                query=query_input.query_text,
                query_id=query_input.query_id or f"query_{int(datetime.utcnow().timestamp())}",
                query_analysis={},
                query_intent="",
                query_complexity="",
                search_queries=[],
                retrieved_documents=[],
                filtered_documents=[],
                reranked_documents=[],
                context="",
                initial_response="",
                refined_response="",
                final_answer="",
                messages=[HumanMessage(content=query_input.query_text)],
                metadata={"start_time": start_time.isoformat()},
                execution_path=[],
                needs_clarification=False,
                needs_multiple_queries=False,
                needs_refinement=False,
                is_complete=False
            )
            
            # 그래프 실행
            final_state = await self.graph.ainvoke(initial_state)
            
            # 처리 시간 계산
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            latency_ms = int(processing_time * 1000)
            
            # 결과 구성
            result = QueryResult(
                query_id=final_state["query_id"],
                query_text=final_state["query"],
                answer=final_state["final_answer"],
                retrieved_documents=[
                    {
                        "document_id": doc.metadata.get("document_id", "unknown"),
                        "title": doc.metadata.get("title", ""),
                        "content": doc.page_content,
                        "score": doc.metadata.get("score", 0.0),
                        "metadata": doc.metadata
                    }
                    for doc in final_state["reranked_documents"]
                ],
                latency_ms=latency_ms,
                pipeline_type="graph_rag",
                metadata={
                    "execution_path": final_state["execution_path"],
                    "query_analysis": final_state["query_analysis"],
                    "search_queries": final_state["search_queries"],
                    "total_documents_retrieved": len(final_state["retrieved_documents"]),
                    "documents_after_filtering": len(final_state["filtered_documents"]),
                    "final_documents_used": len(final_state["reranked_documents"]),
                    "refinement_applied": final_state["needs_refinement"],
                    "processing_time_seconds": processing_time
                }
            )
            
            logger.info(f"LangGraph 쿼리 처리 완료: {query_input.query_id}, 소요시간: {latency_ms}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"LangGraph 쿼리 처리 실패: {str(e)}")
            
            # 오류 결과 반환
            error_result = QueryResult(
                query_id=query_input.query_id or "error_query",
                query_text=query_input.query_text,
                answer=f"처리 중 오류가 발생했습니다: {str(e)}",
                retrieved_documents=[],
                latency_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                pipeline_type="graph_rag",
                metadata={"error": str(e), "status": "failed"}
            )
            
            return error_result
    
    # 노드 구현 함수들
    
    async def _analyze_query_node(self, state: GraphState) -> GraphState:
        """쿼리 분석 노드"""
        try:
            state["execution_path"].append("analyze_query")
            
            # LLM을 사용한 쿼리 분석
            analysis_result = await self.llm.apredict(
                self.query_analysis_prompt.format(query=state["query"])
            )
            
            # JSON 파싱
            try:
                analysis = json.loads(analysis_result)
            except:
                # 파싱 실패 시 기본값 사용
                analysis = {
                    "intent": "factual",
                    "complexity": "medium",
                    "entities": [],
                    "keywords": [state["query"]],
                    "requires_multiple_steps": False,
                    "clarification_needed": False,
                    "suggested_queries": [state["query"]]
                }
            
            state["query_analysis"] = analysis
            state["query_intent"] = analysis.get("intent", "factual")
            state["query_complexity"] = analysis.get("complexity", "medium")
            state["needs_multiple_queries"] = analysis.get("requires_multiple_steps", False)
            state["needs_clarification"] = analysis.get("clarification_needed", False)
            
            logger.info(f"쿼리 분석 완료: {state['query_complexity']} 복잡도, {state['query_intent']} 의도")
            
        except Exception as e:
            logger.error(f"쿼리 분석 실패: {str(e)}")
            # 기본값으로 처리 계속
            state["query_analysis"] = {"intent": "factual", "complexity": "simple"}
            state["query_intent"] = "factual"
            state["query_complexity"] = "simple"
        
        return state
    
    async def _rewrite_queries_node(self, state: GraphState) -> GraphState:
        """쿼리 재작성 노드"""
        try:
            state["execution_path"].append("rewrite_queries")
            
            # 복잡한 쿼리를 여러 개의 간단한 쿼리로 분해
            rewrite_result = await self.llm.apredict(
                self.query_rewrite_prompt.format(
                    original_query=state["query"],
                    analysis=json.dumps(state["query_analysis"], ensure_ascii=False)
                )
            )
            
            # 재작성된 쿼리들 추출
            queries = []
            for line in rewrite_result.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and len(line) > 10:
                    # 번호나 특수문자 제거
                    cleaned = line.lstrip('0123456789.- ')
                    if cleaned:
                        queries.append(cleaned)
            
            # 최소 1개, 최대 3개의 쿼리 유지
            if not queries:
                queries = [state["query"]]
            elif len(queries) > 3:
                queries = queries[:3]
            
            state["search_queries"] = queries
            
            logger.info(f"쿼리 재작성 완료: {len(queries)}개 쿼리 생성")
            
        except Exception as e:
            logger.error(f"쿼리 재작성 실패: {str(e)}")
            state["search_queries"] = [state["query"]]
        
        return state
    
    async def _retrieve_documents_node(self, state: GraphState) -> GraphState:
        """문서 검색 노드"""
        try:
            state["execution_path"].append("retrieve_documents")
            
            all_documents = []
            
            # 검색 쿼리가 없으면 원본 쿼리 사용
            if not state["search_queries"]:
                state["search_queries"] = [state["query"]]
            
            # 각 검색 쿼리에 대해 문서 검색
            for search_query in state["search_queries"]:
                try:
                    search_result = await self.opensearch_service.search(
                        index_name=self.index_name,
                        query={
                            "query_text": search_query,
                            "top_k": self.config.get("retrieval_top_k", 10),
                            "filters": self.config.get("search_filters", {})
                        }
                    )
                    
                    # LangChain Document 객체로 변환
                    for hit in search_result.hits:
                        doc = Document(
                            page_content=hit["chunk_text"],
                            metadata={
                                "document_id": hit["document_id"],
                                "title": hit["title"],
                                "chunk_index": hit["chunk_index"],
                                "score": hit["score"],
                                "search_query": search_query,
                                **hit.get("metadata", {})
                            }
                        )
                        all_documents.append(doc)
                
                except Exception as e:
                    logger.error(f"검색 실패 - 쿼리: {search_query}, 오류: {str(e)}")
            
            # 중복 제거 (document_id + chunk_index 기준)
            seen = set()
            unique_docs = []
            for doc in all_documents:
                key = f"{doc.metadata['document_id']}_{doc.metadata['chunk_index']}"
                if key not in seen:
                    seen.add(key)
                    unique_docs.append(doc)
            
            # 점수 순으로 정렬
            unique_docs.sort(key=lambda x: x.metadata.get("score", 0), reverse=True)
            
            state["retrieved_documents"] = unique_docs
            
            logger.info(f"문서 검색 완료: {len(unique_docs)}개 문서 검색됨")
            
        except Exception as e:
            logger.error(f"문서 검색 실패: {str(e)}")
            state["retrieved_documents"] = []
        
        return state
    
    async def _filter_documents_node(self, state: GraphState) -> GraphState:
        """문서 필터링 노드"""
        try:
            state["execution_path"].append("filter_documents")
            
            filtered_docs = []
            
            for doc in state["retrieved_documents"]:
                # 기본 점수 필터링
                score = doc.metadata.get("score", 0)
                if score < self.config.get("min_relevance_score", 0.3):
                    continue
                
                # 내용 길이 필터링
                if len(doc.page_content.strip()) < 20:
                    continue
                
                # LLM을 사용한 관련성 평가 (선택적)
                if self.config.get("use_llm_filtering", False):
                    try:
                        relevance_result = await self.llm.apredict(
                            self.relevance_prompt.format(
                                query=state["query"],
                                title=doc.metadata.get("title", ""),
                                content=doc.page_content[:500]
                            )
                        )
                        
                        # 점수 추출
                        if "점수:" in relevance_result:
                            score_line = relevance_result.split("점수:")[1].split("\n")[0]
                            try:
                                relevance_score = float(score_line.strip().split()[0])
                                if relevance_score < 7:
                                    continue
                            except:
                                pass
                        
                    except Exception as e:
                        logger.warning(f"LLM 필터링 실패: {str(e)}")
                        # LLM 필터링 실패 시 문서 유지
                
                filtered_docs.append(doc)
            
            state["filtered_documents"] = filtered_docs
            
            logger.info(f"문서 필터링 완료: {len(filtered_docs)}개 문서 유지됨")
            
        except Exception as e:
            logger.error(f"문서 필터링 실패: {str(e)}")
            state["filtered_documents"] = state["retrieved_documents"]
        
        return state
    
    async def _rerank_documents_node(self, state: GraphState) -> GraphState:
        """문서 재순위화 노드"""
        try:
            state["execution_path"].append("rerank_documents")
            
            # 최대 문서 수 제한
            max_docs = self.config.get("max_context_docs", 5)
            
            # 다양성을 고려한 재순위화
            reranked_docs = []
            used_doc_ids = set()
            
            for doc in state["filtered_documents"]:
                if len(reranked_docs) >= max_docs:
                    break
                
                doc_id = doc.metadata.get("document_id")
                
                # 문서 다양성 확보 (같은 문서에서 너무 많은 청크 방지)
                if doc_id in used_doc_ids:
                    doc_count = sum(1 for d in reranked_docs if d.metadata.get("document_id") == doc_id)
                    if doc_count >= 2:  # 문서당 최대 2개 청크
                        continue
                
                reranked_docs.append(doc)
                used_doc_ids.add(doc_id)
            
            state["reranked_documents"] = reranked_docs
            
            logger.info(f"문서 재순위화 완료: {len(reranked_docs)}개 문서 선택됨")
            
        except Exception as e:
            logger.error(f"문서 재순위화 실패: {str(e)}")
            state["reranked_documents"] = state["filtered_documents"][:5]
        
        return state
    
    async def _generate_initial_answer_node(self, state: GraphState) -> GraphState:
        """초기 답변 생성 노드"""
        try:
            state["execution_path"].append("generate_initial_answer")
            
            # 컨텍스트 구성
            context_parts = []
            for doc in state["reranked_documents"]:
                context_part = f"[문서: {doc.metadata.get('title', 'Unknown')}]\n{doc.page_content}"
                context_parts.append(context_part)
            
            context = "\n\n---\n\n".join(context_parts)
            state["context"] = context
            
            if not context.strip():
                state["initial_response"] = "죄송합니다. 관련된 정보를 찾을 수 없습니다."
                return state
            
            # LLM을 사용한 답변 생성
            messages = self.answer_generation_prompt.format_messages(
                query=state["query"],
                intent=state["query_intent"],
                context=context
            )
            
            response = await self.llm.agenerate([messages])
            answer = response.generations[0][0].text.strip()
            
            state["initial_response"] = answer
            
            logger.info("초기 답변 생성 완료")
            
        except Exception as e:
            logger.error(f"초기 답변 생성 실패: {str(e)}")
            state["initial_response"] = f"답변 생성 중 오류가 발생했습니다: {str(e)}"
        
        return state
    
    async def _refine_answer_node(self, state: GraphState) -> GraphState:
        """답변 개선 노드"""
        try:
            state["execution_path"].append("refine_answer")
            
            # 추가 컨텍스트 구성
            additional_context = f"쿼리 분석: {state['query_analysis']}\n"
            additional_context += f"검색된 문서 수: {len(state['retrieved_documents'])}\n"
            additional_context += f"사용된 검색 쿼리: {state['search_queries']}"
            
            # 답변 개선
            refined_answer = await self.llm.apredict(
                self.refinement_prompt.format(
                    query=state["query"],
                    initial_answer=state["initial_response"],
                    additional_context=additional_context
                )
            )
            
            state["refined_response"] = refined_answer
            
            logger.info("답변 개선 완료")
            
        except Exception as e:
            logger.error(f"답변 개선 실패: {str(e)}")
            state["refined_response"] = state["initial_response"]
        
        return state
    
    async def _finalize_answer_node(self, state: GraphState) -> GraphState:
        """최종 답변 완성 노드"""
        state["execution_path"].append("finalize_answer")
        
        # 최종 답변 결정
        if state["needs_refinement"] and state["refined_response"]:
            state["final_answer"] = state["refined_response"]
        else:
            state["final_answer"] = state["initial_response"]
        
        state["is_complete"] = True
        
        logger.info("최종 답변 완성")
        
        return state
    
    # 조건부 라우팅 함수들
    
    def _should_use_multiple_queries(self, state: GraphState) -> Literal["simple", "complex"]:
        """복잡도에 따른 라우팅 결정"""
        complexity = state["query_complexity"]
        needs_multiple = state["needs_multiple_queries"]
        
        if complexity in ["complex"] or needs_multiple:
            return "complex"
        else:
            return "simple"
    
    def _should_refine_answer(self, state: GraphState) -> Literal["refine", "finalize"]:
        """답변 개선 필요성 판단"""
        # 답변 품질 간단 체크
        answer = state["initial_response"]
        
        # 개선이 필요한 경우들
        if len(answer) < 50:  # 너무 짧은 답변
            state["needs_refinement"] = True
            return "refine"
        
        if "오류" in answer or "실패" in answer:  # 오류 메시지 포함
            state["needs_refinement"] = True
            return "refine"
        
        if state["query_complexity"] == "complex":  # 복잡한 쿼리
            state["needs_refinement"] = True
            return "refine"
        
        state["needs_refinement"] = False
        return "finalize"
    
    async def _route_complexity_node(self, state: GraphState) -> GraphState:
        """복잡도 라우팅 노드"""
        state["execution_path"].append("route_complexity")
        return state
    
    async def _check_quality_node(self, state: GraphState) -> GraphState:
        """품질 검사 노드"""
        state["execution_path"].append("check_quality")
        return state
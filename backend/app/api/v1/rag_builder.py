# rag-studio/backend/app/api/v1/rag_builder.py
"""
RAG Builder API 엔드포인트

LangGraph 컴포넌트를 사용한 시각적 RAG 파이프라인 구성을 지원합니다.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import json

from fastapi import APIRouter, HTTPException, Depends, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.utils.logger import logger
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


# RAG Builder 스키마 정의

class NodePosition(BaseModel):
    """노드 위치"""
    x: float
    y: float


class NodeData(BaseModel):
    """노드 데이터"""
    label: str
    type: str
    config: Optional[Dict[str, Any]] = {}


class GraphNode(BaseModel):
    """그래프 노드"""
    id: str
    type: str  # input, output, process
    position: NodePosition
    data: NodeData


class GraphEdge(BaseModel):
    """그래프 엣지"""
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    label: Optional[str] = None


class GraphState(BaseModel):
    """그래프 상태"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    viewport: Optional[Dict[str, Any]] = None


class ComponentDefinition(BaseModel):
    """컴포넌트 정의"""
    id: str
    name: str
    category: str
    description: str
    icon: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    config_schema: Optional[Dict[str, Any]] = None


class PipelineTemplate(BaseModel):
    """파이프라인 템플릿"""
    id: str
    name: str
    description: str
    category: str
    graph: GraphState
    created_at: datetime
    updated_at: datetime


# 사용 가능한 컴포넌트 정의
AVAILABLE_COMPONENTS = [
    ComponentDefinition(
        id="data_loader",
        name="Data Loader",
        category="Input",
        description="Load documents from various sources",
        icon="📄",
        inputs=[],
        outputs=[{"name": "documents", "type": "Document[]"}],
        config_schema={
            "type": "object",
            "properties": {
                "source_type": {
                    "type": "string",
                    "enum": ["file", "url", "database"],
                    "description": "Data source type"
                },
                "path": {
                    "type": "string",
                    "description": "Path or URL to data"
                }
            }
        }
    ),
    ComponentDefinition(
        id="text_splitter",
        name="Text Splitter",
        category="Processing",
        description="Split documents into chunks",
        icon="✂️",
        inputs=[{"name": "documents", "type": "Document[]"}],
        outputs=[{"name": "chunks", "type": "Chunk[]"}],
        config_schema={
            "type": "object",
            "properties": {
                "chunk_size": {
                    "type": "integer",
                    "default": 1000,
                    "description": "Size of each chunk"
                },
                "chunk_overlap": {
                    "type": "integer",
                    "default": 200,
                    "description": "Overlap between chunks"
                },
                "separator": {
                    "type": "string",
                    "default": "\n\n",
                    "description": "Text separator"
                }
            }
        }
    ),
    ComponentDefinition(
        id="embedding_model",
        name="Embedding Model",
        category="Embedding",
        description="Generate embeddings for text chunks",
        icon="🧠",
        inputs=[{"name": "chunks", "type": "Chunk[]"}],
        outputs=[{"name": "embeddings", "type": "Embedding[]"}],
        config_schema={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "enum": ["openai", "sentence-transformers", "custom"],
                    "default": "openai",
                    "description": "Embedding model to use"
                },
                "model_name": {
                    "type": "string",
                    "default": "text-embedding-3-small",
                    "description": "Specific model name"
                }
            }
        }
    ),
    ComponentDefinition(
        id="vector_store",
        name="Vector Store",
        category="Storage",
        description="Store and retrieve vector embeddings",
        icon="📦",
        inputs=[{"name": "embeddings", "type": "Embedding[]"}],
        outputs=[{"name": "retriever", "type": "Retriever"}],
        config_schema={
            "type": "object",
            "properties": {
                "index_name": {
                    "type": "string",
                    "description": "OpenSearch index name"
                },
                "similarity_metric": {
                    "type": "string",
                    "enum": ["cosine", "euclidean", "dot_product"],
                    "default": "cosine",
                    "description": "Similarity metric"
                }
            }
        }
    ),
    ComponentDefinition(
        id="retriever",
        name="Retriever",
        category="Retrieval",
        description="Retrieve relevant documents",
        icon="🔍",
        inputs=[{"name": "query", "type": "string"}],
        outputs=[{"name": "documents", "type": "Document[]"}],
        config_schema={
            "type": "object",
            "properties": {
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "Number of documents to retrieve"
                },
                "filter": {
                    "type": "object",
                    "description": "Metadata filters"
                }
            }
        }
    ),
    ComponentDefinition(
        id="llm_chain",
        name="LLM Chain",
        category="Generation",
        description="Generate answers using LLM",
        icon="🔗",
        inputs=[
            {"name": "query", "type": "string"},
            {"name": "context", "type": "Document[]"}
        ],
        outputs=[{"name": "answer", "type": "string"}],
        config_schema={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "default": "gpt-4-turbo-preview",
                    "description": "LLM model to use"
                },
                "temperature": {
                    "type": "number",
                    "default": 0.7,
                    "minimum": 0,
                    "maximum": 2,
                    "description": "Sampling temperature"
                },
                "max_tokens": {
                    "type": "integer",
                    "default": 2000,
                    "description": "Maximum tokens to generate"
                },
                "prompt_template": {
                    "type": "string",
                    "description": "Custom prompt template"
                }
            }
        }
    ),
    ComponentDefinition(
        id="output_parser",
        name="Output Parser",
        category="Output",
        description="Parse and format the output",
        icon="💡",
        inputs=[{"name": "answer", "type": "string"}],
        outputs=[{"name": "formatted_output", "type": "any"}],
        config_schema={
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["text", "json", "markdown"],
                    "default": "text",
                    "description": "Output format"
                }
            }
        }
    )
]


@router.get("/components", response_model=List[ComponentDefinition])
async def get_available_components() -> List[ComponentDefinition]:
    """
    사용 가능한 RAG 컴포넌트 목록 조회
    
    Returns:
        List[ComponentDefinition]: 컴포넌트 정의 목록
    """
    return AVAILABLE_COMPONENTS


@router.get("/components/{component_id}", response_model=ComponentDefinition)
async def get_component_details(component_id: str) -> ComponentDefinition:
    """
    특정 컴포넌트 상세 정보 조회
    
    Args:
        component_id: 컴포넌트 ID
        
    Returns:
        ComponentDefinition: 컴포넌트 정의
    """
    component = next(
        (c for c in AVAILABLE_COMPONENTS if c.id == component_id),
        None
    )
    
    if not component:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component not found: {component_id}"
        )
    
    return component


@router.post("/validate", response_model=Dict[str, Any])
async def validate_pipeline_graph(
    graph: GraphState,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    파이프라인 그래프 유효성 검증
    
    Args:
        graph: 검증할 그래프
        current_user: 현재 사용자
        
    Returns:
        Dict[str, Any]: 검증 결과
    """
    errors = []
    warnings = []
    
    # 노드 ID 중복 확인
    node_ids = [node.id for node in graph.nodes]
    if len(node_ids) != len(set(node_ids)):
        errors.append("Duplicate node IDs found")
    
    # 엣지 유효성 확인
    for edge in graph.edges:
        if edge.source not in node_ids:
            errors.append(f"Edge source '{edge.source}' not found in nodes")
        if edge.target not in node_ids:
            errors.append(f"Edge target '{edge.target}' not found in nodes")
    
    # 입력/출력 노드 확인
    input_nodes = [n for n in graph.nodes if n.type == "input"]
    output_nodes = [n for n in graph.nodes if n.type == "output"]
    
    if not input_nodes:
        warnings.append("No input nodes found")
    if not output_nodes:
        warnings.append("No output nodes found")
    
    # 연결성 확인 (간단한 버전)
    connected_nodes = set()
    for edge in graph.edges:
        connected_nodes.add(edge.source)
        connected_nodes.add(edge.target)
    
    isolated_nodes = set(node_ids) - connected_nodes
    if isolated_nodes:
        warnings.append(f"Isolated nodes found: {list(isolated_nodes)}")
    
    # 결과 구성
    is_valid = len(errors) == 0
    
    result = {
        "is_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges)
    }
    
    logger.info(f"그래프 검증 완료: valid={is_valid}, user={current_user.username}")
    
    return result


@router.post("/compile", response_model=Dict[str, Any])
async def compile_pipeline_graph(
    graph: GraphState,
    pipeline_name: str = Body(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    파이프라인 그래프를 실행 가능한 코드로 컴파일
    
    Args:
        graph: 컴파일할 그래프
        pipeline_name: 파이프라인 이름
        current_user: 현재 사용자
        
    Returns:
        Dict[str, Any]: 컴파일 결과
    """
    try:
        # 그래프 검증
        validation = await validate_pipeline_graph(graph, current_user)
        if not validation["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid graph: {validation['errors']}"
            )
        
        # 노드를 컴포넌트 타입별로 그룹화
        nodes_by_type = {}
        for node in graph.nodes:
            node_type = node.data.type
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []
            nodes_by_type[node_type].append(node)
        
        # 실행 순서 결정 (간단한 토폴로지 정렬)
        execution_order = _topological_sort(graph.nodes, graph.edges)
        
        # LangGraph 코드 생성 (의사 코드)
        code_snippet = f"""
# Auto-generated RAG Pipeline: {pipeline_name}
# Generated at: {datetime.utcnow().isoformat()}

from langchain.schema import Document
from langgraph.graph import StateGraph, END

# Define the graph state
class PipelineState(TypedDict):
    query: str
    documents: List[Document]
    embeddings: List[List[float]]
    retrieved_docs: List[Document]
    answer: str

# Create the graph
workflow = StateGraph(PipelineState)

# Add nodes based on components
"""
        
        for node in execution_order:
            component_type = node.data.type
            config = node.data.config or {}
            
            code_snippet += f"""
# Node: {node.data.label} ({component_type})
async def {node.id}_node(state: PipelineState) -> PipelineState:
    # Component configuration: {json.dumps(config, indent=2)}
    # TODO: Implement {component_type} logic
    return state

workflow.add_node("{node.id}", {node.id}_node)
"""
        
        # 엣지 추가
        code_snippet += "\n# Add edges\n"
        for edge in graph.edges:
            code_snippet += f'workflow.add_edge("{edge.source}", "{edge.target}")\n'
        
        # 파이프라인 ID 생성
        pipeline_id = str(uuid.uuid4())
        
        # 결과 반환
        result = {
            "pipeline_id": pipeline_id,
            "pipeline_name": pipeline_name,
            "code_snippet": code_snippet,
            "execution_order": [node.id for node in execution_order],
            "component_count": len(graph.nodes),
            "connection_count": len(graph.edges),
            "estimated_latency_ms": len(graph.nodes) * 100,  # 예상 지연시간
            "compiled_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"파이프라인 컴파일 완료: {pipeline_name}, user={current_user.username}")
        
        return result
        
    except Exception as e:
        logger.error(f"파이프라인 컴파일 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compilation failed: {str(e)}"
        )


@router.get("/templates", response_model=List[PipelineTemplate])
async def get_pipeline_templates() -> List[PipelineTemplate]:
    """
    사전 정의된 파이프라인 템플릿 목록 조회
    
    Returns:
        List[PipelineTemplate]: 템플릿 목록
    """
    # 샘플 템플릿들
    templates = [
        {
            "id": "basic-rag",
            "name": "Basic RAG Pipeline",
            "description": "Simple retrieval-augmented generation pipeline",
            "category": "starter",
            "graph": {
                "nodes": [
                    {
                        "id": "loader",
                        "type": "input",
                        "position": {"x": 100, "y": 100},
                        "data": {
                            "label": "Document Loader",
                            "type": "data_loader",
                            "config": {"source_type": "file"}
                        }
                    },
                    {
                        "id": "splitter",
                        "type": "process",
                        "position": {"x": 300, "y": 100},
                        "data": {
                            "label": "Text Splitter",
                            "type": "text_splitter",
                            "config": {"chunk_size": 1000}
                        }
                    },
                    {
                        "id": "embedder",
                        "type": "process",
                        "position": {"x": 500, "y": 100},
                        "data": {
                            "label": "Embedding Model",
                            "type": "embedding_model",
                            "config": {"model": "openai"}
                        }
                    },
                    {
                        "id": "output",
                        "type": "output",
                        "position": {"x": 700, "y": 100},
                        "data": {
                            "label": "Output",
                            "type": "output_parser",
                            "config": {"format": "text"}
                        }
                    }
                ],
                "edges": [
                    {"id": "e1", "source": "loader", "target": "splitter"},
                    {"id": "e2", "source": "splitter", "target": "embedder"},
                    {"id": "e3", "source": "embedder", "target": "output"}
                ]
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    
    return templates


@router.post("/templates/{template_id}/clone", response_model=GraphState)
async def clone_template(
    template_id: str,
    current_user: User = Depends(get_current_user)
) -> GraphState:
    """
    템플릿을 복제하여 새 파이프라인 생성
    
    Args:
        template_id: 템플릿 ID
        current_user: 현재 사용자
        
    Returns:
        GraphState: 복제된 그래프
    """
    # 템플릿 조회 (실제로는 DB에서)
    templates = await get_pipeline_templates()
    template = next((t for t in templates if t["id"] == template_id), None)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}"
        )
    
    # 새 ID로 노드 복제
    cloned_graph = template["graph"].copy()
    
    # 노드 ID 재생성
    id_mapping = {}
    for node in cloned_graph["nodes"]:
        old_id = node["id"]
        new_id = f"{old_id}_{uuid.uuid4().hex[:8]}"
        id_mapping[old_id] = new_id
        node["id"] = new_id
    
    # 엣지 ID 및 참조 업데이트
    for edge in cloned_graph["edges"]:
        edge["id"] = f"e_{uuid.uuid4().hex[:8]}"
        edge["source"] = id_mapping.get(edge["source"], edge["source"])
        edge["target"] = id_mapping.get(edge["target"], edge["target"])
    
    logger.info(f"템플릿 복제 완료: {template_id}, user={current_user.username}")
    
    return GraphState(**cloned_graph)


def _topological_sort(nodes: List[GraphNode], edges: List[GraphEdge]) -> List[GraphNode]:
    """
    토폴로지 정렬을 사용한 노드 실행 순서 결정
    
    Args:
        nodes: 노드 리스트
        edges: 엣지 리스트
        
    Returns:
        List[GraphNode]: 정렬된 노드 리스트
    """
    # 인접 리스트 구성
    adj_list = {node.id: [] for node in nodes}
    in_degree = {node.id: 0 for node in nodes}
    
    for edge in edges:
        adj_list[edge.source].append(edge.target)
        in_degree[edge.target] += 1
    
    # 진입 차수가 0인 노드로 시작
    queue = [node for node in nodes if in_degree[node.id] == 0]
    result = []
    
    while queue:
        current = queue.pop(0)
        result.append(current)
        
        # 인접 노드의 진입 차수 감소
        for neighbor_id in adj_list[current.id]:
            in_degree[neighbor_id] -= 1
            if in_degree[neighbor_id] == 0:
                neighbor = next(n for n in nodes if n.id == neighbor_id)
                queue.append(neighbor)
    
    # 사이클 확인
    if len(result) != len(nodes):
        raise ValueError("Graph contains a cycle")
    
    return result
# rag-studio/backend/app/services/opensearch_service.py
"""
OpenSearch 연동 서비스 모듈

OpenSearch 클러스터와의 모든 상호작용을 관리하며,
인덱스 생성, 문서 색인, 검색, 모니터링 기능을 제공합니다.
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncio

from opensearchpy import AsyncOpenSearch, exceptions
from opensearchpy.helpers import async_bulk
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.utils.logger import logger
from app.schemas.opensearch import (
    IndexConfig, 
    DocumentInput, 
    SearchQuery, 
    SearchResult,
    ClusterHealth,
    IndexStats
)


class OpenSearchService:
    """
    OpenSearch 클러스터와의 상호작용을 담당하는 서비스 클래스
    
    이 클래스는 문서 색인, 벡터 검색, 클러스터 모니터링 등
    OpenSearch의 모든 기능을 추상화하여 제공합니다.
    """
    
    def __init__(self):
        """
        OpenSearch 서비스 초기화
        
        클라이언트 연결을 설정하고 임베딩 모델을 로드합니다.
        """
        # OpenSearch 클라이언트 초기화
        self.client = AsyncOpenSearch(
            hosts=[{
                'host': settings.OPENSEARCH_HOST,
                'port': settings.OPENSEARCH_PORT
            }],
            http_auth=(
                settings.OPENSEARCH_USER, 
                settings.OPENSEARCH_PASSWORD
            ) if settings.OPENSEARCH_USER else None,
            use_ssl=settings.OPENSEARCH_USE_SSL,
            verify_certs=False,  # 개발 환경용 설정
            ssl_show_warn=False
        )
        
        # 임베딩 모델 초기화 (로컬 모델 사용)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        logger.info("OpenSearch 서비스가 초기화되었습니다.")
    
    async def check_connection(self) -> bool:
        """
        OpenSearch 클러스터 연결 상태 확인
        
        Returns:
            bool: 연결 성공 여부
        """
        try:
            # 클러스터 정보 조회로 연결 확인
            info = await self.client.info()
            cluster_name = info['cluster_name']
            version = info['version']['number']
            
            logger.info(f"OpenSearch 클러스터 연결 성공: {cluster_name} (v{version})")
            
            connection_status = True
            return connection_status
            
        except Exception as e:
            logger.error(f"OpenSearch 연결 실패: {str(e)}")
            connection_status = False
            return connection_status
    
    async def create_index(self, index_name: str, config: IndexConfig) -> Dict[str, Any]:
        """
        새로운 인덱스 생성
        
        Args:
            index_name: 생성할 인덱스 이름
            config: 인덱스 설정 정보
            
        Returns:
            Dict[str, Any]: 생성 결과
        """
        try:
            # 인덱스 매핑 정의
            index_body = {
                "settings": {
                    "number_of_shards": config.number_of_shards,
                    "number_of_replicas": config.number_of_replicas,
                    "analysis": {
                        "analyzer": {
                            "korean_analyzer": {
                                "type": "custom",
                                "tokenizer": "nori_tokenizer",
                                "filter": ["lowercase", "stop", "snowball"]
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        # 문서 기본 필드
                        "document_id": {"type": "keyword"},
                        "title": {
                            "type": "text",
                            "analyzer": "korean_analyzer",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "korean_analyzer"
                        },
                        "chunk_text": {
                            "type": "text",
                            "analyzer": "korean_analyzer"
                        },
                        
                        # 벡터 임베딩 필드
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": config.embedding_dimension,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 512,
                                    "m": 16
                                }
                            }
                        },
                        
                        # 메타데이터 필드
                        "metadata": {
                            "type": "object",
                            "enabled": True
                        },
                        "source": {"type": "keyword"},
                        "chunk_index": {"type": "integer"},
                        "created_at": {"type": "date"},
                        "updated_at": {"type": "date"}
                    }
                }
            }
            
            # 인덱스 생성
            response = await self.client.indices.create(
                index=index_name,
                body=index_body
            )
            
            logger.info(f"인덱스 '{index_name}' 생성 완료")
            
            creation_result = {
                "index": index_name,
                "acknowledged": response.get("acknowledged", False),
                "shards_acknowledged": response.get("shards_acknowledged", False)
            }
            
            return creation_result
            
        except exceptions.RequestError as e:
            if e.error == "resource_already_exists_exception":
                logger.warning(f"인덱스 '{index_name}'가 이미 존재합니다.")
                existing_result = {
                    "index": index_name,
                    "acknowledged": False,
                    "error": "Index already exists"
                }
                return existing_result
            raise
    
    async def index_documents(
        self, 
        index_name: str, 
        documents: List[DocumentInput]
    ) -> Dict[str, Any]:
        """
        문서 일괄 색인
        
        Args:
            index_name: 대상 인덱스 이름
            documents: 색인할 문서 리스트
            
        Returns:
            Dict[str, Any]: 색인 결과 통계
        """
        try:
            # 색인할 문서 준비
            actions = []
            
            for doc in documents:
                # 텍스트를 청크로 분할
                chunks = self._split_text(
                    doc.content,
                    chunk_size=settings.CHUNK_SIZE,
                    overlap=settings.CHUNK_OVERLAP
                )
                
                # 각 청크에 대해 임베딩 생성 및 문서 준비
                for idx, chunk in enumerate(chunks):
                    # 임베딩 생성
                    embedding = self.embedding_model.encode(chunk).tolist()
                    
                    # 색인할 문서 구조
                    action = {
                        "_index": index_name,
                        "_source": {
                            "document_id": doc.document_id,
                            "title": doc.title,
                            "content": doc.content,
                            "chunk_text": chunk,
                            "chunk_index": idx,
                            "embedding": embedding,
                            "metadata": doc.metadata or {},
                            "source": doc.source,
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat()
                        }
                    }
                    
                    actions.append(action)
            
            # 일괄 색인 실행
            success, failed = await async_bulk(
                self.client,
                actions,
                chunk_size=100,
                request_timeout=30
            )
            
            logger.info(
                f"문서 색인 완료: 성공 {success}개, 실패 {len(failed)}개"
            )
            
            # 색인 결과 통계
            indexing_stats = {
                "total_documents": len(documents),
                "total_chunks": len(actions),
                "successful": success,
                "failed": len(failed),
                "failed_items": failed[:10] if failed else []  # 실패 항목 샘플
            }
            
            return indexing_stats
            
        except Exception as e:
            logger.error(f"문서 색인 중 오류 발생: {str(e)}")
            raise
    
    async def search(
        self, 
        index_name: str, 
        query: SearchQuery
    ) -> SearchResult:
        """
        벡터 유사도 검색 수행
        
        Args:
            index_name: 검색 대상 인덱스
            query: 검색 쿼리 정보
            
        Returns:
            SearchResult: 검색 결과
        """
        try:
            # 쿼리 텍스트를 임베딩으로 변환
            query_embedding = self.embedding_model.encode(query.query_text).tolist()
            
            # OpenSearch 쿼리 구성
            search_body = {
                "size": query.top_k,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "must": []
                            }
                        },
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                            "params": {
                                "query_vector": query_embedding
                            }
                        }
                    }
                }
            }
            
            # 필터 조건 추가
            if query.filters:
                for field, value in query.filters.items():
                    search_body["query"]["script_score"]["query"]["bool"]["must"].append({
                        "term": {field: value}
                    })
            
            # 검색 실행
            response = await self.client.search(
                index=index_name,
                body=search_body
            )
            
            # 검색 결과 파싱
            hits = []
            for hit in response["hits"]["hits"]:
                parsed_hit = {
                    "document_id": hit["_source"]["document_id"],
                    "title": hit["_source"]["title"],
                    "chunk_text": hit["_source"]["chunk_text"],
                    "chunk_index": hit["_source"]["chunk_index"],
                    "score": hit["_score"],
                    "metadata": hit["_source"].get("metadata", {})
                }
                hits.append(parsed_hit)
            
            # 검색 결과 구성
            search_result = SearchResult(
                query=query.query_text,
                total_hits=response["hits"]["total"]["value"],
                hits=hits,
                took_ms=response["took"]
            )
            
            return search_result
            
        except Exception as e:
            logger.error(f"검색 중 오류 발생: {str(e)}")
            raise
    
    async def get_cluster_health(self) -> ClusterHealth:
        """
        클러스터 상태 정보 조회
        
        Returns:
            ClusterHealth: 클러스터 상태 정보
        """
        try:
            # 클러스터 상태 조회
            health = await self.client.cluster.health()
            
            # 노드 정보 조회
            nodes_info = await self.client.nodes.info()
            node_count = len(nodes_info["nodes"])
            
            # 클러스터 상태 객체 생성
            cluster_health = ClusterHealth(
                cluster_name=health["cluster_name"],
                status=health["status"],
                node_count=node_count,
                active_shards=health["active_shards"],
                relocating_shards=health["relocating_shards"],
                initializing_shards=health["initializing_shards"],
                unassigned_shards=health["unassigned_shards"],
                delayed_unassigned_shards=health["delayed_unassigned_shards"],
                active_shards_percent=health["active_shards_percent_as_number"]
            )
            
            return cluster_health
            
        except Exception as e:
            logger.error(f"클러스터 상태 조회 실패: {str(e)}")
            raise
    
    async def get_index_stats(self, index_name: str) -> IndexStats:
        """
        인덱스 통계 정보 조회
        
        Args:
            index_name: 조회할 인덱스 이름
            
        Returns:
            IndexStats: 인덱스 통계 정보
        """
        try:
            # 인덱스 통계 조회
            stats = await self.client.indices.stats(index=index_name)
            index_info = stats["indices"][index_name]
            
            # 문서 수 조회
            count_response = await self.client.count(index=index_name)
            doc_count = count_response["count"]
            
            # 인덱스 통계 객체 생성
            index_stats = IndexStats(
                index_name=index_name,
                document_count=doc_count,
                size_in_bytes=index_info["total"]["store"]["size_in_bytes"],
                size_human=self._bytes_to_human_readable(
                    index_info["total"]["store"]["size_in_bytes"]
                ),
                primary_shards=index_info["primaries"]["docs"]["count"],
                total_shards=len(index_info["shards"])
            )
            
            return index_stats
            
        except Exception as e:
            logger.error(f"인덱스 통계 조회 실패: {str(e)}")
            raise
    
    def _split_text(
        self, 
        text: str, 
        chunk_size: int = 1000, 
        overlap: int = 200
    ) -> List[str]:
        """
        텍스트를 청크로 분할
        
        Args:
            text: 분할할 텍스트
            chunk_size: 청크 크기
            overlap: 청크 간 중첩 크기
            
        Returns:
            List[str]: 분할된 청크 리스트
        """
        # 텍스트가 비어있는 경우 빈 리스트 반환
        if not text:
            return []
        
        # 청크 리스트 초기화
        chunks = []
        
        # 텍스트 길이가 청크 크기보다 작은 경우
        if len(text) <= chunk_size:
            chunks.append(text)
            return chunks
        
        # 슬라이딩 윈도우 방식으로 청크 생성
        start = 0
        while start < len(text):
            # 청크 끝 위치 계산
            end = start + chunk_size
            
            # 마지막 청크인 경우
            if end >= len(text):
                chunk = text[start:]
                chunks.append(chunk)
                break
            
            # 단어 경계에서 자르기 위해 공백 위치 찾기
            while end > start and text[end] not in ' \n\t':
                end -= 1
            
            # 공백을 찾지 못한 경우 원래 위치 사용
            if end == start:
                end = start + chunk_size
            
            # 청크 추가
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # 다음 시작 위치 계산 (오버랩 적용)
            start = end - overlap
        
        return chunks
    
    def _bytes_to_human_readable(self, bytes_size: int) -> str:
        """
        바이트 크기를 사람이 읽기 쉬운 형식으로 변환
        
        Args:
            bytes_size: 바이트 단위 크기
            
        Returns:
            str: 사람이 읽기 쉬운 크기 문자열
        """
        # 단위 정의
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        
        # 크기 변환
        size = float(bytes_size)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        # 포맷팅된 문자열 생성
        if unit_index == 0:
            formatted_size = f"{int(size)}{units[unit_index]}"
        else:
            formatted_size = f"{size:.2f}{units[unit_index]}"
        
        return formatted_size
    
    async def close(self):
        """
        OpenSearch 클라이언트 연결 종료
        """
        await self.client.close()
        logger.info("OpenSearch 연결이 종료되었습니다.")


# 서비스 인스턴스 생성 함수
def get_opensearch_service() -> OpenSearchService:
    """
    OpenSearch 서비스 인스턴스를 반환하는 팩토리 함수
    
    Returns:
        OpenSearchService: OpenSearch 서비스 인스턴스
    """
    service = OpenSearchService()
    return service
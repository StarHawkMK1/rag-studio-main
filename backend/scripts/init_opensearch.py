#!/usr/bin/env python3
# rag-studio/backend/scripts/init_opensearch.py
"""
OpenSearch 클러스터 초기화 스크립트

OpenSearch 클러스터를 초기 설정하고 기본 인덱스를 생성합니다.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings
from app.utils.logger import logger
from app.services.opensearch_service import OpenSearchService
from app.schemas.opensearch import IndexConfig


class OpenSearchInitializer:
    """OpenSearch 초기화 클래스"""
    
    def __init__(self):
        self.opensearch_service = OpenSearchService()
        self.default_indices = [
            {
                "name": "rag-documents",
                "description": "기본 RAG 문서 인덱스",
                "config": IndexConfig(
                    number_of_shards=2,
                    number_of_replicas=1,
                    embedding_dimension=384
                )
            },
            {
                "name": "rag-test",
                "description": "테스트용 인덱스",
                "config": IndexConfig(
                    number_of_shards=1,
                    number_of_replicas=0,
                    embedding_dimension=384
                )
            },
            {
                "name": "rag-benchmark",
                "description": "벤치마크용 인덱스",
                "config": IndexConfig(
                    number_of_shards=1,
                    number_of_replicas=1,
                    embedding_dimension=768
                )
            }
        ]
    
    async def check_connection(self) -> bool:
        """OpenSearch 연결 확인"""
        try:
            connected = await self.opensearch_service.check_connection()
            if connected:
                logger.info("✅ OpenSearch 연결 성공")
                return True
            else:
                logger.error("❌ OpenSearch 연결 실패")
                return False
        except Exception as e:
            logger.error(f"❌ OpenSearch 연결 중 오류: {str(e)}")
            return False
    
    async def get_cluster_info(self) -> Dict[str, Any]:
        """클러스터 정보 조회"""
        try:
            # 클러스터 상태
            health = await self.opensearch_service.get_cluster_health()
            
            # 기본 정보
            info = await self.opensearch_service.client.info()
            
            cluster_info = {
                "cluster_name": health.cluster_name,
                "status": health.status,
                "node_count": health.node_count,
                "version": info.get("version", {}).get("number", "unknown"),
                "active_shards": health.active_shards,
                "unassigned_shards": health.unassigned_shards
            }
            
            logger.info(f"📊 클러스터 정보: {cluster_info}")
            return cluster_info
            
        except Exception as e:
            logger.error(f"❌ 클러스터 정보 조회 실패: {str(e)}")
            return {}
    
    async def create_default_indices(self) -> bool:
        """기본 인덱스들 생성"""
        success_count = 0
        
        for index_info in self.default_indices:
            try:
                index_name = index_info["name"]
                config = index_info["config"]
                description = index_info["description"]
                
                logger.info(f"📝 인덱스 생성 중: {index_name} ({description})")
                
                # 인덱스 생성
                result = await self.opensearch_service.create_index(index_name, config)
                
                if result.get("acknowledged", False):
                    logger.info(f"✅ 인덱스 생성 성공: {index_name}")
                    success_count += 1
                else:
                    logger.warning(f"⚠️ 인덱스 생성 응답 확인 안됨: {index_name}")
                
            except Exception as e:
                if "resource_already_exists_exception" in str(e):
                    logger.info(f"ℹ️ 인덱스가 이미 존재함: {index_name}")
                    success_count += 1
                else:
                    logger.error(f"❌ 인덱스 생성 실패: {index_name}, 오류: {str(e)}")
        
        logger.info(f"📈 인덱스 생성 완료: {success_count}/{len(self.default_indices)}")
        return success_count == len(self.default_indices)
    
    async def setup_index_templates(self) -> bool:
        """인덱스 템플릿 설정"""
        try:
            # RAG 문서용 인덱스 템플릿
            rag_template = {
                "index_patterns": ["rag-*"],
                "template": {
                    "settings": {
                        "number_of_shards": 2,
                        "number_of_replicas": 1,
                        "analysis": {
                            "analyzer": {
                                "korean_analyzer": {
                                    "type": "custom",
                                    "tokenizer": "nori_tokenizer",
                                    "filter": ["lowercase", "stop"]
                                }
                            }
                        }
                    },
                    "mappings": {
                        "properties": {
                            "document_id": {"type": "keyword"},
                            "title": {
                                "type": "text",
                                "analyzer": "korean_analyzer",
                                "fields": {"keyword": {"type": "keyword"}}
                            },
                            "content": {"type": "text", "analyzer": "korean_analyzer"},
                            "chunk_text": {"type": "text", "analyzer": "korean_analyzer"},
                            "embedding": {
                                "type": "knn_vector",
                                "dimension": 384,
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "cosinesimil",
                                    "engine": "nmslib"
                                }
                            },
                            "metadata": {"type": "object"},
                            "source": {"type": "keyword"},
                            "chunk_index": {"type": "integer"},
                            "created_at": {"type": "date"},
                            "updated_at": {"type": "date"}
                        }
                    }
                }
            }
            
            # 템플릿 생성
            response = await self.opensearch_service.client.indices.put_index_template(
                name="rag-documents-template",
                body=rag_template
            )
            
            if response.get("acknowledged", False):
                logger.info("✅ 인덱스 템플릿 생성 성공")
                return True
            else:
                logger.warning("⚠️ 인덱스 템플릿 생성 응답 확인 안됨")
                return False
                
        except Exception as e:
            logger.error(f"❌ 인덱스 템플릿 생성 실패: {str(e)}")
            return False
    
    async def verify_setup(self) -> bool:
        """설정 검증"""
        try:
            success = True
            
            # 인덱스 존재 확인
            for index_info in self.default_indices:
                index_name = index_info["name"]
                try:
                    stats = await self.opensearch_service.get_index_stats(index_name)
                    logger.info(f"✅ 인덱스 확인: {index_name} (문서 수: {stats.document_count})")
                except Exception as e:
                    logger.error(f"❌ 인덱스 확인 실패: {index_name}, 오류: {str(e)}")
                    success = False
            
            # 템플릿 확인
            try:
                response = await self.opensearch_service.client.indices.get_index_template(
                    name="rag-documents-template"
                )
                if response:
                    logger.info("✅ 인덱스 템플릿 확인")
                else:
                    logger.warning("⚠️ 인덱스 템플릿 없음")
            except Exception as e:
                logger.warning(f"⚠️ 인덱스 템플릿 확인 실패: {str(e)}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 설정 검증 중 오류: {str(e)}")
            return False
    
    async def load_sample_data(self) -> bool:
        """샘플 데이터 로드"""
        try:
            from app.schemas.opensearch import DocumentInput
            
            # 샘플 문서들
            sample_documents = [
                DocumentInput(
                    document_id="sample_001",
                    title="RAG 시스템 소개",
                    content="""
                    RAG(Retrieval-Augmented Generation)는 검색과 생성을 결합한 AI 시스템입니다.
                    이 시스템은 방대한 문서 데이터베이스에서 관련 정보를 검색하고,
                    이를 바탕으로 자연스러운 답변을 생성합니다.
                    RAG는 특히 최신 정보나 도메인 특화 지식이 필요한 질의응답에 효과적입니다.
                    """,
                    source="sample",
                    metadata={"category": "introduction", "language": "ko"}
                ),
                DocumentInput(
                    document_id="sample_002", 
                    title="OpenSearch 벡터 검색",
                    content="""
                    OpenSearch는 강력한 벡터 검색 기능을 제공합니다.
                    k-NN(k-Nearest Neighbor) 알고리즘을 사용하여 
                    의미적으로 유사한 문서를 빠르게 찾을 수 있습니다.
                    HNSW(Hierarchical Navigable Small World) 알고리즘을 통해
                    대규모 벡터 데이터에서도 효율적인 검색이 가능합니다.
                    """,
                    source="sample",
                    metadata={"category": "technical", "language": "ko"}
                ),
                DocumentInput(
                    document_id="sample_003",
                    title="LangChain과 LangGraph",
                    content="""
                    LangChain은 LLM 애플리케이션 개발을 위한 프레임워크입니다.
                    LangGraph는 복잡한 워크플로우를 상태 그래프로 모델링할 수 있게 해줍니다.
                    이를 통해 다단계 추론이나 조건부 실행이 필요한
                    고급 RAG 파이프라인을 구현할 수 있습니다.
                    """,
                    source="sample", 
                    metadata={"category": "framework", "language": "ko"}
                )
            ]
            
            # 테스트 인덱스에 샘플 데이터 색인
            result = await self.opensearch_service.index_documents(
                "rag-test",
                sample_documents
            )
            
            if result["successful"] > 0:
                logger.info(f"✅ 샘플 데이터 로드 성공: {result['successful']}개 문서")
                return True
            else:
                logger.error("❌ 샘플 데이터 로드 실패")
                return False
                
        except Exception as e:
            logger.error(f"❌ 샘플 데이터 로드 중 오류: {str(e)}")
            return False
    
    async def cleanup_connection(self):
        """연결 정리"""
        try:
            await self.opensearch_service.close()
            logger.info("🔌 OpenSearch 연결 종료")
        except Exception as e:
            logger.warning(f"⚠️ 연결 종료 중 오류: {str(e)}")


async def main():
    """메인 초기화 함수"""
    logger.info("🚀 OpenSearch 클러스터 초기화 시작")
    
    initializer = OpenSearchInitializer()
    
    try:
        # 1. 연결 확인
        if not await initializer.check_connection():
            logger.error("💥 OpenSearch에 연결할 수 없습니다. 설정을 확인하세요.")
            return False
        
        # 2. 클러스터 정보 조회
        await initializer.get_cluster_info()
        
        # 3. 인덱스 템플릿 설정
        await initializer.setup_index_templates()
        
        # 4. 기본 인덱스 생성
        if not await initializer.create_default_indices():
            logger.error("💥 기본 인덱스 생성에 실패했습니다.")
            return False
        
        # 5. 샘플 데이터 로드
        await initializer.load_sample_data()
        
        # 6. 설정 검증
        if await initializer.verify_setup():
            logger.info("🎉 OpenSearch 초기화 완료!")
            return True
        else:
            logger.error("💥 설정 검증에 실패했습니다.")
            return False
            
    except KeyboardInterrupt:
        logger.info("⏹️ 사용자에 의해 중단됨")
        return False
    except Exception as e:
        logger.error(f"💥 초기화 중 예상치 못한 오류: {str(e)}")
        return False
    finally:
        await initializer.cleanup_connection()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenSearch 클러스터 초기화")
    parser.add_argument(
        "--skip-sample-data",
        action="store_true",
        help="샘플 데이터 로드 건너뛰기"
    )
    parser.add_argument(
        "--force",
        action="store_true", 
        help="기존 인덱스가 있어도 강제 진행"
    )
    
    args = parser.parse_args()
    
    # 비동기 실행
    success = asyncio.run(main())
    
    if success:
        print("\n✅ OpenSearch 초기화가 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        print("\n❌ OpenSearch 초기화에 실패했습니다!")
        sys.exit(1)
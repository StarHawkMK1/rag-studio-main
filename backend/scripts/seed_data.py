#!/usr/bin/env python3
# rag-studio/backend/scripts/seed_data.py
"""
초기 데이터 생성 스크립트

개발 및 테스트를 위한 초기 데이터를 생성합니다.
"""

import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.utils.logger import logger
from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base
from app.models.user import User
from app.models.pipeline import Pipeline
from app.models.rag_config import PromptTemplate, LLMConfiguration, RAGConfiguration
from app.models.opensearch import IndexConfiguration, EmbeddingModel
from app.core.security import get_password_hash
from app.schemas.pipeline import PipelineType, PipelineStatus
from app.services.opensearch_service import OpenSearchService
from app.schemas.opensearch import DocumentInput


class DataSeeder:
    """데이터 시딩 클래스"""
    
    def __init__(self):
        self.opensearch_service = OpenSearchService()
        
    async def create_tables(self):
        """데이터베이스 테이블 생성"""
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ 데이터베이스 테이블 생성 완료")
        except Exception as e:
            logger.error(f"❌ 테이블 생성 실패: {str(e)}")
            raise
    
    async def create_users(self, db: AsyncSession) -> List[User]:
        """사용자 데이터 생성"""
        users_data = [
            {
                "email": "admin@ragstudio.com",
                "username": "admin",
                "full_name": "시스템 관리자",
                "password": "admin123!@#",
                "is_active": True,
                "is_superuser": True
            },
            {
                "email": "demo@ragstudio.com", 
                "username": "demo",
                "full_name": "데모 사용자",
                "password": "demo123!@#",
                "is_active": True,
                "is_superuser": False
            },
            {
                "email": "test@ragstudio.com",
                "username": "test",
                "full_name": "테스트 사용자", 
                "password": "test123!@#",
                "is_active": True,
                "is_superuser": False
            }
        ]
        
        created_users = []
        
        for user_data in users_data:
            # 기존 사용자 확인
            result = await db.execute(
                db.query(User).filter(User.email == user_data["email"])
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                logger.info(f"ℹ️ 사용자가 이미 존재함: {user_data['email']}")
                created_users.append(existing_user)
                continue
            
            # 새 사용자 생성
            user = User(
                email=user_data["email"],
                username=user_data["username"],
                full_name=user_data["full_name"],
                hashed_password=get_password_hash(user_data["password"]),
                is_active=user_data["is_active"],
                is_superuser=user_data["is_superuser"]
            )
            
            db.add(user)
            created_users.append(user)
            logger.info(f"✅ 사용자 생성: {user_data['email']}")
        
        await db.commit()
        
        # 사용자 정보 새로고침
        for user in created_users:
            await db.refresh(user)
        
        return created_users
    
    async def create_embedding_models(self, db: AsyncSession) -> List[EmbeddingModel]:
        """임베딩 모델 데이터 생성"""
        models_data = [
            {
                "name": "OpenAI Text Embedding 3 Small",
                "provider": "openai",
                "model_id": "text-embedding-3-small",
                "dimension": 1536,
                "max_input_length": 8191,
                "is_active": True,
                "is_default": True,
                "description": "OpenAI의 최신 임베딩 모델 (소형)"
            },
            {
                "name": "Sentence Transformers All-MiniLM-L6-v2",
                "provider": "huggingface",
                "model_id": "sentence-transformers/all-MiniLM-L6-v2",
                "dimension": 384,
                "max_input_length": 256,
                "is_active": True,
                "is_default": False,
                "description": "경량화된 다국어 임베딩 모델"
            },
            {
                "name": "OpenAI Text Embedding Ada 002",
                "provider": "openai", 
                "model_id": "text-embedding-ada-002",
                "dimension": 1536,
                "max_input_length": 8191,
                "is_active": False,
                "is_default": False,
                "description": "OpenAI의 이전 세대 임베딩 모델"
            }
        ]
        
        created_models = []
        
        for model_data in models_data:
            # 기존 모델 확인
            result = await db.execute(
                db.query(EmbeddingModel).filter(EmbeddingModel.name == model_data["name"])
            )
            existing_model = result.scalar_one_or_none()
            
            if existing_model:
                logger.info(f"ℹ️ 임베딩 모델이 이미 존재함: {model_data['name']}")
                created_models.append(existing_model)
                continue
            
            # 새 모델 생성
            model = EmbeddingModel(**model_data)
            db.add(model)
            created_models.append(model)
            logger.info(f"✅ 임베딩 모델 생성: {model_data['name']}")
        
        await db.commit()
        
        for model in created_models:
            await db.refresh(model)
        
        return created_models
    
    async def create_prompt_templates(self, db: AsyncSession, admin_user: User) -> List[PromptTemplate]:
        """프롬프트 템플릿 생성"""
        templates_data = [
            {
                "name": "기본 QA 프롬프트",
                "description": "일반적인 질의응답을 위한 기본 프롬프트",
                "template_text": """다음 문맥을 참고하여 질문에 답변해주세요.

문맥:
{context}

질문: {question}

답변: 문맥에 기반하여 정확하고 도움이 되는 답변을 제공하겠습니다.""",
                "template_format": "f-string",
                "variables": [
                    {"name": "context", "type": "string", "required": True},
                    {"name": "question", "type": "string", "required": True}
                ],
                "category": "qa",
                "use_case": "naive_rag",
                "is_active": True,
                "is_default": True
            },
            {
                "name": "분석적 질문 프롬프트",
                "description": "복잡한 분석이 필요한 질문을 위한 프롬프트",
                "template_text": """제공된 문서들을 종합적으로 분석하여 질문에 답변하세요.

관련 문서들:
{context}

질문: {question}

분석 지침:
1. 여러 문서의 정보를 종합하여 분석
2. 근거와 함께 논리적 결론 제시
3. 불확실한 부분은 명시

분석 결과:""",
                "template_format": "f-string",
                "variables": [
                    {"name": "context", "type": "string", "required": True},
                    {"name": "question", "type": "string", "required": True}
                ],
                "category": "analysis",
                "use_case": "graph_rag",
                "is_active": True,
                "is_default": False
            },
            {
                "name": "요약 프롬프트",
                "description": "문서 요약을 위한 프롬프트",
                "template_text": """다음 문서를 요약해주세요.

문서 내용:
{content}

요약 요구사항:
- 핵심 내용을 3-5개 문장으로 요약
- 중요한 키워드 포함
- 객관적이고 정확한 요약

요약:""",
                "template_format": "f-string",
                "variables": [
                    {"name": "content", "type": "string", "required": True}
                ],
                "category": "summarization",
                "use_case": "naive_rag",
                "is_active": True,
                "is_default": False
            }
        ]
        
        created_templates = []
        
        for template_data in templates_data:
            # 기존 템플릿 확인
            result = await db.execute(
                db.query(PromptTemplate).filter(PromptTemplate.name == template_data["name"])
            )
            existing_template = result.scalar_one_or_none()
            
            if existing_template:
                logger.info(f"ℹ️ 프롬프트 템플릿이 이미 존재함: {template_data['name']}")
                created_templates.append(existing_template)
                continue
            
            # 새 템플릿 생성
            template = PromptTemplate(
                **template_data,
                created_by=admin_user.id
            )
            db.add(template)
            created_templates.append(template)
            logger.info(f"✅ 프롬프트 템플릿 생성: {template_data['name']}")
        
        await db.commit()
        
        for template in created_templates:
            await db.refresh(template)
        
        return created_templates
    
    async def create_llm_configurations(self, db: AsyncSession, admin_user: User) -> List[LLMConfiguration]:
        """LLM 설정 생성"""
        configs_data = [
            {
                "name": "GPT-4 Turbo",
                "provider": "openai",
                "model_name": "gpt-4-turbo-preview",
                "temperature": 0.7,
                "max_tokens": 2000,
                "description": "OpenAI GPT-4 Turbo 모델",
                "is_active": True,
                "is_default": True
            },
            {
                "name": "GPT-3.5 Turbo",
                "provider": "openai", 
                "model_name": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 1500,
                "description": "OpenAI GPT-3.5 Turbo 모델",
                "is_active": True,
                "is_default": False
            },
            {
                "name": "Conservative GPT-4",
                "provider": "openai",
                "model_name": "gpt-4-turbo-preview",
                "temperature": 0.3,
                "max_tokens": 2000,
                "description": "보수적인 설정의 GPT-4 모델",
                "is_active": True,
                "is_default": False
            }
        ]
        
        created_configs = []
        
        for config_data in configs_data:
            # 기존 설정 확인
            result = await db.execute(
                db.query(LLMConfiguration).filter(LLMConfiguration.name == config_data["name"])
            )
            existing_config = result.scalar_one_or_none()
            
            if existing_config:
                logger.info(f"ℹ️ LLM 설정이 이미 존재함: {config_data['name']}")
                created_configs.append(existing_config)
                continue
            
            # 새 설정 생성
            config = LLMConfiguration(
                **config_data,
                created_by=admin_user.id
            )
            db.add(config)
            created_configs.append(config)
            logger.info(f"✅ LLM 설정 생성: {config_data['name']}")
        
        await db.commit()
        
        for config in created_configs:
            await db.refresh(config)
        
        return created_configs
    
    async def create_index_configurations(self, db: AsyncSession, admin_user: User) -> List[IndexConfiguration]:
        """인덱스 설정 생성"""
        configs_data = [
            {
                "name": "rag-documents",
                "description": "기본 RAG 문서 인덱스",
                "number_of_shards": 2,
                "number_of_replicas": 1,
                "embedding_dimension": 384,
                "is_active": True,
                "index_created": True
            },
            {
                "name": "rag-test",
                "description": "테스트용 인덱스",
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "embedding_dimension": 384,
                "is_active": True,
                "index_created": True
            },
            {
                "name": "rag-benchmark",
                "description": "벤치마크용 인덱스",
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "embedding_dimension": 768,
                "is_active": True,
                "index_created": True
            }
        ]
        
        created_configs = []
        
        for config_data in configs_data:
            # 기존 설정 확인
            result = await db.execute(
                db.query(IndexConfiguration).filter(IndexConfiguration.name == config_data["name"])
            )
            existing_config = result.scalar_one_or_none()
            
            if existing_config:
                logger.info(f"ℹ️ 인덱스 설정이 이미 존재함: {config_data['name']}")
                created_configs.append(existing_config)
                continue
            
            # 새 설정 생성
            config = IndexConfiguration(
                **config_data,
                created_by=admin_user.id
            )
            db.add(config)
            created_configs.append(config)
            logger.info(f"✅ 인덱스 설정 생성: {config_data['name']}")
        
        await db.commit()
        
        for config in created_configs:
            await db.refresh(config)
        
        return created_configs
    
    async def create_pipelines(self, db: AsyncSession, admin_user: User) -> List[Pipeline]:
        """파이프라인 생성"""
        pipelines_data = [
            {
                "name": "기본 QA 파이프라인",
                "description": "간단한 질의응답을 위한 기본 파이프라인",
                "pipeline_type": PipelineType.NAIVE_RAG,
                "status": PipelineStatus.INACTIVE,
                "index_name": "rag-documents",
                "config": {
                    "retrieval_top_k": 5,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "search_filters": {}
                }
            },
            {
                "name": "고급 분석 파이프라인",
                "description": "복잡한 분석을 위한 Graph RAG 파이프라인",
                "pipeline_type": PipelineType.GRAPH_RAG,
                "status": PipelineStatus.INACTIVE,
                "index_name": "rag-documents",
                "config": {
                    "retrieval_top_k": 10,
                    "temperature": 0.5,
                    "max_tokens": 3000,
                    "use_llm_filtering": True,
                    "max_context_docs": 7
                }
            },
            {
                "name": "테스트 파이프라인",
                "description": "개발 및 테스트용 파이프라인",
                "pipeline_type": PipelineType.NAIVE_RAG,
                "status": PipelineStatus.INACTIVE,
                "index_name": "rag-test",
                "config": {
                    "retrieval_top_k": 3,
                    "temperature": 0.8,
                    "max_tokens": 1500,
                    "search_filters": {}
                }
            }
        ]
        
        created_pipelines = []
        
        for pipeline_data in pipelines_data:
            # 기존 파이프라인 확인
            result = await db.execute(
                db.query(Pipeline).filter(Pipeline.name == pipeline_data["name"])
            )
            existing_pipeline = result.scalar_one_or_none()
            
            if existing_pipeline:
                logger.info(f"ℹ️ 파이프라인이 이미 존재함: {pipeline_data['name']}")
                created_pipelines.append(existing_pipeline)
                continue
            
            # 새 파이프라인 생성
            pipeline = Pipeline(
                **pipeline_data,
                created_by=admin_user.id
            )
            db.add(pipeline)
            created_pipelines.append(pipeline)
            logger.info(f"✅ 파이프라인 생성: {pipeline_data['name']}")
        
        await db.commit()
        
        for pipeline in created_pipelines:
            await db.refresh(pipeline)
        
        return created_pipelines
    
    async def create_sample_documents(self) -> bool:
        """샘플 문서 생성"""
        try:
            sample_docs = [
                DocumentInput(
                    document_id="doc_ai_basics_001",
                    title="인공지능 기초 개념",
                    content="""
                    인공지능(AI)은 인간의 지능을 모방하여 학습, 추론, 인식 등의 작업을 수행하는 컴퓨터 시스템입니다.
                    기계학습은 AI의 하위 분야로, 데이터로부터 패턴을 학습하여 예측이나 결정을 내립니다.
                    딥러닝은 신경망을 사용한 기계학습의 한 방법으로, 복잡한 패턴 인식에 탁월합니다.
                    자연어처리(NLP)는 컴퓨터가 인간의 언어를 이해하고 생성하는 AI 분야입니다.
                    """,
                    source="seed",
                    metadata={"category": "ai_basics", "difficulty": "beginner"}
                ),
                DocumentInput(
                    document_id="doc_rag_system_001",
                    title="RAG 시스템 아키텍처",
                    content="""
                    RAG(Retrieval-Augmented Generation) 시스템은 검색과 생성을 결합한 AI 아키텍처입니다.
                    문서 저장소에서 관련 정보를 검색하고, 이를 바탕으로 LLM이 답변을 생성합니다.
                    벡터 데이터베이스는 문서를 임베딩 벡터로 변환하여 의미적 검색을 가능하게 합니다.
                    OpenSearch, Pinecone, Weaviate 등이 벡터 검색을 지원하는 대표적인 데이터베이스입니다.
                    """,
                    source="seed",
                    metadata={"category": "rag_system", "difficulty": "intermediate"}
                ),
                DocumentInput(
                    document_id="doc_llm_models_001",
                    title="대규모 언어 모델(LLM) 종류",
                    content="""
                    GPT(Generative Pre-trained Transformer) 시리즈는 OpenAI에서 개발한 대표적인 LLM입니다.
                    Claude는 Anthropic에서 개발한 안전성에 중점을 둔 AI 어시스턴트입니다.
                    LLaMA는 Meta에서 개발한 오픈소스 언어 모델입니다.
                    PaLM은 Google에서 개발한 대규모 언어 모델입니다.
                    각 모델은 고유한 특성과 성능을 가지고 있어 용도에 따라 선택해야 합니다.
                    """,
                    source="seed",
                    metadata={"category": "llm_models", "difficulty": "intermediate"}
                ),
                DocumentInput(
                    document_id="doc_embedding_001",
                    title="텍스트 임베딩과 벡터 검색",
                    content="""
                    텍스트 임베딩은 텍스트를 고차원 벡터 공간의 점으로 변환하는 기술입니다.
                    Word2Vec, GloVe, FastText는 전통적인 임베딩 기법입니다.
                    BERT, RoBERTa, Sentence-BERT는 트랜스포머 기반의 현대적 임베딩 모델입니다.
                    코사인 유사도, 유클리드 거리, 내적 등이 벡터 간 유사도 측정에 사용됩니다.
                    HNSW, LSH 등의 알고리즘으로 대규모 벡터 검색을 효율화할 수 있습니다.
                    """,
                    source="seed",
                    metadata={"category": "embedding", "difficulty": "advanced"}
                ),
                DocumentInput(
                    document_id="doc_prompt_engineering_001",
                    title="프롬프트 엔지니어링 기법",
                    content="""
                    프롬프트 엔지니어링은 AI 모델에서 원하는 결과를 얻기 위해 입력을 최적화하는 기법입니다.
                    Few-shot 프롬프팅은 몇 개의 예시를 제공하여 모델이 패턴을 학습하게 합니다.
                    Chain-of-Thought는 단계별 추론 과정을 명시하여 복잡한 문제 해결 능력을 향상시킵니다.
                    Role-playing은 모델에게 특정 역할을 부여하여 해당 관점에서 답변하게 합니다.
                    Temperature, Top-p 등의 파라미터로 생성 결과의 창의성과 일관성을 조절할 수 있습니다.
                    """,
                    source="seed",
                    metadata={"category": "prompt_engineering", "difficulty": "intermediate"}
                )
            ]
            
            # 문서 색인
            result = await self.opensearch_service.index_documents(
                "rag-documents", 
                sample_docs
            )
            
            if result["successful"] > 0:
                logger.info(f"✅ 샘플 문서 색인 완료: {result['successful']}개")
                return True
            else:
                logger.error(f"❌ 샘플 문서 색인 실패: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 샘플 문서 생성 중 오류: {str(e)}")
            return False


async def main():
    """메인 시딩 함수"""
    logger.info("🌱 초기 데이터 생성 시작")
    
    seeder = DataSeeder()
    
    try:
        # 1. 테이블 생성
        await seeder.create_tables()
        
        # 2. 데이터베이스 세션
        async with AsyncSessionLocal() as db:
            # 3. 사용자 생성
            users = await seeder.create_users(db)
            admin_user = next(u for u in users if u.is_superuser)
            
            # 4. 임베딩 모델 생성
            await seeder.create_embedding_models(db, admin_user)
            
            # 5. 프롬프트 템플릿 생성
            await seeder.create_prompt_templates(db, admin_user)
            
            # 6. LLM 설정 생성
            await seeder.create_llm_configurations(db, admin_user)
            
            # 7. 인덱스 설정 생성
            await seeder.create_index_configurations(db, admin_user)
            
            # 8. 파이프라인 생성
            await seeder.create_pipelines(db, admin_user)
        
        # 9. OpenSearch 샘플 문서 생성
        await seeder.create_sample_documents()
        
        logger.info("🎉 초기 데이터 생성 완료!")
        return True
        
    except Exception as e:
        logger.error(f"💥 데이터 생성 중 오류: {str(e)}")
        return False
    finally:
        await seeder.opensearch_service.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="초기 데이터 생성")
    parser.add_argument(
        "--skip-documents",
        action="store_true",
        help="문서 생성 건너뛰기"
    )
    
    args = parser.parse_args()
    
    # 비동기 실행
    success = asyncio.run(main())
    
    if success:
        print("\n✅ 초기 데이터 생성이 완료되었습니다!")
        print("\n📋 생성된 데이터:")
        print("  👥 사용자: admin, demo, test")
        print("  🔧 파이프라인: 기본 QA, 고급 분석, 테스트")
        print("  📄 샘플 문서: AI 기초, RAG 시스템, LLM 모델 등")
        print("  ⚙️ 설정: 프롬프트 템플릿, LLM 설정, 인덱스 설정")
        print("\n🔑 기본 로그인 정보:")
        print("  관리자: admin@ragstudio.com / admin123!@#")
        print("  데모: demo@ragstudio.com / demo123!@#")
        sys.exit(0)
    else:
        print("\n❌ 초기 데이터 생성에 실패했습니다!")
        sys.exit(1)
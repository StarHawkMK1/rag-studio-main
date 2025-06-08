# rag-studio/backend/app/db/session.py
"""
데이터베이스 세션 관리

SQLAlchemy 비동기 세션을 설정하고 관리합니다.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.logger import logger

# 비동기 엔진 생성
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,  # SQL 로깅
    pool_pre_ping=True,  # 연결 상태 확인
    poolclass=NullPool,  # 연결 풀링 비활성화 (비동기에서는 권장)
)

# 비동기 세션 팩토리
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 커밋 후에도 객체 사용 가능
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    데이터베이스 세션 의존성
    
    FastAPI의 의존성 주입을 위한 함수입니다.
    요청당 하나의 세션을 생성하고, 요청이 끝나면 자동으로 닫습니다.
    
    Yields:
        AsyncSession: 데이터베이스 세션
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    데이터베이스 초기화
    
    테이블 생성 및 초기 데이터 설정을 수행합니다.
    """
    try:
        logger.info("데이터베이스 초기화 시작...")
        
        # 테이블 생성 (main.py의 lifespan에서 처리)
        # 여기서는 추가 초기화 작업만 수행
        
        async with AsyncSessionLocal() as session:
            # 초기 데이터 확인 및 생성
            from app.models.user import User
            
            # 관리자 계정 확인
            result = await session.execute(
                session.query(User).filter(User.username == "admin")
            )
            admin_user = result.scalar_one_or_none()
            
            if not admin_user:
                # 기본 관리자 계정 생성
                from app.core.security import get_password_hash
                
                admin_user = User(
                    username="admin",
                    email="admin@ragpilot.com",
                    full_name="System Administrator",
                    hashed_password=get_password_hash("admin123!@#"),
                    is_active=True,
                    is_superuser=True
                )
                
                session.add(admin_user)
                await session.commit()
                
                logger.info("기본 관리자 계정이 생성되었습니다.")
        
        logger.info("데이터베이스 초기화 완료")
        
    except Exception as e:
        logger.error(f"데이터베이스 초기화 중 오류: {str(e)}")
        raise
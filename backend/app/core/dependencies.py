# rag-studio/backend/app/core/dependencies.py
"""
의존성 주입 모듈

FastAPI의 의존성 주입 시스템을 위한 공통 의존성들을 정의합니다.
"""

from typing import Optional, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.logger import logger
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import TokenPayload

# OAuth2 스키마 정의
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login",
    auto_error=True
)

# Optional OAuth2 스키마 (인증이 선택적인 경우)
optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login",
    auto_error=False
)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    """
    현재 인증된 사용자 조회
    
    Args:
        db: 데이터베이스 세션
        token: JWT 액세스 토큰
        
    Returns:
        User: 현재 사용자 객체
        
    Raises:
        HTTPException: 인증 실패 시
    """
    # 인증 실패 예외
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 토큰 검증
        user_id = security.verify_token(token, token_type="access")
        if user_id is None:
            raise credentials_exception
        
        # 토큰 페이로드 생성
        token_data = TokenPayload(sub=user_id)
        
    except JWTError:
        raise credentials_exception
    
    # 데이터베이스에서 사용자 조회
    result = await db.execute(
        db.query(User).filter(User.id == token_data.sub)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        logger.warning(f"토큰에 있는 사용자를 찾을 수 없음: {token_data.sub}")
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    현재 활성 사용자 조회
    
    Args:
        current_user: 현재 사용자
        
    Returns:
        User: 활성 사용자 객체
        
    Raises:
        HTTPException: 사용자가 비활성 상태인 경우
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return current_user


async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    현재 활성 슈퍼유저 조회
    
    Args:
        current_user: 현재 활성 사용자
        
    Returns:
        User: 슈퍼유저 객체
        
    Raises:
        HTTPException: 사용자가 슈퍼유저가 아닌 경우
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return current_user


async def get_optional_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[Optional[str], Depends(optional_oauth2_scheme)]
) -> Optional[User]:
    """
    선택적 현재 사용자 조회
    
    토큰이 제공되지 않은 경우 None을 반환합니다.
    
    Args:
        db: 데이터베이스 세션
        token: JWT 액세스 토큰 (선택적)
        
    Returns:
        Optional[User]: 사용자 객체 또는 None
    """
    if not token:
        return None
    
    try:
        # 토큰 검증
        user_id = security.verify_token(token, token_type="access")
        if user_id is None:
            return None
        
        # 데이터베이스에서 사용자 조회
        result = await db.execute(
            db.query(User).filter(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        return user
        
    except Exception as e:
        logger.warning(f"선택적 사용자 인증 실패: {str(e)}")
        return None


class PermissionChecker:
    """
    권한 확인 의존성 클래스
    
    특정 권한이 필요한 엔드포인트에서 사용합니다.
    """
    
    def __init__(self, required_permissions: list[str]):
        """
        Args:
            required_permissions: 필요한 권한 목록
        """
        self.required_permissions = required_permissions
    
    async def __call__(
        self,
        current_user: Annotated[User, Depends(get_current_active_user)]
    ) -> User:
        """
        사용자 권한 확인
        
        Args:
            current_user: 현재 활성 사용자
            
        Returns:
            User: 권한이 있는 사용자
            
        Raises:
            HTTPException: 권한이 없는 경우
        """
        # 슈퍼유저는 모든 권한 보유
        if current_user.is_superuser:
            return current_user
        
        # TODO: 실제 권한 시스템 구현
        # 현재는 슈퍼유저만 체크
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required permissions: {', '.join(self.required_permissions)}"
        )


# 공통 권한 체커들
require_admin = PermissionChecker(["admin"])
require_pipeline_create = PermissionChecker(["pipeline:create"])
require_pipeline_delete = PermissionChecker(["pipeline:delete"])
require_benchmark_create = PermissionChecker(["benchmark:create"])


class RateLimiter:
    """
    Rate Limiting 의존성 클래스
    
    API 요청 빈도를 제한합니다.
    """
    
    def __init__(self, calls: int = 10, period: int = 60):
        """
        Args:
            calls: 허용되는 호출 횟수
            period: 기간 (초)
        """
        self.calls = calls
        self.period = period
        self.cache = {}  # 실제로는 Redis 사용 권장
    
    async def __call__(
        self,
        current_user: Annotated[Optional[User], Depends(get_optional_current_user)]
    ):
        """
        Rate limit 확인
        
        Args:
            current_user: 현재 사용자 (선택적)
            
        Raises:
            HTTPException: Rate limit 초과 시
        """
        # 사용자 식별
        if current_user:
            identifier = str(current_user.id)
        else:
            # TODO: IP 주소 기반 식별
            identifier = "anonymous"
        
        # 현재 시간
        now = datetime.utcnow()
        
        # 사용자의 요청 기록 조회
        user_calls = self.cache.get(identifier, [])
        
        # 만료된 기록 제거
        cutoff_time = now - timedelta(seconds=self.period)
        user_calls = [call_time for call_time in user_calls if call_time > cutoff_time]
        
        # Rate limit 확인
        if len(user_calls) >= self.calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.calls} calls per {self.period} seconds."
            )
        
        # 새 요청 기록
        user_calls.append(now)
        self.cache[identifier] = user_calls


# Rate limiter 인스턴스들
general_rate_limit = RateLimiter(calls=100, period=60)  # 분당 100회
strict_rate_limit = RateLimiter(calls=10, period=60)    # 분당 10회
search_rate_limit = RateLimiter(calls=30, period=60)    # 분당 30회
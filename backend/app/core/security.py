# rag-studio/backend/app/core/security.py
"""
보안 및 인증 모듈

JWT 토큰 생성/검증, 비밀번호 해싱 등의 보안 기능을 제공합니다.
"""

from datetime import datetime, timedelta
from typing import Any, Optional, Union

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings
from app.utils.logger import logger

# 비밀번호 해싱 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: Union[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    JWT 액세스 토큰 생성
    
    Args:
        subject: 토큰 주체 (일반적으로 사용자 ID)
        expires_delta: 만료 시간 델타
        
    Returns:
        str: 생성된 JWT 토큰
    """
    # 만료 시간 설정
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # 토큰 페이로드 구성
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    # JWT 토큰 생성
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    JWT 리프레시 토큰 생성
    
    Args:
        subject: 토큰 주체
        expires_delta: 만료 시간 델타
        
    Returns:
        str: 생성된 리프레시 토큰
    """
    # 리프레시 토큰은 더 긴 만료 시간 설정
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)  # 7일
    
    # 토큰 페이로드 구성
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    
    # JWT 토큰 생성
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[str]:
    """
    JWT 토큰 검증
    
    Args:
        token: 검증할 토큰
        token_type: 토큰 타입 (access/refresh)
        
    Returns:
        Optional[str]: 토큰이 유효한 경우 subject, 아니면 None
    """
    try:
        # 토큰 디코드
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # 토큰 타입 확인
        if payload.get("type") != token_type:
            logger.warning(f"잘못된 토큰 타입: {payload.get('type')} (예상: {token_type})")
            return None
        
        # Subject 추출
        subject: str = payload.get("sub")
        if subject is None:
            logger.warning("토큰에 subject가 없습니다.")
            return None
        
        return subject
        
    except JWTError as e:
        logger.warning(f"JWT 토큰 검증 실패: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"토큰 검증 중 예상치 못한 오류: {str(e)}")
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    비밀번호 검증
    
    Args:
        plain_password: 평문 비밀번호
        hashed_password: 해시된 비밀번호
        
    Returns:
        bool: 비밀번호 일치 여부
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    비밀번호 해싱
    
    Args:
        password: 평문 비밀번호
        
    Returns:
        str: 해시된 비밀번호
    """
    return pwd_context.hash(password)


def generate_reset_password_token(email: str) -> str:
    """
    비밀번호 재설정 토큰 생성
    
    Args:
        email: 사용자 이메일
        
    Returns:
        str: 재설정 토큰
    """
    delta = timedelta(hours=1)  # 1시간 유효
    
    to_encode = {
        "exp": datetime.utcnow() + delta,
        "sub": email,
        "type": "reset_password"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def verify_reset_password_token(token: str) -> Optional[str]:
    """
    비밀번호 재설정 토큰 검증
    
    Args:
        token: 재설정 토큰
        
    Returns:
        Optional[str]: 토큰이 유효한 경우 이메일, 아니면 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        if payload.get("type") != "reset_password":
            return None
        
        email: str = payload.get("sub")
        return email
        
    except JWTError:
        return None


def generate_email_verification_token(email: str) -> str:
    """
    이메일 인증 토큰 생성
    
    Args:
        email: 인증할 이메일
        
    Returns:
        str: 인증 토큰
    """
    delta = timedelta(days=7)  # 7일 유효
    
    to_encode = {
        "exp": datetime.utcnow() + delta,
        "sub": email,
        "type": "email_verification"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def verify_email_verification_token(token: str) -> Optional[str]:
    """
    이메일 인증 토큰 검증
    
    Args:
        token: 인증 토큰
        
    Returns:
        Optional[str]: 토큰이 유효한 경우 이메일, 아니면 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        if payload.get("type") != "email_verification":
            return None
        
        email: str = payload.get("sub")
        return email
        
    except JWTError:
        return None
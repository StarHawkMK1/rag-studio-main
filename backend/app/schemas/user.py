# rag-studio/backend/app/schemas/user.py
"""
사용자 관련 스키마
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """사용자 기본 정보"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    """사용자 생성"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """사용자 수정"""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """사용자 응답"""
    id: str
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT 토큰"""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """토큰 페이로드"""
    sub: Optional[str] = None
    exp: Optional[int] = None
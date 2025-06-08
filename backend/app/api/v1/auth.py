# """
# 인증 관련 API 엔드포인트

# 로그인, 회원가입, 토큰 갱신 등의 인증 기능을 제공합니다.
# """

# from datetime import datetime, timedelta
# from typing import Annotated, Any

# from fastapi import APIRouter, Body, Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core import security
# from app.core.config import settings
# from app.core.deps import get_current_user, get_db
# from app.core.logger import logger, log_audit
# from app.models.user import User
# from app.schemas.user import (
#     UserCreate,
#     UserResponse,
#     Token,
#     UserUpdate
# )

# router = APIRouter()


# @router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
# async def register(
#     user_data: UserCreate,
#     db: AsyncSession = Depends(get_db)
# ) -> UserResponse:
#     """
#     새 사용자 등록
    
#     Args:
#         user_data: 사용자 생성 데이터
#         db: 데이터베이스 세션
        
#     Returns:
#         UserResponse: 생성된 사용자 정보
        
#     Raises:
#         HTTPException: 이메일/사용자명이 이미 존재하는 경우
#     """
#     # 이메일 중복 확인
#     result = await db.execute(
#         db.query(User).filter(User.email == user_data.email)
#     )
#     if result.scalar_one_or_none():
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Email already registered"
#         )
    
#     # 사용자명 중복 확인
#     result = await db.execute(
#         db.query(User).filter(User.username == user_data.username)
#     )
#     if result.scalar_one_or_none():
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Username already taken"
#         )
    
#     # 비밀번호 해싱
#     hashed_password = security.get_password_hash(user_data.password)
    
#     # 사용자 생성
#     db_user = User(
#         email=user_data.email,
#         username=user_data.username,
#         full_name=user_data.full_name,
#         hashed_password=hashed_password,
#         is_active=user_data.is_active,
#         is_superuser=user_data.is_superuser
#     )
    
#     db.add(db_user)
#     await db.commit()
#     await db.refresh(db_user)
    
#     # 감사 로그
#     log_audit(
#         action="user_register",
#         resource_type="user",
#         resource_id=str(db_user.id),
#         user_id=str(db_user.id),
#         result="success"
#     )
    
#     logger.info(f"새 사용자 등록: {db_user.username} ({db_user.email})")
    
#     return UserResponse(
#         id=str(db_user.id),
#         email=db_user.email,
#         username=db_user.username,
#         full_name=db_user.full_name,
#         is_active=db_user.is_active,
#         is_superuser=db_user.is_superuser
#     )


# @router.post("/login", response_model=Token)
# async def login(
#     db: AsyncSession = Depends(get_db),
#     form_data: OAuth2PasswordRequestForm = Depends()
# ) -> Token:
#     """
#     사용자 로그인 (OAuth2 호환)
    
#     Args:
#         db: 데이터베이스 세션
#         form_data: 로그인 폼 데이터 (username, password)
        
#     Returns:
#         Token: 액세스 토큰
        
#     Raises:
#         HTTPException: 인증 실패 시
#     """
#     # 사용자 조회 (username 또는 email로 로그인 가능)
#     result = await db.execute(
#         db.query(User).filter(
#             (User.username == form_data.username) |
#             (User.email == form_data.username)
#         )
#     )
#     user = result.scalar_one_or_none()
    
#     # 사용자 확인 및 비밀번호 검증
#     if not user or not security.verify_password(form_data.password, user.hashed_password):
#         logger.warning(f"로그인 실패: {form_data.username}")
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
    
#     # 비활성 사용자 확인
#     if not user.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Inactive user"
#         )
    
#     # 액세스 토큰 생성
#     access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
#     access_token = security.create_access_token(
#         subject=str(user.id),
#         expires_delta=access_token_expires
#     )
    
#     # 감사 로그
#     log_audit(
#         action="user_login",
#         resource_type="user",
#         resource_id=str(user.id),
#         user_id=str(user.id),
#         result="success"
#     )
    
#     logger.info(f"사용자 로그인 성공: {user.username}")
    
#     return Token(
#         access_token=access_token,
#         token_type="bearer"
#     )


# @router.post("/refresh", response_model=Token)
# async def refresh_token(
#     refresh_token: str = Body(..., embed=True),
#     db: AsyncSession = Depends(get_db)
# ) -> Token:
#     """
#     토큰 갱신
    
#     Args:
#         refresh_token: 리프레시 토큰
#         db: 데이터베이스 세션
        
#     Returns:
#         Token: 새로운 액세스 토큰
        
#     Raises:
#         HTTPException: 토큰이 유효하지 않은 경우
#     """
#     # 리프레시 토큰 검증
#     user_id = security.verify_token(refresh_token, token_type="refresh")
#     if not user_id:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid refresh token"
#         )
    
#     # 사용자 확인
#     result = await db.execute(
#         db.query(User).filter(User.id == user_id)
#     )
#     user = result.scalar_one_or_none()
    
#     if not user or not user.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="User not found or inactive"
#         )
    
#     # 새 액세스 토큰 생성
#     access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
#     access_token = security.create_access_token(
#         subject=str(user.id),
#         expires_delta=access_token_expires
#     )
    
#     logger.info(f"토큰 갱신: {user.username}")
    
#     return Token(
#         access_token=access_token,
#         token_type="bearer"
#     )


# @router.get("/me", response_model=UserResponse)
# async def read_users_me(
#     current_user: Annotated[User, Depends(get_current_user)]
# ) -> UserResponse:
#     """
#     현재 사용자 정보 조회
    
#     Args:
#         current_user: 현재 인증된 사용자
        
#     Returns:
#         UserResponse: 사용자 정보
#     """
#     return UserResponse(
#         id=str(current_user.id),
#         email=current_user.email,
#         username=current_user.username,
#         full_name=current_user.full_name,
#         is_active=current_user.is_active,
#         is_superuser=current_user.is_superuser
#     )


# @router.put("/me", response_model=UserResponse)
# async def update_user_me(
#     user_update: UserUpdate,
#     current_user: Annotated[User, Depends(get_current_user)],
#     db: AsyncSession = Depends(get_db)
# ) -> UserResponse:
#     """
#     현재 사용자 정보 수정
    
#     Args:
#         user_update: 수정할 사용자 정보
#         current_user: 현재 인증된 사용자
#         db: 데이터베이스 세션
        
#     Returns:
#         UserResponse: 수정된 사용자 정보
#     """
#     # 수정 사항 적용
#     update_data = user_update.dict(exclude_unset=True)
    
#     # 비밀번호 변경
#     if "password" in update_data:
#         hashed_password = security.get_password_hash(update_data["password"])
#         update_data["hashed_password"] = hashed_password
#         del update_data["password"]
    
#     # 이메일 변경 시 중복 확인
#     if "email" in update_data and update_data["email"] != current_user.email:
#         result = await db.execute(
#             db.query(User).filter(User.email == update_data["email"])
#         )
#         if result.scalar_one_or_none():
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Email already registered"
#             )
    
#     # 사용자명 변경 시 중복 확인
#     if "username" in update_data and update_data["username"] != current_user.username:
#         result = await db.execute(
#             db.query(User).filter(User.username == update_data["username"])
#         )
#         if result.scalar_one_or_none():
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Username already taken"
#             )
    
#     # 업데이트 적용
#     for field, value in update_data.items():
#         setattr(current_user, field, value)
    
#     current_user.updated_at = datetime.utcnow()
    
#     await db.commit()
#     await db.refresh(current_user)
    
#     # 감사 로그
#     log_audit(
#         action="user_update",
#         resource_type="user",
#         resource_id=str(current_user.id),
#         user_id=str(current_user.id),
#         result="success",
#         changes=list(update_data.keys())
#     )
    
#     logger.info(f"사용자 정보 수정: {current_user.username}")
    
#     return UserResponse(
#         id=str(current_user.id),
#         email=current_user.email,
#         username=current_user.username,
#         full_name=current_user.full_name,
#         is_active=current_user.is_active,
#         is_superuser=current_user.is_superuser
#     )


# @router.post("/logout")
# async def logout(
#     current_user: Annotated[User, Depends(get_current_user)]
# ) -> dict[str, str]:
#     """
#     로그아웃
    
#     실제로는 클라이언트에서 토큰을 제거해야 합니다.
#     서버에서는 로그아웃 이벤트만 기록합니다.
    
#     Args:
#         current_user: 현재 인증된 사용자
        
#     Returns:
#         dict: 로그아웃 메시지
#     """
#     # 감사 로그
#     log_audit(
#         action="user_logout",
#         resource_type="user",
#         resource_id=str(current_user.id),
#         user_id=str(current_user.id),
#         result="success"
#     )
    
#     logger.info(f"사용자 로그아웃: {current_user.username}")
    
#     return {"message": "Successfully logged out"}


# @router.post("/reset-password-request")
# async def reset_password_request(
#     email: str = Body(..., embed=True),
#     db: AsyncSession = Depends(get_db)
# ) -> dict
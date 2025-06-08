# rag-studio/backend/app/utils/logger.py
"""
로깅 설정 모듈

구조화된 로깅을 위한 설정을 제공합니다.
"""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from pythonjsonlogger import jsonlogger

from app.core.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    커스텀 JSON 포매터
    
    로그 메시지를 구조화된 JSON 형식으로 변환합니다.
    """
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        """
        로그 레코드에 추가 필드 삽입
        """
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # 타임스탬프 추가
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # 로그 레벨 추가
        log_record['level'] = record.levelname
        
        # 모듈 정보 추가
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # 애플리케이션 정보 추가
        log_record['app_name'] = settings.APP_NAME
        log_record['app_version'] = settings.APP_VERSION
        
        # 환경 정보
        log_record['environment'] = "development" if settings.DEBUG else "production"


def setup_logger(
    name: Optional[str] = None,
    level: Optional[str] = None,
    log_file: Optional[Path] = None
) -> logging.Logger:
    """
    로거 설정
    
    Args:
        name: 로거 이름
        level: 로그 레벨
        log_file: 로그 파일 경로
        
    Returns:
        logging.Logger: 설정된 로거
    """
    # 로거 생성
    logger = logging.getLogger(name or settings.APP_NAME)
    
    # 로그 레벨 설정
    log_level = getattr(logging, level or settings.LOG_LEVEL.upper())
    logger.setLevel(log_level)
    
    # 기존 핸들러 제거
    logger.handlers = []
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    if settings.DEBUG:
        # 개발 환경: 읽기 쉬운 포맷
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # 프로덕션 환경: JSON 포맷
        formatter = CustomJsonFormatter()
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 설정 (선택적)
    if log_file:
        # 로그 디렉토리 생성
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(file_handler)
    
    # 프로파게이션 방지
    logger.propagate = False
    
    return logger


# 전역 로거 인스턴스
logger = setup_logger()


# 특수 로거들
access_logger = setup_logger("access", "INFO")
error_logger = setup_logger("error", "ERROR")
audit_logger = setup_logger("audit", "INFO")


def log_request(
    request_id: str,
    method: str,
    path: str,
    client_ip: str,
    user_id: Optional[str] = None,
    **kwargs
):
    """
    API 요청 로깅
    
    Args:
        request_id: 요청 ID
        method: HTTP 메서드
        path: 요청 경로
        client_ip: 클라이언트 IP
        user_id: 사용자 ID
        **kwargs: 추가 정보
    """
    access_logger.info(
        "API Request",
        extra={
            "request_id": request_id,
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "user_id": user_id,
            **kwargs
        }
    )


def log_response(
    request_id: str,
    status_code: int,
    response_time: float,
    **kwargs
):
    """
    API 응답 로깅
    
    Args:
        request_id: 요청 ID
        status_code: HTTP 상태 코드
        response_time: 응답 시간 (초)
        **kwargs: 추가 정보
    """
    access_logger.info(
        "API Response",
        extra={
            "request_id": request_id,
            "status_code": status_code,
            "response_time_ms": int(response_time * 1000),
            **kwargs
        }
    )


def log_error(
    error_type: str,
    error_message: str,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs
):
    """
    에러 로깅
    
    Args:
        error_type: 에러 타입
        error_message: 에러 메시지
        request_id: 요청 ID
        user_id: 사용자 ID
        **kwargs: 추가 정보
    """
    error_logger.error(
        f"{error_type}: {error_message}",
        extra={
            "error_type": error_type,
            "request_id": request_id,
            "user_id": user_id,
            **kwargs
        },
        exc_info=True
    )


def log_audit(
    action: str,
    resource_type: str,
    resource_id: str,
    user_id: str,
    result: str,
    **kwargs
):
    """
    감사 로깅 (중요 작업 추적)
    
    Args:
        action: 수행된 작업
        resource_type: 리소스 타입
        resource_id: 리소스 ID
        user_id: 수행한 사용자 ID
        result: 작업 결과
        **kwargs: 추가 정보
    """
    audit_logger.info(
        f"Audit: {action} on {resource_type}",
        extra={
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": user_id,
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
    )
# rag-studio/backend/app/api/v1/websocket.py
"""
WebSocket API 엔드포인트

실시간 파이프라인 실행 상태 업데이트 및 로그 스트리밍을 제공합니다.
"""

import json
import asyncio
from typing import Dict, Set, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.exceptions import WebSocketException

from app.core.logger import logger
from app.core.security import verify_token

router = APIRouter()

# 연결된 WebSocket 클라이언트 관리
class ConnectionManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        # 활성 연결: {user_id: {connection_id: websocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # 구독 관리: {topic: set(user_ids)}
        self.subscriptions: Dict[str, Set[str]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str, connection_id: str):
        """새 WebSocket 연결 수락"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        
        self.active_connections[user_id][connection_id] = websocket
        logger.info(f"WebSocket 연결 수립: user={user_id}, conn={connection_id}")
        
    def disconnect(self, user_id: str, connection_id: str):
        """WebSocket 연결 종료"""
        if user_id in self.active_connections:
            self.active_connections[user_id].pop(connection_id, None)
            
            # 사용자의 모든 연결이 종료되면 딕셔너리에서 제거
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
                # 구독도 정리
                for topic, subscribers in self.subscriptions.items():
                    subscribers.discard(user_id)
        
        logger.info(f"WebSocket 연결 종료: user={user_id}, conn={connection_id}")
    
    def subscribe(self, user_id: str, topic: str):
        """토픽 구독"""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = set()
        
        self.subscriptions[topic].add(user_id)
        logger.info(f"토픽 구독: user={user_id}, topic={topic}")
    
    def unsubscribe(self, user_id: str, topic: str):
        """토픽 구독 해제"""
        if topic in self.subscriptions:
            self.subscriptions[topic].discard(user_id)
            
            # 구독자가 없으면 토픽 제거
            if not self.subscriptions[topic]:
                del self.subscriptions[topic]
        
        logger.info(f"토픽 구독 해제: user={user_id}, topic={topic}")
    
    async def send_personal_message(self, message: Dict, user_id: str):
        """특정 사용자에게 메시지 전송"""
        if user_id in self.active_connections:
            disconnected = []
            
            for conn_id, websocket in self.active_connections[user_id].items():
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"메시지 전송 실패: {e}")
                    disconnected.append(conn_id)
            
            # 연결이 끊긴 클라이언트 정리
            for conn_id in disconnected:
                self.disconnect(user_id, conn_id)
    
    async def broadcast_to_topic(self, message: Dict, topic: str):
        """토픽 구독자들에게 브로드캐스트"""
        if topic in self.subscriptions:
            for user_id in self.subscriptions[topic]:
                await self.send_personal_message(message, user_id)
    
    async def broadcast_to_all(self, message: Dict):
        """모든 연결된 클라이언트에게 브로드캐스트"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)


# 전역 연결 관리자
manager = ConnectionManager()


@router.websocket("/pipeline/{pipeline_id}")
async def websocket_pipeline_endpoint(
    websocket: WebSocket,
    pipeline_id: str,
    token: Optional[str] = Query(None)
):
    """
    파이프라인 실행 상태 WebSocket 엔드포인트
    
    실시간으로 파이프라인 실행 상태와 로그를 스트리밍합니다.
    """
    # 토큰 검증
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return
    
    user_id = verify_token(token)
    if not user_id:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return
    
    # 연결 ID 생성
    connection_id = f"{pipeline_id}_{datetime.utcnow().timestamp()}"
    
    # 연결 수락
    await manager.connect(websocket, user_id, connection_id)
    
    # 파이프라인 토픽 구독
    topic = f"pipeline_{pipeline_id}"
    manager.subscribe(user_id, topic)
    
    try:
        # 초기 상태 전송
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "pipeline_id": pipeline_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # 클라이언트 메시지 처리
        while True:
            try:
                # 클라이언트로부터 메시지 수신
                data = await websocket.receive_json()
                
                # 메시지 타입에 따른 처리
                if data.get("type") == "ping":
                    # 핑퐁 처리
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                elif data.get("type") == "subscribe":
                    # 추가 토픽 구독
                    new_topic = data.get("topic")
                    if new_topic:
                        manager.subscribe(user_id, new_topic)
                        await websocket.send_json({
                            "type": "subscribed",
                            "topic": new_topic,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
                elif data.get("type") == "unsubscribe":
                    # 토픽 구독 해제
                    old_topic = data.get("topic")
                    if old_topic:
                        manager.unsubscribe(user_id, old_topic)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "topic": old_topic,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                logger.error(f"WebSocket 오류: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    finally:
        # 연결 종료 처리
        manager.unsubscribe(user_id, topic)
        manager.disconnect(user_id, connection_id)


@router.websocket("/benchmark/{benchmark_id}")
async def websocket_benchmark_endpoint(
    websocket: WebSocket,
    benchmark_id: str,
    token: Optional[str] = Query(None)
):
    """
    벤치마크 실행 상태 WebSocket 엔드포인트
    
    실시간으로 벤치마크 진행 상황을 스트리밍합니다.
    """
    # 토큰 검증
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return
    
    user_id = verify_token(token)
    if not user_id:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return
    
    # 연결 ID 생성
    connection_id = f"{benchmark_id}_{datetime.utcnow().timestamp()}"
    
    # 연결 수락
    await manager.connect(websocket, user_id, connection_id)
    
    # 벤치마크 토픽 구독
    topic = f"benchmark_{benchmark_id}"
    manager.subscribe(user_id, topic)
    
    try:
        # 초기 상태 전송
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "benchmark_id": benchmark_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # 연결 유지
        while True:
            try:
                # 클라이언트 메시지 대기
                data = await websocket.receive_json()
                
                # 핑퐁 처리
                if data.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket 오류: {str(e)}")
                break
                
    finally:
        # 연결 종료 처리
        manager.unsubscribe(user_id, topic)
        manager.disconnect(user_id, connection_id)


# 헬퍼 함수들 (다른 모듈에서 사용)

async def notify_pipeline_status(pipeline_id: str, status: str, message: str = None):
    """파이프라인 상태 알림"""
    await manager.broadcast_to_topic(
        {
            "type": "pipeline_status",
            "pipeline_id": pipeline_id,
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        },
        f"pipeline_{pipeline_id}"
    )


async def notify_pipeline_progress(pipeline_id: str, progress: float, stage: str = None):
    """파이프라인 진행률 알림"""
    await manager.broadcast_to_topic(
        {
            "type": "pipeline_progress",
            "pipeline_id": pipeline_id,
            "progress": progress,
            "stage": stage,
            "timestamp": datetime.utcnow().isoformat()
        },
        f"pipeline_{pipeline_id}"
    )


async def notify_benchmark_progress(
    benchmark_id: str, 
    current: int, 
    total: int, 
    pipeline_id: str = None
):
    """벤치마크 진행률 알림"""
    await manager.broadcast_to_topic(
        {
            "type": "benchmark_progress",
            "benchmark_id": benchmark_id,
            "current": current,
            "total": total,
            "progress": (current / total) * 100 if total > 0 else 0,
            "pipeline_id": pipeline_id,
            "timestamp": datetime.utcnow().isoformat()
        },
        f"benchmark_{benchmark_id}"
    )


async def notify_benchmark_result(
    benchmark_id: str,
    pipeline_id: str,
    metrics: Dict
):
    """벤치마크 결과 알림"""
    await manager.broadcast_to_topic(
        {
            "type": "benchmark_result",
            "benchmark_id": benchmark_id,
            "pipeline_id": pipeline_id,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        },
        f"benchmark_{benchmark_id}"
    )
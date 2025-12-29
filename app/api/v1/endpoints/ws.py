"""
WebSocket endpoints for real-time task progress tracking.
Streams Celery task progress updates to connected clients.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from redis.asyncio import Redis

from app.core.config import settings
from app.infra.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections for task progress streaming.
    Supports multiple clients subscribing to the same task.
    """
    
    def __init__(self):
        # task_id -> list of WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, task_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        async with self._lock:
            if task_id not in self.active_connections:
                self.active_connections[task_id] = []
            self.active_connections[task_id].append(websocket)
        
        logger.info(f"WebSocket connected for task {task_id}")
    
    async def disconnect(self, websocket: WebSocket, task_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if task_id in self.active_connections:
                if websocket in self.active_connections[task_id]:
                    self.active_connections[task_id].remove(websocket)
                # Clean up empty task entries
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
        
        logger.info(f"WebSocket disconnected for task {task_id}")
    
    async def send_to_task(self, task_id: str, data: dict[str, Any]) -> None:
        """Send message to all connections subscribed to a task."""
        async with self._lock:
            connections = self.active_connections.get(task_id, [])
        
        disconnected = []
        for connection in connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            await self.disconnect(conn, task_id)
    
    async def broadcast(self, data: dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        async with self._lock:
            all_connections = [
                conn 
                for conns in self.active_connections.values() 
                for conn in conns
            ]
        
        for connection in all_connections:
            try:
                await connection.send_json(data)
            except Exception:
                pass
    
    def get_connection_count(self, task_id: str | None = None) -> int:
        """Get number of active connections."""
        if task_id:
            return len(self.active_connections.get(task_id, []))
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager instance
manager = ConnectionManager()


async def get_task_progress_from_redis(redis: Redis, task_id: str) -> dict[str, Any] | None:
    """Fetch current task progress from Redis."""
    key = f"task_progress:{task_id}"
    data = await redis.get(key)
    
    if data:
        return json.loads(data)
    return None


async def subscribe_to_task_updates(
    redis: Redis,
    task_id: str,
    websocket: WebSocket,
) -> None:
    """
    Subscribe to Redis pub/sub channel for task updates.
    Streams updates to WebSocket client until task completes or client disconnects.
    
    Enhanced with retry information for failed tasks.
    """
    pubsub = redis.pubsub()
    channel = f"task_updates:{task_id}"
    
    try:
        await pubsub.subscribe(channel)
        logger.info(f"Subscribed to channel: {channel}")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    status = data.get("status")
                    
                    # Determine message type based on status
                    if status == "failed":
                        # Send enhanced error message with retry info
                        await websocket.send_json({
                            "type": "failed",
                            "data": data,
                            "error": data.get("error"),
                            "error_type": data.get("error_type", "unknown"),
                            "can_retry": data.get("can_retry", False),
                            "retry_after": data.get("retry_after"),
                            "api_errors": data.get("api_errors", []),
                            "has_fallback_data": data.get("has_fallback_data", False),
                            "message": data.get("message", "Task failed"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    elif status == "completed":
                        # Send completion with any fallback info
                        await websocket.send_json({
                            "type": "completed",
                            "data": data,
                            "has_fallback_data": data.get("has_fallback_data", False),
                            "api_errors": data.get("api_errors", []),
                            "message": data.get("message", "Task completed"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    else:
                        # Regular progress update
                        await websocket.send_json({
                            "type": "progress",
                            "data": data,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    
                    # Check if task reached terminal state
                    if status in ("completed", "failed", "cancelled"):
                        logger.info(f"Task {task_id} reached terminal state: {status}")
                        break
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in pub/sub message for task {task_id}")
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected during pub/sub for task {task_id}")
                    break
                    
    except asyncio.CancelledError:
        logger.info(f"Subscription cancelled for task {task_id}")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


@router.websocket("/ws/itinerary/{task_id}")
async def websocket_task_progress(
    websocket: WebSocket,
    task_id: str,
) -> None:
    """
    WebSocket endpoint for real-time task progress tracking.
    
    Connects to Redis pub/sub to stream progress updates for a specific task.
    
    Message Types Sent:
    - connected: Initial connection confirmation with current status
    - progress: Task progress update (step, percentage, message)
    - completed: Task finished successfully
    - failed: Task failed with error
    - ping: Keep-alive ping
    
    Message Format:
    ```json
    {
        "type": "progress",
        "data": {
            "task_id": "uuid",
            "status": "progress",
            "step": "searching_flights",
            "progress": 35,
            "message": "Searching for best flight options..."
        },
        "timestamp": "2025-01-01T00:00:00Z"
    }
    ```
    """
    await manager.connect(websocket, task_id)
    redis: Redis | None = None
    
    try:
        # Get Redis connection
        redis = await get_redis()
        
        # Send initial status
        current_progress = await get_task_progress_from_redis(redis, task_id)
        
        if current_progress:
            await websocket.send_json({
                "type": "connected",
                "data": current_progress,
                "message": "Connected to task progress stream",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            # If task already completed, send final status and close
            if current_progress.get("status") in ("completed", "failed", "cancelled"):
                await websocket.send_json({
                    "type": current_progress.get("status"),
                    "data": current_progress,
                    "message": f"Task already {current_progress.get('status')}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return
        else:
            # Task not found - might be pending or invalid
            await websocket.send_json({
                "type": "connected",
                "data": {
                    "task_id": task_id,
                    "status": "pending",
                    "progress": 0,
                    "message": "Waiting for task to start...",
                },
                "message": "Connected, waiting for task updates",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        
        # Create tasks for pub/sub and ping
        pubsub_task = asyncio.create_task(
            subscribe_to_task_updates(redis, task_id, websocket)
        )
        ping_task = asyncio.create_task(
            send_periodic_ping(websocket, task_id, redis)
        )
        
        try:
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [pubsub_task, ping_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except WebSocketDisconnect:
            pubsub_task.cancel()
            ping_task.cancel()
            raise
            
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
    finally:
        await manager.disconnect(websocket, task_id)


async def send_periodic_ping(
    websocket: WebSocket,
    task_id: str,
    redis: Redis,
    interval: float = 15.0,
) -> None:
    """
    Send periodic ping messages to keep connection alive.
    Also checks task status in case pub/sub message was missed.
    """
    try:
        while True:
            await asyncio.sleep(interval)
            
            # Check current status
            current_progress = await get_task_progress_from_redis(redis, task_id)
            
            await websocket.send_json({
                "type": "ping",
                "data": current_progress if current_progress else {"task_id": task_id},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            # Exit if task completed
            if current_progress and current_progress.get("status") in ("completed", "failed", "cancelled"):
                break
                
    except asyncio.CancelledError:
        pass
    except WebSocketDisconnect:
        raise
    except Exception as e:
        logger.warning(f"Ping error for task {task_id}: {e}")


@router.websocket("/ws/itinerary/batch")
async def websocket_batch_progress(
    websocket: WebSocket,
) -> None:
    """
    WebSocket endpoint for tracking multiple tasks simultaneously.
    
    Client sends task IDs to subscribe:
    ```json
    {"action": "subscribe", "task_ids": ["id1", "id2"]}
    {"action": "unsubscribe", "task_ids": ["id1"]}
    ```
    
    Server streams progress for all subscribed tasks.
    """
    await websocket.accept()
    subscribed_tasks: set[str] = set()
    redis: Redis | None = None
    
    try:
        redis = await get_redis()
        
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to batch progress stream. Send subscribe/unsubscribe actions.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Handle incoming messages and stream updates
        receive_task = asyncio.create_task(handle_batch_messages(websocket, subscribed_tasks))
        stream_task = asyncio.create_task(stream_batch_updates(websocket, subscribed_tasks, redis))
        
        try:
            done, pending = await asyncio.wait(
                [receive_task, stream_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except WebSocketDisconnect:
            receive_task.cancel()
            stream_task.cancel()
            raise
            
    except WebSocketDisconnect:
        logger.info("Batch WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Batch WebSocket error: {e}")
    finally:
        subscribed_tasks.clear()


async def handle_batch_messages(
    websocket: WebSocket,
    subscribed_tasks: set[str],
) -> None:
    """Handle incoming messages for batch subscription management."""
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            task_ids = data.get("task_ids", [])
            
            if action == "subscribe":
                subscribed_tasks.update(task_ids)
                await websocket.send_json({
                    "type": "subscribed",
                    "task_ids": list(subscribed_tasks),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            elif action == "unsubscribe":
                subscribed_tasks.difference_update(task_ids)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "task_ids": task_ids,
                    "remaining": list(subscribed_tasks),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                
    except WebSocketDisconnect:
        raise
    except Exception as e:
        logger.warning(f"Error handling batch message: {e}")


async def stream_batch_updates(
    websocket: WebSocket,
    subscribed_tasks: set[str],
    redis: Redis,
    interval: float = 2.0,
) -> None:
    """
    Stream progress updates for all subscribed tasks.
    Uses polling approach for simplicity with multiple tasks.
    """
    try:
        while True:
            await asyncio.sleep(interval)
            
            if not subscribed_tasks:
                continue
            
            updates = []
            completed_tasks = []
            
            for task_id in list(subscribed_tasks):
                progress = await get_task_progress_from_redis(redis, task_id)
                if progress:
                    updates.append(progress)
                    
                    # Mark completed tasks for removal
                    if progress.get("status") in ("completed", "failed", "cancelled"):
                        completed_tasks.append(task_id)
            
            if updates:
                await websocket.send_json({
                    "type": "batch_progress",
                    "data": updates,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            
            # Auto-unsubscribe from completed tasks
            for task_id in completed_tasks:
                subscribed_tasks.discard(task_id)
                
    except asyncio.CancelledError:
        pass
    except WebSocketDisconnect:
        raise
    except Exception as e:
        logger.warning(f"Error streaming batch updates: {e}")


# ============ Proactive Alerts WebSocket ============


class AlertConnectionManager:
    """
    Manages WebSocket connections for proactive travel alerts.
    Users subscribe by user_id to receive alerts about their itineraries.
    """
    
    def __init__(self):
        # user_id -> list of WebSocket connections
        self.user_connections: dict[str, list[WebSocket]] = {}
        # itinerary_id -> list of WebSocket connections
        self.itinerary_connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect_user(self, websocket: WebSocket, user_id: str) -> None:
        """Connect user for receiving alerts."""
        await websocket.accept()
        
        async with self._lock:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(websocket)
        
        logger.info(f"Alert WebSocket connected for user {user_id}")
    
    async def connect_itinerary(self, websocket: WebSocket, itinerary_id: str) -> None:
        """Connect client for alerts about specific itinerary."""
        await websocket.accept()
        
        async with self._lock:
            if itinerary_id not in self.itinerary_connections:
                self.itinerary_connections[itinerary_id] = []
            self.itinerary_connections[itinerary_id].append(websocket)
        
        logger.info(f"Alert WebSocket connected for itinerary {itinerary_id}")
    
    async def disconnect_user(self, websocket: WebSocket, user_id: str) -> None:
        """Disconnect user WebSocket."""
        async with self._lock:
            if user_id in self.user_connections:
                if websocket in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
        
        logger.info(f"Alert WebSocket disconnected for user {user_id}")
    
    async def disconnect_itinerary(self, websocket: WebSocket, itinerary_id: str) -> None:
        """Disconnect itinerary WebSocket."""
        async with self._lock:
            if itinerary_id in self.itinerary_connections:
                if websocket in self.itinerary_connections[itinerary_id]:
                    self.itinerary_connections[itinerary_id].remove(websocket)
                if not self.itinerary_connections[itinerary_id]:
                    del self.itinerary_connections[itinerary_id]
        
        logger.info(f"Alert WebSocket disconnected for itinerary {itinerary_id}")
    
    async def send_to_user(self, user_id: str, alert: dict[str, Any]) -> int:
        """Send alert to all connections for a user. Returns number sent."""
        async with self._lock:
            connections = self.user_connections.get(user_id, [])[:]
        
        sent = 0
        disconnected = []
        
        for conn in connections:
            try:
                await conn.send_json(alert)
                sent += 1
            except Exception:
                disconnected.append(conn)
        
        for conn in disconnected:
            await self.disconnect_user(conn, user_id)
        
        return sent
    
    async def send_to_itinerary(self, itinerary_id: str, alert: dict[str, Any]) -> int:
        """Send alert to all connections for an itinerary. Returns number sent."""
        async with self._lock:
            connections = self.itinerary_connections.get(itinerary_id, [])[:]
        
        sent = 0
        disconnected = []
        
        for conn in connections:
            try:
                await conn.send_json(alert)
                sent += 1
            except Exception:
                disconnected.append(conn)
        
        for conn in disconnected:
            await self.disconnect_itinerary(conn, itinerary_id)
        
        return sent


# Global alert manager
alert_manager = AlertConnectionManager()


@router.websocket("/ws/alerts/user/{user_id}")
async def websocket_user_alerts(
    websocket: WebSocket,
    user_id: str,
) -> None:
    """
    WebSocket endpoint for receiving proactive travel alerts for a user.
    
    Alerts include:
    - Weather warnings affecting itineraries
    - Traffic alerts for upcoming travel
    - Crowd warnings for popular venues
    - Venue closures
    - Flight/hotel changes
    
    Message Format:
    ```json
    {
        "type": "alert",
        "alert_type": "weather_warning",
        "data": {
            "itinerary_id": "uuid",
            "severity": "warning",
            "title": "Rain Expected",
            "message": "Heavy rain expected tomorrow...",
            "affected_day": 2,
            "affected_activities": ["act_123"],
            "action_url": "/replan/uuid",
            "action_text": "View alternatives"
        },
        "timestamp": "2025-01-01T00:00:00Z"
    }
    ```
    """
    await alert_manager.connect_user(websocket, user_id)
    redis: Redis | None = None
    
    try:
        redis = await get_redis()
        
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to alert stream",
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Subscribe to user's alert channel
        await subscribe_to_user_alerts(redis, user_id, websocket)
        
    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from alerts")
    except Exception as e:
        logger.error(f"Alert WebSocket error for user {user_id}: {e}")
    finally:
        await alert_manager.disconnect_user(websocket, user_id)


@router.websocket("/ws/alerts/itinerary/{itinerary_id}")
async def websocket_itinerary_alerts(
    websocket: WebSocket,
    itinerary_id: str,
) -> None:
    """
    WebSocket endpoint for receiving proactive alerts for a specific itinerary.
    
    Useful when viewing a single itinerary - only receives alerts for that trip.
    """
    await alert_manager.connect_itinerary(websocket, itinerary_id)
    redis: Redis | None = None
    
    try:
        redis = await get_redis()
        
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to itinerary alert stream",
            "itinerary_id": itinerary_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Subscribe to itinerary's alert channel
        await subscribe_to_itinerary_alerts(redis, itinerary_id, websocket)
        
    except WebSocketDisconnect:
        logger.info(f"Itinerary {itinerary_id} alert connection disconnected")
    except Exception as e:
        logger.error(f"Alert WebSocket error for itinerary {itinerary_id}: {e}")
    finally:
        await alert_manager.disconnect_itinerary(websocket, itinerary_id)


async def subscribe_to_user_alerts(
    redis: Redis,
    user_id: str,
    websocket: WebSocket,
) -> None:
    """Subscribe to Redis pub/sub channel for user alerts."""
    pubsub = redis.pubsub()
    channel = f"user_alerts:{user_id}"
    
    try:
        await pubsub.subscribe(channel)
        logger.info(f"Subscribed to alert channel: {channel}")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json({
                        "type": "alert",
                        "alert_type": data.get("alert_type", "general"),
                        "data": data,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in alert for user {user_id}")
                except WebSocketDisconnect:
                    break
                    
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


async def subscribe_to_itinerary_alerts(
    redis: Redis,
    itinerary_id: str,
    websocket: WebSocket,
) -> None:
    """Subscribe to Redis pub/sub channel for itinerary alerts."""
    pubsub = redis.pubsub()
    channel = f"itinerary_alerts:{itinerary_id}"
    
    try:
        await pubsub.subscribe(channel)
        logger.info(f"Subscribed to alert channel: {channel}")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json({
                        "type": "alert",
                        "alert_type": data.get("alert_type", "general"),
                        "data": data,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in alert for itinerary {itinerary_id}")
                except WebSocketDisconnect:
                    break
                    
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


# ============ Alert Publishing Utility ============


async def publish_proactive_alert(
    redis: Redis,
    user_id: str | None,
    itinerary_id: str,
    alert_payload: dict[str, Any],
) -> None:
    """
    Publish a proactive alert to Redis for WebSocket delivery.
    
    Args:
        redis: Redis connection
        user_id: User ID to notify (optional)
        itinerary_id: Itinerary ID
        alert_payload: Alert data (ProactiveAlertPayload as dict)
    """
    # Publish to itinerary channel
    itinerary_channel = f"itinerary_alerts:{itinerary_id}"
    await redis.publish(itinerary_channel, json.dumps(alert_payload))
    
    # Also publish to user channel if user_id provided
    if user_id:
        user_channel = f"user_alerts:{user_id}"
        await redis.publish(user_channel, json.dumps(alert_payload))
    
    logger.info(f"Published proactive alert for itinerary {itinerary_id}")

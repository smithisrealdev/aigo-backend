"""
AiGo Backend - Task Progress Tracking Service
Provides real-time task progress tracking via Redis
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings


class TaskStatus(str, Enum):
    """Task execution status."""
    
    PENDING = "pending"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskStep(str, Enum):
    """Itinerary generation steps."""
    
    # Initial steps
    INITIALIZING = "initializing"
    VALIDATING = "validating"
    
    # Processing steps
    EXTRACTING_PARAMS = "extracting_params"
    SEARCHING_FLIGHTS = "searching_flights"
    SEARCHING_HOTELS = "searching_hotels"
    CHECKING_WEATHER = "checking_weather"
    FETCHING_ATTRACTIONS = "fetching_attractions"
    
    # AI Generation steps
    ANALYZING_PREFERENCES = "analyzing_preferences"
    GENERATING_PLAN = "generating_plan"
    OPTIMIZING_ROUTE = "optimizing_route"
    
    # Final steps
    SAVING_ITINERARY = "saving_itinerary"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskProgress:
    """Task progress information."""
    
    task_id: str
    status: TaskStatus
    step: TaskStep | str
    progress: int  # 0-100
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    # Enhanced error handling fields
    error_type: str | None = None  # rate_limit, timeout, network_error, etc.
    error_code: str | None = None  # API-specific error codes
    can_retry: bool = False  # Whether the task can be retried
    retry_after: int | None = None  # Seconds to wait before retry (for rate limits)
    api_errors: list[dict[str, Any]] = field(default_factory=list)  # Per-API error details
    has_fallback_data: bool = False  # Whether fallback data was used
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "step": self.step.value if isinstance(self.step, TaskStep) else self.step,
            "progress": self.progress,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "error_type": self.error_type,
            "error_code": self.error_code,
            "can_retry": self.can_retry,
            "retry_after": self.retry_after,
            "api_errors": self.api_errors,
            "has_fallback_data": self.has_fallback_data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskProgress":
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            status=TaskStatus(data["status"]),
            step=data["step"],
            progress=data["progress"],
            message=data["message"],
            data=data.get("data", {}),
            error=data.get("error"),
            error_type=data.get("error_type"),
            error_code=data.get("error_code"),
            can_retry=data.get("can_retry", False),
            retry_after=data.get("retry_after"),
            api_errors=data.get("api_errors", []),
            has_fallback_data=data.get("has_fallback_data", False),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class TaskProgressTracker:
    """
    Synchronous task progress tracker for use within Celery tasks.
    Uses synchronous Redis client.
    """
    
    # Redis key prefixes
    PROGRESS_KEY_PREFIX = "task_progress"
    CHANNEL_PREFIX = "task_updates"
    TASK_LIST_KEY = "active_tasks"
    
    # TTL for progress data (1 hour)
    PROGRESS_TTL = 3600
    
    def __init__(self, redis_url: str | None = None):
        """Initialize tracker with Redis connection."""
        self.redis_url = redis_url or settings.CELERY_BROKER_URL
        self._redis: Redis | None = None
    
    @property
    def redis(self) -> Redis:
        """Get Redis client, creating if needed."""
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            self._redis.close()
            self._redis = None
    
    def _get_progress_key(self, task_id: str) -> str:
        """Get Redis key for task progress."""
        return f"{self.PROGRESS_KEY_PREFIX}:{task_id}"
    
    def _get_channel(self, task_id: str) -> str:
        """Get Redis pub/sub channel for task updates."""
        return f"{self.CHANNEL_PREFIX}:{task_id}"
    
    def update(
        self,
        task_id: str,
        status: TaskStatus,
        step: TaskStep | str,
        progress: int,
        message: str,
        data: dict[str, Any] | None = None,
        error: str | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
        can_retry: bool = False,
        retry_after: int | None = None,
        api_errors: list[dict[str, Any]] | None = None,
        has_fallback_data: bool = False,
    ) -> TaskProgress:
        """
        Update task progress and publish to subscribers.
        
        Args:
            task_id: Unique task identifier
            status: Current task status
            step: Current processing step
            progress: Progress percentage (0-100)
            message: Human-readable status message
            data: Optional additional data
            error: Error message if failed
            error_type: Type of error (rate_limit, timeout, etc.)
            error_code: API-specific error code
            can_retry: Whether the task can be retried
            retry_after: Seconds to wait before retry
            api_errors: List of per-API error details
            has_fallback_data: Whether fallback data was used
            
        Returns:
            Updated TaskProgress object
        """
        now = datetime.now(timezone.utc)
        
        # Get existing progress or create new
        existing = self.get(task_id)
        created_at = existing.created_at if existing else now
        
        task_progress = TaskProgress(
            task_id=task_id,
            status=status,
            step=step,
            progress=progress,
            message=message,
            data=data or {},
            error=error,
            error_type=error_type,
            error_code=error_code,
            can_retry=can_retry,
            retry_after=retry_after,
            api_errors=api_errors or [],
            has_fallback_data=has_fallback_data,
            created_at=created_at,
            updated_at=now,
        )
        
        # Store in Redis
        key = self._get_progress_key(task_id)
        self.redis.setex(key, self.PROGRESS_TTL, json.dumps(task_progress.to_dict()))
        
        # Add to active tasks set
        if status in (TaskStatus.PENDING, TaskStatus.STARTED, TaskStatus.PROGRESS):
            self.redis.sadd(self.TASK_LIST_KEY, task_id)
        else:
            self.redis.srem(self.TASK_LIST_KEY, task_id)
        
        # Publish update to channel
        channel = self._get_channel(task_id)
        self.redis.publish(channel, json.dumps(task_progress.to_dict()))
        
        return task_progress
    
    def get(self, task_id: str) -> TaskProgress | None:
        """Get current task progress."""
        key = self._get_progress_key(task_id)
        data = self.redis.get(key)
        
        if data:
            return TaskProgress.from_dict(json.loads(data))
        return None
    
    def get_active_tasks(self) -> list[str]:
        """Get list of active task IDs."""
        return list(self.redis.smembers(self.TASK_LIST_KEY))
    
    def delete(self, task_id: str) -> bool:
        """Delete task progress data."""
        key = self._get_progress_key(task_id)
        self.redis.srem(self.TASK_LIST_KEY, task_id)
        return bool(self.redis.delete(key))


class AsyncTaskProgressTracker:
    """
    Async task progress tracker for use in FastAPI endpoints.
    Uses async Redis client.
    """
    
    PROGRESS_KEY_PREFIX = "task_progress"
    CHANNEL_PREFIX = "task_updates"
    TASK_LIST_KEY = "active_tasks"
    PROGRESS_TTL = 3600
    
    def __init__(self, redis: AsyncRedis):
        """Initialize with async Redis client."""
        self.redis = redis
    
    def _get_progress_key(self, task_id: str) -> str:
        return f"{self.PROGRESS_KEY_PREFIX}:{task_id}"
    
    def _get_channel(self, task_id: str) -> str:
        return f"{self.CHANNEL_PREFIX}:{task_id}"
    
    async def get(self, task_id: str) -> TaskProgress | None:
        """Get current task progress."""
        key = self._get_progress_key(task_id)
        data = await self.redis.get(key)
        
        if data:
            return TaskProgress.from_dict(json.loads(data))
        return None
    
    async def get_active_tasks(self) -> list[str]:
        """Get list of active task IDs."""
        return list(await self.redis.smembers(self.TASK_LIST_KEY))
    
    async def get_multiple(self, task_ids: list[str]) -> dict[str, TaskProgress | None]:
        """Get progress for multiple tasks."""
        result = {}
        for task_id in task_ids:
            result[task_id] = await self.get(task_id)
        return result
    
    async def subscribe_to_task(self, task_id: str):
        """
        Subscribe to task updates via Redis pub/sub.
        Returns an async generator that yields TaskProgress updates.
        """
        pubsub = self.redis.pubsub()
        channel = self._get_channel(task_id)
        
        await pubsub.subscribe(channel)
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield TaskProgress.from_dict(data)
                    
                    # Stop if task completed or failed
                    if data["status"] in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
                        break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
    
    async def delete(self, task_id: str) -> bool:
        """Delete task progress data."""
        key = self._get_progress_key(task_id)
        await self.redis.srem(self.TASK_LIST_KEY, task_id)
        return bool(await self.redis.delete(key))


# Factory function for FastAPI dependency
async def get_task_tracker(redis: AsyncRedis) -> AsyncTaskProgressTracker:
    """Get async task progress tracker."""
    return AsyncTaskProgressTracker(redis)

"""Redis configuration and client management."""

import json
from typing import Any, AsyncIterator

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

# Redis connection pool
redis_pool: ConnectionPool | None = None
redis_client: Redis | None = None


async def init_redis() -> Redis:
    """Initialize Redis connection pool and client."""
    global redis_pool, redis_client

    redis_pool = ConnectionPool.from_url(
        str(settings.REDIS_URL),
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        decode_responses=True,
    )
    redis_client = Redis(connection_pool=redis_pool)

    # Test connection
    await redis_client.ping()

    return redis_client


async def get_redis() -> Redis:
    """Get Redis client instance."""
    if redis_client is None:
        return await init_redis()
    return redis_client


async def close_redis() -> None:
    """Close Redis connections."""
    global redis_pool, redis_client

    if redis_client:
        await redis_client.close()
        redis_client = None

    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None


class CacheService:
    """Service for caching operations."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.default_ttl = settings.REDIS_DEFAULT_TTL

    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        return await self.redis.get(key)

    async def set(
        self, key: str, value: str, ttl: int | None = None
    ) -> bool:
        """Set a value in cache with optional TTL."""
        return await self.redis.set(key, value, ex=ttl or self.default_ttl)

    async def delete(self, key: str) -> int:
        """Delete a key from cache."""
        return await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        return bool(await self.redis.exists(key))

    async def set_json(
        self, key: str, data: dict, ttl: int | None = None
    ) -> bool:
        """Set a JSON value in cache."""
        return await self.set(key, json.dumps(data), ttl)

    async def get_json(self, key: str) -> dict | None:
        """Get a JSON value from cache."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None


class TaskProgressService:
    """
    Service for task progress tracking via Redis.
    Used by FastAPI endpoints to query task status.
    """
    
    PROGRESS_KEY_PREFIX = "task_progress"
    CHANNEL_PREFIX = "task_updates"
    
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
    
    async def get_progress(self, task_id: str) -> dict[str, Any] | None:
        """Get current progress for a task."""
        key = f"{self.PROGRESS_KEY_PREFIX}:{task_id}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def subscribe_progress(self, task_id: str) -> AsyncIterator[dict[str, Any]]:
        """
        Subscribe to task progress updates.
        Yields progress updates as they occur.
        """
        pubsub = self.redis.pubsub()
        channel = f"{self.CHANNEL_PREFIX}:{task_id}"
        
        await pubsub.subscribe(channel)
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield data
                    
                    # Stop if terminal state
                    if data.get("status") in ("completed", "failed", "cancelled"):
                        break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
    
    async def get_user_active_tasks(self, user_id: str) -> list[dict[str, Any]]:
        """Get all active tasks for a user."""
        # Scan for user's task keys
        pattern = f"{self.PROGRESS_KEY_PREFIX}:*"
        tasks = []
        
        async for key in self.redis.scan_iter(match=pattern, count=100):
            data = await self.redis.get(key)
            if data:
                progress = json.loads(data)
                # Filter by user if user_id is in data
                if progress.get("data", {}).get("user_id") == user_id:
                    tasks.append(progress)
        
        return tasks

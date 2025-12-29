"""
AiGo Backend - Celery Application Configuration
Enhanced Celery setup with Redis broker and progress tracking
"""

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    
    celery = Celery(
        "aigo",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "app.domains.itinerary.tasks",
        ],
    )

    # Task serialization
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Bangkok",
        enable_utc=True,
    )

    # Task execution settings
    celery.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_time_limit=3600,  # 1 hour hard limit
        task_soft_time_limit=3300,  # 55 minutes soft limit
        task_track_started=True,  # Track when task starts
    )

    # Worker settings
    celery.conf.update(
        worker_prefetch_multiplier=1,
        worker_concurrency=4,
        worker_max_tasks_per_child=1000,
        worker_send_task_events=True,  # Send task events for monitoring
    )

    # Result settings
    celery.conf.update(
        result_expires=86400,  # 24 hours
        result_extended=True,
        result_backend_transport_options={
            "retry_policy": {
                "timeout": 5.0,
            }
        },
    )

    # Define task queues
    celery.conf.task_queues = (
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("itinerary", Exchange("itinerary"), routing_key="itinerary.#"),
        Queue("high_priority", Exchange("high_priority"), routing_key="high.#"),
    )

    celery.conf.task_default_queue = "default"
    celery.conf.task_default_exchange = "default"
    celery.conf.task_default_routing_key = "default"

    # Task routing
    celery.conf.task_routes = {
        "app.domains.itinerary.tasks.*": {"queue": "itinerary"},
        "app.domains.*.tasks.high_priority_*": {"queue": "high_priority"},
    }

    # Error handling & retry
    celery.conf.task_annotations = {
        "*": {
            "rate_limit": "100/m",
            "max_retries": 3,
            "default_retry_delay": 60,
            "autoretry_for": (Exception,),
            "retry_backoff": True,
            "retry_backoff_max": 600,
            "retry_jitter": True,
        },
        "app.domains.itinerary.tasks.generate_itinerary_task": {
            "rate_limit": "10/m",  # More restrictive for AI tasks
            "max_retries": 2,
            "time_limit": 600,  # 10 minutes
            "soft_time_limit": 540,  # 9 minutes
        },
    }

    # Beat schedule (for periodic tasks)
    celery.conf.beat_schedule = {
        # Example: cleanup stale tasks every hour
        # "cleanup-stale-tasks": {
        #     "task": "app.domains.itinerary.tasks.cleanup_stale_tasks",
        #     "schedule": crontab(minute=0),
        # },
    }

    return celery


# Create the Celery application instance
celery_app = create_celery_app()


# Task base class with progress tracking
class ProgressTask(celery_app.Task):
    """Base task class with progress tracking capabilities."""

    abstract = True
    
    def update_progress(
        self,
        task_id: str,
        step: str,
        progress: int,
        message: str,
        data: dict | None = None,
    ) -> None:
        """
        Update task progress in Redis for real-time tracking.
        
        Args:
            task_id: The task ID
            step: Current step name
            progress: Progress percentage (0-100)
            message: Human-readable status message
            data: Optional additional data
        """
        import json
        from redis import Redis
        
        redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
        
        progress_data = {
            "task_id": task_id,
            "step": step,
            "progress": progress,
            "message": message,
            "data": data or {},
            "timestamp": self._get_timestamp(),
        }
        
        # Store progress in Redis with TTL
        key = f"task_progress:{task_id}"
        redis_client.setex(key, 3600, json.dumps(progress_data))
        
        # Also publish to channel for WebSocket subscribers
        channel = f"task_updates:{task_id}"
        redis_client.publish(channel, json.dumps(progress_data))
        
        redis_client.close()

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        self.update_progress(
            task_id=task_id,
            step="completed",
            progress=100,
            message="Task completed successfully",
            data={"result": retval} if isinstance(retval, dict) else None,
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        import json
        from redis import Redis
        
        redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
        
        error_data = {
            "task_id": task_id,
            "step": "failed",
            "progress": -1,
            "message": f"Task failed: {str(exc)}",
            "error": str(exc),
            "timestamp": self._get_timestamp(),
        }
        
        key = f"task_progress:{task_id}"
        redis_client.setex(key, 3600, json.dumps(error_data))
        
        channel = f"task_updates:{task_id}"
        redis_client.publish(channel, json.dumps(error_data))
        
        redis_client.close()


# Register the base task class
celery_app.Task = ProgressTask

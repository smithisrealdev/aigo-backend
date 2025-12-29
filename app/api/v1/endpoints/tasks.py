"""
Task management API endpoints.
REST endpoints for starting and monitoring Celery tasks.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.domains.itinerary.tasks import generate_itinerary_task, update_itinerary_task
from app.infra.redis import get_redis, TaskProgressService

router = APIRouter()


# ============ Schemas ============


class GenerateItineraryRequest(BaseModel):
    """Request to generate a new itinerary from natural language."""
    
    prompt: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Natural language description of the trip",
        examples=["Plan a 7-day trip to Tokyo focusing on culture, food, and technology"],
    )
    preferences: dict[str, Any] | None = Field(
        default=None,
        description="Optional user preferences",
        examples=[{"budget": "medium", "pace": "relaxed", "interests": ["food", "history"]}],
    )


class UpdateItineraryRequest(BaseModel):
    """Request to update an existing itinerary."""
    
    itinerary_id: UUID = Field(..., description="ID of the itinerary to update")
    prompt: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Description of the changes to make",
        examples=["Add more food experiences on day 3"],
    )
    current_itinerary: dict[str, Any] = Field(
        ...,
        description="Current itinerary data to be updated",
    )


class TaskResponse(BaseModel):
    """Response after starting a task."""
    
    task_id: str = Field(..., description="Celery task ID for tracking")
    itinerary_id: str = Field(..., description="ID of the itinerary being generated")
    status: str = Field(..., description="Initial task status")
    message: str = Field(..., description="Human-readable message")
    websocket_url: str = Field(..., description="WebSocket URL for progress tracking")
    created_at: str = Field(..., description="Task creation timestamp")


class TaskProgressResponse(BaseModel):
    """Task progress information."""
    
    task_id: str
    status: str
    step: str | None = None
    progress: int
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TaskListResponse(BaseModel):
    """List of active tasks."""
    
    tasks: list[TaskProgressResponse]
    total: int


# ============ Dependencies ============


async def get_task_progress_service(
    redis: Redis = Depends(get_redis),
) -> TaskProgressService:
    """Get task progress service dependency."""
    return TaskProgressService(redis)


# TODO: Replace with actual auth
async def get_current_user_id() -> str:
    """Temporary placeholder for current user ID."""
    return "00000000-0000-0000-0000-000000000001"


# ============ Endpoints ============


@router.post(
    "/generate",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate itinerary from prompt",
    description="Start an async task to generate a travel itinerary from natural language.",
)
async def generate_itinerary(
    request: GenerateItineraryRequest,
    user_id: str = Depends(get_current_user_id),
) -> TaskResponse:
    """
    Generate a new itinerary from natural language prompt.
    
    This endpoint:
    1. Creates a new itinerary ID
    2. Dispatches a Celery task for async generation
    3. Returns task ID for progress tracking via WebSocket
    
    Track progress via WebSocket: ws://host/api/v1/ws/itinerary/{task_id}
    """
    # Generate itinerary ID
    itinerary_id = str(uuid4())
    
    # Dispatch Celery task
    result = generate_itinerary_task.delay(
        itinerary_id=itinerary_id,
        user_prompt=request.prompt,
        user_id=user_id,
        preferences=request.preferences,
    )
    
    task_id = result.id
    
    return TaskResponse(
        task_id=task_id,
        itinerary_id=itinerary_id,
        status="pending",
        message="Itinerary generation started. Connect to WebSocket for progress updates.",
        websocket_url=f"/api/v1/ws/itinerary/{task_id}",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post(
    "/update",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Update existing itinerary",
    description="Start an async task to update an existing itinerary based on feedback.",
)
async def update_itinerary_async(
    request: UpdateItineraryRequest,
    user_id: str = Depends(get_current_user_id),
) -> TaskResponse:
    """
    Update an existing itinerary based on user feedback.
    
    This endpoint dispatches a Celery task for async update.
    Track progress via WebSocket.
    """
    itinerary_id = str(request.itinerary_id)
    
    # Dispatch Celery task
    result = update_itinerary_task.delay(
        itinerary_id=itinerary_id,
        update_prompt=request.prompt,
        current_itinerary=request.current_itinerary,
    )
    
    task_id = result.id
    
    return TaskResponse(
        task_id=task_id,
        itinerary_id=itinerary_id,
        status="pending",
        message="Itinerary update started. Connect to WebSocket for progress updates.",
        websocket_url=f"/api/v1/ws/itinerary/{task_id}",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/{task_id}",
    response_model=TaskProgressResponse,
    summary="Get task progress",
    description="Get current progress of a specific task.",
)
async def get_task_progress(
    task_id: str,
    service: TaskProgressService = Depends(get_task_progress_service),
) -> TaskProgressResponse:
    """
    Get current progress of a task.
    
    For real-time updates, use the WebSocket endpoint instead.
    """
    progress = await service.get_progress(task_id)
    
    if not progress:
        # Check Celery result backend
        from app.infra.celery_app import celery_app
        
        result = celery_app.AsyncResult(task_id)
        
        if result.state == "PENDING":
            return TaskProgressResponse(
                task_id=task_id,
                status="pending",
                progress=0,
                message="Task is waiting to be processed",
            )
        elif result.state == "STARTED":
            return TaskProgressResponse(
                task_id=task_id,
                status="started",
                progress=5,
                message="Task has started processing",
            )
        elif result.state == "SUCCESS":
            return TaskProgressResponse(
                task_id=task_id,
                status="completed",
                progress=100,
                message="Task completed successfully",
                data=result.result if isinstance(result.result, dict) else {},
            )
        elif result.state == "FAILURE":
            return TaskProgressResponse(
                task_id=task_id,
                status="failed",
                progress=-1,
                message="Task failed",
                error=str(result.result),
            )
        else:
            return TaskProgressResponse(
                task_id=task_id,
                status=result.state.lower(),
                progress=0,
                message=f"Task state: {result.state}",
            )
    
    return TaskProgressResponse(
        task_id=progress.get("task_id", task_id),
        status=progress.get("status", "unknown"),
        step=progress.get("step"),
        progress=progress.get("progress", 0),
        message=progress.get("message", ""),
        data=progress.get("data", {}),
        error=progress.get("error"),
        created_at=progress.get("created_at"),
        updated_at=progress.get("updated_at"),
    )


@router.get(
    "/{task_id}/result",
    summary="Get task result",
    description="Get the final result of a completed task.",
)
async def get_task_result(
    task_id: str,
) -> dict[str, Any]:
    """
    Get the final result of a completed task.
    
    Returns the generated itinerary data if the task completed successfully.
    """
    from app.infra.celery_app import celery_app
    
    result = celery_app.AsyncResult(task_id)
    
    if not result.ready():
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail={
                "message": "Task is still processing",
                "state": result.state,
                "websocket_url": f"/api/v1/ws/itinerary/{task_id}",
            },
        )
    
    if result.failed():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Task failed",
                "error": str(result.result),
            },
        )
    
    return {
        "task_id": task_id,
        "status": "completed",
        "result": result.result,
    }


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel/revoke a task",
    description="Attempt to cancel a pending or running task.",
)
async def cancel_task(
    task_id: str,
    service: TaskProgressService = Depends(get_task_progress_service),
) -> None:
    """
    Cancel a pending or running task.
    
    Note: Tasks that have already started may not be immediately cancelled.
    """
    from app.infra.celery_app import celery_app
    
    # Revoke the task
    celery_app.control.revoke(task_id, terminate=True)
    
    # Update progress in Redis
    redis = service.redis
    key = f"task_progress:{task_id}"
    
    import json
    progress_data = {
        "task_id": task_id,
        "status": "cancelled",
        "step": "cancelled",
        "progress": -1,
        "message": "Task was cancelled by user",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await redis.setex(key, 3600, json.dumps(progress_data))
    
    # Publish cancellation
    channel = f"task_updates:{task_id}"
    await redis.publish(channel, json.dumps(progress_data))


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List active tasks",
    description="Get list of active tasks for the current user.",
)
async def list_tasks(
    service: TaskProgressService = Depends(get_task_progress_service),
    user_id: str = Depends(get_current_user_id),
) -> TaskListResponse:
    """
    List all active tasks for the current user.
    """
    tasks = await service.get_user_active_tasks(user_id)
    
    return TaskListResponse(
        tasks=[
            TaskProgressResponse(
                task_id=t.get("task_id", ""),
                status=t.get("status", "unknown"),
                step=t.get("step"),
                progress=t.get("progress", 0),
                message=t.get("message", ""),
                data=t.get("data", {}),
                error=t.get("error"),
                created_at=t.get("created_at"),
                updated_at=t.get("updated_at"),
            )
            for t in tasks
        ],
        total=len(tasks),
    )

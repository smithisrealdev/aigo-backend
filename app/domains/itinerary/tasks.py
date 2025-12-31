"""
AiGo Backend - Itinerary Generation Tasks
Celery tasks for async itinerary generation with progress tracking
Integrated with LangGraph AI workflow
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from app.infra.celery_app import celery_app
from app.infra.task_progress import (
    TaskProgressTracker,
    TaskStatus,
    TaskStep,
)

logger = logging.getLogger(__name__)


# ============ Step Configuration (for fallback and reference) ============


class ItineraryGenerationSteps:
    """Configuration for itinerary generation steps."""
    
    STEPS = [
        {
            "step": TaskStep.INITIALIZING,
            "progress": 5,
            "message": "🚀 Initializing itinerary generation...",
            "duration": 0.5,
        },
        {
            "step": TaskStep.VALIDATING,
            "progress": 10,
            "message": "✅ Validating request parameters...",
            "duration": 0.5,
        },
        {
            "step": TaskStep.EXTRACTING_PARAMS,
            "progress": 20,
            "message": "🔍 Extracting travel parameters from your request...",
            "duration": 2.0,
        },
        {
            "step": TaskStep.SEARCHING_FLIGHTS,
            "progress": 35,
            "message": "✈️ Searching for best flight options...",
            "duration": 3.0,
        },
        {
            "step": TaskStep.SEARCHING_HOTELS,
            "progress": 50,
            "message": "🏨 Finding accommodations...",
            "duration": 2.5,
        },
        {
            "step": TaskStep.CHECKING_WEATHER,
            "progress": 60,
            "message": "🌤️ Checking weather forecasts...",
            "duration": 1.5,
        },
        {
            "step": TaskStep.FETCHING_ATTRACTIONS,
            "progress": 70,
            "message": "🎯 Discovering local attractions...",
            "duration": 2.0,
        },
        {
            "step": TaskStep.ANALYZING_PREFERENCES,
            "progress": 80,
            "message": "🧠 Analyzing your preferences...",
            "duration": 1.5,
        },
        {
            "step": TaskStep.GENERATING_PLAN,
            "progress": 90,
            "message": "📝 AI is generating your personalized itinerary...",
            "duration": 3.0,
        },
        {
            "step": TaskStep.OPTIMIZING_ROUTE,
            "progress": 95,
            "message": "🗺️ Optimizing travel routes...",
            "duration": 1.0,
        },
        {
            "step": TaskStep.SAVING_ITINERARY,
            "progress": 98,
            "message": "💾 Saving your itinerary...",
            "duration": 0.5,
        },
    ]


# ============ Progress Callback for LangGraph ============


class LangGraphProgressCallback:
    """
    Progress callback adapter for LangGraph workflow.
    
    Translates LangGraph workflow steps to Celery task progress updates.
    """
    
    def __init__(self, task_id: str, tracker: TaskProgressTracker, itinerary_id: str):
        self.task_id = task_id
        self.tracker = tracker
        self.itinerary_id = itinerary_id
        
        # Map LangGraph steps to TaskStep
        self.step_mapping = {
            "intent_extraction": TaskStep.EXTRACTING_PARAMS,
            "data_gathering": TaskStep.SEARCHING_FLIGHTS,  # Combined flights/hotels/weather
            "itinerary_generation": TaskStep.GENERATING_PLAN,
            "route_optimization": TaskStep.OPTIMIZING_ROUTE,
            "monetization": TaskStep.GENERATING_PLAN,
            "finalization": TaskStep.SAVING_ITINERARY,
        }
    
    async def __call__(
        self,
        step: Any,
        progress: int,
        message: str,
    ) -> None:
        """Update progress via the tracker."""
        # Map LangGraph step to TaskStep
        step_value = step.value if hasattr(step, "value") else str(step)
        task_step = self.step_mapping.get(step_value, TaskStep.GENERATING_PLAN)
        
        self.tracker.update(
            task_id=self.task_id,
            status=TaskStatus.PROGRESS,
            step=task_step,
            progress=progress,
            message=message,
            data={"itinerary_id": self.itinerary_id},
        )


# ============ Main Celery Task ============


@celery_app.task(
    bind=True,
    name="app.domains.itinerary.tasks.generate_itinerary_task",
    max_retries=2,
    soft_time_limit=540,
    time_limit=600,
)
def generate_itinerary_task(
    self,
    itinerary_id: str,
    user_prompt: str,
    user_id: str | None = None,
    preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate travel itinerary based on user prompt using LangGraph AI workflow.
    
    This task processes the user's travel request through the Intelligence Engine:
    1. Intent Extraction - Parse natural language into structured parameters
    2. Data Gathering - Fetch flights, hotels, weather, attractions in parallel
    3. Itinerary Generation - AI creates day-by-day plans
    4. Route Optimization - Add transit details between activities
    5. Monetization - Inject affiliate booking links
    6. Finalization - Compile and save the complete itinerary
    
    Args:
        itinerary_id: Unique identifier for the itinerary
        user_prompt: Natural language travel request
        user_id: Optional user ID for personalization
        preferences: Optional user preferences
        
    Returns:
        Dictionary containing generated itinerary data
    """
    task_id = self.request.id
    tracker = TaskProgressTracker()
    
    try:
        # Initialize
        tracker.update(
            task_id=task_id,
            status=TaskStatus.STARTED,
            step=TaskStep.INITIALIZING,
            progress=0,
            message="🚀 Starting AI-powered itinerary generation...",
            data={
                "itinerary_id": itinerary_id,
                "user_prompt": user_prompt[:100] + "..." if len(user_prompt) > 100 else user_prompt,
            },
        )
        
        # Validate inputs
        tracker.update(
            task_id=task_id,
            status=TaskStatus.PROGRESS,
            step=TaskStep.VALIDATING,
            progress=5,
            message="✅ Validating request parameters...",
            data={"itinerary_id": itinerary_id},
        )
        
        if not user_prompt or len(user_prompt.strip()) < 10:
            raise ValueError("Please provide a more detailed travel request")
        
        # Create progress callback for LangGraph
        progress_callback = LangGraphProgressCallback(task_id, tracker, itinerary_id)
        
        # Run LangGraph workflow and save to DB in same event loop
        # This prevents "Future attached to different loop" errors in Python 3.14
        generated_itinerary, itinerary_dict = asyncio.run(
            _run_workflow_and_save(
                itinerary_id=itinerary_id,
                user_prompt=user_prompt,
                user_id=user_id,
                preferences=preferences,
                progress_callback=progress_callback,
                task_id=task_id,
                tracker=tracker,
            )
        )
        
        if not generated_itinerary:
            raise RuntimeError("AI workflow failed to generate itinerary")
        
        # Mark as completed
        tracker.update(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            step=TaskStep.COMPLETED,
            progress=100,
            message="🎉 Your itinerary is ready!",
            data={
                "itinerary_id": itinerary_id,
                "destination": itinerary_dict.get("destination"),
                "duration_days": itinerary_dict.get("duration_days"),
            },
        )
        
        logger.info(f"Itinerary {itinerary_id} generated and saved successfully")
        
        return {
            "success": True,
            "task_id": task_id,
            "itinerary_id": itinerary_id,
            "itinerary": itinerary_dict,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        
    except SoftTimeLimitExceeded:
        # Handle timeout gracefully
        logger.error(f"Task {task_id} timed out")
        tracker.update(
            task_id=task_id,
            status=TaskStatus.FAILED,
            step=TaskStep.FAILED,
            progress=-1,
            message="Task timed out. Please try again with a simpler request.",
            error="SoftTimeLimitExceeded",
            error_type="timeout",
            can_retry=True,
            retry_after=30,  # Suggest waiting 30 seconds
        )
        # Mark failed in database (using sync to avoid event loop issues)
        _mark_itinerary_failed_sync(itinerary_id, "Task timed out")
        raise
        
    except Exception as e:
        # Handle other errors with enhanced error classification
        logger.error(f"Task {task_id} failed: {e}")
        
        # Classify error type
        error_type = _classify_task_error(e)
        can_retry = error_type in ("timeout", "rate_limit", "network_error", "service_unavailable")
        retry_after = _get_retry_delay(error_type)
        
        tracker.update(
            task_id=task_id,
            status=TaskStatus.FAILED,
            step=TaskStep.FAILED,
            progress=-1,
            message=_get_user_friendly_error_message(e, error_type),
            error=str(e),
            error_type=error_type,
            can_retry=can_retry,
            retry_after=retry_after,
        )
        
        # Mark failed in database (using sync to avoid event loop issues)
        _mark_itinerary_failed_sync(itinerary_id, str(e))
        
        # Retry if attempts remaining and error is retriable
        if can_retry and self.request.retries < self.max_retries:
            tracker.update(
                task_id=task_id,
                status=TaskStatus.RETRYING,
                step=TaskStep.INITIALIZING,
                progress=0,
                message=f"Retrying... (attempt {self.request.retries + 2}/{self.max_retries + 1})",
            )
            raise self.retry(exc=e, countdown=retry_after or 30)
        
        raise
        
    finally:
        tracker.close()


def _classify_task_error(exception: Exception) -> str:
    """Classify an exception into an error type for the UI."""
    from app.domains.itinerary.tools.base import (
        RateLimitError,
        AuthenticationError,
    )
    
    exc_name = type(exception).__name__.lower()
    exc_msg = str(exception).lower()
    
    # Check specific exception types
    if isinstance(exception, RateLimitError):
        return "rate_limit"
    if isinstance(exception, AuthenticationError):
        return "authentication"
    if "timeout" in exc_name or "timeout" in exc_msg:
        return "timeout"
    if "rate" in exc_msg and "limit" in exc_msg:
        return "rate_limit"
    if "network" in exc_msg or "connection" in exc_msg:
        return "network_error"
    if "service" in exc_msg and ("unavailable" in exc_msg or "error" in exc_msg):
        return "service_unavailable"
    if "invalid" in exc_msg or "validation" in exc_msg:
        return "validation_error"
    
    return "unknown"


def _get_retry_delay(error_type: str) -> int | None:
    """Get recommended retry delay based on error type."""
    delays = {
        "rate_limit": 60,  # Wait 1 minute for rate limits
        "timeout": 30,  # 30 seconds for timeouts
        "network_error": 15,  # 15 seconds for network issues
        "service_unavailable": 45,  # 45 seconds for service issues
    }
    return delays.get(error_type)


def _get_user_friendly_error_message(exception: Exception, error_type: str) -> str:
    """Get a user-friendly error message based on error type."""
    messages = {
        "rate_limit": "🚦 Too many requests. Please wait a moment and try again.",
        "timeout": "⏱️ Request took too long. Try again with a simpler request.",
        "network_error": "🌐 Network connection issue. Please check your connection.",
        "service_unavailable": "🔧 External service temporarily unavailable. Please try again.",
        "authentication": "🔐 Authentication error. Please contact support.",
        "validation_error": "📝 Invalid request. Please check your input.",
        "unknown": f"❌ An error occurred: {str(exception)[:100]}",
    }
    return messages.get(error_type, messages["unknown"])


async def _run_langgraph_workflow(
    itinerary_id: str,
    user_prompt: str,
    user_id: str | None,
    preferences: dict[str, Any] | None,
    progress_callback: LangGraphProgressCallback,
):
    """
    Run the LangGraph planner workflow.
    
    Imports here to avoid circular imports and allow lazy loading.
    """
    from app.domains.itinerary.services.planner_graph import run_planner
    
    return await run_planner(
        itinerary_id=itinerary_id,
        user_prompt=user_prompt,
        user_id=user_id,
        preferences=preferences,
        progress_callback=progress_callback,
    )


async def _run_workflow_and_save(
    itinerary_id: str,
    user_prompt: str,
    user_id: str | None,
    preferences: dict[str, Any] | None,
    progress_callback: LangGraphProgressCallback,
    task_id: str,
    tracker: TaskProgressTracker,
) -> tuple[Any, dict[str, Any]]:
    """
    Run the LangGraph workflow and save to database in a single event loop.
    
    This prevents the "Future attached to different loop" error in Python 3.14+
    by keeping all async operations in the same event loop context.
    
    Returns:
        Tuple of (generated_itinerary, itinerary_dict)
    """
    # Run LangGraph workflow
    generated_itinerary = await _run_langgraph_workflow(
        itinerary_id=itinerary_id,
        user_prompt=user_prompt,
        user_id=user_id,
        preferences=preferences,
        progress_callback=progress_callback,
    )
    
    if not generated_itinerary:
        return None, {}
    
    # Convert to serializable dict
    itinerary_dict = generated_itinerary.model_dump(mode="json")
    
    # Save to database
    tracker.update(
        task_id=task_id,
        status=TaskStatus.PROGRESS,
        step=TaskStep.SAVING_ITINERARY,
        progress=98,
        message="💾 Saving your itinerary to database...",
        data={"itinerary_id": itinerary_id},
    )
    
    await _save_itinerary_to_db(
        itinerary_id=itinerary_id,
        itinerary_data=itinerary_dict,
    )
    
    return generated_itinerary, itinerary_dict


async def _save_itinerary_to_db(
    itinerary_id: str,
    itinerary_data: dict[str, Any],
) -> None:
    """
    Save AI-generated itinerary data to database.
    
    Uses async session factory for database operations within Celery task.
    """
    from datetime import date as date_type
    from uuid import UUID as UUIDType
    
    from app.infra.database import async_session_factory
    from app.domains.itinerary.repository import ItineraryRepository
    
    async with async_session_factory() as session:
        repo = ItineraryRepository(session)
        
        # Extract key fields from itinerary data
        update_fields = {
            "title": itinerary_data.get("title"),
            "destination": itinerary_data.get("destination"),
        }
        
        # Parse dates if present
        if itinerary_data.get("start_date"):
            start = itinerary_data["start_date"]
            update_fields["start_date"] = (
                date_type.fromisoformat(start) if isinstance(start, str) else start
            )
        
        if itinerary_data.get("end_date"):
            end = itinerary_data["end_date"]
            update_fields["end_date"] = (
                date_type.fromisoformat(end) if isinstance(end, str) else end
            )
        
        if itinerary_data.get("total_estimated_cost"):
            update_fields["total_budget"] = itinerary_data["total_estimated_cost"]
        
        if itinerary_data.get("currency"):
            update_fields["currency"] = itinerary_data["currency"]
        
        # Save full data to JSONB field
        await repo.save_generated_data(
            itinerary_id=UUIDType(itinerary_id),
            data=itinerary_data,
            update_fields=update_fields,
        )
        
        await session.commit()
        logger.info(f"Itinerary {itinerary_id} saved to database")


async def _mark_itinerary_failed(
    itinerary_id: str,
    error_message: str,
) -> None:
    """
    Mark itinerary as failed in database.
    """
    from uuid import UUID as UUIDType
    
    from app.infra.database import async_session_factory
    from app.domains.itinerary.repository import ItineraryRepository
    
    try:
        async with async_session_factory() as session:
            repo = ItineraryRepository(session)
            await repo.mark_generation_failed(
                itinerary_id=UUIDType(itinerary_id),
                error_message=error_message,
            )
            await session.commit()
            logger.info(f"Itinerary {itinerary_id} marked as failed")
    except Exception as e:
        logger.error(f"Failed to mark itinerary {itinerary_id} as failed: {e}")


def _mark_itinerary_failed_sync(
    itinerary_id: str,
    error_message: str,
) -> None:
    """
    Mark itinerary as failed using synchronous database connection.
    Used in exception handlers where asyncio event loop may be closed.
    
    Falls back to logging if synchronous database driver is not available.
    """
    import os
    from app.core.config import settings
    
    try:
        # Try using psycopg2 if available
        import psycopg2
        
        # Parse DATABASE_URL for psycopg2
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        cur.execute(
            """
            UPDATE itineraries 
            SET status = 'FAILED', 
                generation_error = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (error_message[:500], str(itinerary_id))  # Truncate error message
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Itinerary {itinerary_id} marked as failed (sync)")
    except ImportError:
        # psycopg2 not available, log warning but don't crash
        logger.warning(
            f"psycopg2 not available, cannot mark itinerary {itinerary_id} as failed in DB. "
            f"Error was: {error_message[:200]}"
        )
    except Exception as e:
        logger.error(f"Failed to mark itinerary {itinerary_id} as failed (sync): {e}")


# ============ Update Itinerary Task ============


@celery_app.task(
    bind=True,
    name="app.domains.itinerary.tasks.update_itinerary_task",
)
def update_itinerary_task(
    self,
    itinerary_id: str,
    update_prompt: str,
    current_itinerary: dict[str, Any],
) -> dict[str, Any]:
    """
    Update an existing itinerary based on user feedback.
    
    Args:
        itinerary_id: ID of itinerary to update
        update_prompt: User's update request
        current_itinerary: Current itinerary data
        
    Returns:
        Updated itinerary data
    """
    task_id = self.request.id
    tracker = TaskProgressTracker()
    
    try:
        tracker.update(
            task_id=task_id,
            status=TaskStatus.STARTED,
            step="analyzing_changes",
            progress=20,
            message="🔄 Analyzing your requested changes...",
        )
        
        time.sleep(1.5)
        
        tracker.update(
            task_id=task_id,
            status=TaskStatus.PROGRESS,
            step="updating_plan",
            progress=60,
            message="📝 Updating your itinerary...",
        )
        
        time.sleep(2.0)
        
        # Mock update - add update note
        updated_itinerary = current_itinerary.copy()
        updated_itinerary["last_updated"] = datetime.now(timezone.utc).isoformat()
        updated_itinerary["update_note"] = f"Updated based on: {update_prompt}"
        
        tracker.update(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            step=TaskStep.COMPLETED,
            progress=100,
            message="✅ Itinerary updated successfully!",
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "itinerary_id": itinerary_id,
            "itinerary": updated_itinerary,
        }
        
    except Exception as e:
        tracker.update(
            task_id=task_id,
            status=TaskStatus.FAILED,
            step=TaskStep.FAILED,
            progress=-1,
            message=f"Failed to update itinerary: {str(e)}",
            error=str(e),
        )
        raise
        
    finally:
        tracker.close()


# ============ Replan Itinerary Task ============


class ReplanProgressCallback:
    """
    Progress callback adapter for LangGraph replan workflow.
    
    Translates replan workflow steps to Celery task progress updates.
    """
    
    def __init__(self, task_id: str, tracker: TaskProgressTracker, itinerary_id: str):
        self.task_id = task_id
        self.tracker = tracker
        self.itinerary_id = itinerary_id
    
    async def __call__(
        self,
        step: Any,
        progress: int,
        message: str,
    ) -> None:
        """Update progress via the tracker."""
        step_value = step.value if hasattr(step, "value") else str(step)
        
        self.tracker.update(
            task_id=self.task_id,
            status=TaskStatus.PROGRESS,
            step=step_value,
            progress=progress,
            message=message,
            data={"itinerary_id": self.itinerary_id},
        )


@celery_app.task(
    bind=True,
    name="app.domains.itinerary.tasks.replan_itinerary_task",
    max_retries=1,
    soft_time_limit=300,
    time_limit=360,
)
def replan_itinerary_task(
    self,
    itinerary_id: str,
    trigger_type: str,
    trigger_reason: str,
    trigger_details: str | None = None,
    current_location: dict | None = None,
    affected_day: int | None = None,
    affected_activity_ids: list[str] | None = None,
    user_preferences: dict | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Smart replan of travel itinerary based on real-time triggers.
    
    This task processes replan requests through the Intelligence Engine:
    1. Load State - Get current itinerary from checkpointer
    2. Impact Analysis - Identify which activities are affected
    3. Dynamic Substitution - Find alternatives (weather/traffic/crowd)
    4. Transit Update - Update routes for new activities
    5. Monetization Update - Update affiliate links
    6. Finalization - Create new version and save
    
    Args:
        itinerary_id: ID of the itinerary to replan
        trigger_type: Type of trigger (weather, traffic, crowd, user_request)
        trigger_reason: user_initiated or system_proactive
        trigger_details: Additional details about the trigger
        current_location: User's current GPS location
        affected_day: Specific day to focus on
        affected_activity_ids: Specific activities to consider
        user_preferences: Additional preferences
        user_id: User ID for tracking
        
    Returns:
        Dictionary containing replan result with changes
    """
    task_id = self.request.id
    tracker = TaskProgressTracker()
    
    try:
        # Initialize
        tracker.update(
            task_id=task_id,
            status=TaskStatus.STARTED,
            step="initializing_replan",
            progress=0,
            message="🔄 Starting smart replan...",
            data={
                "itinerary_id": itinerary_id,
                "trigger_type": trigger_type,
                "trigger_reason": trigger_reason,
            },
        )
        
        # Load current itinerary from database
        tracker.update(
            task_id=task_id,
            status=TaskStatus.PROGRESS,
            step="loading_itinerary",
            progress=5,
            message="📂 Loading your current itinerary...",
            data={"itinerary_id": itinerary_id},
        )
        
        current_data, current_version = asyncio.run(
            _load_itinerary_for_replan(itinerary_id)
        )
        
        if not current_data:
            raise ValueError("Itinerary not found or no data available")
        
        # Create progress callback for LangGraph
        progress_callback = ReplanProgressCallback(task_id, tracker, itinerary_id)
        
        # Run LangGraph replan workflow
        replan_result = asyncio.run(
            _run_replan_workflow(
                itinerary_id=itinerary_id,
                current_data=current_data,
                current_version=current_version,
                trigger_type=trigger_type,
                trigger_reason=trigger_reason,
                trigger_details=trigger_details,
                current_location=current_location,
                affected_day=affected_day,
                affected_activity_ids=affected_activity_ids,
                user_preferences=user_preferences,
                user_id=user_id,
                progress_callback=progress_callback,
            )
        )
        
        if not replan_result or not replan_result.get("success"):
            error_msg = replan_result.get("error", "Unknown error") if replan_result else "Workflow failed"
            raise RuntimeError(f"Replan workflow failed: {error_msg}")
        
        # Save updated itinerary to database
        tracker.update(
            task_id=task_id,
            status=TaskStatus.PROGRESS,
            step="saving_changes",
            progress=95,
            message="💾 Saving your updated itinerary...",
            data={"itinerary_id": itinerary_id},
        )
        
        asyncio.run(_save_replan_result(
            itinerary_id=itinerary_id,
            updated_data=replan_result["updated_data"],
            new_version=replan_result["new_version"],
            changes=replan_result.get("changes", []),
            current_data=current_data,
            current_version=current_version,
        ))
        
        # Mark as completed
        summary = replan_result.get("summary", {})
        tracker.update(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            step=TaskStep.COMPLETED,
            progress=100,
            message="🎉 Your itinerary has been updated!",
            data={
                "itinerary_id": itinerary_id,
                "new_version": replan_result["new_version"],
                "total_changes": summary.get("total_changes", 0),
                "is_critical": replan_result.get("is_critical", False),
            },
        )
        
        logger.info(f"Itinerary {itinerary_id} replanned to version {replan_result['new_version']}")
        
        return {
            "success": True,
            "task_id": task_id,
            "itinerary_id": itinerary_id,
            "new_version": replan_result["new_version"],
            "changes": replan_result.get("changes", []),
            "summary": summary,
            "is_critical": replan_result.get("is_critical", False),
            "alert_message": replan_result.get("alert_message"),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        
    except SoftTimeLimitExceeded:
        logger.error(f"Replan task {task_id} timed out")
        tracker.update(
            task_id=task_id,
            status=TaskStatus.FAILED,
            step=TaskStep.FAILED,
            progress=-1,
            message="Replan timed out. Please try again.",
            error="SoftTimeLimitExceeded",
        )
        raise
        
    except Exception as e:
        logger.error(f"Replan task {task_id} failed: {e}")
        tracker.update(
            task_id=task_id,
            status=TaskStatus.FAILED,
            step=TaskStep.FAILED,
            progress=-1,
            message=f"Failed to replan: {str(e)}",
            error=str(e),
        )
        
        # Retry if attempts remaining
        if self.request.retries < self.max_retries:
            tracker.update(
                task_id=task_id,
                status=TaskStatus.RETRYING,
                step="initializing_replan",
                progress=0,
                message=f"Retrying replan... (attempt {self.request.retries + 2})",
            )
            raise self.retry(exc=e, countdown=15)
        
        raise
        
    finally:
        tracker.close()


async def _load_itinerary_for_replan(itinerary_id: str) -> tuple[dict | None, int]:
    """
    Load itinerary data and version for replan.
    """
    from uuid import UUID as UUIDType
    
    from app.infra.database import async_session_factory
    from app.domains.itinerary.repository import ItineraryRepository
    
    async with async_session_factory() as session:
        repo = ItineraryRepository(session)
        itinerary = await repo.get_full_itinerary(UUIDType(itinerary_id))
        
        if not itinerary:
            return None, 0
        
        return itinerary.data or {}, itinerary.version or 1


async def _run_replan_workflow(
    itinerary_id: str,
    current_data: dict,
    current_version: int,
    trigger_type: str,
    trigger_reason: str,
    trigger_details: str | None,
    current_location: dict | None,
    affected_day: int | None,
    affected_activity_ids: list[str] | None,
    user_preferences: dict | None,
    user_id: str | None,
    progress_callback: ReplanProgressCallback,
) -> dict | None:
    """
    Run the LangGraph replan workflow.
    """
    from app.domains.itinerary.services.replan_graph import run_replan
    
    return await run_replan(
        itinerary_id=itinerary_id,
        current_data=current_data,
        current_version=current_version,
        trigger_type=trigger_type,
        trigger_reason=trigger_reason,
        trigger_details=trigger_details,
        current_location=current_location,
        affected_day=affected_day,
        affected_activity_ids=affected_activity_ids,
        user_preferences=user_preferences,
        user_id=user_id,
        progress_callback=progress_callback,
    )


async def _save_replan_result(
    itinerary_id: str,
    updated_data: dict,
    new_version: int,
    changes: list,
    current_data: dict,
    current_version: int,
) -> None:
    """
    Save replan result to database with version history.
    """
    from datetime import date as date_type
    from uuid import UUID as UUIDType
    
    from app.infra.database import async_session_factory
    from app.domains.itinerary.repository import ItineraryRepository
    
    async with async_session_factory() as session:
        repo = ItineraryRepository(session)
        
        # Save with version history
        await repo.save_replan_result(
            itinerary_id=UUIDType(itinerary_id),
            updated_data=updated_data,
            new_version=new_version,
            changes=changes,
            previous_data=current_data,
            previous_version=current_version,
        )
        
        await session.commit()
        logger.info(f"Replan result saved for itinerary {itinerary_id}, version {new_version}")


@celery_app.task(name="app.domains.itinerary.tasks.cleanup_stale_tasks")
def cleanup_stale_tasks() -> dict[str, Any]:
    """
    Periodic task to clean up stale task progress entries.
    """
    tracker = TaskProgressTracker()
    
    try:
        active_tasks = tracker.get_active_tasks()
        cleaned = 0
        
        for task_id in active_tasks:
            progress = tracker.get(task_id)
            if progress:
                # Check if task is stale (no update for 30 minutes)
                age = (datetime.now(timezone.utc) - progress.updated_at).total_seconds()
                if age > 1800:  # 30 minutes
                    tracker.delete(task_id)
                    cleaned += 1
        
        return {
            "success": True,
            "checked": len(active_tasks),
            "cleaned": cleaned,
        }
        
    finally:
        tracker.close()

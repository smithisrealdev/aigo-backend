"""Itinerary API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.itinerary.schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    GenerateItineraryRequest,
    GenerateItineraryResponse,
    ItineraryCreate,
    ItineraryFullDataResponse,
    ItineraryListResponse,
    ItineraryResponse,
    ItineraryStatusResponse,
    ItineraryUpdate,
    ReplanRequest,
    ReplanResponse,
    VersionHistoryResponse,
)
from app.domains.itinerary.services import ItineraryService
from app.infra.database import get_db

router = APIRouter()


# TODO: Replace with actual auth dependency
async def get_current_user_id() -> UUID:
    """Temporary placeholder for current user ID."""
    # This will be replaced with actual JWT auth
    return UUID("00000000-0000-0000-0000-000000000001")


def get_itinerary_service(
    session: AsyncSession = Depends(get_db),
) -> ItineraryService:
    """Dependency for getting ItineraryService."""
    return ItineraryService(session)


# ==================== AI Generation Endpoints ====================


@router.post(
    "/generate",
    response_model=GenerateItineraryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate itinerary from natural language prompt",
    description="""
    Submit a natural language description of your trip and receive an 
    AI-generated itinerary. This endpoint returns immediately with a task ID
    that can be used to track generation progress.
    
    **Progress Tracking:**
    - WebSocket: Connect to `/api/v1/ws/itinerary/{task_id}` for real-time updates
    - Polling: GET `/api/v1/tasks/{task_id}` for current status
    
    **Example prompts:**
    - "Plan a 5-day trip to Tokyo with focus on food and culture"
    - "Family vacation to Paris for 7 days with kids, budget $5000"
    - "Adventure trip to Costa Rica, hiking and beaches, moderate budget"
    """,
)
async def generate_itinerary(
    request: GenerateItineraryRequest,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> GenerateItineraryResponse:
    """
    Generate a new itinerary from natural language prompt.
    
    The itinerary is generated asynchronously via a background task.
    Returns immediately with task and itinerary IDs for progress tracking.
    """
    return await service.generate_itinerary_from_prompt(user_id, request)


# ==================== CRUD Endpoints ====================


@router.post(
    "",
    response_model=ItineraryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new itinerary",
)
async def create_itinerary(
    data: ItineraryCreate,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> ItineraryResponse:
    """Create a new travel itinerary."""
    return await service.create_itinerary(user_id, data)


@router.get(
    "",
    response_model=ItineraryListResponse,
    summary="Get all itineraries",
)
async def get_itineraries(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> ItineraryListResponse:
    """Get paginated list of user's itineraries."""
    return await service.get_itineraries(user_id, page=page, size=size)


@router.get(
    "/{itinerary_id}",
    response_model=ItineraryFullDataResponse,
    summary="Get an itinerary by ID with full AI-generated data",
    description="""
    Retrieve a complete itinerary including all AI-generated content.
    
    **Response includes:**
    - Basic itinerary metadata (title, dates, budget)
    - Generation status and task information
    - Complete AI-generated plan in the `data` field (when status is COMPLETED)
    
    **The `data` field contains:**
    - Daily plans with activities, timings, and descriptions
    - Transit details between activities
    - Weather forecasts and packing suggestions
    - Booking options with affiliate links
    - Cost breakdowns and totals
    
    **Status values:**
    - `processing`: AI is generating the itinerary
    - `completed`: Ready with full data
    - `failed`: Generation failed (check `generation_error`)
    """,
)
async def get_itinerary(
    itinerary_id: UUID,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> ItineraryFullDataResponse:
    """Get a specific itinerary by ID with full AI-generated data."""
    itinerary = await service.get_full_itinerary(itinerary_id, user_id)
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found",
        )
    return ItineraryFullDataResponse.model_validate(itinerary)


@router.get(
    "/{itinerary_id}/status",
    response_model=ItineraryStatusResponse,
    summary="Check itinerary generation status",
    description="""
    Lightweight endpoint to check if an itinerary is ready.
    
    Use this for polling instead of fetching the full itinerary data.
    Returns only status information without the complete AI-generated data.
    """,
)
async def get_itinerary_status(
    itinerary_id: UUID,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> ItineraryStatusResponse:
    """Check itinerary generation status."""
    itinerary = await service.get_itinerary(itinerary_id, user_id)
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found",
        )
    return ItineraryStatusResponse(
        id=itinerary.id,
        status=itinerary.status,
        generation_task_id=itinerary.generation_task_id,
        generation_error=getattr(itinerary, "generation_error", None),
        completed_at=getattr(itinerary, "completed_at", None),
        is_ready=itinerary.status.value == "completed" and getattr(itinerary, "data", None) is not None,
    )


@router.patch(
    "/{itinerary_id}",
    response_model=ItineraryResponse,
    summary="Update an itinerary",
)
async def update_itinerary(
    itinerary_id: UUID,
    data: ItineraryUpdate,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> ItineraryResponse:
    """Update an existing itinerary."""
    itinerary = await service.update_itinerary(itinerary_id, user_id, data)
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found",
        )
    return itinerary


@router.delete(
    "/{itinerary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an itinerary",
)
async def delete_itinerary(
    itinerary_id: UUID,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    """Delete an itinerary."""
    deleted = await service.delete_itinerary(itinerary_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found",
        )


# ============ Activity Endpoints ============


@router.post(
    "/{itinerary_id}/activities",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an activity to an itinerary",
)
async def add_activity(
    itinerary_id: UUID,
    data: ActivityCreate,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> ActivityResponse:
    """Add a new activity to an itinerary."""
    activity = await service.add_activity(itinerary_id, user_id, data)
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found",
        )
    return activity


@router.patch(
    "/activities/{activity_id}",
    response_model=ActivityResponse,
    summary="Update an activity",
)
async def update_activity(
    activity_id: UUID,
    data: ActivityUpdate,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> ActivityResponse:
    """Update an existing activity."""
    activity = await service.update_activity(activity_id, user_id, data)
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )
    return activity


@router.delete(
    "/activities/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an activity",
)
async def delete_activity(
    activity_id: UUID,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    """Delete an activity."""
    deleted = await service.delete_activity(activity_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )


# ============ Smart Re-plan Endpoints ============


@router.post(
    "/{itinerary_id}/replan",
    response_model=ReplanResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Smart replan itinerary based on real-time triggers",
    description="""
    Trigger a smart re-plan of the itinerary based on real-time conditions.
    
    **Trigger Types:**
    - `weather`: Weather conditions changed (rain, heat wave, etc.)
    - `traffic`: Traffic conditions affect travel time
    - `crowd`: Venue crowding levels are high
    - `user_request`: User wants to modify specific activities
    - `schedule_change`: Flight/hotel timing changed
    - `venue_closure`: A venue is unexpectedly closed
    
    **Replan Reasons:**
    - `user_initiated`: User explicitly requested the replan
    - `system_proactive`: System detected an issue and suggests changes
    
    **Process:**
    1. Analyzes impact on current activities
    2. Finds suitable substitutions (indoor for rain, hidden gems for crowds)
    3. Updates transit routes to new locations
    4. Updates affiliate links for new bookings
    5. Creates new version with change tracking
    
    **Progress Tracking:**
    - WebSocket: Connect to `/api/v1/ws/itinerary/{task_id}` for real-time updates
    - The response includes a `task_id` for tracking
    
    **Version History:**
    - Each replan creates a new version
    - Previous versions are stored for rollback capability
    - Use GET `/{itinerary_id}/versions` to see history
    """,
)
async def replan_itinerary(
    itinerary_id: UUID,
    request: ReplanRequest,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> ReplanResponse:
    """
    Trigger a smart re-plan of the itinerary.
    
    Returns immediately with task ID for progress tracking.
    The actual replan happens asynchronously via a background task.
    """
    # Verify itinerary exists and belongs to user
    itinerary = await service.get_itinerary(itinerary_id, user_id)
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found",
        )
    
    # Check if itinerary has data to replan
    if not getattr(itinerary, "data", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Itinerary has no generated data to replan. Generate first.",
        )
    
    # Check if replan already in progress
    if getattr(itinerary, "replan_task_id", None):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A replan is already in progress for this itinerary",
        )
    
    return await service.trigger_replan(
        itinerary_id=itinerary_id,
        user_id=user_id,
        request=request,
    )


@router.get(
    "/{itinerary_id}/versions",
    response_model=VersionHistoryResponse,
    summary="Get version history for an itinerary",
    description="""
    Retrieve the version history of an itinerary, including all changes
    made through replanning.
    
    **Response includes:**
    - Current version number
    - List of previous versions with:
      - Version number
      - Timestamp of change
      - Reason for change
      - List of specific changes made
    
    **Note:** Only the last 10 versions are kept for storage efficiency.
    """,
)
async def get_version_history(
    itinerary_id: UUID,
    service: ItineraryService = Depends(get_itinerary_service),
    user_id: UUID = Depends(get_current_user_id),
) -> VersionHistoryResponse:
    """Get version history for an itinerary."""
    itinerary = await service.get_itinerary(itinerary_id, user_id)
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found",
        )
    
    history = getattr(itinerary, "version_history", None) or []
    
    return VersionHistoryResponse(
        itinerary_id=itinerary_id,
        current_version=getattr(itinerary, "version", 1),
        versions=[
            {
                "version": v.get("version", i + 1),
                "timestamp": v.get("timestamp"),
                "reason": v.get("reason"),
                "changes_count": len(v.get("changes", [])),
            }
            for i, v in enumerate(history)
        ],
        last_replan_at=getattr(itinerary, "last_replan_at", None),
    )

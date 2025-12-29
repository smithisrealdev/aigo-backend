"""Services for the Itinerary domain - Business logic layer."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.itinerary.models import (
    Activity,
    ActivityCategory,
    DailyPlan,
    Itinerary,
    ItineraryStatus,
)
from app.domains.itinerary.repository import (
    ActivityRepository,
    DailyPlanRepository,
    ItineraryRepository,
)
from app.domains.itinerary.schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    DailyPlanCreate,
    DailyPlanResponse,
    DailyPlanUpdate,
    GenerateItineraryRequest,
    GenerateItineraryResponse,
    ItineraryCreate,
    ItineraryListResponse,
    ItineraryResponse,
    ItinerarySummary,
    ItineraryUpdate,
    ReplanRequest,
    ReplanResponse,
)


class ItineraryService:
    """Service for Itinerary business logic.

    This service layer encapsulates all business logic related to
    itinerary management, providing a clean interface for the API layer.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            session: Async database session
        """
        self.session = session
        self.repository = ItineraryRepository(session)
        self.activity_repository = ActivityRepository(session)
        self.daily_plan_repository = DailyPlanRepository(session)

    # ==================== AI Generation Operations ====================

    async def generate_itinerary_from_prompt(
        self,
        user_id: UUID,
        request: GenerateItineraryRequest,
    ) -> GenerateItineraryResponse:
        """
        Generate a new itinerary from natural language prompt.
        
        Creates an itinerary record with PROCESSING status and dispatches
        a Celery task for async AI-powered generation.
        
        Args:
            user_id: Owner's UUID
            request: Generation request with prompt and budget
            
        Returns:
            Response containing itinerary_id and task_id for tracking
        """
        from app.domains.itinerary.tasks import generate_itinerary_task
        
        # Extract destination hint from prompt (basic extraction)
        # In production, this would use NLP or LLM
        destination = self._extract_destination_hint(request.prompt)
        
        # Create placeholder itinerary with PROCESSING status
        # Dates will be updated by the AI generation task
        today = date.today()
        placeholder_data = {
            "user_id": user_id,
            "title": f"Trip to {destination}",
            "description": f"AI-generated itinerary based on: {request.prompt[:100]}...",
            "destination": destination,
            "start_date": today + timedelta(days=30),  # Placeholder
            "end_date": today + timedelta(days=37),    # Placeholder
            "total_budget": request.budget,
            "currency": request.currency,
            "status": ItineraryStatus.PROCESSING,
            "original_prompt": request.prompt,
        }
        
        itinerary = await self.repository.create(placeholder_data)
        await self.session.commit()
        
        # Dispatch Celery task
        result = generate_itinerary_task.delay(
            itinerary_id=str(itinerary.id),
            user_prompt=request.prompt,
            user_id=str(user_id),
            preferences=request.preferences,
        )
        
        task_id = result.id
        
        # Update itinerary with task ID
        await self.repository.update(
            itinerary.id,
            {"generation_task_id": task_id},
        )
        await self.session.commit()
        
        return GenerateItineraryResponse(
            itinerary_id=itinerary.id,
            task_id=task_id,
            status=ItineraryStatus.PROCESSING,
            message="Itinerary generation started. Track progress via WebSocket.",
            websocket_url=f"/api/v1/ws/itinerary/{task_id}",
            poll_url=f"/api/v1/tasks/{task_id}",
            created_at=datetime.now(timezone.utc),
        )

    def _extract_destination_hint(self, prompt: str) -> str:
        """
        Extract destination from prompt using simple heuristics.
        
        TODO: Replace with NLP/LLM for better extraction.
        """
        # Common patterns: "trip to X", "visit X", "travel to X", "go to X"
        import re
        
        patterns = [
            r"(?:trip|travel|visit|go|going|fly|flying)\s+to\s+([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+in|\s+,|$)",
            r"(?:explore|exploring)\s+([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+in|\s+,|$)",
            r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s+(?:trip|vacation|holiday)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                destination = match.group(1).strip()
                # Clean up common words
                destination = re.sub(r'\b(for|in|with|and|the)\b', '', destination, flags=re.IGNORECASE)
                return destination.strip() or "Unknown Destination"
        
        return "Unknown Destination"

    async def update_itinerary_from_task(
        self,
        itinerary_id: UUID,
        task_result: dict[str, Any],
    ) -> Itinerary | None:
        """
        Update itinerary with AI-generated content from completed task.
        
        Called by Celery task upon successful completion.
        
        Args:
            itinerary_id: Itinerary UUID
            task_result: Generated itinerary data from task
            
        Returns:
            Updated itinerary or None if not found
        """
        itinerary = await self.repository.get_by_id(itinerary_id)
        if not itinerary:
            return None
        
        # Extract data from task result
        generated = task_result.get("itinerary", {})
        
        update_data = {
            "title": generated.get("title", itinerary.title),
            "description": generated.get("summary", itinerary.description),
            "destination": generated.get("destination", itinerary.destination),
            "status": ItineraryStatus.PLANNED,
        }
        
        # Update dates if provided
        if generated.get("start_date"):
            update_data["start_date"] = date.fromisoformat(generated["start_date"])
        if generated.get("end_date"):
            update_data["end_date"] = date.fromisoformat(generated["end_date"])
        
        await self.repository.update(itinerary_id, update_data)
        
        # Create daily plans and activities from generated data
        daily_plans = generated.get("daily_plans", [])
        for plan_data in daily_plans:
            await self._create_daily_plan_from_generated(itinerary_id, plan_data)
        
        await self.session.commit()
        return await self.repository.get_by_id(itinerary_id)

    async def _create_daily_plan_from_generated(
        self,
        itinerary_id: UUID,
        plan_data: dict[str, Any],
    ) -> DailyPlan:
        """Create a daily plan from AI-generated data."""
        daily_plan = await self.daily_plan_repository.create({
            "itinerary_id": itinerary_id,
            "day_number": plan_data.get("day", 1),
            "date": date.fromisoformat(plan_data["date"]) if plan_data.get("date") else None,
            "title": plan_data.get("title"),
            "notes": plan_data.get("notes"),
        })
        
        # Create activities for this day
        for activity_data in plan_data.get("activities", []):
            await self.activity_repository.create({
                "itinerary_id": itinerary_id,
                "daily_plan_id": daily_plan.id,
                "title": activity_data.get("title", "Activity"),
                "category": self._map_category(activity_data.get("category")),
                "day_number": plan_data.get("day", 1),
                "duration_minutes": activity_data.get("duration"),
                "location_name": activity_data.get("location"),
                "notes": activity_data.get("notes"),
            })
        
        return daily_plan

    def _map_category(self, category: str | None) -> ActivityCategory:
        """Map string category to ActivityCategory enum."""
        if not category:
            return ActivityCategory.OTHER
        
        category_map = {
            "transportation": ActivityCategory.TRANSPORTATION,
            "accommodation": ActivityCategory.ACCOMMODATION,
            "dining": ActivityCategory.DINING,
            "food": ActivityCategory.DINING,
            "sightseeing": ActivityCategory.SIGHTSEEING,
            "culture": ActivityCategory.SIGHTSEEING,
            "entertainment": ActivityCategory.ENTERTAINMENT,
            "shopping": ActivityCategory.SHOPPING,
        }
        
        return category_map.get(category.lower(), ActivityCategory.OTHER)

    async def mark_generation_failed(
        self,
        itinerary_id: UUID,
        error_message: str,
    ) -> None:
        """Mark itinerary generation as failed."""
        await self.repository.update(
            itinerary_id,
            {
                "status": ItineraryStatus.FAILED,
                "notes": f"Generation failed: {error_message}",
            },
        )
        await self.session.commit()

    # ==================== Smart Re-plan Operations ====================

    async def trigger_replan(
        self,
        itinerary_id: UUID,
        user_id: UUID,
        request: "ReplanRequest",
    ) -> "ReplanResponse":
        """
        Trigger a smart re-plan of the itinerary.
        
        Creates a Celery task for async replan and returns immediately
        with task ID for progress tracking.
        
        Args:
            itinerary_id: Itinerary UUID
            user_id: Owner's UUID for authorization
            request: Replan request with trigger details
            
        Returns:
            Replan response with task ID for tracking
        """
        from app.domains.itinerary.schemas import ReplanResponse
        from app.domains.itinerary.tasks import replan_itinerary_task
        
        # Get current itinerary for version info
        itinerary = await self.repository.get_by_id(itinerary_id)
        if not itinerary:
            raise ValueError("Itinerary not found")
        
        current_version = getattr(itinerary, "version", 1) or 1
        
        # Prepare location dict
        current_location = None
        if request.current_gps_location:
            current_location = {
                "latitude": request.current_gps_location.latitude,
                "longitude": request.current_gps_location.longitude,
                "accuracy_meters": request.current_gps_location.accuracy_meters,
            }
        
        # Dispatch Celery replan task
        result = replan_itinerary_task.delay(
            itinerary_id=str(itinerary_id),
            trigger_type=request.trigger_type.value,
            trigger_reason=request.reason.value,
            trigger_details=request.trigger_details,
            current_location=current_location,
            affected_day=request.affected_day,
            affected_activity_ids=request.affected_activity_ids,
            user_preferences=request.user_preferences,
            user_id=str(user_id),
        )
        
        task_id = result.id
        
        # Store task ID on itinerary
        await self.repository.set_replan_task_id(itinerary_id, task_id)
        await self.session.commit()
        
        return ReplanResponse(
            itinerary_id=itinerary_id,
            task_id=task_id,
            status="processing",
            message="Smart replan started. Track progress via WebSocket.",
            websocket_url=f"/api/v1/ws/itinerary/{task_id}",
            version=current_version + 1,
            previous_version=current_version,
            is_critical=False,
            alert_message=None,
            created_at=datetime.now(timezone.utc),
        )

    # ==================== Itinerary Operations ====================

    async def create_itinerary(
        self, user_id: UUID, data: ItineraryCreate
    ) -> ItineraryResponse:
        """Create a new itinerary with optional activities and daily plans.

        Args:
            user_id: Owner's UUID
            data: Itinerary creation data

        Returns:
            Created itinerary response
        """
        # Create base itinerary
        itinerary_data = data.model_dump(exclude={"activities", "daily_plans"})
        itinerary_data["user_id"] = user_id
        itinerary = await self.repository.create(itinerary_data)

        # Generate daily plans if not provided
        if not data.daily_plans:
            await self._generate_daily_plans(itinerary)
        else:
            for plan_data in data.daily_plans:
                await self._create_daily_plan(itinerary.id, plan_data)

        # Create activities if provided
        for activity_data in data.activities:
            activity_dict = activity_data.model_dump()
            activity_dict["itinerary_id"] = itinerary.id
            await self.activity_repository.create(activity_dict)

        await self.session.commit()

        # Refresh to get relationships
        return await self.get_itinerary(itinerary.id, user_id)  # type: ignore

    async def get_itinerary(
        self, itinerary_id: UUID, user_id: UUID
    ) -> ItineraryResponse | None:
        """Get an itinerary by ID with full details.

        Args:
            itinerary_id: Itinerary UUID
            user_id: Owner's UUID for authorization

        Returns:
            Itinerary response or None if not found
        """
        itinerary = await self.repository.get_with_full_details(
            itinerary_id, user_id
        )
        if not itinerary:
            return None
        return ItineraryResponse.model_validate(itinerary)

    async def get_full_itinerary(
        self, itinerary_id: UUID, user_id: UUID
    ) -> Itinerary | None:
        """Get an itinerary with full AI-generated data.

        Returns the raw Itinerary model including the `data` JSONB field
        containing the complete AI-generated itinerary.

        Args:
            itinerary_id: Itinerary UUID
            user_id: Owner's UUID for authorization

        Returns:
            Itinerary model instance or None if not found
        """
        return await self.repository.get_full_itinerary(
            itinerary_id, user_id
        )

    async def get_itineraries(
        self,
        user_id: UUID,
        *,
        status: ItineraryStatus | None = None,
        page: int = 1,
        size: int = 10,
    ) -> ItineraryListResponse:
        """Get paginated list of itineraries for a user.

        Args:
            user_id: Owner's UUID
            status: Optional status filter
            page: Page number (1-indexed)
            size: Items per page

        Returns:
            Paginated itinerary list response
        """
        skip = (page - 1) * size
        items, total = await self.repository.find_by_user(
            user_id, status=status, skip=skip, limit=size
        )

        return ItineraryListResponse(
            items=[ItineraryResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            size=size,
            pages=ceil(total / size) if total > 0 else 0,
        )

    async def get_upcoming_itineraries(
        self, user_id: UUID, limit: int = 5
    ) -> list[ItinerarySummary]:
        """Get upcoming itineraries for dashboard.

        Args:
            user_id: Owner's UUID
            limit: Maximum items to return

        Returns:
            List of itinerary summaries
        """
        items = await self.repository.find_upcoming(user_id, limit=limit)
        return [ItinerarySummary.model_validate(item) for item in items]

    async def update_itinerary(
        self, itinerary_id: UUID, user_id: UUID, data: ItineraryUpdate
    ) -> ItineraryResponse | None:
        """Update an itinerary.

        Args:
            itinerary_id: Itinerary UUID
            user_id: Owner's UUID for authorization
            data: Update data

        Returns:
            Updated itinerary or None if not found
        """
        # Verify ownership first
        existing = await self.repository.find_one(
            Itinerary.id == itinerary_id,
            Itinerary.user_id == user_id,
        )
        if not existing:
            return None

        itinerary = await self.repository.update(itinerary_id, data)
        if not itinerary:
            return None

        await self.session.commit()
        return await self.get_itinerary(itinerary_id, user_id)

    async def update_status(
        self, itinerary_id: UUID, user_id: UUID, status: ItineraryStatus
    ) -> ItineraryResponse | None:
        """Update itinerary status.

        Args:
            itinerary_id: Itinerary UUID
            user_id: Owner's UUID for authorization
            status: New status

        Returns:
            Updated itinerary or None if not found
        """
        itinerary = await self.repository.update_status(
            itinerary_id, user_id, status
        )
        if not itinerary:
            return None

        await self.session.commit()
        return ItineraryResponse.model_validate(itinerary)

    async def delete_itinerary(self, itinerary_id: UUID, user_id: UUID) -> bool:
        """Delete an itinerary.

        Args:
            itinerary_id: Itinerary UUID
            user_id: Owner's UUID for authorization

        Returns:
            True if deleted, False if not found
        """
        # Verify ownership
        existing = await self.repository.find_one(
            Itinerary.id == itinerary_id,
            Itinerary.user_id == user_id,
        )
        if not existing:
            return False

        deleted = await self.repository.delete(itinerary_id)
        if deleted:
            await self.session.commit()
        return deleted

    # ==================== Daily Plan Operations ====================

    async def _generate_daily_plans(self, itinerary: Itinerary) -> None:
        """Auto-generate daily plans based on itinerary dates.

        Args:
            itinerary: The itinerary to generate plans for
        """
        current_date = itinerary.start_date
        day_number = 1

        while current_date <= itinerary.end_date:
            plan_data = {
                "itinerary_id": itinerary.id,
                "day_number": day_number,
                "date": current_date,
                "title": f"Day {day_number}",
            }
            await self.daily_plan_repository.create(plan_data)
            current_date += timedelta(days=1)
            day_number += 1

    async def _create_daily_plan(
        self, itinerary_id: UUID, data: DailyPlanCreate
    ) -> DailyPlan:
        """Create a daily plan with activities.

        Args:
            itinerary_id: Parent itinerary UUID
            data: Daily plan creation data

        Returns:
            Created daily plan
        """
        plan_data = data.model_dump(exclude={"activities"}, by_alias=True)
        plan_data["itinerary_id"] = itinerary_id
        # Ensure we use 'date' for the model field
        if "plan_date" in plan_data:
            plan_data["date"] = plan_data.pop("plan_date")
        daily_plan = await self.daily_plan_repository.create(plan_data)

        # Create activities
        for activity_data in data.activities:
            activity_dict = activity_data.model_dump()
            activity_dict["itinerary_id"] = itinerary_id
            activity_dict["daily_plan_id"] = daily_plan.id
            activity_dict["day_number"] = data.day_number
            await self.activity_repository.create(activity_dict)

        return daily_plan

    async def get_daily_plan(
        self, itinerary_id: UUID, user_id: UUID, day_number: int
    ) -> DailyPlanResponse | None:
        """Get a specific daily plan.

        Args:
            itinerary_id: Parent itinerary UUID
            user_id: Owner's UUID for authorization
            day_number: Day number to retrieve

        Returns:
            Daily plan response or None
        """
        # Verify ownership
        itinerary = await self.repository.find_one(
            Itinerary.id == itinerary_id,
            Itinerary.user_id == user_id,
        )
        if not itinerary:
            return None

        plan = await self.daily_plan_repository.get_by_day(
            itinerary_id, day_number
        )
        if not plan:
            return None

        return DailyPlanResponse.model_validate(plan)

    async def update_daily_plan(
        self,
        daily_plan_id: UUID,
        user_id: UUID,
        data: DailyPlanUpdate,
    ) -> DailyPlanResponse | None:
        """Update a daily plan.

        Args:
            daily_plan_id: Daily plan UUID
            user_id: Owner's UUID for authorization
            data: Update data

        Returns:
            Updated daily plan or None
        """
        # Get plan and verify ownership through itinerary
        plan = await self.daily_plan_repository.get_by_id(daily_plan_id)
        if not plan:
            return None

        itinerary = await self.repository.find_one(
            Itinerary.id == plan.itinerary_id,
            Itinerary.user_id == user_id,
        )
        if not itinerary:
            return None

        updated = await self.daily_plan_repository.update(daily_plan_id, data)
        if not updated:
            return None

        await self.session.commit()
        return DailyPlanResponse.model_validate(updated)

    # ==================== Activity Operations ====================

    async def add_activity(
        self, itinerary_id: UUID, user_id: UUID, data: ActivityCreate
    ) -> ActivityResponse | None:
        """Add an activity to an itinerary.

        Args:
            itinerary_id: Parent itinerary UUID
            user_id: Owner's UUID for authorization
            data: Activity creation data

        Returns:
            Created activity or None if itinerary not found
        """
        # Verify itinerary ownership
        itinerary = await self.repository.find_one(
            Itinerary.id == itinerary_id,
            Itinerary.user_id == user_id,
        )
        if not itinerary:
            return None

        activity_data = data.model_dump()
        activity_data["itinerary_id"] = itinerary_id
        activity = await self.activity_repository.create(activity_data)

        await self.session.commit()
        return ActivityResponse.model_validate(activity)

    async def update_activity(
        self, activity_id: UUID, user_id: UUID, data: ActivityUpdate
    ) -> ActivityResponse | None:
        """Update an activity.

        Args:
            activity_id: Activity UUID
            user_id: Owner's UUID for authorization
            data: Update data

        Returns:
            Updated activity or None if not found
        """
        # Get activity and verify ownership through itinerary
        activity = await self.activity_repository.get_by_id(activity_id)
        if not activity:
            return None

        # Verify ownership
        itinerary = await self.repository.find_one(
            Itinerary.id == activity.itinerary_id,
            Itinerary.user_id == user_id,
        )
        if not itinerary:
            return None

        updated_activity = await self.activity_repository.update(
            activity_id, data
        )
        if not updated_activity:
            return None

        await self.session.commit()
        return ActivityResponse.model_validate(updated_activity)

    async def delete_activity(self, activity_id: UUID, user_id: UUID) -> bool:
        """Delete an activity.

        Args:
            activity_id: Activity UUID
            user_id: Owner's UUID for authorization

        Returns:
            True if deleted, False otherwise
        """
        # Get activity and verify ownership
        activity = await self.activity_repository.get_by_id(activity_id)
        if not activity:
            return False

        itinerary = await self.repository.find_one(
            Itinerary.id == activity.itinerary_id,
            Itinerary.user_id == user_id,
        )
        if not itinerary:
            return False

        deleted = await self.activity_repository.delete(activity_id)
        if deleted:
            await self.session.commit()
        return deleted

    async def reorder_activities(
        self,
        itinerary_id: UUID,
        user_id: UUID,
        day_number: int,
        activity_orders: list[tuple[UUID, int]],
    ) -> bool:
        """Reorder activities within a day.

        Args:
            itinerary_id: Parent itinerary UUID
            user_id: Owner's UUID for authorization
            day_number: Day number
            activity_orders: List of (activity_id, new_order) tuples

        Returns:
            True if successful, False otherwise
        """
        # Verify ownership
        itinerary = await self.repository.find_one(
            Itinerary.id == itinerary_id,
            Itinerary.user_id == user_id,
        )
        if not itinerary:
            return False

        await self.activity_repository.reorder_activities(
            itinerary_id, day_number, activity_orders
        )
        await self.session.commit()
        return True

    # ==================== Budget Operations ====================

    async def calculate_trip_budget(
        self, itinerary_id: UUID, user_id: UUID
    ) -> Decimal | None:
        """Calculate total budget from all activities.

        Args:
            itinerary_id: Itinerary UUID
            user_id: Owner's UUID for authorization

        Returns:
            Total estimated cost or None if not found
        """
        # Verify ownership
        itinerary = await self.repository.find_one(
            Itinerary.id == itinerary_id,
            Itinerary.user_id == user_id,
        )
        if not itinerary:
            return None

        return await self.activity_repository.calculate_total_cost(itinerary_id)

    async def sync_budget(
        self, itinerary_id: UUID, user_id: UUID
    ) -> ItineraryResponse | None:
        """Sync itinerary budget with sum of activity costs.

        Args:
            itinerary_id: Itinerary UUID
            user_id: Owner's UUID for authorization

        Returns:
            Updated itinerary or None if not found
        """
        total_cost = await self.calculate_trip_budget(itinerary_id, user_id)
        if total_cost is None:
            return None

        itinerary = await self.repository.update_budget(
            itinerary_id, user_id, total_cost
        )
        if not itinerary:
            return None

        await self.session.commit()
        return ItineraryResponse.model_validate(itinerary)

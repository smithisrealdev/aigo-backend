"""Repository for Itinerary domain - Data access layer using Generic Repository."""

from datetime import date as date_type
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.itinerary.models import (
    Activity,
    ActivityCategory,
    DailyPlan,
    Itinerary,
    ItineraryStatus,
)
from app.domains.itinerary.schemas import (
    ActivityCreate,
    ActivityUpdate,
    DailyPlanCreate,
    DailyPlanUpdate,
    ItineraryCreate,
    ItineraryUpdate,
)
from app.domains.shared.repository import GenericRepository
from app.domains.shared.specifications import Specification


# ==================== Specifications ====================


class ItineraryByUserSpec(Specification[Itinerary]):
    """Specification for filtering itineraries by user."""

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    def to_expression(self) -> Any:
        """Return filter expression for user_id."""
        return Itinerary.user_id == self.user_id


class ItineraryByStatusSpec(Specification[Itinerary]):
    """Specification for filtering itineraries by status."""

    def __init__(self, status: ItineraryStatus) -> None:
        self.status = status

    def to_expression(self) -> Any:
        """Return filter expression for status."""
        return Itinerary.status == self.status


class ItineraryByDateRangeSpec(Specification[Itinerary]):
    """Specification for filtering itineraries by date range."""

    def __init__(self, start_date: date_type, end_date: date_type) -> None:
        self.start_date = start_date
        self.end_date = end_date

    def to_expression(self) -> Any:
        """Return filter expression for date range overlap."""
        return and_(
            Itinerary.start_date <= self.end_date,
            Itinerary.end_date >= self.start_date,
        )


class ItineraryByDestinationSpec(Specification[Itinerary]):
    """Specification for filtering itineraries by destination."""

    def __init__(self, destination: str) -> None:
        self.destination = destination

    def to_expression(self) -> Any:
        """Return filter expression for destination (case-insensitive)."""
        return Itinerary.destination.ilike(f"%{self.destination}%")


class UpcomingItinerarySpec(Specification[Itinerary]):
    """Specification for filtering upcoming itineraries."""

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    def to_expression(self) -> Any:
        """Return filter expression for upcoming trips."""
        today = date_type.today()
        return and_(
            Itinerary.user_id == self.user_id,
            Itinerary.start_date >= today,
            Itinerary.status.in_(
                [ItineraryStatus.PLANNED, ItineraryStatus.CONFIRMED]
            ),
        )


# ==================== Repositories ====================


class ItineraryRepository(
    GenericRepository[Itinerary, ItineraryCreate, ItineraryUpdate]
):
    """Repository for Itinerary CRUD operations.

    Extends GenericRepository with domain-specific query methods.
    All operations are non-blocking using async/await.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with Itinerary model."""
        super().__init__(Itinerary, session)

    async def find_by_user(
        self,
        user_id: UUID,
        *,
        status: ItineraryStatus | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[Sequence[Itinerary], int]:
        """Find itineraries for a specific user with optional status filter.

        Args:
            user_id: The user's UUID
            status: Optional status filter
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            Tuple of (itineraries, total_count)
        """
        conditions = [Itinerary.user_id == user_id]
        if status:
            conditions.append(Itinerary.status == status)

        items = await self.find_many(
            *conditions,
            skip=skip,
            limit=limit,
            order_by=Itinerary.start_date.desc(),
            load_relations=["activities", "daily_plans"],
        )
        total = await self.count(*conditions)
        return items, total

    async def find_upcoming(
        self,
        user_id: UUID,
        *,
        limit: int = 5,
    ) -> Sequence[Itinerary]:
        """Find upcoming itineraries for a user.

        Args:
            user_id: The user's UUID
            limit: Maximum records to return

        Returns:
            Sequence of upcoming itineraries
        """
        spec = UpcomingItinerarySpec(user_id)
        return await self.find_many(
            spec.to_expression(),
            limit=limit,
            order_by=Itinerary.start_date.asc(),
        )

    async def find_by_destination(
        self,
        destination: str,
        *,
        user_id: UUID | None = None,
        is_public: bool | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> Sequence[Itinerary]:
        """Find itineraries by destination.

        Args:
            destination: Destination to search for
            user_id: Optional user filter
            is_public: Optional public filter
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            Sequence of matching itineraries
        """
        conditions = [Itinerary.destination.ilike(f"%{destination}%")]
        if user_id:
            conditions.append(Itinerary.user_id == user_id)
        if is_public is not None:
            conditions.append(Itinerary.is_public == is_public)

        return await self.find_many(
            *conditions,
            skip=skip,
            limit=limit,
        )

    async def get_with_full_details(
        self, id: UUID, user_id: UUID
    ) -> Itinerary | None:
        """Get itinerary with all related data loaded.

        Args:
            id: Itinerary UUID
            user_id: Owner's UUID for authorization

        Returns:
            Itinerary with activities and daily_plans or None
        """
        return await self.find_one(
            Itinerary.id == id,
            Itinerary.user_id == user_id,
            load_relations=["activities", "daily_plans"],
        )

    async def update_status(
        self,
        id: UUID,
        user_id: UUID,
        status: ItineraryStatus,
    ) -> Itinerary | None:
        """Update itinerary status.

        Args:
            id: Itinerary UUID
            user_id: Owner's UUID for authorization
            status: New status

        Returns:
            Updated itinerary or None if not found
        """
        itinerary = await self.find_one(
            Itinerary.id == id,
            Itinerary.user_id == user_id,
        )
        if not itinerary:
            return None

        itinerary.status = status
        await self._session.flush()
        await self._session.refresh(itinerary)
        return itinerary

    async def update_budget(
        self,
        id: UUID,
        user_id: UUID,
        total_budget: Decimal,
    ) -> Itinerary | None:
        """Update itinerary budget.

        Args:
            id: Itinerary UUID
            user_id: Owner's UUID for authorization
            total_budget: New budget amount

        Returns:
            Updated itinerary or None if not found
        """
        itinerary = await self.find_one(
            Itinerary.id == id,
            Itinerary.user_id == user_id,
        )
        if not itinerary:
            return None

        return await self.update(id, {"total_budget": total_budget})

    async def save_generated_data(
        self,
        itinerary_id: UUID,
        data: dict,
        *,
        update_fields: dict | None = None,
    ) -> Itinerary | None:
        """Save AI-generated itinerary data to JSONB field.

        Args:
            itinerary_id: Itinerary UUID
            data: Complete AI-generated itinerary dict (AIFullItinerary.model_dump())
            update_fields: Additional fields to update (title, destination, dates, etc.)

        Returns:
            Updated itinerary or None if not found
        """
        from datetime import datetime, timezone
        
        itinerary = await self.get_by_id(itinerary_id)
        if not itinerary:
            return None

        # Build update dict
        updates = {
            "data": data,
            "status": ItineraryStatus.COMPLETED,
            "completed_at": datetime.now(timezone.utc),
        }

        # Merge additional field updates
        if update_fields:
            updates.update(update_fields)

        return await self.update(itinerary_id, updates)

    async def mark_generation_failed(
        self,
        itinerary_id: UUID,
        error_message: str,
    ) -> Itinerary | None:
        """Mark itinerary generation as failed.

        Args:
            itinerary_id: Itinerary UUID
            error_message: Error message describing the failure

        Returns:
            Updated itinerary or None if not found
        """
        itinerary = await self.get_by_id(itinerary_id)
        if not itinerary:
            return None

        return await self.update(
            itinerary_id,
            {
                "status": ItineraryStatus.FAILED,
                "generation_error": error_message,
            },
        )

    async def find_by_task_id(
        self,
        task_id: str,
    ) -> Itinerary | None:
        """Find itinerary by Celery task ID.

        Args:
            task_id: Celery task ID

        Returns:
            Itinerary or None if not found
        """
        return await self.find_one(
            Itinerary.generation_task_id == task_id,
        )

    async def get_full_itinerary(
        self,
        itinerary_id: UUID,
        user_id: UUID | None = None,
    ) -> Itinerary | None:
        """Get itinerary with full AI-generated data.

        Args:
            itinerary_id: Itinerary UUID
            user_id: Optional user_id for authorization check

        Returns:
            Itinerary with data field loaded, or None
        """
        conditions = [Itinerary.id == itinerary_id]
        if user_id:
            conditions.append(Itinerary.user_id == user_id)

        return await self.find_one(
            *conditions,
            load_relations=["activities", "daily_plans"],
        )

    async def save_replan_result(
        self,
        itinerary_id: UUID,
        updated_data: dict,
        new_version: int,
        changes: list,
        previous_data: dict,
        previous_version: int,
    ) -> Itinerary | None:
        """Save replan result with version history.

        Args:
            itinerary_id: Itinerary UUID
            updated_data: New AI-generated itinerary data
            new_version: New version number
            changes: List of changes made
            previous_data: Previous itinerary data (for history)
            previous_version: Previous version number

        Returns:
            Updated itinerary or None if not found
        """
        from datetime import datetime, timezone

        itinerary = await self.get_by_id(itinerary_id)
        if not itinerary:
            return None

        # Build version history entry
        history_entry = {
            "version": previous_version,
            "data": previous_data,
            "changes": changes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "replan",
        }

        # Get existing history or initialize
        existing_history = itinerary.version_history or []
        existing_history.append(history_entry)

        # Keep only last 10 versions to limit storage
        if len(existing_history) > 10:
            existing_history = existing_history[-10:]

        # Update itinerary with new version
        updates = {
            "data": updated_data,
            "version": new_version,
            "version_history": existing_history,
            "last_replan_at": datetime.now(timezone.utc),
            "replan_task_id": None,  # Clear as task completed
        }

        return await self.update(itinerary_id, updates)

    async def set_replan_task_id(
        self,
        itinerary_id: UUID,
        task_id: str,
    ) -> Itinerary | None:
        """Set the Celery task ID for an ongoing replan operation.

        Args:
            itinerary_id: Itinerary UUID
            task_id: Celery task ID

        Returns:
            Updated itinerary or None if not found
        """
        itinerary = await self.get_by_id(itinerary_id)
        if not itinerary:
            return None

        return await self.update(
            itinerary_id,
            {"replan_task_id": task_id},
        )

    async def get_version_history(
        self,
        itinerary_id: UUID,
        user_id: UUID | None = None,
    ) -> list[dict] | None:
        """Get version history for an itinerary.

        Args:
            itinerary_id: Itinerary UUID
            user_id: Optional user_id for authorization check

        Returns:
            List of version history entries or None if not found
        """
        itinerary = await self.get_full_itinerary(itinerary_id, user_id)
        if not itinerary:
            return None

        return itinerary.version_history or []


class DailyPlanRepository(
    GenericRepository[DailyPlan, DailyPlanCreate, DailyPlanUpdate]
):
    """Repository for DailyPlan CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with DailyPlan model."""
        super().__init__(DailyPlan, session)

    async def find_by_itinerary(
        self,
        itinerary_id: UUID,
    ) -> Sequence[DailyPlan]:
        """Get all daily plans for an itinerary.

        Args:
            itinerary_id: The itinerary's UUID

        Returns:
            Sequence of daily plans ordered by day number
        """
        return await self.find_many(
            DailyPlan.itinerary_id == itinerary_id,
            order_by=DailyPlan.day_number.asc(),
            load_relations=["activities"],
        )

    async def get_by_day(
        self,
        itinerary_id: UUID,
        day_number: int,
    ) -> DailyPlan | None:
        """Get daily plan for a specific day.

        Args:
            itinerary_id: The itinerary's UUID
            day_number: Day number (1-indexed)

        Returns:
            DailyPlan or None
        """
        return await self.find_one(
            DailyPlan.itinerary_id == itinerary_id,
            DailyPlan.day_number == day_number,
        )


class ActivityRepository(
    GenericRepository[Activity, ActivityCreate, ActivityUpdate]
):
    """Repository for Activity CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with Activity model."""
        super().__init__(Activity, session)

    async def find_by_itinerary(
        self,
        itinerary_id: UUID,
        *,
        day_number: int | None = None,
        category: ActivityCategory | None = None,
    ) -> Sequence[Activity]:
        """Get activities for an itinerary.

        Args:
            itinerary_id: The itinerary's UUID
            day_number: Optional day filter
            category: Optional category filter

        Returns:
            Sequence of activities ordered by day and order
        """
        conditions = [Activity.itinerary_id == itinerary_id]
        if day_number:
            conditions.append(Activity.day_number == day_number)
        if category:
            conditions.append(Activity.category == category)

        return await self.find_many(
            *conditions,
            order_by=[Activity.day_number.asc(), Activity.order.asc()],
        )

    async def find_by_daily_plan(
        self,
        daily_plan_id: UUID,
    ) -> Sequence[Activity]:
        """Get activities for a daily plan.

        Args:
            daily_plan_id: The daily plan's UUID

        Returns:
            Sequence of activities ordered by order
        """
        return await self.find_many(
            Activity.daily_plan_id == daily_plan_id,
            order_by=Activity.order.asc(),
        )

    async def reorder_activities(
        self,
        itinerary_id: UUID,
        day_number: int,
        activity_orders: list[tuple[UUID, int]],
    ) -> None:
        """Reorder activities within a day.

        Args:
            itinerary_id: The itinerary's UUID
            day_number: Day number
            activity_orders: List of (activity_id, new_order) tuples
        """
        for activity_id, order in activity_orders:
            await self.update(activity_id, {"order": order})
        await self._session.flush()

    async def calculate_day_cost(
        self,
        itinerary_id: UUID,
        day_number: int,
    ) -> Decimal:
        """Calculate total estimated cost for a day.

        Args:
            itinerary_id: The itinerary's UUID
            day_number: Day number

        Returns:
            Total estimated cost as Decimal
        """
        activities = await self.find_by_itinerary(
            itinerary_id,
            day_number=day_number,
        )
        return sum(a.estimated_cost or Decimal("0") for a in activities)

    async def calculate_total_cost(
        self,
        itinerary_id: UUID,
    ) -> Decimal:
        """Calculate total estimated cost for entire itinerary.

        Args:
            itinerary_id: The itinerary's UUID

        Returns:
            Total estimated cost as Decimal
        """
        activities = await self.find_by_itinerary(itinerary_id)
        return sum(a.estimated_cost or Decimal("0") for a in activities)

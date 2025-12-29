"""SQLAlchemy models for the Itinerary domain."""

import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.database import Base


class ItineraryStatus(str, enum.Enum):
    """Enum for itinerary status."""

    DRAFT = "draft"
    PROCESSING = "processing"  # AI is generating the itinerary
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"  # AI generation failed


class ActivityCategory(str, enum.Enum):
    """Enum for activity categories."""

    TRANSPORTATION = "transportation"
    ACCOMMODATION = "accommodation"
    DINING = "dining"
    SIGHTSEEING = "sightseeing"
    ENTERTAINMENT = "entertainment"
    SHOPPING = "shopping"
    OTHER = "other"


class Itinerary(Base):
    """Itinerary model representing a travel plan.

    Attributes:
        id: Unique identifier (UUID) - inherited from Base
        user_id: Reference to the user who owns this itinerary
        destination: Primary destination of the trip
        start_date: Trip start date
        end_date: Trip end date
        total_budget: Budget allocated for the trip
        status: Current status of the itinerary
        created_at: Creation timestamp - inherited from Base
        updated_at: Last update timestamp - inherited from Base
    """

    __tablename__ = "itineraries"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    destination: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    total_budget: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="THB",
    )
    status: Mapped[ItineraryStatus] = mapped_column(
        Enum(ItineraryStatus, native_enum=True, name="itinerary_status"),
        nullable=False,
        default=ItineraryStatus.DRAFT,
        index=True,
    )
    cover_image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    is_public: Mapped[bool] = mapped_column(
        default=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # AI Generation fields
    original_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Original user prompt for AI generation",
    )
    generation_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Celery task ID for async generation",
    )
    
    # Full AI-generated itinerary data (JSONB)
    data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete AI-generated itinerary JSON (AIFullItinerary schema)",
    )
    
    # Error tracking for failed generations
    generation_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if AI generation failed",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When AI generation completed",
    )
    
    # Versioning for Smart Re-plan
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
        comment="Current version number (incremented on each replan)",
    )
    version_history: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="History of all versions with changes [{version, data, changes, timestamp}]",
    )
    last_replan_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the itinerary was last replanned",
    )
    replan_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Celery task ID for ongoing replan",
    )

    # Relationships
    activities: Mapped[list["Activity"]] = relationship(
        "Activity",
        back_populates="itinerary",
        cascade="all, delete-orphan",
        order_by="Activity.day_number, Activity.order",
        lazy="selectin",
    )
    daily_plans: Mapped[list["DailyPlan"]] = relationship(
        "DailyPlan",
        back_populates="itinerary",
        cascade="all, delete-orphan",
        order_by="DailyPlan.day_number",
        lazy="selectin",
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="valid_date_range"),
        CheckConstraint("total_budget >= 0", name="non_negative_budget"),
        Index("ix_itineraries_user_status", "user_id", "status"),
        Index("ix_itineraries_user_dates", "user_id", "start_date", "end_date"),
    )

    @property
    def duration_days(self) -> int:
        """Calculate trip duration in days."""
        return (self.end_date - self.start_date).days + 1

    @property
    def is_active(self) -> bool:
        """Check if itinerary is in active status."""
        return self.status in (
            ItineraryStatus.PLANNED,
            ItineraryStatus.CONFIRMED,
            ItineraryStatus.IN_PROGRESS,
        )


class DailyPlan(Base):
    """Daily plan for organizing activities by day."""

    __tablename__ = "daily_plans"

    itinerary_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("itineraries.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_number: Mapped[int] = mapped_column(
        nullable=False,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    daily_budget: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=True,
    )

    # Relationships
    itinerary: Mapped["Itinerary"] = relationship(
        "Itinerary",
        back_populates="daily_plans",
    )
    activities: Mapped[list["Activity"]] = relationship(
        "Activity",
        back_populates="daily_plan",
        cascade="all, delete-orphan",
        order_by="Activity.order",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_daily_plans_itinerary_day", "itinerary_id", "day_number", unique=True
        ),
    )


class Activity(Base):
    """Activity model representing a single activity in an itinerary."""

    __tablename__ = "activities"

    itinerary_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("itineraries.id", ondelete="CASCADE"),
        nullable=False,
    )
    daily_plan_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("daily_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    day_number: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )
    order: Mapped[int] = mapped_column(
        default=0,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    category: Mapped[ActivityCategory] = mapped_column(
        Enum(ActivityCategory, native_enum=True, name="activity_category"),
        nullable=False,
        default=ActivityCategory.SIGHTSEEING,
    )

    # Location information
    location_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    location_address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    latitude: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    longitude: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    google_place_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Time information
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_minutes: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Cost information
    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=True,
    )
    actual_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=True,
    )

    # Booking information
    booking_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    booking_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    itinerary: Mapped["Itinerary"] = relationship(
        "Itinerary",
        back_populates="activities",
    )
    daily_plan: Mapped["DailyPlan | None"] = relationship(
        "DailyPlan",
        back_populates="activities",
    )

    __table_args__ = (
        CheckConstraint(
            "end_time IS NULL OR start_time IS NULL OR end_time >= start_time",
            name="valid_activity_time",
        ),
        CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="non_negative_estimated_cost",
        ),
        CheckConstraint(
            "actual_cost IS NULL OR actual_cost >= 0",
            name="non_negative_actual_cost",
        ),
        Index("ix_activities_itinerary_day", "itinerary_id", "day_number"),
    )

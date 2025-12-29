"""User preferences model for onboarding and personalization.

This module defines the UserPreferences model with support for:
- Travel style preferences
- Food preferences
- Mobility preferences
- Budget preferences
- Onboarding status tracking
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.database import Base


class TravelStyle(str, enum.Enum):
    """Enum for travel style preferences."""
    
    RELAXED = "relaxed"           # เน้นพักผ่อน
    ADVENTUROUS = "adventurous"   # ชอบผจญภัย
    CULTURAL = "cultural"         # สนใจวัฒนธรรม
    FOODIE = "foodie"             # เน้นกิน
    BUDGET = "budget"             # ประหยัด
    LUXURY = "luxury"             # หรูหรา


class MobilityPreference(str, enum.Enum):
    """Enum for mobility preferences."""
    
    WALKING = "walking"           # เน้นเดิน
    PUBLIC_TRANSIT = "public_transit"  # ขนส่งสาธารณะ
    DRIVING = "driving"           # ขับรถเอง
    MIXED = "mixed"               # ผสมผสาน


class FoodPreference(str, enum.Enum):
    """Enum for food preferences."""
    
    LOCAL = "local"               # อาหารท้องถิ่น
    INTERNATIONAL = "international"  # อาหารนานาชาติ
    VEGETARIAN = "vegetarian"     # มังสวิรัติ
    HALAL = "halal"               # ฮาลาล
    ANY = "any"                   # ไม่จำกัด


class BudgetLevel(str, enum.Enum):
    """Enum for budget level preferences."""
    
    BUDGET = "budget"             # ประหยัด
    MODERATE = "moderate"         # ปานกลาง
    PREMIUM = "premium"           # พรีเมี่ยม
    LUXURY = "luxury"             # หรูหรา


class UserPreferences(Base):
    """User preferences model for travel personalization.
    
    Attributes:
        user_id: Reference to the user
        travel_styles: List of preferred travel styles
        food_preference: Food preference
        mobility_preference: Preferred mode of transportation
        budget_level: Budget level preference
        interests: List of specific interests (e.g., temples, beaches, nightlife)
        dietary_restrictions: List of dietary restrictions
        accessibility_needs: Accessibility requirements
        preferred_languages: Preferred languages for communication
        has_completed_onboarding: Whether onboarding is complete
        onboarding_completed_at: Timestamp when onboarding was completed
        custom_preferences: JSON field for additional custom preferences
    """

    __tablename__ = "user_preferences"

    # Foreign key to users table
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Travel style preferences (can select multiple)
    travel_styles: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )

    # Food preference
    food_preference: Mapped[FoodPreference | None] = mapped_column(
        Enum(FoodPreference),
        nullable=True,
    )

    # Mobility preference
    mobility_preference: Mapped[MobilityPreference | None] = mapped_column(
        Enum(MobilityPreference),
        nullable=True,
    )

    # Budget level
    budget_level: Mapped[BudgetLevel | None] = mapped_column(
        Enum(BudgetLevel),
        nullable=True,
    )

    # Specific interests (e.g., ["temples", "beaches", "shopping", "nightlife"])
    interests: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
    )

    # Dietary restrictions (e.g., ["no_pork", "no_shellfish", "gluten_free"])
    dietary_restrictions: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
    )

    # Accessibility needs description
    accessibility_needs: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Preferred languages (e.g., ["th", "en", "zh"])
    preferred_languages: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(10)),
        nullable=True,
    )

    # Onboarding status
    has_completed_onboarding: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    onboarding_step: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # Custom preferences as JSON for flexibility
    custom_preferences: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserPreferences(user_id={self.user_id}, onboarding={self.has_completed_onboarding})>"

    def complete_onboarding(self) -> None:
        """Mark onboarding as complete."""
        self.has_completed_onboarding = True
        self.onboarding_completed_at = func.now()

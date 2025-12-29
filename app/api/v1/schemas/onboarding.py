"""Onboarding schemas for API requests and responses.

This module defines request/response schemas for onboarding endpoints
including questions, preferences, and onboarding status.
"""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============ Enums ============


class TravelStyleEnum(str, Enum):
    """Travel style options."""
    
    RELAXED = "relaxed"
    ADVENTUROUS = "adventurous"
    CULTURAL = "cultural"
    FOODIE = "foodie"
    BUDGET = "budget"
    LUXURY = "luxury"


class MobilityPreferenceEnum(str, Enum):
    """Mobility preference options."""
    
    WALKING = "walking"
    PUBLIC_TRANSIT = "public_transit"
    DRIVING = "driving"
    MIXED = "mixed"


class FoodPreferenceEnum(str, Enum):
    """Food preference options."""
    
    LOCAL = "local"
    INTERNATIONAL = "international"
    VEGETARIAN = "vegetarian"
    HALAL = "halal"
    ANY = "any"


class BudgetLevelEnum(str, Enum):
    """Budget level options."""
    
    BUDGET = "budget"
    MODERATE = "moderate"
    PREMIUM = "premium"
    LUXURY = "luxury"


# ============ Question Schemas ============


class OnboardingOption(BaseModel):
    """Single option for an onboarding question."""
    
    value: str = Field(..., description="Option value to be stored")
    label_th: str = Field(..., description="Thai label for display")
    label_en: str = Field(..., description="English label for display")
    icon: str | None = Field(None, description="Optional icon name or emoji")


class OnboardingQuestion(BaseModel):
    """Single onboarding question with options."""
    
    id: str = Field(..., description="Unique question identifier")
    question_th: str = Field(..., description="Question text in Thai")
    question_en: str = Field(..., description="Question text in English")
    description_th: str | None = Field(None, description="Additional description in Thai")
    description_en: str | None = Field(None, description="Additional description in English")
    question_type: Literal["single", "multiple", "text"] = Field(
        ..., 
        description="Type of answer expected"
    )
    field_name: str = Field(..., description="Field name in preferences")
    options: list[OnboardingOption] | None = Field(
        None, 
        description="Available options for single/multiple choice"
    )
    is_required: bool = Field(default=False, description="Whether answer is required")
    is_skippable: bool = Field(default=True, description="Whether question can be skipped")


class OnboardingQuestionsResponse(BaseModel):
    """Response containing all onboarding questions."""
    
    total_steps: int = Field(..., description="Total number of onboarding steps")
    current_step: int = Field(..., description="User's current step")
    questions: list[OnboardingQuestion] = Field(..., description="List of questions")


# ============ Answer Schemas ============


class OnboardingAnswerRequest(BaseModel):
    """Request to save onboarding answers for a specific step."""
    
    step: int = Field(..., ge=1, description="Step number being answered")
    answers: dict = Field(
        ..., 
        description="Map of question_id/field_name to answer value(s)"
    )


class SkipOnboardingRequest(BaseModel):
    """Request to skip remaining onboarding steps."""
    
    skip_remaining: bool = Field(
        default=True, 
        description="Confirm skipping remaining questions"
    )


# ============ Preferences Schemas ============


class UserPreferencesBase(BaseModel):
    """Base schema for user preferences."""
    
    travel_styles: list[TravelStyleEnum] | None = Field(
        None, 
        description="Preferred travel styles"
    )
    food_preference: FoodPreferenceEnum | None = Field(
        None, 
        description="Food preference"
    )
    mobility_preference: MobilityPreferenceEnum | None = Field(
        None, 
        description="Preferred mode of transportation"
    )
    budget_level: BudgetLevelEnum | None = Field(
        None, 
        description="Budget level"
    )
    interests: list[str] | None = Field(
        None, 
        description="Specific interests"
    )
    dietary_restrictions: list[str] | None = Field(
        None, 
        description="Dietary restrictions"
    )
    accessibility_needs: str | None = Field(
        None, 
        max_length=500,
        description="Accessibility requirements"
    )
    preferred_languages: list[str] | None = Field(
        None, 
        description="Preferred languages (ISO codes)"
    )


class UserPreferencesCreate(UserPreferencesBase):
    """Schema for creating user preferences."""
    
    pass


class UserPreferencesUpdate(UserPreferencesBase):
    """Schema for updating user preferences."""
    
    custom_preferences: dict | None = Field(
        None, 
        description="Additional custom preferences"
    )


class UserPreferencesResponse(UserPreferencesBase):
    """Response schema for user preferences."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    has_completed_onboarding: bool
    onboarding_completed_at: datetime | None
    onboarding_step: int
    custom_preferences: dict | None
    created_at: datetime
    updated_at: datetime


# ============ Status Schemas ============


class OnboardingStatusResponse(BaseModel):
    """Response for onboarding status check."""
    
    has_accepted_terms: bool = Field(
        ..., 
        description="Whether user has accepted terms"
    )
    has_completed_onboarding: bool = Field(
        ..., 
        description="Whether onboarding is complete"
    )
    current_step: int = Field(
        ..., 
        description="Current onboarding step (0 if not started)"
    )
    total_steps: int = Field(
        ..., 
        description="Total number of onboarding steps"
    )
    next_action: Literal["accept_terms", "continue_onboarding", "complete"] = Field(
        ..., 
        description="Next action required from user"
    )


class CompleteOnboardingResponse(BaseModel):
    """Response after completing onboarding."""
    
    message: str
    preferences: UserPreferencesResponse

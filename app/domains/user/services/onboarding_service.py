"""Onboarding service for user profile setup.

This module provides business logic for the onboarding flow including:
- Getting onboarding questions
- Saving user answers
- Tracking onboarding progress
- Completing onboarding
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.onboarding import (
    CompleteOnboardingResponse,
    OnboardingAnswerRequest,
    OnboardingOption,
    OnboardingQuestion,
    OnboardingQuestionsResponse,
    OnboardingStatusResponse,
    UserPreferencesResponse,
    UserPreferencesUpdate,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.domains.user.models import User
from app.domains.user.preferences_repository import UserPreferencesRepository


# Total number of onboarding steps
TOTAL_ONBOARDING_STEPS = 4


# Onboarding questions data
ONBOARDING_QUESTIONS: list[OnboardingQuestion] = [
    # Step 1: Travel Style
    OnboardingQuestion(
        id="travel_style",
        question_th="สไตล์การเที่ยวของคุณเป็นแบบไหน?",
        question_en="What's your travel style?",
        description_th="เลือกได้มากกว่า 1 ข้อ",
        description_en="You can select more than one",
        question_type="multiple",
        field_name="travel_styles",
        is_required=False,
        is_skippable=True,
        options=[
            OnboardingOption(
                value="relaxed",
                label_th="ชิลๆ พักผ่อน",
                label_en="Relaxed & Easy",
                icon="🏖️",
            ),
            OnboardingOption(
                value="adventurous",
                label_th="ผจญภัย ท้าทาย",
                label_en="Adventurous",
                icon="🏔️",
            ),
            OnboardingOption(
                value="cultural",
                label_th="สนใจวัฒนธรรม ประวัติศาสตร์",
                label_en="Cultural & Historical",
                icon="🏛️",
            ),
            OnboardingOption(
                value="foodie",
                label_th="เน้นกิน ตามหาของอร่อย",
                label_en="Food Explorer",
                icon="🍜",
            ),
            OnboardingOption(
                value="budget",
                label_th="ประหยัด คุ้มค่า",
                label_en="Budget-Friendly",
                icon="💰",
            ),
            OnboardingOption(
                value="luxury",
                label_th="หรูหรา พรีเมี่ยม",
                label_en="Luxury",
                icon="✨",
            ),
        ],
    ),
    # Step 2: Food Preference
    OnboardingQuestion(
        id="food_pref",
        question_th="ชอบกินอาหารแบบไหน?",
        question_en="What type of food do you prefer?",
        description_th="เราจะแนะนำร้านอาหารที่เหมาะกับคุณ",
        description_en="We'll recommend restaurants that suit you",
        question_type="single",
        field_name="food_preference",
        is_required=False,
        is_skippable=True,
        options=[
            OnboardingOption(
                value="local",
                label_th="อาหารท้องถิ่น / Local food",
                label_en="Local Cuisine",
                icon="🍲",
            ),
            OnboardingOption(
                value="international",
                label_th="อาหารนานาชาติ",
                label_en="International",
                icon="🌎",
            ),
            OnboardingOption(
                value="vegetarian",
                label_th="มังสวิรัติ / Vegetarian",
                label_en="Vegetarian",
                icon="🥗",
            ),
            OnboardingOption(
                value="halal",
                label_th="ฮาลาล / Halal",
                label_en="Halal",
                icon="🌙",
            ),
            OnboardingOption(
                value="any",
                label_th="กินได้ทุกอย่าง",
                label_en="No Preference",
                icon="😋",
            ),
        ],
    ),
    # Step 3: Mobility Preference
    OnboardingQuestion(
        id="mobility_pref",
        question_th="เน้นเดินหรือเน้นนั่งรถ?",
        question_en="How do you prefer to get around?",
        description_th="เราจะวางแผนเส้นทางให้เหมาะกับคุณ",
        description_en="We'll plan routes that fit your style",
        question_type="single",
        field_name="mobility_preference",
        is_required=False,
        is_skippable=True,
        options=[
            OnboardingOption(
                value="walking",
                label_th="เน้นเดิน ชอบสำรวจ",
                label_en="Walking & Exploring",
                icon="🚶",
            ),
            OnboardingOption(
                value="public_transit",
                label_th="ขนส่งสาธารณะ",
                label_en="Public Transit",
                icon="🚇",
            ),
            OnboardingOption(
                value="driving",
                label_th="ขับรถเอง / Taxi",
                label_en="Driving / Taxi",
                icon="🚗",
            ),
            OnboardingOption(
                value="mixed",
                label_th="ผสมผสาน แล้วแต่สถานการณ์",
                label_en="Mixed - Depends",
                icon="🔀",
            ),
        ],
    ),
    # Step 4: Budget Level
    OnboardingQuestion(
        id="budget_level",
        question_th="งบประมาณในการเที่ยวประมาณไหน?",
        question_en="What's your typical travel budget?",
        description_th="เราจะแนะนำที่พักและกิจกรรมที่เหมาะสม",
        description_en="We'll recommend suitable accommodations and activities",
        question_type="single",
        field_name="budget_level",
        is_required=False,
        is_skippable=True,
        options=[
            OnboardingOption(
                value="budget",
                label_th="ประหยัด (Backpacker style)",
                label_en="Budget (Backpacker)",
                icon="🎒",
            ),
            OnboardingOption(
                value="moderate",
                label_th="ปานกลาง (Mid-range)",
                label_en="Moderate (Mid-range)",
                icon="👍",
            ),
            OnboardingOption(
                value="premium",
                label_th="พรีเมี่ยม (Comfort first)",
                label_en="Premium (Comfort First)",
                icon="⭐",
            ),
            OnboardingOption(
                value="luxury",
                label_th="หรูหรา (Best of the best)",
                label_en="Luxury (Best of Best)",
                icon="👑",
            ),
        ],
    ),
]


# Question index by step (1-indexed)
QUESTIONS_BY_STEP: dict[int, list[OnboardingQuestion]] = {
    1: [ONBOARDING_QUESTIONS[0]],  # Travel style
    2: [ONBOARDING_QUESTIONS[1]],  # Food preference
    3: [ONBOARDING_QUESTIONS[2]],  # Mobility preference
    4: [ONBOARDING_QUESTIONS[3]],  # Budget level
}


class OnboardingService:
    """Service for onboarding operations.
    
    Handles the onboarding flow including questions, answers,
    progress tracking, and completion.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with database session."""
        self._session = session
        self._prefs_repo = UserPreferencesRepository(session)

    async def get_onboarding_status(self, user: User) -> OnboardingStatusResponse:
        """Get current onboarding status for user.
        
        Args:
            user: The authenticated user
            
        Returns:
            OnboardingStatusResponse with current status
        """
        prefs, _ = await self._prefs_repo.get_or_create_for_user(user.id)
        await self._session.commit()
        
        # Determine next action
        next_action: Literal["accept_terms", "continue_onboarding", "complete"]
        if not user.has_accepted_terms:
            next_action = "accept_terms"
        elif not prefs.has_completed_onboarding:
            next_action = "continue_onboarding"
        else:
            next_action = "complete"
        
        return OnboardingStatusResponse(
            has_accepted_terms=user.has_accepted_terms,
            has_completed_onboarding=prefs.has_completed_onboarding,
            current_step=prefs.onboarding_step,
            total_steps=TOTAL_ONBOARDING_STEPS,
            next_action=next_action,
        )

    async def get_onboarding_questions(
        self,
        user: User,
        step: int | None = None,
    ) -> OnboardingQuestionsResponse:
        """Get onboarding questions.
        
        Args:
            user: The authenticated user
            step: Optional specific step to get (returns all if None)
            
        Returns:
            OnboardingQuestionsResponse with questions
        """
        prefs, _ = await self._prefs_repo.get_or_create_for_user(user.id)
        await self._session.commit()
        
        if step is not None:
            if step < 1 or step > TOTAL_ONBOARDING_STEPS:
                raise BadRequestError(f"Invalid step: {step}. Must be 1-{TOTAL_ONBOARDING_STEPS}")
            questions = QUESTIONS_BY_STEP.get(step, [])
        else:
            questions = ONBOARDING_QUESTIONS
        
        return OnboardingQuestionsResponse(
            total_steps=TOTAL_ONBOARDING_STEPS,
            current_step=prefs.onboarding_step,
            questions=questions,
        )

    async def save_onboarding_answers(
        self,
        user: User,
        data: OnboardingAnswerRequest,
    ) -> UserPreferencesResponse:
        """Save onboarding answers for a specific step.
        
        Args:
            user: The authenticated user
            data: The answers to save
            
        Returns:
            Updated UserPreferencesResponse
        """
        if data.step < 1 or data.step > TOTAL_ONBOARDING_STEPS:
            raise BadRequestError(f"Invalid step: {data.step}")
        
        prefs, _ = await self._prefs_repo.get_or_create_for_user(user.id)
        
        # Build update dict from answers
        update_data: dict = {}
        
        for field_name, value in data.answers.items():
            # Validate field name is valid
            valid_fields = {
                "travel_styles", "food_preference", "mobility_preference",
                "budget_level", "interests", "dietary_restrictions",
                "accessibility_needs", "preferred_languages", "custom_preferences",
            }
            if field_name in valid_fields:
                update_data[field_name] = value
        
        # Update step if advancing
        if data.step >= prefs.onboarding_step:
            update_data["onboarding_step"] = data.step
        
        # Update preferences
        await self._prefs_repo.update(prefs.id, update_data)
        await self._session.commit()
        
        # Refresh and return
        updated_prefs = await self._prefs_repo.find_by_user_id(user.id)
        return UserPreferencesResponse.model_validate(updated_prefs)

    async def skip_onboarding(self, user: User) -> UserPreferencesResponse:
        """Skip remaining onboarding steps and mark as complete.
        
        Args:
            user: The authenticated user
            
        Returns:
            Updated UserPreferencesResponse
        """
        prefs, _ = await self._prefs_repo.get_or_create_for_user(user.id)
        
        await self._prefs_repo.update(
            prefs.id,
            {
                "has_completed_onboarding": True,
                "onboarding_completed_at": datetime.utcnow(),
                "onboarding_step": TOTAL_ONBOARDING_STEPS,
            },
        )
        await self._session.commit()
        
        updated_prefs = await self._prefs_repo.find_by_user_id(user.id)
        return UserPreferencesResponse.model_validate(updated_prefs)

    async def complete_onboarding(self, user: User) -> CompleteOnboardingResponse:
        """Mark onboarding as complete.
        
        Args:
            user: The authenticated user
            
        Returns:
            CompleteOnboardingResponse with success message
        """
        prefs, _ = await self._prefs_repo.get_or_create_for_user(user.id)
        
        await self._prefs_repo.update(
            prefs.id,
            {
                "has_completed_onboarding": True,
                "onboarding_completed_at": datetime.utcnow(),
            },
        )
        await self._session.commit()
        
        updated_prefs = await self._prefs_repo.find_by_user_id(user.id)
        
        return CompleteOnboardingResponse(
            message="Onboarding completed successfully! Welcome to AiGo! 🎉",
            preferences=UserPreferencesResponse.model_validate(updated_prefs),
        )

    async def get_user_preferences(self, user: User) -> UserPreferencesResponse:
        """Get current user preferences.
        
        Args:
            user: The authenticated user
            
        Returns:
            UserPreferencesResponse
        """
        prefs, _ = await self._prefs_repo.get_or_create_for_user(user.id)
        await self._session.commit()
        
        return UserPreferencesResponse.model_validate(prefs)

    async def update_user_preferences(
        self,
        user: User,
        data: UserPreferencesUpdate,
    ) -> UserPreferencesResponse:
        """Update user preferences.
        
        Args:
            user: The authenticated user
            data: The preferences to update
            
        Returns:
            Updated UserPreferencesResponse
        """
        prefs, _ = await self._prefs_repo.get_or_create_for_user(user.id)
        
        # Only update non-None fields
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        
        if update_data:
            await self._prefs_repo.update(prefs.id, update_data)
            await self._session.commit()
        
        updated_prefs = await self._prefs_repo.find_by_user_id(user.id)
        return UserPreferencesResponse.model_validate(updated_prefs)

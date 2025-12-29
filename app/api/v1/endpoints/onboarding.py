"""Onboarding API endpoints.

This module provides REST API endpoints for:
- Getting onboarding status
- Getting onboarding questions
- Saving onboarding answers
- Skipping onboarding
- Completing onboarding
- Managing user preferences
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.onboarding import (
    CompleteOnboardingResponse,
    OnboardingAnswerRequest,
    OnboardingQuestionsResponse,
    OnboardingStatusResponse,
    SkipOnboardingRequest,
    UserPreferencesResponse,
    UserPreferencesUpdate,
)
from app.core.deps import ActiveUser
from app.domains.user.services.onboarding_service import OnboardingService
from app.infra.database import get_db

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


# Dependency for onboarding service
async def get_onboarding_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingService:
    """Get onboarding service instance."""
    return OnboardingService(session)


@router.get(
    "/status",
    response_model=OnboardingStatusResponse,
    summary="Get onboarding status",
    description="Check current onboarding status and determine next action.",
)
async def get_onboarding_status(
    current_user: ActiveUser,
    onboarding_service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> OnboardingStatusResponse:
    """Get onboarding status for current user.
    
    Returns:
        - Whether user has accepted terms
        - Whether onboarding is complete
        - Current step number
        - Next action required (accept_terms, continue_onboarding, or complete)
    
    Raises:
        401 Unauthorized: If not authenticated
    """
    return await onboarding_service.get_onboarding_status(current_user)


@router.get(
    "/questions",
    response_model=OnboardingQuestionsResponse,
    summary="Get onboarding questions",
    description="Get onboarding questions for display. Can optionally filter by step.",
)
async def get_onboarding_questions(
    current_user: ActiveUser,
    onboarding_service: Annotated[OnboardingService, Depends(get_onboarding_service)],
    step: int | None = Query(
        None,
        ge=1,
        le=4,
        description="Specific step to get questions for (1-4). Returns all if not specified.",
    ),
) -> OnboardingQuestionsResponse:
    """Get onboarding questions.
    
    Returns questions with options in both Thai and English.
    If step is specified, returns only questions for that step.
    
    Raises:
        401 Unauthorized: If not authenticated
        400 Bad Request: If step is invalid
    """
    return await onboarding_service.get_onboarding_questions(current_user, step)


@router.post(
    "/answers",
    response_model=UserPreferencesResponse,
    summary="Save onboarding answers",
    description="Save answers for a specific onboarding step.",
)
async def save_onboarding_answers(
    data: OnboardingAnswerRequest,
    current_user: ActiveUser,
    onboarding_service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> UserPreferencesResponse:
    """Save onboarding answers for a step.
    
    Example request body:
    ```json
    {
        "step": 1,
        "answers": {
            "travel_styles": ["relaxed", "foodie"]
        }
    }
    ```
    
    Raises:
        401 Unauthorized: If not authenticated
        400 Bad Request: If step or answers are invalid
    """
    return await onboarding_service.save_onboarding_answers(current_user, data)


@router.post(
    "/skip",
    response_model=UserPreferencesResponse,
    summary="Skip onboarding",
    description="Skip remaining onboarding steps and mark as complete.",
)
async def skip_onboarding(
    data: SkipOnboardingRequest,
    current_user: ActiveUser,
    onboarding_service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> UserPreferencesResponse:
    """Skip remaining onboarding steps.
    
    User can always update preferences later in settings.
    
    Raises:
        401 Unauthorized: If not authenticated
    """
    return await onboarding_service.skip_onboarding(current_user)


@router.post(
    "/complete",
    response_model=CompleteOnboardingResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete onboarding",
    description="Mark onboarding as complete after all steps.",
)
async def complete_onboarding(
    current_user: ActiveUser,
    onboarding_service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> CompleteOnboardingResponse:
    """Complete the onboarding process.
    
    Call this after the user has completed all onboarding steps
    or after they choose to skip the remaining steps.
    
    Raises:
        401 Unauthorized: If not authenticated
    """
    return await onboarding_service.complete_onboarding(current_user)


@router.get(
    "/preferences",
    response_model=UserPreferencesResponse,
    summary="Get user preferences",
    description="Get current user travel preferences.",
)
async def get_preferences(
    current_user: ActiveUser,
    onboarding_service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> UserPreferencesResponse:
    """Get current user preferences.
    
    Returns all stored preferences including:
    - Travel styles
    - Food preference
    - Mobility preference
    - Budget level
    - Interests
    - Dietary restrictions
    - And more...
    
    Raises:
        401 Unauthorized: If not authenticated
    """
    return await onboarding_service.get_user_preferences(current_user)


@router.patch(
    "/preferences",
    response_model=UserPreferencesResponse,
    summary="Update user preferences",
    description="Update user travel preferences. Can be used anytime after registration.",
)
async def update_preferences(
    data: UserPreferencesUpdate,
    current_user: ActiveUser,
    onboarding_service: Annotated[OnboardingService, Depends(get_onboarding_service)],
) -> UserPreferencesResponse:
    """Update user preferences.
    
    Partial updates are supported - only include fields you want to change.
    
    Example request body:
    ```json
    {
        "food_preference": "local",
        "budget_level": "moderate"
    }
    ```
    
    Raises:
        401 Unauthorized: If not authenticated
        422 Unprocessable Entity: If validation fails
    """
    return await onboarding_service.update_user_preferences(current_user, data)

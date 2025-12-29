"""Authentication schemas for API requests and responses.

This module defines request/response schemas for auth endpoints
including login, registration, social login, and token operations.
"""

import enum
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AuthProviderEnum(str, enum.Enum):
    """Auth provider enum for schemas (mirrors domain model)."""

    LOCAL = "local"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    APPLE = "apple"


# ============ Request Schemas ============


class LoginRequest(BaseModel):
    """Schema for email/password login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets minimum security requirements."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class SocialLoginRequest(BaseModel):
    """Schema for social login (Google/Facebook/Apple).
    
    The token is the OAuth access token or ID token from the provider.
    """

    provider: Literal["google", "facebook", "apple"] = Field(
        ...,
        description="OAuth provider (google, facebook, apple)",
    )
    token: str = Field(
        ...,
        min_length=1,
        description="OAuth access token or ID token from the provider",
    )


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh."""

    refresh_token: str = Field(..., min_length=1)


class AcceptTermsRequest(BaseModel):
    """Schema for accepting terms of service."""

    accept: bool = Field(
        ...,
        description="Must be True to accept terms",
    )

    @field_validator("accept")
    @classmethod
    def must_accept(cls, v: bool) -> bool:
        """Validate that terms are accepted."""
        if not v:
            raise ValueError("You must accept the terms of service")
        return v


# ============ Response Schemas ============


class UserInResponse(BaseModel):
    """User data included in auth responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    avatar_url: str | None = None
    provider: str  # String to avoid import issues
    is_active: bool
    is_verified: bool
    has_accepted_terms: bool
    terms_accepted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OnboardingStatus(BaseModel):
    """Onboarding status included in auth response."""
    
    has_completed_onboarding: bool = Field(
        default=False,
        description="Whether user has completed onboarding"
    )
    current_step: int = Field(
        default=0,
        description="Current onboarding step (0 if not started)"
    )
    next_action: str = Field(
        default="accept_terms",
        description="Next action: accept_terms, continue_onboarding, or complete"
    )


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


class AuthResponse(BaseModel):
    """Standard auth response with tokens and user profile."""

    message: str
    tokens: TokenResponse
    user: UserInResponse
    onboarding: OnboardingStatus | None = Field(
        None,
        description="Onboarding status (included for new registrations and logins)"
    )


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
    success: bool = True


class TermsAcceptedResponse(BaseModel):
    """Response after accepting terms."""

    message: str
    user: UserInResponse

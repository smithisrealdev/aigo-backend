"""Pydantic schemas for the User domain.

This module defines the request/response schemas for user operations
including local registration, social login, and profile updates.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domains.user.models import AuthProvider


# ============ Base Schemas ============


class UserBase(BaseModel):
    """Base schema for User with common fields."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    avatar_url: str | None = Field(None, max_length=500)


# ============ Create Schemas ============


class UserCreate(UserBase):
    """Schema for creating a local user (email/password registration).
    
    Password requirements:
    - Minimum 8 characters
    - Maximum 100 characters
    """

    password: str = Field(..., min_length=8, max_length=100)
    
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


class UserCreateSocial(UserBase):
    """Schema for creating a user via social login.
    
    Social users don't require a password as authentication
    is handled by the OAuth provider.
    """

    provider: AuthProvider = Field(..., description="OAuth provider")
    social_id: str = Field(..., min_length=1, max_length=255)
    is_verified: bool = Field(
        default=True,
        description="Social logins are typically pre-verified"
    )


# ============ Update Schemas ============


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    full_name: str | None = Field(None, min_length=1, max_length=255)
    avatar_url: str | None = Field(None, max_length=500)


class UserUpdatePassword(BaseModel):
    """Schema for updating user password."""

    current_password: str = Field(..., min_length=8, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, v: str) -> str:
        """Validate new password meets minimum security requirements."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class TermsAcceptance(BaseModel):
    """Schema for accepting terms of service."""

    accept: bool = Field(
        ...,
        description="Must be True to accept terms"
    )

    @field_validator("accept")
    @classmethod
    def must_accept_terms(cls, v: bool) -> bool:
        """Validate that terms are accepted."""
        if not v:
            raise ValueError("You must accept the terms of service")
        return v


# ============ Response Schemas ============


class UserResponse(UserBase):
    """Schema for user response (public data)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: AuthProvider
    is_active: bool
    is_verified: bool
    has_accepted_terms: bool
    terms_accepted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserProfileResponse(UserResponse):
    """Schema for detailed user profile response."""

    last_login_at: datetime | None = None


class UserMinimalResponse(BaseModel):
    """Minimal user response for embedding in other responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    avatar_url: str | None = None

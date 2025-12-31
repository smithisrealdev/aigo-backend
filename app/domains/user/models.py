"""SQLAlchemy models for the User domain.

This module defines the User model with support for:
- Local authentication (email/password)
- Social login (Google, Facebook, Apple)
- Terms acceptance tracking
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Index, String, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.database import Base


class AuthProvider(str, enum.Enum):
    """Enum for authentication providers.
    
    Supports both local (email/password) and social login providers.
    """

    LOCAL = "local"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    APPLE = "apple"


class User(Base):
    """User model with social login and terms acceptance support.
    
    Attributes:
        email: User's email address (unique identifier)
        hashed_password: Bcrypt hashed password (nullable for social login)
        full_name: User's full display name
        avatar_url: URL to user's profile picture
        provider: Authentication provider (LOCAL, GOOGLE, FACEBOOK, APPLE)
        social_id: Unique identifier from social provider
        is_active: Whether the user account is active
        is_verified: Whether the user's email is verified
        has_accepted_terms: Whether user has accepted terms of service
        terms_accepted_at: Timestamp when terms were accepted
        last_login_at: Timestamp of last successful login
    """

    __tablename__ = "users"

    # Authentication fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # Nullable for social login users
    )
    
    # Profile fields
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Social login fields
    provider: Mapped[str] = mapped_column(
        PG_ENUM('local', 'google', 'facebook', 'apple', name='authprovider', create_type=False),
        nullable=False,
        server_default='local',
    )
    social_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # Only set for social login users
        index=True,
    )

    # Account status fields
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Terms acceptance fields
    has_accepted_terms: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Login tracking
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Indexes for common queries
    __table_args__ = (
        # Composite index for social login lookups
        Index("ix_users_provider_social_id", "provider", "social_id"),
    )

    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<User(id={self.id}, email={self.email}, provider={self.provider})>"

    def accept_terms(self) -> None:
        """Mark the user as having accepted the terms of service."""
        self.has_accepted_terms = True
        self.terms_accepted_at = func.now()

    def update_last_login(self) -> None:
        """Update the last login timestamp."""
        self.last_login_at = func.now()

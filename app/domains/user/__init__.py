"""User domain module.

This module contains all user-related functionality including:
- User model with social login support
- User preferences model for onboarding
- Authentication providers (LOCAL, GOOGLE, FACEBOOK, APPLE)
- Terms acceptance tracking
- Password hashing utilities

Note: Use direct imports to avoid circular dependencies:

    from app.domains.user.models import User, AuthProvider
    from app.domains.user.preferences import UserPreferences
    from app.domains.user.repository import UserRepository
    from app.domains.user.preferences_repository import UserPreferencesRepository
    from app.domains.user.schemas import UserCreate, UserResponse
    from app.domains.user.security import PasswordHasher
"""

__all__ = [
    "AuthProvider",
    "User",
    "UserPreferences",
    "UserRepository",
    "UserPreferencesRepository",
    "UserCreate",
    "UserCreateSocial",
    "UserResponse",
    "UserUpdate",
    "PasswordHasher",
]

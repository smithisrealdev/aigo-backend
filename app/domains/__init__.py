"""Domain modules - Business logic organized by bounded contexts.

Note: Domain modules are imported lazily to avoid circular imports.
Import them directly where needed:

    from app.domains.user.models import User, AuthProvider
    from app.domains.user.repository import UserRepository
    from app.domains.user.schemas import UserCreate, UserResponse
"""

__all__ = [
    # User domain exports (import directly from app.domains.user.*)
    "AuthProvider",
    "User",
    "UserRepository",
    "UserCreate",
    "UserCreateSocial",
    "UserResponse",
    "UserUpdate",
]

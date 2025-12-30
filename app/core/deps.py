"""FastAPI dependencies for authentication and authorization.

This module provides injectable dependencies for:
- Current user retrieval from JWT
- Active user validation
- Terms acceptance verification
- Role-based access control (future)
"""

from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenPayload, token_service
from app.core.exceptions import (
    InactiveUserError,
    InvalidTokenError,
    TermsNotAcceptedError,
    UnverifiedUserError,
    UserNotFoundError,
)

# Type checking imports (not executed at runtime)
if TYPE_CHECKING:
    from app.domains.user.models import User

# OAuth2 scheme for token extraction from Authorization header
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login/form",
    auto_error=True,
)

# Optional OAuth2 scheme (doesn't raise error if token missing)
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login/form",
    auto_error=False,
)


def _get_user_repository(session: AsyncSession):
    """Lazy import and instantiate UserRepository."""
    from app.domains.user.repository import UserRepository
    return UserRepository(session)


async def get_db_session_dep() -> AsyncSession:
    """Get database session dependency with lazy import."""
    from app.infra.database import get_db
    async for session in get_db():
        yield session


async def get_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> TokenPayload:
    """Extract and validate JWT payload from Authorization header.
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        Validated TokenPayload
        
    Raises:
        InvalidTokenError: If token is invalid or expired
    """
    payload = token_service.decode_access_token(token)
    if payload is None:
        raise InvalidTokenError()
    return payload


async def get_current_user_id(
    token_payload: Annotated[TokenPayload, Depends(get_token_payload)],
) -> UUID:
    """Get the current authenticated user ID from JWT token.
    
    This is a lightweight dependency that only extracts the user ID
    without database lookup. Use when you only need the ID.
    
    Args:
        token_payload: Validated JWT payload
        
    Returns:
        The user's UUID
        
    Raises:
        InvalidTokenError: If token is invalid or user ID malformed
    """
    try:
        return UUID(token_payload.sub)
    except ValueError:
        raise InvalidTokenError("Invalid user ID in token")


async def get_current_user(
    token_payload: Annotated[TokenPayload, Depends(get_token_payload)],
    session: Annotated[AsyncSession, Depends(get_db_session_dep)],
) -> "User":
    """Get the current authenticated user from JWT token.
    
    This dependency:
    1. Extracts and validates the JWT token
    2. Retrieves the user from database
    3. Verifies the user exists
    
    Args:
        token_payload: Validated JWT payload
        session: Database session
        
    Returns:
        The authenticated User
        
    Raises:
        InvalidTokenError: If token is invalid
        UserNotFoundError: If user doesn't exist
    """
    try:
        user_id = UUID(token_payload.sub)
    except ValueError:
        raise InvalidTokenError("Invalid user ID in token")

    repo = _get_user_repository(session)
    user = await repo.get(user_id)

    if user is None:
        raise UserNotFoundError()

    return user


async def get_current_active_user(
    current_user: Annotated[Any, Depends(get_current_user)],
) -> "User":
    """Get the current user and verify they are active.
    
    Use this dependency for endpoints that require an active user.
    
    Args:
        current_user: The authenticated user
        
    Returns:
        The active User
        
    Raises:
        InactiveUserError: If user account is inactive
    """
    if not current_user.is_active:
        raise InactiveUserError()
    return current_user


async def get_current_verified_user(
    current_user: Annotated[Any, Depends(get_current_active_user)],
) -> "User":
    """Get the current user and verify their email is verified.
    
    Use this dependency for endpoints that require email verification.
    
    Args:
        current_user: The active user
        
    Returns:
        The verified User
        
    Raises:
        UnverifiedUserError: If email not verified
    """
    if not current_user.is_verified:
        raise UnverifiedUserError()
    return current_user


async def check_terms_accepted(
    current_user: Annotated[Any, Depends(get_current_active_user)],
) -> "User":
    """Verify that the user has accepted terms of service.
    
    Use this dependency to protect routes that require terms acceptance.
    Blocks access with 403 Forbidden if terms not accepted.
    
    Args:
        current_user: The active user
        
    Returns:
        The User (if terms accepted)
        
    Raises:
        TermsNotAcceptedError: If terms not accepted (403 Forbidden)
    """
    if not current_user.has_accepted_terms:
        raise TermsNotAcceptedError()
    return current_user


async def get_current_user_with_terms(
    current_user: Annotated[Any, Depends(check_terms_accepted)],
) -> "User":
    """Convenience dependency combining active user + terms check.
    
    Use this for protected routes like Itinerary Generation.
    
    Args:
        current_user: User who has accepted terms
        
    Returns:
        The fully validated User
    """
    return current_user


async def get_optional_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme_optional)],
    session: Annotated[AsyncSession, Depends(get_db_session_dep)],
) -> "User | None":
    """Get current user if authenticated, None otherwise.
    
    Use this for endpoints that work with or without authentication.
    
    Args:
        token: Optional JWT token
        session: Database session
        
    Returns:
        User if authenticated, None otherwise
    """
    if token is None:
        return None

    payload = token_service.decode_access_token(token)
    if payload is None:
        return None

    try:
        user_id = UUID(payload.sub)
    except ValueError:
        return None

    repo = _get_user_repository(session)
    user = await repo.get(user_id)

    if user is None or not user.is_active:
        return None

    return user


# Type aliases for cleaner dependency injection
# Using Any to avoid circular import issues at runtime
CurrentUser = Annotated[Any, Depends(get_current_user)]
ActiveUser = Annotated[Any, Depends(get_current_active_user)]
VerifiedUser = Annotated[Any, Depends(get_current_verified_user)]
UserWithTerms = Annotated[Any, Depends(get_current_user_with_terms)]
OptionalUser = Annotated[Any, Depends(get_optional_current_user)]

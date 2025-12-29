"""Security utilities for authentication and authorization.

This module provides backward-compatible password utilities.
For JWT token operations, use app.core.auth instead.
"""

from datetime import timedelta

from app.core.auth import (
    TokenPair,
    TokenPayload,
    TokenService,
    create_access_token as _create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_access_token,
    decode_refresh_token,
    token_service,
)
from app.domains.user.security import (
    PasswordHasher,
    hash_password,
    verify_password,
)

# Re-export for backward compatibility
pwd_context = PasswordHasher
ALGORITHM = "HS256"


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.
    
    Backward-compatible wrapper around auth.create_access_token.
    """
    return _create_access_token(subject, expires_delta)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return hash_password(password)


__all__ = [
    "ALGORITHM",
    "PasswordHasher",
    "TokenPair",
    "TokenPayload",
    "TokenService",
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_access_token",
    "decode_refresh_token",
    "get_password_hash",
    "hash_password",
    "token_service",
    "verify_password",
]

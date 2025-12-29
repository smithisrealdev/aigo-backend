"""Authentication service with JWT token management.

This module provides:
- Access token and refresh token generation
- Token validation and decoding
- User authentication via email/password
- OAuth2 password bearer scheme for FastAPI
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings


class TokenType(str, Enum):
    """Enum for token types."""

    ACCESS = "access"
    REFRESH = "refresh"


# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""

    sub: str  # Subject (user_id)
    exp: datetime  # Expiration time
    iat: datetime  # Issued at
    type: TokenType  # Token type (access/refresh)
    jti: str | None = None  # JWT ID for refresh token revocation


class TokenPair(BaseModel):
    """Schema for access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Access token expiry in seconds


class TokenResponse(BaseModel):
    """Schema for token response to client."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenService:
    """Service for JWT token operations.
    
    Handles creation, validation, and decoding of JWTs
    for both access and refresh tokens.
    
    Example:
        token_service = TokenService()
        tokens = token_service.create_token_pair(user_id)
        payload = token_service.decode_access_token(tokens.access_token)
    """

    def __init__(
        self,
        secret_key: str = settings.SECRET_KEY,
        algorithm: str = ALGORITHM,
    ) -> None:
        """Initialize the token service.
        
        Args:
            secret_key: Secret key for JWT encoding
            algorithm: JWT algorithm (default: HS256)
        """
        self._secret_key = secret_key
        self._algorithm = algorithm

    def create_access_token(
        self,
        user_id: UUID | str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT access token.
        
        Args:
            user_id: The user's unique identifier
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT access token string
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        now = datetime.now(timezone.utc)
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "exp": expire,
            "iat": now,
            "type": TokenType.ACCESS.value,
        }

        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def create_refresh_token(
        self,
        user_id: UUID | str,
        expires_delta: timedelta | None = None,
        jti: str | None = None,
    ) -> str:
        """Create a JWT refresh token.
        
        Args:
            user_id: The user's unique identifier
            expires_delta: Optional custom expiration time
            jti: Optional JWT ID for token revocation
            
        Returns:
            Encoded JWT refresh token string
        """
        if expires_delta is None:
            expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        now = datetime.now(timezone.utc)
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "exp": expire,
            "iat": now,
            "type": TokenType.REFRESH.value,
        }

        if jti:
            payload["jti"] = jti

        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def create_token_pair(
        self,
        user_id: UUID | str,
        refresh_jti: str | None = None,
    ) -> TokenPair:
        """Create both access and refresh tokens.
        
        Args:
            user_id: The user's unique identifier
            refresh_jti: Optional JWT ID for refresh token
            
        Returns:
            TokenPair with both tokens
        """
        access_token = self.create_access_token(user_id)
        refresh_token = self.create_refresh_token(user_id, jti=refresh_jti)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        )

    def decode_token(self, token: str) -> TokenPayload | None:
        """Decode and validate a JWT token.
        
        Args:
            token: The JWT token string
            
        Returns:
            TokenPayload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
            )
            return TokenPayload(
                sub=payload["sub"],
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                type=TokenType(payload["type"]),
                jti=payload.get("jti"),
            )
        except JWTError:
            return None

    def decode_access_token(self, token: str) -> TokenPayload | None:
        """Decode and validate an access token.
        
        Args:
            token: The JWT access token string
            
        Returns:
            TokenPayload if valid access token, None otherwise
        """
        payload = self.decode_token(token)
        if payload and payload.type == TokenType.ACCESS:
            return payload
        return None

    def decode_refresh_token(self, token: str) -> TokenPayload | None:
        """Decode and validate a refresh token.
        
        Args:
            token: The JWT refresh token string
            
        Returns:
            TokenPayload if valid refresh token, None otherwise
        """
        payload = self.decode_token(token)
        if payload and payload.type == TokenType.REFRESH:
            return payload
        return None

    def get_user_id_from_token(self, token: str) -> UUID | None:
        """Extract user ID from a token.
        
        Args:
            token: The JWT token string
            
        Returns:
            User UUID if valid, None otherwise
        """
        payload = self.decode_token(token)
        if payload:
            try:
                return UUID(payload.sub)
            except ValueError:
                return None
        return None


# Global token service instance
token_service = TokenService()


# Convenience functions for direct usage
def create_access_token(
    user_id: UUID | str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    return token_service.create_access_token(user_id, expires_delta)


def create_refresh_token(
    user_id: UUID | str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token."""
    return token_service.create_refresh_token(user_id, expires_delta)


def create_token_pair(user_id: UUID | str) -> TokenPair:
    """Create both access and refresh tokens."""
    return token_service.create_token_pair(user_id)


def decode_access_token(token: str) -> TokenPayload | None:
    """Decode and validate an access token."""
    return token_service.decode_access_token(token)


def decode_refresh_token(token: str) -> TokenPayload | None:
    """Decode and validate a refresh token."""
    return token_service.decode_refresh_token(token)

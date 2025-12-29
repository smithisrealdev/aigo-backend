"""API v1 schemas package."""

from app.api.v1.schemas.auth import (
    AcceptTermsRequest,
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    SocialLoginRequest,
    TermsAcceptedResponse,
    TokenResponse,
    UserInResponse,
)

__all__ = [
    "AcceptTermsRequest",
    "AuthResponse",
    "LoginRequest",
    "MessageResponse",
    "RefreshTokenRequest",
    "RegisterRequest",
    "SocialLoginRequest",
    "TermsAcceptedResponse",
    "TokenResponse",
    "UserInResponse",
]

"""Authentication API endpoints.

This module provides REST API endpoints for:
- User registration (email/password)
- User login (email/password)
- Social login (Google/Facebook/Apple)
- Token refresh
- Terms acceptance
- Current user profile
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.auth import (
    AcceptTermsRequest,
    AuthResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SocialLoginRequest,
    TermsAcceptedResponse,
    TokenResponse,
    UserInResponse,
)
from app.core.deps import ActiveUser, get_current_active_user
from app.domains.user.services import AuthService
from app.infra.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Dependency for auth service
async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthService:
    """Get auth service instance."""
    return AuthService(session)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password.",
)
async def register(
    data: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    """Register a new user with email/password.
    
    Returns JWT tokens and user profile on success.
    
    Raises:
        409 Conflict: If email already registered
        422 Unprocessable Entity: If validation fails
    """
    return await auth_service.register(data)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login with email/password",
    description="Authenticate user with email and password.",
)
async def login(
    data: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    """Login with email and password.
    
    Returns JWT tokens and user profile on success.
    
    Raises:
        401 Unauthorized: If credentials invalid
    """
    return await auth_service.login(data)


@router.post(
    "/login/form",
    response_model=AuthResponse,
    summary="Login with OAuth2 form",
    description="Login endpoint compatible with OAuth2 password flow.",
    include_in_schema=False,  # Hide from docs, used for OAuth2 scheme
)
async def login_form(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    """Login with OAuth2 password form.
    
    This endpoint is for OAuth2 compatibility.
    Use /auth/login for regular API calls.
    """
    login_data = LoginRequest(
        email=form_data.username,
        password=form_data.password,
    )
    return await auth_service.login(login_data)


@router.post(
    "/social-login",
    response_model=AuthResponse,
    summary="Login with social provider",
    description="Authenticate or register user via Google, Facebook, or Apple.",
)
async def social_login(
    data: SocialLoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    """Login or register via social provider.
    
    Validates the OAuth token with the provider and either:
    - Returns existing user if found
    - Creates new user if not found
    
    Supported providers: google, facebook, apple
    
    Raises:
        401 Unauthorized: If token validation fails
    """
    return await auth_service.social_login(data)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get new access token using refresh token.",
)
async def refresh_token(
    data: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Refresh access token.
    
    Use the refresh token to obtain a new access token
    when the current one expires.
    
    Raises:
        401 Unauthorized: If refresh token invalid
    """
    return await auth_service.refresh_tokens(data.refresh_token)


@router.post(
    "/accept-terms",
    response_model=TermsAcceptedResponse,
    summary="Accept terms of service",
    description="Mark current user as having accepted terms of service.",
)
async def accept_terms(
    data: AcceptTermsRequest,
    current_user: ActiveUser,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TermsAcceptedResponse:
    """Accept terms of service.
    
    Must be called before accessing protected resources
    that require terms acceptance.
    
    Raises:
        401 Unauthorized: If not authenticated
        422 Unprocessable Entity: If accept is not True
    """
    return await auth_service.accept_terms(current_user)


@router.get(
    "/me",
    response_model=UserInResponse,
    summary="Get current user profile",
    description="Get the authenticated user's profile.",
)
async def get_me(
    current_user: ActiveUser,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserInResponse:
    """Get current user profile.
    
    Returns the authenticated user's profile information.
    
    Raises:
        401 Unauthorized: If not authenticated
    """
    return await auth_service.get_current_user_profile(current_user)

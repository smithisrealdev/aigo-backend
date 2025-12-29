"""Authentication service for user login, registration, and token management.

This module provides the business logic for authentication operations
including local and social login, registration, and token refresh.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.auth import (
    AuthResponse,
    LoginRequest,
    OnboardingStatus,
    RegisterRequest,
    SocialLoginRequest,
    TermsAcceptedResponse,
    TokenResponse,
    UserInResponse,
)
from app.core.auth import create_token_pair, decode_refresh_token
from app.core.config import settings
from app.core.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.domains.user.models import AuthProvider, User
from app.domains.user.preferences_repository import UserPreferencesRepository
from app.domains.user.repository import UserRepository
from app.domains.user.schemas import UserCreate, UserCreateSocial
from app.domains.user.security import verify_password
from app.domains.user.social_auth import SocialAuthError, social_auth_validator


class AuthService:
    """Service for authentication operations.
    
    Handles user registration, login (local and social),
    token management, and terms acceptance.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with database session."""
        self._session = session
        self._repo = UserRepository(session)
        self._prefs_repo = UserPreferencesRepository(session)

    async def _get_onboarding_status(self, user: User) -> OnboardingStatus:
        """Get onboarding status for user.
        
        Args:
            user: The user to check
            
        Returns:
            OnboardingStatus with current state
        """
        prefs, _ = await self._prefs_repo.get_or_create_for_user(user.id)
        
        # Determine next action
        if not user.has_accepted_terms:
            next_action = "accept_terms"
        elif not prefs.has_completed_onboarding:
            next_action = "continue_onboarding"
        else:
            next_action = "complete"
        
        return OnboardingStatus(
            has_completed_onboarding=prefs.has_completed_onboarding,
            current_step=prefs.onboarding_step,
            next_action=next_action,
        )

    async def register(self, data: RegisterRequest) -> AuthResponse:
        """Register a new user with email/password.
        
        Args:
            data: Registration data
            
        Returns:
            AuthResponse with tokens and user profile
            
        Raises:
            UserAlreadyExistsError: If email already registered
        """
        # Check if email already exists
        existing = await self._repo.find_by_email(data.email)
        if existing:
            raise UserAlreadyExistsError()

        # Create user with hashed password
        user_data = UserCreate(
            email=data.email,
            password=data.password,
            full_name=data.full_name,
        )
        user = await self._repo.create_local_user(user_data)
        await self._session.commit()
        await self._session.refresh(user)

        # Get onboarding status
        onboarding_status = await self._get_onboarding_status(user)
        await self._session.commit()

        # Generate tokens
        token_pair = create_token_pair(user.id)

        return AuthResponse(
            message="Registration successful",
            tokens=TokenResponse(
                access_token=token_pair.access_token,
                refresh_token=token_pair.refresh_token,
                expires_in=token_pair.expires_in,
            ),
            user=UserInResponse.model_validate(user),
            onboarding=onboarding_status,
        )

    async def login(self, data: LoginRequest) -> AuthResponse:
        """Authenticate user with email/password.
        
        Args:
            data: Login credentials
            
        Returns:
            AuthResponse with tokens and user profile
            
        Raises:
            InvalidCredentialsError: If credentials invalid
        """
        # Find user by email
        user = await self._repo.find_by_email(data.email)
        if not user:
            raise InvalidCredentialsError()

        # Check if user has password (not social login only)
        if not user.hashed_password:
            raise InvalidCredentialsError()

        # Verify password
        if not verify_password(data.password, user.hashed_password):
            raise InvalidCredentialsError()

        # Update last login
        await self._repo.update_last_login(user.id)
        await self._session.commit()
        await self._session.refresh(user)

        # Get onboarding status
        onboarding_status = await self._get_onboarding_status(user)
        await self._session.commit()

        # Generate tokens
        token_pair = create_token_pair(user.id)

        return AuthResponse(
            message="Login successful",
            tokens=TokenResponse(
                access_token=token_pair.access_token,
                refresh_token=token_pair.refresh_token,
                expires_in=token_pair.expires_in,
            ),
            user=UserInResponse.model_validate(user),
            onboarding=onboarding_status,
        )

    async def social_login(self, data: SocialLoginRequest) -> AuthResponse:
        """Authenticate or register user via social provider.
        
        Validates the OAuth token with the provider and either:
        - Returns existing user if found by social_id
        - Creates new user if not found
        
        Args:
            data: Social login data with provider and token
            
        Returns:
            AuthResponse with tokens and user profile
            
        Raises:
            InvalidCredentialsError: If token validation fails
        """
        # Convert string provider to AuthProvider enum
        provider_enum = AuthProvider(data.provider)
        
        try:
            # Validate token with provider
            user_info = await social_auth_validator.validate_token(
                provider_enum,
                data.token,
            )
        except SocialAuthError as e:
            raise InvalidCredentialsError()

        # Check if user exists by social_id
        user = await self._repo.find_by_social_id(
            user_info.provider,
            user_info.social_id,
        )

        if user:
            # Existing user - update last login
            await self._repo.update_last_login(user.id)
            
            # Optionally update profile if changed
            update_data = {}
            if user_info.avatar_url and user.avatar_url != user_info.avatar_url:
                update_data["avatar_url"] = user_info.avatar_url
            if user_info.full_name and user.full_name != user_info.full_name:
                update_data["full_name"] = user_info.full_name
            
            if update_data:
                await self._repo.update(user.id, update_data)
            
            await self._session.commit()
            await self._session.refresh(user)
            message = "Login successful"
        else:
            # Check if email already exists (different provider)
            existing_by_email = await self._repo.find_by_email(user_info.email)
            if existing_by_email:
                # Link social account to existing user? 
                # For now, create separate account with modified email
                # In production, you might want to handle account linking
                pass

            # Create new user
            social_data = UserCreateSocial(
                email=user_info.email,
                full_name=user_info.full_name,
                avatar_url=user_info.avatar_url,
                provider=user_info.provider,
                social_id=user_info.social_id,
                is_verified=user_info.is_verified,
            )
            user = await self._repo.create_social_user(social_data)
            await self._session.commit()
            await self._session.refresh(user)
            message = "Registration successful"

        # Get onboarding status
        onboarding_status = await self._get_onboarding_status(user)
        await self._session.commit()

        # Generate tokens
        token_pair = create_token_pair(user.id)

        return AuthResponse(
            message=message,
            tokens=TokenResponse(
                access_token=token_pair.access_token,
                refresh_token=token_pair.refresh_token,
                expires_in=token_pair.expires_in,
            ),
            user=UserInResponse.model_validate(user),
            onboarding=onboarding_status,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            New TokenResponse with fresh tokens
            
        Raises:
            InvalidTokenError: If refresh token invalid
        """
        # Decode and validate refresh token
        payload = decode_refresh_token(refresh_token)
        if not payload:
            raise InvalidTokenError("Invalid refresh token")

        # Get user
        try:
            user_id = UUID(payload.sub)
        except ValueError:
            raise InvalidTokenError("Invalid user ID in token")

        user = await self._repo.get(user_id)
        if not user or not user.is_active:
            raise InvalidTokenError("User not found or inactive")

        # Generate new tokens
        token_pair = create_token_pair(user.id)

        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
        )

    async def accept_terms(self, user: User) -> TermsAcceptedResponse:
        """Accept terms of service for user.
        
        Args:
            user: The authenticated user
            
        Returns:
            TermsAcceptedResponse with updated user
        """
        await self._repo.accept_terms(user.id)
        await self._session.commit()
        
        # Re-fetch user from this session to get updated data
        updated_user = await self._repo.get(user.id)

        return TermsAcceptedResponse(
            message="Terms of service accepted",
            user=UserInResponse.model_validate(updated_user),
        )

    async def get_current_user_profile(self, user: User) -> UserInResponse:
        """Get current user profile.
        
        Args:
            user: The authenticated user
            
        Returns:
            UserInResponse with user profile
        """
        return UserInResponse.model_validate(user)

"""Social OAuth provider token validation.

This module handles validation of OAuth tokens from
Google, Facebook, and Apple providers.
"""

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.domains.user.models import AuthProvider


@dataclass
class SocialUserInfo:
    """User information extracted from social provider."""

    provider: AuthProvider
    social_id: str
    email: str
    full_name: str
    avatar_url: str | None = None
    is_verified: bool = True


class SocialAuthError(Exception):
    """Exception raised when social auth validation fails."""

    def __init__(self, message: str, provider: AuthProvider) -> None:
        self.message = message
        self.provider = provider
        super().__init__(message)


class SocialAuthValidator:
    """Validates OAuth tokens from social providers.
    
    Supports Google, Facebook, and Apple authentication.
    """

    # Provider token info endpoints
    GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    FACEBOOK_GRAPH_URL = "https://graph.facebook.com/me"
    APPLE_AUTH_URL = "https://appleid.apple.com/auth/token"

    def __init__(self) -> None:
        """Initialize the validator with HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def validate_token(
        self,
        provider: AuthProvider,
        token: str,
    ) -> SocialUserInfo:
        """Validate OAuth token and extract user info.
        
        Args:
            provider: The OAuth provider
            token: The OAuth token (access token or ID token)
            
        Returns:
            SocialUserInfo with user details
            
        Raises:
            SocialAuthError: If validation fails
        """
        if provider == AuthProvider.GOOGLE:
            return await self._validate_google_token(token)
        elif provider == AuthProvider.FACEBOOK:
            return await self._validate_facebook_token(token)
        elif provider == AuthProvider.APPLE:
            return await self._validate_apple_token(token)
        else:
            raise SocialAuthError(
                f"Unsupported provider: {provider}",
                provider,
            )

    async def _validate_google_token(self, token: str) -> SocialUserInfo:
        """Validate Google OAuth token.
        
        For ID tokens, we validate with tokeninfo endpoint.
        For access tokens, we fetch user info.
        """
        try:
            # Try to get user info with access token first
            response = await self._client.get(
                self.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                data = response.json()
                return SocialUserInfo(
                    provider=AuthProvider.GOOGLE,
                    social_id=data["sub"],
                    email=data["email"],
                    full_name=data.get("name", data.get("email", "").split("@")[0]),
                    avatar_url=data.get("picture"),
                    is_verified=data.get("email_verified", False),
                )

            # Fallback to tokeninfo for ID tokens
            response = await self._client.get(
                self.GOOGLE_TOKEN_INFO_URL,
                params={"id_token": token},
            )

            if response.status_code != 200:
                raise SocialAuthError(
                    "Invalid Google token",
                    AuthProvider.GOOGLE,
                )

            data = response.json()

            # Verify the token is for our app
            if settings.GOOGLE_CLIENT_ID and data.get("aud") != settings.GOOGLE_CLIENT_ID:
                raise SocialAuthError(
                    "Token not issued for this application",
                    AuthProvider.GOOGLE,
                )

            return SocialUserInfo(
                provider=AuthProvider.GOOGLE,
                social_id=data["sub"],
                email=data["email"],
                full_name=data.get("name", data.get("email", "").split("@")[0]),
                avatar_url=data.get("picture"),
                is_verified=data.get("email_verified", "false") == "true",
            )

        except httpx.RequestError as e:
            raise SocialAuthError(
                f"Failed to validate Google token: {e}",
                AuthProvider.GOOGLE,
            )

    async def _validate_facebook_token(self, token: str) -> SocialUserInfo:
        """Validate Facebook OAuth token."""
        try:
            # Get user info from Facebook Graph API
            response = await self._client.get(
                self.FACEBOOK_GRAPH_URL,
                params={
                    "access_token": token,
                    "fields": "id,email,name,picture.type(large)",
                },
            )

            if response.status_code != 200:
                error_data = response.json().get("error", {})
                raise SocialAuthError(
                    error_data.get("message", "Invalid Facebook token"),
                    AuthProvider.FACEBOOK,
                )

            data = response.json()

            # Extract avatar URL from nested structure
            avatar_url = None
            if "picture" in data and "data" in data["picture"]:
                avatar_url = data["picture"]["data"].get("url")

            return SocialUserInfo(
                provider=AuthProvider.FACEBOOK,
                social_id=data["id"],
                email=data.get("email", f"{data['id']}@facebook.com"),
                full_name=data.get("name", "Facebook User"),
                avatar_url=avatar_url,
                is_verified=True,  # Facebook requires verified email
            )

        except httpx.RequestError as e:
            raise SocialAuthError(
                f"Failed to validate Facebook token: {e}",
                AuthProvider.FACEBOOK,
            )

    async def _validate_apple_token(self, token: str) -> SocialUserInfo:
        """Validate Apple ID token.
        
        Apple uses JWT ID tokens that can be validated locally.
        The token contains user info in the payload.
        """
        try:
            from jose import jwt, JWTError

            # Apple ID tokens are JWTs - decode without verification for user info
            # In production, you should verify the signature using Apple's public keys
            try:
                # Decode without verification to get claims
                # Note: In production, fetch Apple's public keys and verify
                unverified_claims = jwt.get_unverified_claims(token)
            except JWTError as e:
                raise SocialAuthError(
                    f"Invalid Apple ID token: {e}",
                    AuthProvider.APPLE,
                )

            # Verify issuer
            if unverified_claims.get("iss") != "https://appleid.apple.com":
                raise SocialAuthError(
                    "Invalid token issuer",
                    AuthProvider.APPLE,
                )

            # Verify audience (your app's client ID)
            if settings.APPLE_CLIENT_ID:
                aud = unverified_claims.get("aud")
                if aud != settings.APPLE_CLIENT_ID:
                    raise SocialAuthError(
                        "Token not issued for this application",
                        AuthProvider.APPLE,
                    )

            # Extract user info
            # Apple only provides email on first login, so handle missing email
            email = unverified_claims.get("email")
            sub = unverified_claims.get("sub")

            if not sub:
                raise SocialAuthError(
                    "Missing user ID in Apple token",
                    AuthProvider.APPLE,
                )

            # If no email, create a placeholder (will need to be updated later)
            if not email:
                email = f"{sub}@privaterelay.appleid.com"

            return SocialUserInfo(
                provider=AuthProvider.APPLE,
                social_id=sub,
                email=email,
                full_name=unverified_claims.get("name", "Apple User"),
                avatar_url=None,  # Apple doesn't provide avatar
                is_verified=unverified_claims.get("email_verified", "false") == "true",
            )

        except ImportError:
            raise SocialAuthError(
                "JWT library not available for Apple auth",
                AuthProvider.APPLE,
            )


# Global validator instance
social_auth_validator = SocialAuthValidator()

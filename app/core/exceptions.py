"""Custom exceptions for authentication and authorization.

This module defines HTTP exceptions used throughout the auth system.
"""

from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """Base exception for authentication errors."""

    def __init__(
        self,
        detail: str = "Could not validate credentials",
        headers: dict[str, str] | None = None,
    ) -> None:
        if headers is None:
            headers = {"WWW-Authenticate": "Bearer"}
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers,
        )


class InvalidTokenError(AuthenticationError):
    """Raised when the JWT token is invalid or expired."""

    def __init__(self, detail: str = "Invalid or expired token") -> None:
        super().__init__(detail=detail)


class TokenExpiredError(AuthenticationError):
    """Raised when the JWT token has expired."""

    def __init__(self) -> None:
        super().__init__(detail="Token has expired")


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""

    def __init__(self) -> None:
        super().__init__(detail="Incorrect email or password")


class InactiveUserError(HTTPException):
    """Raised when user account is inactive."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )


class UnverifiedUserError(HTTPException):
    """Raised when user email is not verified."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified",
        )


class TermsNotAcceptedError(HTTPException):
    """Raised when user has not accepted terms of service."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Terms of service not accepted. Please accept the terms to continue.",
        )


class UserNotFoundError(HTTPException):
    """Raised when user is not found in database."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


class UserAlreadyExistsError(HTTPException):
    """Raised when trying to create a user with existing email."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )


class PasswordChangeNotAllowedError(HTTPException):
    """Raised when social login user tries to change password."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change not allowed for social login accounts",
        )


class BadRequestError(HTTPException):
    """Raised for general bad request errors."""

    def __init__(self, detail: str = "Bad request") -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class NotFoundError(HTTPException):
    """Raised when a resource is not found."""

    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )

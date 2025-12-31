"""Repository for User domain.

This module provides data access operations for the User model
following the Repository pattern with async SQLAlchemy.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.shared.repository import GenericRepository
from app.domains.user.models import AuthProvider, User
from app.domains.user.schemas import UserCreate, UserCreateSocial, UserUpdate
from app.domains.user.security import hash_password


class UserRepository(GenericRepository[User, UserCreate, UserUpdate]):
    """Repository for User CRUD operations.
    
    Extends the generic repository with user-specific queries
    such as finding by email, social ID, or provider.
    
    Example:
        repo = UserRepository(session)
        user = await repo.find_by_email("user@example.com")
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session."""
        super().__init__(User, session)

    async def find_by_email(self, email: str) -> User | None:
        """Find a user by their email address.
        
        Args:
            email: The email address to search for
            
        Returns:
            The User if found, None otherwise
        """
        return await self.find_one(User.email == email)

    async def find_by_social_id(
        self,
        provider: AuthProvider,
        social_id: str,
    ) -> User | None:
        """Find a user by their social login credentials.
        
        Args:
            provider: The OAuth provider (GOOGLE, FACEBOOK, APPLE)
            social_id: The unique ID from the provider
            
        Returns:
            The User if found, None otherwise
        """
        stmt = select(User).where(
            User.provider == provider,
            User.social_id == social_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_local_user(self, data: UserCreate) -> User:
        """Create a new local user with hashed password.
        
        Args:
            data: User creation data including password
            
        Returns:
            The newly created User
        """
        user_data = data.model_dump(exclude={"password"})
        user_data["hashed_password"] = hash_password(data.password)
        user_data["provider"] = AuthProvider.LOCAL.value  # Use .value for database insertion
        
        return await self.create(user_data)

    async def create_social_user(self, data: UserCreateSocial) -> User:
        """Create a new user from social login.
        
        Args:
            data: Social user creation data
            
        Returns:
            The newly created User
        """
        user_data = data.model_dump()
        # Social users don't have passwords
        user_data["hashed_password"] = None
        
        return await self.create(user_data)

    async def find_or_create_social_user(
        self,
        data: UserCreateSocial,
    ) -> tuple[User, bool]:
        """Find existing social user or create a new one.
        
        This is useful for social login flows where the user
        might already exist.
        
        Args:
            data: Social user data
            
        Returns:
            Tuple of (User, created) where created is True if new
        """
        existing = await self.find_by_social_id(data.provider, data.social_id)
        if existing:
            return existing, False
        
        new_user = await self.create_social_user(data)
        return new_user, True

    async def update_password(
        self,
        user_id: UUID,
        new_password: str,
    ) -> User | None:
        """Update a user's password.
        
        Args:
            user_id: The user's ID
            new_password: The new plain text password (will be hashed)
            
        Returns:
            The updated User if found, None otherwise
        """
        hashed = hash_password(new_password)
        return await self.update(
            user_id,
            {"hashed_password": hashed},
        )

    async def accept_terms(self, user_id: UUID) -> User | None:
        """Mark a user as having accepted the terms of service.
        
        Args:
            user_id: The user's ID
            
        Returns:
            The updated User if found, None otherwise
        """
        return await self.update(
            user_id,
            {
                "has_accepted_terms": True,
                "terms_accepted_at": datetime.utcnow(),
            },
        )

    async def update_last_login(self, user_id: UUID) -> User | None:
        """Update the user's last login timestamp.
        
        Args:
            user_id: The user's ID
            
        Returns:
            The updated User if found, None otherwise
        """
        return await self.update(
            user_id,
            {"last_login_at": datetime.utcnow()},
        )

    async def find_active_users(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[User]:
        """Find all active users with pagination.
        
        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            
        Returns:
            List of active Users
        """
        stmt = (
            select(User)
            .where(User.is_active == True)  # noqa: E712
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def email_exists(self, email: str) -> bool:
        """Check if an email address is already registered.
        
        Args:
            email: The email address to check
            
        Returns:
            True if email exists, False otherwise
        """
        user = await self.find_by_email(email)
        return user is not None

    async def deactivate_user(self, user_id: UUID) -> User | None:
        """Deactivate a user account.
        
        Args:
            user_id: The user's ID
            
        Returns:
            The updated User if found, None otherwise
        """
        return await self.update(user_id, {"is_active": False})

    async def verify_user(self, user_id: UUID) -> User | None:
        """Mark a user's email as verified.
        
        Args:
            user_id: The user's ID
            
        Returns:
            The updated User if found, None otherwise
        """
        return await self.update(user_id, {"is_verified": True})

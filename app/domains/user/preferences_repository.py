"""Repository for User Preferences domain.

This module provides data access operations for the UserPreferences model
following the Repository pattern with async SQLAlchemy.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.shared.repository import GenericRepository
from app.domains.user.preferences import UserPreferences


class UserPreferencesRepository(GenericRepository[UserPreferences, dict, dict]):
    """Repository for UserPreferences CRUD operations.
    
    Extends the generic repository with preferences-specific queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session."""
        super().__init__(UserPreferences, session)

    async def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        """Find preferences by user ID.
        
        Args:
            user_id: The user's ID
            
        Returns:
            The UserPreferences if found, None otherwise
        """
        stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_for_user(self, user_id: UUID) -> UserPreferences:
        """Create empty preferences for a user.
        
        Args:
            user_id: The user's ID
            
        Returns:
            The newly created UserPreferences
        """
        return await self.create({"user_id": user_id})

    async def get_or_create_for_user(self, user_id: UUID) -> tuple[UserPreferences, bool]:
        """Get existing preferences or create new ones.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Tuple of (UserPreferences, created) where created is True if new
        """
        existing = await self.find_by_user_id(user_id)
        if existing:
            return existing, False
        
        new_prefs = await self.create_for_user(user_id)
        return new_prefs, True

    async def update_preferences(
        self,
        user_id: UUID,
        data: dict,
    ) -> UserPreferences | None:
        """Update user preferences.
        
        Args:
            user_id: The user's ID
            data: Dictionary of fields to update
            
        Returns:
            The updated UserPreferences if found, None otherwise
        """
        prefs = await self.find_by_user_id(user_id)
        if not prefs:
            return None
        
        return await self.update(prefs.id, data)

    async def update_onboarding_step(
        self,
        user_id: UUID,
        step: int,
    ) -> UserPreferences | None:
        """Update the current onboarding step.
        
        Args:
            user_id: The user's ID
            step: The new step number
            
        Returns:
            The updated UserPreferences if found, None otherwise
        """
        return await self.update_preferences(user_id, {"onboarding_step": step})

    async def complete_onboarding(self, user_id: UUID) -> UserPreferences | None:
        """Mark onboarding as complete.
        
        Args:
            user_id: The user's ID
            
        Returns:
            The updated UserPreferences if found, None otherwise
        """
        return await self.update_preferences(
            user_id,
            {
                "has_completed_onboarding": True,
                "onboarding_completed_at": datetime.utcnow(),
            },
        )

    async def has_completed_onboarding(self, user_id: UUID) -> bool:
        """Check if user has completed onboarding.
        
        Args:
            user_id: The user's ID
            
        Returns:
            True if onboarding is complete, False otherwise
        """
        prefs = await self.find_by_user_id(user_id)
        if not prefs:
            return False
        return prefs.has_completed_onboarding

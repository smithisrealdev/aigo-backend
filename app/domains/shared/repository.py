"""Generic Async Repository Pattern for DDD.

This module provides a generic repository base class that handles
common CRUD operations with full async support using SQLAlchemy 2.0.
"""

from typing import Any, Generic, Sequence, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infra.database import Base

# Type variables for generic repository
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class GenericRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic async repository providing standard CRUD operations.

    This class implements the Repository pattern with full async support,
    providing a clean abstraction layer between the domain and data access.

    Type Parameters:
        ModelType: The SQLAlchemy model class
        CreateSchemaType: Pydantic schema for creation
        UpdateSchemaType: Pydantic schema for updates

    Example:
        class UserRepository(GenericRepository[User, UserCreate, UserUpdate]):
            def __init__(self, session: AsyncSession):
                super().__init__(User, session)

            async def find_by_email(self, email: str) -> User | None:
                return await self.find_one(User.email == email)
    """

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            model: The SQLAlchemy model class
            session: Async database session
        """
        self._model = model
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Get the database session."""
        return self._session

    @property
    def model(self) -> type[ModelType]:
        """Get the model class."""
        return self._model

    # ==================== CREATE Operations ====================

    async def create(self, data: CreateSchemaType | dict[str, Any]) -> ModelType:
        """Create a new record.

        Args:
            data: Pydantic schema or dict with creation data

        Returns:
            The created model instance
        """
        if isinstance(data, BaseModel):
            obj_data = data.model_dump(exclude_unset=True)
        else:
            obj_data = data

        db_obj = self._model(**obj_data)
        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def create_many(
        self, data_list: list[CreateSchemaType | dict[str, Any]]
    ) -> list[ModelType]:
        """Create multiple records in a single transaction.

        Args:
            data_list: List of Pydantic schemas or dicts

        Returns:
            List of created model instances
        """
        db_objects = []
        for data in data_list:
            if isinstance(data, BaseModel):
                obj_data = data.model_dump(exclude_unset=True)
            else:
                obj_data = data
            db_objects.append(self._model(**obj_data))

        self._session.add_all(db_objects)
        await self._session.flush()
        for obj in db_objects:
            await self._session.refresh(obj)
        return db_objects

    # ==================== READ Operations ====================

    async def get_by_id(
        self,
        id: UUID,
        *,
        load_relations: list[str] | None = None,
    ) -> ModelType | None:
        """Get a record by its ID.

        Args:
            id: The UUID of the record
            load_relations: Optional list of relationship names to eager load

        Returns:
            The model instance or None if not found
        """
        stmt = select(self._model).where(self._model.id == id)
        stmt = self._apply_eager_loading(stmt, load_relations)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get(
        self,
        id: UUID,
        *,
        load_relations: list[str] | None = None,
    ) -> ModelType:
        """Get a record by ID, raising an error if not found.

        Args:
            id: The UUID of the record
            load_relations: Optional list of relationship names to eager load

        Returns:
            The model instance

        Raises:
            ValueError: If record not found
        """
        obj = await self.get_by_id(id, load_relations=load_relations)
        if obj is None:
            raise ValueError(f"{self._model.__name__} with id {id} not found")
        return obj

    async def find_one(
        self,
        *conditions: Any,
        load_relations: list[str] | None = None,
    ) -> ModelType | None:
        """Find a single record matching the conditions.

        Args:
            *conditions: SQLAlchemy filter conditions
            load_relations: Optional list of relationship names to eager load

        Returns:
            The model instance or None
        """
        stmt = select(self._model).where(*conditions)
        stmt = self._apply_eager_loading(stmt, load_relations)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_many(
        self,
        *conditions: Any,
        skip: int = 0,
        limit: int = 100,
        order_by: Any | None = None,
        load_relations: list[str] | None = None,
    ) -> Sequence[ModelType]:
        """Find multiple records matching the conditions.

        Args:
            *conditions: SQLAlchemy filter conditions
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return
            order_by: Column or list of columns for ordering
            load_relations: Optional list of relationship names to eager load

        Returns:
            Sequence of model instances
        """
        stmt = select(self._model)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = self._apply_ordering(stmt, order_by)
        stmt = self._apply_eager_loading(stmt, load_relations)
        stmt = stmt.offset(skip).limit(limit)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def find_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: Any | None = None,
        load_relations: list[str] | None = None,
    ) -> Sequence[ModelType]:
        """Get all records with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records
            order_by: Column for ordering
            load_relations: Relationships to eager load

        Returns:
            Sequence of model instances
        """
        return await self.find_many(
            skip=skip,
            limit=limit,
            order_by=order_by,
            load_relations=load_relations,
        )

    async def count(self, *conditions: Any) -> int:
        """Count records matching the conditions.

        Args:
            *conditions: SQLAlchemy filter conditions

        Returns:
            Number of matching records
        """
        stmt = select(func.count()).select_from(self._model)
        if conditions:
            stmt = stmt.where(*conditions)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def exists(self, *conditions: Any) -> bool:
        """Check if any record exists matching the conditions.

        Args:
            *conditions: SQLAlchemy filter conditions

        Returns:
            True if at least one record exists
        """
        return await self.count(*conditions) > 0

    # ==================== UPDATE Operations ====================

    async def update(
        self,
        id: UUID,
        data: UpdateSchemaType | dict[str, Any],
    ) -> ModelType | None:
        """Update a record by ID.

        Args:
            id: The UUID of the record to update
            data: Pydantic schema or dict with update data

        Returns:
            The updated model instance or None if not found
        """
        db_obj = await self.get_by_id(id)
        if db_obj is None:
            return None

        if isinstance(data, BaseModel):
            update_data = data.model_dump(exclude_unset=True)
        else:
            update_data = data

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def update_many(
        self,
        *conditions: Any,
        data: dict[str, Any],
    ) -> int:
        """Update multiple records matching the conditions.

        Args:
            *conditions: SQLAlchemy filter conditions
            data: Dict with update data

        Returns:
            Number of updated records
        """
        stmt = update(self._model).where(*conditions).values(**data)
        result = await self._session.execute(stmt)
        return result.rowcount

    # ==================== DELETE Operations ====================

    async def delete(self, id: UUID) -> bool:
        """Delete a record by ID.

        Args:
            id: The UUID of the record to delete

        Returns:
            True if deleted, False if not found
        """
        db_obj = await self.get_by_id(id)
        if db_obj is None:
            return False

        await self._session.delete(db_obj)
        await self._session.flush()
        return True

    async def delete_many(self, *conditions: Any) -> int:
        """Delete multiple records matching the conditions.

        Args:
            *conditions: SQLAlchemy filter conditions

        Returns:
            Number of deleted records
        """
        stmt = delete(self._model).where(*conditions)
        result = await self._session.execute(stmt)
        return result.rowcount

    # ==================== Helper Methods ====================

    def _apply_eager_loading(
        self,
        stmt: Select[tuple[ModelType]],
        load_relations: list[str] | None,
    ) -> Select[tuple[ModelType]]:
        """Apply eager loading for relationships."""
        if load_relations:
            for relation in load_relations:
                if "." in relation:
                    # Nested relationship - only load first level for now
                    stmt = stmt.options(
                        selectinload(getattr(self._model, relation.split(".")[0]))
                    )
                else:
                    stmt = stmt.options(selectinload(getattr(self._model, relation)))
        return stmt

    def _apply_ordering(
        self,
        stmt: Select[tuple[ModelType]],
        order_by: Any | None,
    ) -> Select[tuple[ModelType]]:
        """Apply ordering to the query."""
        if order_by is not None:
            if isinstance(order_by, (list, tuple)):
                stmt = stmt.order_by(*order_by)
            else:
                stmt = stmt.order_by(order_by)
        else:
            # Default ordering by created_at descending
            if hasattr(self._model, "created_at"):
                stmt = stmt.order_by(self._model.created_at.desc())
        return stmt

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self._session.rollback()

"""Database configuration and session management using SQLAlchemy 2.0 async.

This module provides:
- Async engine and session configuration
- Base model with common fields (id, created_at, updated_at)
- Transaction management utilities
- Database lifecycle management
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import MetaData, event, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

# Naming convention for constraints (important for Alembic migrations)
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Provides:
    - UUID primary key
    - Automatic created_at and updated_at timestamps
    - Proper metadata naming conventions
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Common columns for all models
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        sort_order=-10,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
        sort_order=100,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        sort_order=101,
    )

    def __repr__(self) -> str:
        """String representation of the model."""
        return f"<{self.__class__.__name__}(id={self.id})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class DatabaseManager:
    """Manages database connections and sessions.

    Provides centralized database lifecycle management with:
    - Connection pooling
    - Session factory
    - Transaction management
    - Health checks
    """

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine, creating it if necessary."""
        if self._engine is None:
            self._engine = create_async_engine(
                str(settings.DATABASE_URL),
                echo=settings.DEBUG,
                pool_pre_ping=True,
                pool_size=getattr(settings, "DB_POOL_SIZE", 10),
                max_overflow=getattr(settings, "DB_MAX_OVERFLOW", 20),
                pool_timeout=30,
                pool_recycle=1800,  # Recycle connections after 30 minutes
            )
            # Register event listeners for debugging
            if settings.DEBUG:
                self._register_debug_events()
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory, creating it if necessary."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    def _register_debug_events(self) -> None:
        """Register SQLAlchemy event listeners for debugging."""

        @event.listens_for(self.engine.sync_engine, "before_cursor_execute")
        def before_cursor_execute(
            conn: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            conn.info.setdefault("query_start_time", []).append(datetime.now())

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for database sessions with automatic cleanup."""
        session = self.session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for database transactions with automatic commit/rollback."""
        async with self.session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def init(self) -> None:
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """Close all database connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Global database manager instance
db_manager = DatabaseManager()


def async_session_factory() -> AsyncSession:
    """
    Get an async session for use outside of FastAPI request context.
    
    Useful for Celery tasks and other background processes.
    Returns a context manager that auto-closes the session.
    
    Usage:
        async with async_session_factory() as session:
            repo = SomeRepository(session)
            await repo.do_something()
            await session.commit()
    """
    return db_manager.session()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting async database sessions.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with db_manager.session() as session:
        yield session


async def get_db_transaction() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting sessions with automatic transaction management.

    Usage:
        @router.post("/items")
        async def create_item(db: AsyncSession = Depends(get_db_transaction)):
            # Changes will be automatically committed on success
            ...
    """
    async with db_manager.transaction() as session:
        yield session


async def init_db() -> None:
    """Initialize database tables."""
    await db_manager.init()


async def close_db() -> None:
    """Close database connections."""
    await db_manager.close()

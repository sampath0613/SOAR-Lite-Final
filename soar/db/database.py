"""
Database initialization and session management.
Handles async SQLAlchemy engine setup and session factory.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from soar.config import settings
from soar.models.incident import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages async database connection and session factory."""

    def __init__(self, database_url: str):
        """Initialize database manager with connection string."""
        self.database_url = database_url
        self.engine = None
        self.async_session_factory = None

    async def init(self) -> None:
        """Initialize async engine and session factory."""
        logger.info(f"Initializing database: {self.database_url}")

        self.engine = create_async_engine(
            self.database_url,
            echo=False,  # Set to True for SQL query logging
            future=True,
        )

        self.async_session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        # Create all tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")

    async def close(self) -> None:
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session as context manager."""
        if not self.async_session_factory:
            raise RuntimeError("Database not initialized. Call init() first.")

        async with self.async_session_factory() as session:
            try:
                yield session
            except Exception as error:
                await session.rollback()
                logger.error(f"Database session error: {error}")
                raise
            finally:
                await session.close()


# Global database manager instance
db_manager = DatabaseManager(settings.DATABASE_URL)


async def init_db() -> None:
    """Initialize database (called from main.py on startup)."""
    await db_manager.init()


async def close_db() -> None:
    """Close database connection (called from main.py on shutdown)."""
    await db_manager.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection function for FastAPI routes."""
    async for session in db_manager.get_session():
        yield session

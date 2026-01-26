"""Database connection management using asyncpg."""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
from asyncpg import Pool, Connection

from word_learn.config import get_settings


class Database:
    """Async PostgreSQL database connection pool manager."""

    _pool: Optional[Pool] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_pool(cls) -> Pool:
        """Get or create the connection pool.

        Returns:
            asyncpg connection pool
        """
        if cls._pool is None:
            async with cls._lock:
                if cls._pool is None:
                    settings = get_settings()
                    cls._pool = await asyncpg.create_pool(
                        settings.database_url,
                        min_size=1,
                        max_size=10,
                    )
        return cls._pool

    @classmethod
    async def close(cls) -> None:
        """Close the connection pool."""
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    @asynccontextmanager
    async def connection(cls) -> AsyncGenerator[Connection, None]:
        """Get a connection from the pool.

        Yields:
            asyncpg connection
        """
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            yield conn

    @classmethod
    @asynccontextmanager
    async def transaction(cls) -> AsyncGenerator[Connection, None]:
        """Get a connection with an active transaction.

        Yields:
            asyncpg connection with transaction
        """
        async with cls.connection() as conn:
            async with conn.transaction():
                yield conn


async def init_db() -> None:
    """Initialize the database connection pool."""
    await Database.get_pool()


async def close_db() -> None:
    """Close the database connection pool."""
    await Database.close()

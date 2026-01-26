"""Pytest configuration and shared fixtures."""
import asyncio
import os
from datetime import datetime, time, timedelta
from typing import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
import asyncpg

# Set test environment variables before importing app modules
os.environ.setdefault("BOT_TOKEN", "test_token")
os.environ.setdefault("DATABASE_URL", "postgresql://word_learn:password@localhost:5432/word_learn_test")
os.environ.setdefault("SOURCE_LANG", "en")
os.environ.setdefault("TARGET_LANG", "ru")

from word_learn.database import Database
from word_learn.repositories import PracticeRepository, WordsRepository


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """Create a test database pool."""
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://word_learn:password@localhost:5432/word_learn_test"
    )

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)

    # Clean up tables before each test
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM current_practice")
        await conn.execute("DELETE FROM current_practice_stats")
        await conn.execute("DELETE FROM today_practice")
        await conn.execute("DELETE FROM word_skiplist")
        await conn.execute("DELETE FROM word_practice")
        await conn.execute("DELETE FROM reminders")
        await conn.execute("DELETE FROM words")

    # Patch the Database class to use our test pool
    original_pool = Database._pool
    Database._pool = pool

    yield pool

    # Restore original pool
    Database._pool = original_pool
    await pool.close()


@pytest_asyncio.fixture
async def practice_repository(db_pool) -> PracticeRepository:
    """Create a PracticeRepository instance."""
    return PracticeRepository()


@pytest_asyncio.fixture
async def words_repository(db_pool) -> WordsRepository:
    """Create a WordsRepository instance."""
    return WordsRepository()


@pytest.fixture
def chat_id() -> int:
    """Return a test chat ID."""
    return 12345


@pytest.fixture
def sample_word_data() -> dict:
    """Return sample word data."""
    return {"en": "cat", "nl": "kat", "ru": "кот"}


@pytest.fixture
def sample_word_data_2() -> dict:
    """Return second sample word data."""
    return {"en": "dog", "nl": "hond", "ru": "собака"}

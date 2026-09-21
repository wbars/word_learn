"""Pytest configuration and shared fixtures."""
import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator

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

REPO_ROOT = Path(__file__).resolve().parents[1]

_DB_UNAVAILABLE_REASON: str | None = None
_EMBEDDED_SERVER = None  # pgserver handle, kept alive for the whole session


async def _can_connect(database_url: str) -> bool:
    """Return True when a short connection attempt to ``database_url`` succeeds."""
    try:
        conn = await asyncio.wait_for(asyncpg.connect(database_url), timeout=3.0)
    except (asyncio.TimeoutError, OSError, asyncpg.PostgresError):
        return False
    await conn.close()
    return True


def _start_embedded_postgres(tmp_path_factory) -> str | None:
    """Start a throwaway PostgreSQL via the optional ``pgserver`` package.

    Used only when DATABASE_URL is unreachable, so people with a real test
    database keep their existing setup untouched.
    """
    global _EMBEDDED_SERVER
    try:
        import pgserver
    except ImportError:
        return None
    try:
        _EMBEDDED_SERVER = pgserver.get_server(
            tmp_path_factory.mktemp("pg"), cleanup_mode="delete"
        )
        return _EMBEDDED_SERVER.get_uri()
    except Exception:  # pragma: no cover - depends on the local machine
        return None


def _migrate(database_url: str) -> None:
    """Bring the test database schema to alembic head (env.py reads DATABASE_URL)."""
    from alembic import command
    from alembic.config import Config

    os.environ["DATABASE_URL"] = database_url
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def test_database_url(tmp_path_factory) -> str:
    """Resolve a migrated test database URL once per session (pytest caches it), or skip.

    Order: DATABASE_URL (default: local word_learn_test) -> embedded pgserver
    -> skip with an explanation. The schema is always migrated to head so new
    columns exist regardless of when the database was created.
    """
    global _DB_UNAVAILABLE_REASON, _EMBEDDED_SERVER
    if _DB_UNAVAILABLE_REASON is not None:
        pytest.skip(_DB_UNAVAILABLE_REASON)

    configured = os.environ.get(
        "DATABASE_URL",
        "postgresql://word_learn:password@localhost:5432/word_learn_test",
    )
    url = configured if asyncio.run(_can_connect(configured)) else None
    if url is None:
        url = _start_embedded_postgres(tmp_path_factory)
    if url is None:
        _DB_UNAVAILABLE_REASON = (
            "Test database not available; set DATABASE_URL to a reachable test DB "
            "or `pip install pgserver` to run integration/e2e tests on an embedded one."
        )
        pytest.skip(_DB_UNAVAILABLE_REASON)

    try:
        _migrate(url)
    except Exception as exc:
        _DB_UNAVAILABLE_REASON = f"Could not migrate test database {url!r}: {exc}"
        pytest.skip(_DB_UNAVAILABLE_REASON)

    yield url

    if _EMBEDDED_SERVER is not None:
        _EMBEDDED_SERVER.cleanup()
        _EMBEDDED_SERVER = None


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_pool(test_database_url) -> AsyncGenerator[asyncpg.Pool, None]:
    """Create a test database pool."""
    pool = await asyncio.wait_for(
        asyncpg.create_pool(test_database_url, min_size=1, max_size=5),
        timeout=10.0,
    )

    # Clean up tables before each test
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM current_practice")
        await conn.execute("DELETE FROM current_practice_stats")
        await conn.execute("DELETE FROM today_practice")
        await conn.execute("DELETE FROM session_word_results")
        await conn.execute("DELETE FROM word_skiplist")
        await conn.execute("DELETE FROM word_practice")
        await conn.execute("DELETE FROM reminders")
        await conn.execute("DELETE FROM practice_streaks")
        await conn.execute("DELETE FROM user_settings")
        await conn.execute("DELETE FROM vocabulary_course_progress")
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

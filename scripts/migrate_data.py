#!/usr/bin/env python3
"""Migration script to transfer data from MySQL to PostgreSQL.

This script migrates data from the PHP bot's MySQL databases to the
new Python bot's PostgreSQL databases.

Usage:
    python scripts/migrate_data.py [--dry-run]

Environment variables:
    MYSQL_HOST: MySQL host (default: localhost)
    MYSQL_PORT: MySQL port (default: 3306)
    MYSQL_PASSWORD: MySQL password

The script will migrate BOTH databases:
    - word_learner (EN-RU) -> word_learn_en
    - word_learner_dutch (NL-EN) -> word_learn_dutch
"""
import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Any

# MySQL connector (pip install mysql-connector-python)
try:
    import mysql.connector
except ImportError:
    print("Error: mysql-connector-python not installed")
    print("Run: pip install mysql-connector-python")
    sys.exit(1)

import asyncpg


@dataclass
class MigrationConfig:
    """Configuration for a single database migration."""
    mysql_db: str
    mysql_user: str
    pg_db: str
    pg_url: str
    description: str


# Migration configurations for both bots
MIGRATIONS = [
    MigrationConfig(
        mysql_db="word_learner",
        mysql_user="word_learner",
        pg_db="word_learn_en",
        pg_url=os.environ.get(
            "DATABASE_URL_EN",
            "postgresql://word_learn:password@localhost:5432/word_learn_en"
        ),
        description="English-Russian bot",
    ),
    MigrationConfig(
        mysql_db="word_learner_dutch",
        mysql_user="word_learner_dutch",
        pg_db="word_learn_dutch",
        pg_url=os.environ.get(
            "DATABASE_URL_DUTCH",
            "postgresql://word_learn:password@localhost:5433/word_learn_dutch"
        ),
        description="Dutch-English bot",
    ),
]


def get_mysql_connection(config: MigrationConfig) -> mysql.connector.MySQLConnection:
    """Create MySQL connection."""
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=config.mysql_user,
        password=os.environ.get("MYSQL_PASSWORD", "password"),
        database=config.mysql_db,
    )


async def migrate_words(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: asyncpg.Connection,
    dry_run: bool = False,
) -> int:
    """Migrate words table."""
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute("SELECT id, en, nl, ru FROM words ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()

    if dry_run:
        print(f"  Would migrate {len(rows)} words")
        return len(rows)

    # Insert with explicit IDs to preserve foreign key relationships
    for row in rows:
        await pg_conn.execute(
            """
            INSERT INTO words (id, en, nl, ru)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET en = $2, nl = $3, ru = $4
            """,
            row["id"],
            row.get("en"),
            row.get("nl"),
            row.get("ru"),
        )

    # Reset sequence to max ID + 1
    max_id = max(row["id"] for row in rows) if rows else 0
    await pg_conn.execute(f"SELECT setval('words_id_seq', {max_id})")

    print(f"  Migrated {len(rows)} words")
    return len(rows)


async def migrate_word_practice(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: asyncpg.Connection,
    dry_run: bool = False,
) -> int:
    """Migrate word_practice table."""
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, word_id, chat_id, next_date, stage, deleted
        FROM word_practice
        ORDER BY id
    """)
    rows = cursor.fetchall()
    cursor.close()

    if dry_run:
        print(f"  Would migrate {len(rows)} practice records")
        return len(rows)

    for row in rows:
        await pg_conn.execute(
            """
            INSERT INTO word_practice (id, word_id, chat_id, next_date, stage, deleted)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO NOTHING
            """,
            row["id"],
            row["word_id"],
            row["chat_id"],
            row["next_date"],
            row["stage"],
            bool(row.get("deleted", 0)),
        )

    max_id = max(row["id"] for row in rows) if rows else 0
    await pg_conn.execute(f"SELECT setval('word_practice_id_seq', {max_id})")

    print(f"  Migrated {len(rows)} practice records")
    return len(rows)


async def migrate_word_skiplist(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: asyncpg.Connection,
    dry_run: bool = False,
) -> int:
    """Migrate word_skiplist table."""
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute("SELECT word_id, chat_id FROM word_skiplist")
    rows = cursor.fetchall()
    cursor.close()

    if dry_run:
        print(f"  Would migrate {len(rows)} skiplist entries")
        return len(rows)

    for row in rows:
        await pg_conn.execute(
            """
            INSERT INTO word_skiplist (word_id, chat_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            row["word_id"],
            row["chat_id"],
        )

    print(f"  Migrated {len(rows)} skiplist entries")
    return len(rows)


async def migrate_current_practice(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: asyncpg.Connection,
    dry_run: bool = False,
) -> int:
    """Migrate current_practice table."""
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute("SELECT chat_id, word_id FROM current_practice")
    rows = cursor.fetchall()
    cursor.close()

    if dry_run:
        print(f"  Would migrate {len(rows)} current practice entries")
        return len(rows)

    for row in rows:
        await pg_conn.execute(
            """
            INSERT INTO current_practice (chat_id, word_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            row["chat_id"],
            row["word_id"],
        )

    print(f"  Migrated {len(rows)} current practice entries")
    return len(rows)


async def migrate_current_practice_stats(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: asyncpg.Connection,
    dry_run: bool = False,
) -> int:
    """Migrate current_practice_stats table."""
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute("SELECT chat_id, correct, total FROM current_practice_stats")
    rows = cursor.fetchall()
    cursor.close()

    if dry_run:
        print(f"  Would migrate {len(rows)} practice stats")
        return len(rows)

    for row in rows:
        await pg_conn.execute(
            """
            INSERT INTO current_practice_stats (chat_id, correct, total)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id) DO UPDATE SET correct = $2, total = $3
            """,
            row["chat_id"],
            row.get("correct", 0),
            row.get("total", 0),
        )

    print(f"  Migrated {len(rows)} practice stats")
    return len(rows)


async def migrate_reminders(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: asyncpg.Connection,
    dry_run: bool = False,
) -> int:
    """Migrate reminders table."""
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute("SELECT chat_id, remind_time, next_remind FROM reminders")
    rows = cursor.fetchall()
    cursor.close()

    if dry_run:
        print(f"  Would migrate {len(rows)} reminders")
        return len(rows)

    for row in rows:
        await pg_conn.execute(
            """
            INSERT INTO reminders (chat_id, remind_time, next_remind)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id) DO UPDATE SET remind_time = $2, next_remind = $3
            """,
            row["chat_id"],
            row["remind_time"],
            row["next_remind"],
        )

    print(f"  Migrated {len(rows)} reminders")
    return len(rows)


async def migrate_today_practice(
    mysql_conn: mysql.connector.MySQLConnection,
    pg_conn: asyncpg.Connection,
    dry_run: bool = False,
) -> int:
    """Migrate today_practice table."""
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute("SELECT word_practice_id, date FROM today_practice")
    rows = cursor.fetchall()
    cursor.close()

    if dry_run:
        print(f"  Would migrate {len(rows)} today practice entries")
        return len(rows)

    for row in rows:
        await pg_conn.execute(
            """
            INSERT INTO today_practice (word_practice_id, date)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            row["word_practice_id"],
            row["date"],
        )

    print(f"  Migrated {len(rows)} today practice entries")
    return len(rows)


async def migrate_database(config: MigrationConfig, dry_run: bool = False) -> None:
    """Migrate a single database."""
    print(f"\n{'='*60}")
    print(f"Migrating: {config.description}")
    print(f"MySQL: {config.mysql_db} -> PostgreSQL: {config.pg_db}")
    print(f"{'='*60}")

    # Connect to MySQL
    try:
        mysql_conn = get_mysql_connection(config)
        print(f"Connected to MySQL: {config.mysql_db}")
    except Exception as e:
        print(f"Failed to connect to MySQL: {e}")
        return

    # Connect to PostgreSQL
    try:
        pg_conn = await asyncpg.connect(config.pg_url)
        print(f"Connected to PostgreSQL: {config.pg_db}")
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        mysql_conn.close()
        return

    try:
        # Migrate tables in order (respecting foreign keys)
        print("\nMigrating tables:")

        await migrate_words(mysql_conn, pg_conn, dry_run)
        await migrate_word_practice(mysql_conn, pg_conn, dry_run)
        await migrate_word_skiplist(mysql_conn, pg_conn, dry_run)
        await migrate_current_practice(mysql_conn, pg_conn, dry_run)
        await migrate_current_practice_stats(mysql_conn, pg_conn, dry_run)
        await migrate_reminders(mysql_conn, pg_conn, dry_run)
        await migrate_today_practice(mysql_conn, pg_conn, dry_run)

        if dry_run:
            print("\n[DRY RUN] No changes were made")
        else:
            print(f"\nMigration complete for {config.description}!")

    finally:
        mysql_conn.close()
        await pg_conn.close()


async def verify_migration(config: MigrationConfig) -> None:
    """Verify migration by comparing row counts."""
    print(f"\nVerifying: {config.description}")

    mysql_conn = get_mysql_connection(config)
    pg_conn = await asyncpg.connect(config.pg_url)

    tables = [
        "words",
        "word_practice",
        "word_skiplist",
        "current_practice",
        "current_practice_stats",
        "reminders",
        "today_practice",
    ]

    print(f"{'Table':<25} {'MySQL':>10} {'PostgreSQL':>12} {'Match':>8}")
    print("-" * 60)

    all_match = True
    for table in tables:
        cursor = mysql_conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        mysql_count = cursor.fetchone()[0]
        cursor.close()

        pg_count = await pg_conn.fetchval(f"SELECT COUNT(*) FROM {table}")

        match = "OK" if mysql_count == pg_count else "MISMATCH"
        if mysql_count != pg_count:
            all_match = False

        print(f"{table:<25} {mysql_count:>10} {pg_count:>12} {match:>8}")

    mysql_conn.close()
    await pg_conn.close()

    if all_match:
        print("\nAll tables verified successfully!")
    else:
        print("\nWARNING: Some tables have mismatched counts!")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Migrate data from MySQL to PostgreSQL")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify migration by comparing row counts",
    )
    parser.add_argument(
        "--bot",
        choices=["en", "dutch", "all"],
        default="all",
        help="Which bot to migrate (default: all)",
    )
    args = parser.parse_args()

    # Filter migrations based on --bot argument
    configs = MIGRATIONS
    if args.bot == "en":
        configs = [m for m in MIGRATIONS if "English" in m.description]
    elif args.bot == "dutch":
        configs = [m for m in MIGRATIONS if "Dutch" in m.description]

    if args.verify:
        for config in configs:
            await verify_migration(config)
    else:
        for config in configs:
            await migrate_database(config, args.dry_run)

        if not args.dry_run:
            print("\n" + "="*60)
            print("Migration completed for all databases!")
            print("Run with --verify to check row counts")
            print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

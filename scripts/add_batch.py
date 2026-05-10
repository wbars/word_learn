#!/usr/bin/env python3
"""Add a batch of words to the Dutch bot database.

Usage:
    python scripts/add_batch.py batches/batch_001_essential.txt --chat-id CHAT_ID

Alternatively set ADMIN_CHAT_ID in the environment.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

import asyncpg

# Dutch bot database
DATABASE_URL = "postgresql://postgres:EluVnhukWpxAGDiaxRBoGxBCXtjCLoiy@shinkansen.proxy.rlwy.net:33993/railway"


def parse_batch_file(filepath: str) -> list[tuple[str, str]]:
    """Parse batch file and return list of (dutch, russian) tuples."""
    word_pairs = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse word pair (format: dutch|russian)
            if '|' not in line:
                print(f"  Warning: line {line_num} has no separator: {line}")
                continue

            parts = line.split('|', 1)
            dutch = parts[0].strip()
            russian = parts[1].strip()

            if dutch and russian:
                word_pairs.append((dutch, russian))
            else:
                print(f"  Warning: line {line_num} has empty part: {line}")

    return word_pairs


async def add_batch(filepath: str, chat_id: int, dry_run: bool = False):
    """Add batch of words to database."""
    print(f"\n{'='*60}")
    print(f"  Adding batch: {filepath}")
    print(f"  Chat ID: {chat_id}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    # Parse batch file
    word_pairs = parse_batch_file(filepath)
    print(f"Parsed {len(word_pairs)} word pairs from file\n")

    if not word_pairs:
        print("No words to add!")
        return

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Check for existing words to avoid duplicates
        existing = set()
        for dutch, russian in word_pairs:
            # Check if this exact pair exists
            row = await conn.fetchrow(
                "SELECT id FROM words WHERE nl = $1 AND en = $2",
                dutch, russian
            )
            if row:
                existing.add((dutch, russian))

        if existing:
            print(f"Skipping {len(existing)} existing word pairs")

        # Filter out existing
        new_pairs = [(d, r) for d, r in word_pairs if (d, r) not in existing]
        print(f"Adding {len(new_pairs)} new word pairs (bidirectional = {len(new_pairs) * 2} entries)\n")

        if dry_run:
            print("DRY RUN - would add:")
            for dutch, russian in new_pairs[:10]:
                print(f"  {dutch} <-> {russian}")
            if len(new_pairs) > 10:
                print(f"  ... and {len(new_pairs) - 10} more")
            await conn.close()
            return

        # Add words
        added_count = 0
        now = datetime.now(timezone.utc)

        for dutch, russian in new_pairs:
            # Add Dutch -> Russian direction
            # In this DB: nl column = Dutch, en column = Russian
            word1_id = await conn.fetchval(
                """
                INSERT INTO words (nl, en)
                VALUES ($1, $2)
                RETURNING id
                """,
                dutch, russian
            )

            # Add to word_practice
            await conn.execute(
                """
                INSERT INTO word_practice (word_id, chat_id, next_date, stage, deleted)
                VALUES ($1, $2, $3, 0, false)
                ON CONFLICT DO NOTHING
                """,
                word1_id, chat_id, now
            )

            # Add Russian -> Dutch direction (reversed)
            word2_id = await conn.fetchval(
                """
                INSERT INTO words (nl, en)
                VALUES ($1, $2)
                RETURNING id
                """,
                russian, dutch
            )

            # Add to word_practice
            await conn.execute(
                """
                INSERT INTO word_practice (word_id, chat_id, next_date, stage, deleted)
                VALUES ($1, $2, $3, 0, false)
                ON CONFLICT DO NOTHING
                """,
                word2_id, chat_id, now
            )

            added_count += 1
            print(f"  Added: {dutch} <-> {russian}")

        print(f"\n{'='*60}")
        print(f"  SUCCESS: Added {added_count} word pairs ({added_count * 2} practice entries)")
        print(f"{'='*60}\n")

        # Show updated stats
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM word_practice WHERE chat_id = $1 AND deleted = false",
            chat_id
        )
        print(f"Total words in practice for chat {chat_id}: {total}")

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description='Add word batch to Dutch bot database')
    parser.add_argument('batch_file', help='Path to batch file')
    parser.add_argument('--chat-id', type=int, default=None,
                        help='Telegram chat ID (or set ADMIN_CHAT_ID)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Parse and validate only, do not insert')

    args = parser.parse_args()

    if not Path(args.batch_file).exists():
        print(f"Error: File not found: {args.batch_file}")
        sys.exit(1)

    chat_id = args.chat_id
    if chat_id is None:
        env_chat_id = os.environ.get("ADMIN_CHAT_ID")
        if not env_chat_id:
            parser.error("Provide --chat-id or set ADMIN_CHAT_ID")
        try:
            chat_id = int(env_chat_id)
        except ValueError:
            parser.error("ADMIN_CHAT_ID must be an integer")

    await add_batch(args.batch_file, chat_id, args.dry_run)


if __name__ == '__main__':
    asyncio.run(main())

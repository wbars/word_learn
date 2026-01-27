#!/usr/bin/env python3
"""Import MySQL dump to Railway PostgreSQL.

This script reads a MySQL dump file and imports it to PostgreSQL,
handling the necessary data type conversions.

Usage:
    python scripts/import_to_railway.py <mysql_dump.sql> <postgresql_url>

Example:
    python scripts/import_to_railway.py backups/word_learner_en.sql "postgresql://user:pass@host/db"
"""
import argparse
import asyncio
import re
import sys
from datetime import datetime
from typing import Optional

import asyncpg


def parse_mysql_dump(filepath: str) -> dict:
    """Parse MySQL dump file and extract data.

    Returns dict with table_name -> list of row dicts
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    data = {
        'words': [],
        'word_practice': [],
        'word_skiplist': [],
        'current_practice': [],
        'current_practice_stats': [],
        'reminders': [],
        'today_practice': [],
    }

    # Find INSERT statements using character-by-character parsing
    # to properly handle semicolons inside quoted strings
    insert_start_pattern = re.compile(
        r"INSERT INTO `?(\w+)`?\s+(?:\([^)]+\)\s+)?VALUES\s*",
        re.IGNORECASE
    )

    for match in insert_start_pattern.finditer(content):
        table_name = match.group(1)
        if table_name not in data:
            continue

        # Find the end of the VALUES clause by tracking quotes
        values_start = match.end()
        values_str = extract_values_clause(content, values_start)

        if values_str:
            # Parse values - handle multiple rows in one INSERT
            rows = parse_values(values_str, table_name)
            data[table_name].extend(rows)

    return data


def extract_values_clause(content: str, start: int) -> str:
    """Extract VALUES clause handling semicolons inside quoted strings."""
    i = start
    in_string = False
    string_char = None
    escape_next = False

    while i < len(content):
        c = content[i]

        if escape_next:
            escape_next = False
            i += 1
            continue

        if c == '\\':
            escape_next = True
            i += 1
            continue

        if c in ("'", '"') and not in_string:
            in_string = True
            string_char = c
        elif c == string_char and in_string:
            in_string = False
            string_char = None
        elif c == ';' and not in_string:
            # Found the end of the INSERT statement
            return content[start:i]

        i += 1

    # No semicolon found, return whatever we have
    return content[start:]


def parse_values(values_str: str, table_name: str) -> list:
    """Parse VALUES clause into list of dicts."""
    rows = []

    # Parse character by character to handle nested parens and quotes
    i = 0
    while i < len(values_str):
        # Find start of row
        if values_str[i] == '(':
            # Find matching closing paren
            row_start = i + 1
            depth = 1
            in_string = False
            string_char = None
            escape_next = False
            j = row_start

            while j < len(values_str) and depth > 0:
                c = values_str[j]

                if escape_next:
                    escape_next = False
                    j += 1
                    continue

                if c == '\\':
                    escape_next = True
                    j += 1
                    continue

                if c in ("'", '"') and not in_string:
                    in_string = True
                    string_char = c
                elif c == string_char and in_string:
                    in_string = False
                    string_char = None
                elif not in_string:
                    if c == '(':
                        depth += 1
                    elif c == ')':
                        depth -= 1

                j += 1

            row_str = values_str[row_start:j-1]
            values = parse_row_values(row_str)

            if values:
                row_dict = map_values_to_columns(table_name, values)
                if row_dict:
                    rows.append(row_dict)

            i = j
        else:
            i += 1

    return rows


def parse_row_values(row_str: str) -> list:
    """Parse a single row's values."""
    values = []
    current = ""
    in_string = False
    string_char = None
    escape_next = False

    for char in row_str:
        if escape_next:
            current += char
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            current += char
            continue

        if char in ('"', "'") and not in_string:
            in_string = True
            string_char = char
            current += char
        elif char == string_char and in_string:
            in_string = False
            string_char = None
            current += char
        elif char == ',' and not in_string:
            values.append(parse_value(current.strip()))
            current = ""
        else:
            current += char

    if current.strip():
        values.append(parse_value(current.strip()))

    return values


def parse_value(val: str):
    """Parse a single value from MySQL dump."""
    if val.upper() == 'NULL':
        return None
    if val.startswith(("'", '"')) and val.endswith(("'", '"')):
        # Remove quotes and unescape
        return val[1:-1].replace("\\'", "'").replace('\\"', '"').replace('\\n', '\n')
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def map_values_to_columns(table_name: str, values: list) -> Optional[dict]:
    """Map values to column names based on table schema."""
    # Column order matches the MySQL dump CREATE TABLE statements
    schemas = {
        'words': ['en', 'ru', 'nl', 'id'],
        'word_practice': ['word_id', 'chat_id', 'next_date', 'stage', 'deleted', 'id'],
        'word_skiplist': ['word_id', 'chat_id'],
        'current_practice': ['chat_id', 'word_id'],
        'current_practice_stats': ['chat_id', 'correct', 'total'],
        'reminders': ['chat_id', 'remind_time', 'next_remind'],
        'today_practice': ['date', 'word_practice_id'],
    }

    if table_name not in schemas:
        return None

    columns = schemas[table_name]
    if len(values) < len(columns):
        # Pad with None if fewer values
        values = values + [None] * (len(columns) - len(values))

    return dict(zip(columns, values[:len(columns)]))


async def import_to_postgres(data: dict, pg_url: str, dry_run: bool = False):
    """Import parsed data to PostgreSQL."""
    print(f"\nConnecting to PostgreSQL...")
    conn = await asyncpg.connect(pg_url)

    try:
        print("Importing data...\n")

        # Import in order (respecting foreign keys)
        await import_words(conn, data['words'], dry_run)
        await import_word_practice(conn, data['word_practice'], dry_run)
        await import_word_skiplist(conn, data['word_skiplist'], dry_run)
        await import_current_practice(conn, data['current_practice'], dry_run)
        await import_current_practice_stats(conn, data['current_practice_stats'], dry_run)
        await import_reminders(conn, data['reminders'], dry_run)
        await import_today_practice(conn, data['today_practice'], dry_run)

        print("\nImport complete!")

    finally:
        await conn.close()


async def import_words(conn, rows: list, dry_run: bool):
    """Import words table."""
    print(f"  words: {len(rows)} rows", end="")
    if dry_run:
        print(" (dry run)")
        return

    skipped = 0
    for row in rows:
        word_id = row.get('id')
        if word_id is None:
            skipped += 1
            continue
        try:
            await conn.execute("""
                INSERT INTO words (id, en, nl, ru)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET en = $2, nl = $3, ru = $4
            """, word_id, row.get('en'), row.get('nl'), row.get('ru'))
        except Exception as e:
            print(f"\n    Warning: skipping word {word_id}: {e}")
            skipped += 1

    # Reset sequence
    valid_ids = [r.get('id') for r in rows if r.get('id')]
    if valid_ids:
        max_id = max(valid_ids)
        await conn.execute(f"SELECT setval('words_id_seq', {max_id})")

    if skipped:
        print(f" OK ({skipped} skipped)")
    else:
        print(" OK")


async def import_word_practice(conn, rows: list, dry_run: bool):
    """Import word_practice table."""
    print(f"  word_practice: {len(rows)} rows", end="")
    if dry_run:
        print(" (dry run)")
        return

    skipped = 0
    for row in rows:
        if not row.get('id') or not row.get('word_id'):
            skipped += 1
            continue

        next_date = row.get('next_date')
        if isinstance(next_date, str):
            try:
                next_date = datetime.strptime(next_date, '%Y-%m-%d %H:%M:%S')
            except:
                next_date = datetime.now()

        deleted = bool(row.get('deleted', 0))

        try:
            await conn.execute("""
                INSERT INTO word_practice (id, word_id, chat_id, next_date, stage, deleted)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
            """, row.get('id'), row.get('word_id'), row.get('chat_id'),
                next_date, row.get('stage', 0), deleted)
        except Exception as e:
            skipped += 1

    valid_ids = [r.get('id') for r in rows if r.get('id')]
    if valid_ids:
        max_id = max(valid_ids)
        await conn.execute(f"SELECT setval('word_practice_id_seq', {max_id})")

    if skipped:
        print(f" OK ({skipped} skipped)")
    else:
        print(" OK")


async def import_word_skiplist(conn, rows: list, dry_run: bool):
    """Import word_skiplist table."""
    print(f"  word_skiplist: {len(rows)} rows", end="")
    if dry_run:
        print(" (dry run)")
        return

    for row in rows:
        await conn.execute("""
            INSERT INTO word_skiplist (word_id, chat_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, row.get('word_id'), row.get('chat_id'))

    print(" OK")


async def import_current_practice(conn, rows: list, dry_run: bool):
    """Import current_practice table."""
    print(f"  current_practice: {len(rows)} rows", end="")
    if dry_run:
        print(" (dry run)")
        return

    for row in rows:
        await conn.execute("""
            INSERT INTO current_practice (chat_id, word_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, row.get('chat_id'), row.get('word_id'))

    print(" OK")


async def import_current_practice_stats(conn, rows: list, dry_run: bool):
    """Import current_practice_stats table."""
    print(f"  current_practice_stats: {len(rows)} rows", end="")
    if dry_run:
        print(" (dry run)")
        return

    for row in rows:
        await conn.execute("""
            INSERT INTO current_practice_stats (chat_id, correct, total)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id) DO UPDATE SET correct = $2, total = $3
        """, row.get('chat_id'), row.get('correct', 0), row.get('total', 0))

    print(" OK")


async def import_reminders(conn, rows: list, dry_run: bool):
    """Import reminders table."""
    print(f"  reminders: {len(rows)} rows", end="")
    if dry_run:
        print(" (dry run)")
        return

    for row in rows:
        remind_time = row.get('remind_time')
        if isinstance(remind_time, str):
            try:
                from datetime import time
                parts = remind_time.split(':')
                remind_time = time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
            except:
                continue

        next_remind = row.get('next_remind')
        if isinstance(next_remind, str):
            try:
                next_remind = datetime.strptime(next_remind, '%Y-%m-%d %H:%M:%S')
            except:
                next_remind = datetime.now()

        await conn.execute("""
            INSERT INTO reminders (chat_id, remind_time, next_remind)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id) DO UPDATE SET remind_time = $2, next_remind = $3
        """, row.get('chat_id'), remind_time, next_remind)

    print(" OK")


async def import_today_practice(conn, rows: list, dry_run: bool):
    """Import today_practice table."""
    print(f"  today_practice: {len(rows)} rows", end="")
    if dry_run:
        print(" (dry run)")
        return

    skipped = 0
    for row in rows:
        if not row.get('word_practice_id'):
            skipped += 1
            continue

        date_val = row.get('date')
        if isinstance(date_val, str):
            try:
                from datetime import date
                date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
            except:
                date_val = datetime.now().date()

        try:
            await conn.execute("""
                INSERT INTO today_practice (word_practice_id, date)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """, row.get('word_practice_id'), date_val)
        except Exception:
            skipped += 1

    if skipped:
        print(f" OK ({skipped} skipped)")
    else:
        print(" OK")


async def main():
    parser = argparse.ArgumentParser(description='Import MySQL dump to PostgreSQL')
    parser.add_argument('mysql_dump', help='Path to MySQL dump file')
    parser.add_argument('pg_url', help='PostgreSQL connection URL')
    parser.add_argument('--dry-run', action='store_true', help='Parse only, do not import')
    args = parser.parse_args()

    print("=" * 50)
    print("  MySQL to PostgreSQL Import")
    print("=" * 50)
    print(f"\nSource: {args.mysql_dump}")
    print(f"Target: {args.pg_url.split('@')[1] if '@' in args.pg_url else args.pg_url}")

    print("\nParsing MySQL dump...")
    data = parse_mysql_dump(args.mysql_dump)

    print("\nData summary:")
    for table, rows in data.items():
        print(f"  {table}: {len(rows)} rows")

    await import_to_postgres(data, args.pg_url, args.dry_run)


if __name__ == '__main__':
    asyncio.run(main())

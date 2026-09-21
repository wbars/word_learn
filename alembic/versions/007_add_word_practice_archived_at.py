"""Add archived_at column to word_practice for the reversible word archive

Revision ID: 007
Revises: 006
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL = active card; a timestamp = the card is archived (hidden from
    # practice but fully restorable). Independent of the `deleted` flag.
    op.add_column(
        "word_practice",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("word_practice", "archived_at")

"""Add vocabulary course progress table

Revision ID: 005
Revises: 004
Create Date: 2026-05-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vocabulary_course_progress",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.Text(), nullable=False),
        sa.Column("last_added_batch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_added_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("chat_id", "course_id"),
    )


def downgrade() -> None:
    op.drop_table("vocabulary_course_progress")

"""Add reverse_cards and daily_limit toggles to user_settings

Revision ID: 008
Revises: 007
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both flags default to TRUE so every chat keeps the behaviour it had
    # before this migration (reversed card on add, 67-76 words a day) until it
    # opts out with /reverse_cards_off or /daily_limit_off.
    op.add_column(
        "user_settings",
        sa.Column(
            "reverse_cards",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "daily_limit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "daily_limit")
    op.drop_column("user_settings", "reverse_cards")

"""Add consecutive_failures column to word_practice

Revision ID: 003
Revises: 002
Create Date: 2024-01-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'word_practice',
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('word_practice', 'consecutive_failures')

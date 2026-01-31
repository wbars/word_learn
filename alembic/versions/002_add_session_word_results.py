"""Add session word results table

Revision ID: 002
Revises: 001
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # session_word_results: per-word results during practice session
    op.create_table(
        'session_word_results',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('word_id', sa.Integer(), nullable=False),
        sa.Column('result', sa.String(10), nullable=False),  # 'correct', 'incorrect', 'deleted'
        sa.Column('old_stage', sa.Integer(), nullable=False),
        sa.Column('new_stage', sa.Integer(), nullable=True),  # NULL for deleted
        sa.Column('word_source', sa.Text(), nullable=False),
        sa.Column('word_target', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('chat_id', 'word_id'),
        sa.ForeignKeyConstraint(['word_id'], ['words.id'], ondelete='CASCADE')
    )


def downgrade() -> None:
    op.drop_table('session_word_results')

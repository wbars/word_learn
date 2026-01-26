"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # words: vocabulary entries (multi-language)
    op.create_table(
        'words',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('en', sa.Text(), nullable=True),
        sa.Column('nl', sa.Text(), nullable=True),
        sa.Column('ru', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # word_practice: user's learning progress per word
    op.create_table(
        'word_practice',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('word_id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('next_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('stage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['word_id'], ['words.id'], ondelete='CASCADE')
    )
    op.create_index(
        'idx_word_practice_lookup',
        'word_practice',
        ['chat_id', 'next_date', 'deleted']
    )
    op.create_index(
        'idx_word_practice_word_chat',
        'word_practice',
        ['word_id', 'chat_id']
    )

    # word_skiplist: words user skipped during /addWords
    op.create_table(
        'word_skiplist',
        sa.Column('word_id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('word_id', 'chat_id'),
        sa.ForeignKeyConstraint(['word_id'], ['words.id'], ondelete='CASCADE')
    )

    # current_practice: active practice session
    op.create_table(
        'current_practice',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('word_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('chat_id', 'word_id'),
        sa.ForeignKeyConstraint(['word_id'], ['words.id'], ondelete='CASCADE')
    )

    # today_practice: daily word pool (67-76 random words)
    op.create_table(
        'today_practice',
        sa.Column('word_practice_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE')),
        sa.PrimaryKeyConstraint('word_practice_id', 'date'),
        sa.ForeignKeyConstraint(['word_practice_id'], ['word_practice.id'], ondelete='CASCADE')
    )
    op.create_index('idx_today_practice_date', 'today_practice', ['date'])

    # current_practice_stats: session statistics
    op.create_table(
        'current_practice_stats',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('correct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('chat_id')
    )

    # reminders: daily reminder settings
    op.create_table(
        'reminders',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('remind_time', sa.Time(), nullable=False),
        sa.Column('next_remind', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('chat_id')
    )


def downgrade() -> None:
    op.drop_table('reminders')
    op.drop_table('current_practice_stats')
    op.drop_index('idx_today_practice_date', 'today_practice')
    op.drop_table('today_practice')
    op.drop_table('current_practice')
    op.drop_table('word_skiplist')
    op.drop_index('idx_word_practice_word_chat', 'word_practice')
    op.drop_index('idx_word_practice_lookup', 'word_practice')
    op.drop_table('word_practice')
    op.drop_table('words')

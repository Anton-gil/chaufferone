"""outbound_log table

Revision ID: d8e5a1b7c9f0
Revises: c7d1e2f3a4b5
Create Date: 2026-09-29 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e5a1b7c9f0'
down_revision: Union[str, Sequence[str], None] = 'c7d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'outbound_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('host', sa.String(), nullable=False),
        sa.Column('purpose', sa.String(), nullable=False),
        sa.Column('ok', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_outbound_log_host', 'outbound_log', ['host'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_outbound_log_host', table_name='outbound_log')
    op.drop_table('outbound_log')

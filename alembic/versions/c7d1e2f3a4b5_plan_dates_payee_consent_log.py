"""plan dates, payee, consent log

Revision ID: c7d1e2f3a4b5
Revises: 1820e2fbfcc9
Create Date: 2026-09-30 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d1e2f3a4b5'
down_revision: Union[str, Sequence[str], None] = '1820e2fbfcc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('obligations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('planned_on', sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column('plan_locked', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column('payee', sa.String(), nullable=True))
        batch_op.create_index('ix_obligations_planned_on', ['planned_on'], unique=False)

    op.create_table(
        'consent_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('proposal_id', sa.String(), nullable=True),
        sa.Column('spoken_proposal', sa.Text(), nullable=True),
        sa.Column('utterance', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(), nullable=False),
        sa.Column('parsed_by', sa.String(), nullable=False, server_default='rules'),
        sa.Column('applied_moves', sa.JSON(), nullable=False),
        sa.Column('reply', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_consent_log_user_id', 'consent_log', ['user_id'], unique=False)
    op.create_index('ix_consent_log_proposal_id', 'consent_log', ['proposal_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_consent_log_proposal_id', table_name='consent_log')
    op.drop_index('ix_consent_log_user_id', table_name='consent_log')
    op.drop_table('consent_log')
    with op.batch_alter_table('obligations', schema=None) as batch_op:
        batch_op.drop_index('ix_obligations_planned_on')
        batch_op.drop_column('payee')
        batch_op.drop_column('plan_locked')
        batch_op.drop_column('planned_on')

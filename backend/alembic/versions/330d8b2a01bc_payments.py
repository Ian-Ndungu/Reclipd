"""Test-mode payment ledger."""
from alembic import op
import sqlalchemy as sa
revision = '330d8b2a01bc'
down_revision = '220c7a1f09ab'
branch_labels = depends_on = None

def upgrade():
    op.create_table('payments',
        sa.Column('reference', sa.String(40), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('minutes', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_payments_user_id','payments',['user_id'])

def downgrade():
    op.drop_table('payments')

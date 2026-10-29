"""PayPal sandbox order and capture identities."""
from alembic import op
import sqlalchemy as sa
revision='660a1b5e04ef'
down_revision='550f0a4d03de'
branch_labels=depends_on=None
def upgrade():
    op.add_column('payments',sa.Column('provider',sa.String(20),nullable=False,server_default='paystack'))
    op.add_column('payments',sa.Column('provider_order_id',sa.String(64),nullable=True))
    op.add_column('payments',sa.Column('provider_capture_id',sa.String(64),nullable=True))
    op.create_index('ix_payments_order_unique','payments',['provider_order_id'],unique=True)
    op.create_index('ix_payments_capture_unique','payments',['provider_capture_id'],unique=True)
def downgrade():
    op.drop_index('ix_payments_capture_unique',table_name='payments')
    op.drop_index('ix_payments_order_unique',table_name='payments')
    for name in ['provider_capture_id','provider_order_id','provider']:op.drop_column('payments',name)

"""Expiring credit buckets and idempotent project reservations."""
from alembic import op
import sqlalchemy as sa
import hashlib
revision='440e9c3b02cd'
down_revision='330d8b2a01bc'
branch_labels=depends_on=None

def upgrade():
    op.add_column('users',sa.Column('credit_identity',sa.String(64),nullable=True))
    op.create_index('ix_users_credit_identity','users',['credit_identity'],unique=True)
    seen=set()
    connection=op.get_bind()
    for row in connection.execute(sa.text('SELECT id,email FROM users ORDER BY created_at,id')):
        local,domain=row.email.strip().casefold().split('@',1)
        if domain in {'gmail.com','googlemail.com'}:
            domain='gmail.com';local=local.split('+',1)[0].replace('.','')
        key=hashlib.sha256(f'{local}@{domain}'.encode()).hexdigest()
        if key not in seen:
            connection.execute(sa.text('UPDATE users SET credit_identity=:key WHERE id=:id'),{'key':key,'id':row.id})
            seen.add(key)
    op.add_column('users',sa.Column('credit_initialized',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('payments',sa.Column('currency',sa.String(3),nullable=False,server_default='KES'))
    op.add_column('payments',sa.Column('pack_id',sa.String(40),nullable=True))
    op.add_column('payments',sa.Column('paid_at',sa.DateTime(timezone=True),nullable=True))
    op.create_table('credit_grants',sa.Column('id',sa.String(100),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('kind',sa.String(20),nullable=False),sa.Column('seconds',sa.Float(),nullable=False),sa.Column('remaining',sa.Float(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint('remaining >= 0 AND remaining <= seconds',name='credit_nonnegative'))
    op.create_index('ix_credit_grants_user_id','credit_grants',['user_id'])
    op.create_table('credit_reservations',sa.Column('project_id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('name',sa.String(200),nullable=False),sa.Column('seconds',sa.Float(),nullable=False),sa.Column('allocations',sa.JSON(),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_credit_reservations_user_id','credit_reservations',['user_id'])

def downgrade():
    op.drop_table('credit_reservations');op.drop_table('credit_grants')
    for name in ['paid_at','pack_id','currency']:op.drop_column('payments',name)
    op.drop_index('ix_users_credit_identity',table_name='users')
    op.drop_column('users','credit_identity');op.drop_column('users','credit_initialized')

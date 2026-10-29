"""Account preferences, session revocation, recovery and deletion."""
from alembic import op
import sqlalchemy as sa
revision='550f0a4d03de'
down_revision='440e9c3b02cd'
branch_labels=depends_on=None

def upgrade():
    op.add_column('users',sa.Column('deletion_keys',sa.JSON(),nullable=False,server_default='[]'))
    op.add_column('users',sa.Column('preferences',sa.JSON(),nullable=False,server_default='{}'))
    op.add_column('users',sa.Column('session_version',sa.Integer(),nullable=False,server_default='0'))
    op.add_column('users',sa.Column('deleted',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('users',sa.Column('reset_digest',sa.String(64),nullable=True))
    op.add_column('users',sa.Column('reset_expires',sa.DateTime(timezone=True),nullable=True))
    op.create_index('ix_users_reset_digest','users',['reset_digest'])

def downgrade():
    op.drop_index('ix_users_reset_digest',table_name='users')
    for name in ['deletion_keys','reset_expires','reset_digest','deleted','session_version','preferences']:
        op.drop_column('users',name)

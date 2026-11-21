"""Encrypted Google Drive connection records."""
from alembic import op
import sqlalchemy as sa

revision = "770a1b6c02de"
down_revision = "660a1b5e04ef"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "drive_connections",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("drive_connections")

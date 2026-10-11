"""Owner-scoped connections between YouTube IDs and authorized stored originals."""

from alembic import op
import sqlalchemy as sa

revision = "220c7a1f09ab"
down_revision = "114d1757a67f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_connections",
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True
        ),
        sa.Column("video_id", sa.String(11), primary_key=True),
        sa.Column(
            "project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("source_connections")

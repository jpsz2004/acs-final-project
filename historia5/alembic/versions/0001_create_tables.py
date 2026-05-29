"""create users, jobs, texts tables

Revision ID: 0001_create_tables
Revises:
Create Date: 2026-05-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_create_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        # notified: guards exactly-once event publishing across workers.
        # Once a worker sets this to True, no other worker can publish
        # JobCompletedEvent for the same job (try_mark_notified atomicity).
        sa.Column("notified", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])

    op.create_table(
        "texts",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(32), nullable=True),
        sa.Column("sentiment", sa.String(32), nullable=True),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_texts_job_id", "texts", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_texts_job_id", table_name="texts")
    op.drop_table("texts")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("users")

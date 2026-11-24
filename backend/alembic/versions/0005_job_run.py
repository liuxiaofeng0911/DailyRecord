"""定时任务执行记录表

Revision ID: 0005_job_run
Revises: 0004_tag_icon
Create Date: 2026-11-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_job_run"
down_revision = "0004_tag_icon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("dr_job_run"):
        return
    op.create_table(
        "dr_job_run",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("job_name", sa.String(length=64), nullable=False),
        sa.Column("run_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="RUNNING"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("job_name", "run_key", name="uq_dr_job_run"),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("dr_job_run"):
        op.drop_table("dr_job_run")

"""修改留痕日志表

Revision ID: 0003_change_log
Revises: 0002_photo_trash
Create Date: 2026-11-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_change_log"
down_revision = "0002_photo_trash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("dr_change_log"):
        return
    op.create_table(
        "dr_change_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("operator_id", sa.BigInteger(), nullable=False),
        sa.Column("operator_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("entry_id", sa.BigInteger(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_dr_change_log_user_time", "dr_change_log", ["user_id", "created_at"])
    op.create_index("idx_dr_change_log_entry", "dr_change_log", ["entry_date", "created_at"])
    op.create_index("idx_dr_change_log_entity", "dr_change_log", ["entity_type", "entity_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("dr_change_log"):
        op.drop_table("dr_change_log")

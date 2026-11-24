"""标签图标字段

Revision ID: 0004_tag_icon
Revises: 0003_change_log
Create Date: 2026-11-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_tag_icon"
down_revision = "0003_change_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("tag"):
        return
    columns = {column["name"] for column in inspector.get_columns("tag")}
    if "icon" not in columns:
        op.add_column("tag", sa.Column("icon", sa.String(length=32), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("tag"):
        columns = {column["name"] for column in inspector.get_columns("tag")}
        if "icon" in columns:
            op.drop_column("tag", "icon")

"""照片软删除与回收站字段

Revision ID: 0002_photo_trash
Revises: 0001_initial
Create Date: 2026-11-24

注意：0001 使用当前模型元数据建表，因此本迁移对新库是幂等的（列已存在则跳过），
对旧库补齐缺失列。
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_photo_trash"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _existing_columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    columns = _existing_columns("photo")
    if not columns:
        return
    additions = {
        "origin": sa.Column("origin", sa.String(length=8), nullable=False, server_default="import"),
        "deleted_at": sa.Column("deleted_at", sa.DateTime(), nullable=True),
        "deleted_by": sa.Column("deleted_by", sa.String(length=64), nullable=True),
        "purge_after": sa.Column("purge_after", sa.DateTime(), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("photo", column)
    op.execute("UPDATE photo SET origin = 'upload' WHERE origin IS NULL")


def downgrade() -> None:
    columns = _existing_columns("photo")
    for name in ("purge_after", "deleted_by", "deleted_at", "origin"):
        if name in columns:
            op.drop_column("photo", name)

"""建表脚本：按模型创建全部表结构并写入种子数据

结构变更直接修改模型后重建，不再累计增量迁移脚本；
旧库残留的历史版本号会在 alembic/env.py 中自动清理。

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

from app.db import Base
import app.models  # noqa: F401
from app.services.bootstrap import ensure_seed_data

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

AUDIT_COLUMNS = ("insert_user", "update_user")


def _align_legacy_columns(bind) -> None:
    """历史库审计字段沿用 BigTrans 的 varchar(10)，写入较长账号会报错，这里按模型放宽。"""
    if bind.dialect.name != "postgresql":
        return
    inspector = sa.inspect(bind)
    for table in Base.metadata.sorted_tables:
        existing = {column["name"]: column for column in inspector.get_columns(table.name)}
        for name in AUDIT_COLUMNS:
            column = table.columns.get(name)
            if column is None or name not in existing:
                continue
            db_length = getattr(existing[name]["type"], "length", None)
            model_length = getattr(column.type, "length", None)
            if db_length and model_length and db_length < model_length:
                bind.execute(
                    sa.text(
                        f'ALTER TABLE "{table.name}" ALTER COLUMN "{name}" '
                        f"TYPE VARCHAR({model_length})"
                    )
                )


def upgrade() -> None:
    bind = op.get_bind()
    # 一次性创建全部表（含 BigTrans 系统表与扩展字段），再写入种子数据
    Base.metadata.create_all(bind=bind)
    _align_legacy_columns(bind)
    with Session(bind=bind) as db:
        ensure_seed_data(db)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

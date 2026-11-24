"""初始表结构：系统表、业务表、应用支撑表与种子数据

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-22
"""

from alembic import op
from sqlalchemy.orm import Session

from app.db import Base
import app.models  # noqa: F401
from app.services.bootstrap import ensure_seed_data

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # 一次性创建全部表（含 BigTrans 系统表与扩展字段），再写入种子数据
    Base.metadata.create_all(bind=bind)
    with Session(bind=bind) as db:
        ensure_seed_data(db)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

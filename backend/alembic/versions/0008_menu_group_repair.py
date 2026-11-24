"""修复旧库“系统管理”分组被页面占用的问题

Revision ID: 0008_menu_group_repair
Revises: 0007_immich_credential
Create Date: 2026-11-24
"""

from alembic import op
from sqlalchemy.orm import Session

from app.services.bootstrap import ensure_menu_data

revision = "0008_menu_group_repair"
down_revision = "0007_immich_credential"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with Session(bind=op.get_bind()) as db:
        ensure_menu_data(db)


def downgrade() -> None:
    # 基础数据修复，回滚时保留，避免误删用户授权
    pass

"""菜单种子与角色默认菜单

Revision ID: 0006_menu_seed
Revises: 0005_job_run
Create Date: 2026-11-24
"""

from alembic import op
from sqlalchemy.orm import Session

from app.services.bootstrap import ensure_menu_data

revision = "0006_menu_seed"
down_revision = "0005_job_run"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with Session(bind=op.get_bind()) as db:
        ensure_menu_data(db)


def downgrade() -> None:
    # 菜单属于基础数据，回滚时保留，避免误删用户授权
    pass

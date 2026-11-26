"""新增组织共享总开关与双向可见规则表

Revision ID: 0002_org_share
Revises: 0001_initial
Create Date: 2026-11-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

from app.models import OrgShareConfig, OrgShareRule
from app.services.bootstrap import ensure_seed_data

revision = "0002_org_share"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # 新装库已在 0001 的 create_all 中建表，这里只补齐历史库缺失的表
    for table in (OrgShareConfig.__table__, OrgShareRule.__table__):
        if not inspector.has_table(table.name):
            table.create(bind)
    with Session(bind=bind) as db:
        ensure_seed_data(db)


def downgrade() -> None:
    bind = op.get_bind()
    for name in ("t_org_share_rule", "t_org_share_config"):
        if sa.inspect(bind).has_table(name):
            op.drop_table(name)

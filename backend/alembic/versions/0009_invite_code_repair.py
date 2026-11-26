"""修复历史库邀请码表缺失或不完整导致的注册异常

Revision ID: 0009_invite_code_repair
Revises: 0008_menu_group_repair
Create Date: 2026-11-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_invite_code_repair"
down_revision = "0008_menu_group_repair"
branch_labels = None
depends_on = None

REQUIRED_COLUMNS: dict[str, sa.types.TypeEngine] = {
    "code_hash": sa.String(length=64),
    "created_by": sa.BigInteger(),
    "used_by": sa.BigInteger(),
    "expires_at": sa.DateTime(),
    "used_at": sa.DateTime(),
    "insert_time": sa.DateTime(),
    "remark": sa.Text(),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("dr_invite_code"):
        # 老库根本没有邀请码表，开启邀请码注册时会直接报服务异常
        op.create_table(
            "dr_invite_code",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("used_by", sa.BigInteger(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("insert_time", sa.DateTime(), nullable=False),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.UniqueConstraint("code_hash", name="uq_dr_invite_code_code_hash"),
        )
        return

    columns = {column["name"] for column in inspector.get_columns("dr_invite_code")}
    for name, column_type in REQUIRED_COLUMNS.items():
        if name not in columns:
            op.add_column("dr_invite_code", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    # 只做补全，不删除历史数据
    pass

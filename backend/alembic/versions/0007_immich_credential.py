"""Immich 每账号凭据表

Revision ID: 0007_immich_credential
Revises: 0006_menu_seed
Create Date: 2026-11-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_immich_credential"
down_revision = "0006_menu_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("dr_immich_credential"):
        return
    op.create_table(
        "dr_immich_credential",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("immich_user_id", sa.String(length=64), nullable=True),
        sa.Column("immich_email", sa.String(length=255), nullable=True),
        sa.Column("base_url", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("api_key_cipher", sa.Text(), nullable=True),
        sa.Column("api_key_hint", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("album_id", sa.String(length=64), nullable=True),
        sa.Column("provision_source", sa.String(length=8), nullable=False, server_default="auto"),
        sa.Column(
            "provision_status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column("provision_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_provision_error", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="disabled"),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("provisioned_at", sa.DateTime(), nullable=True),
        sa.Column("insert_time", sa.DateTime(), nullable=False),
        sa.Column("update_time", sa.DateTime(), nullable=False),
        sa.Column("insert_user", sa.String(length=64), nullable=True),
        sa.Column("update_user", sa.String(length=64), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.BigInteger(), nullable=False, server_default="1"),
        sa.UniqueConstraint("user_id", name="uq_dr_immich_credential_user_id"),
    )
    op.create_index("ix_dr_immich_credential_user_id", "dr_immich_credential", ["user_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("dr_immich_credential"):
        op.drop_table("dr_immich_credential")

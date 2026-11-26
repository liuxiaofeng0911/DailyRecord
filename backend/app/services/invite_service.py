"""邀请码服务：生成、校验与核销。

邀请码只保存 SHA-256 摘要，明文仅在生成时返回一次。
"""

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError
from ..models import InviteCode
from .timeutil import now_shanghai

CODE_BYTES = 12


def hash_code(value: str) -> str:
    """统一小写后哈希，避免大小写差异导致邀请码“无效”。"""
    return hashlib.sha256((value or "").strip().lower().encode()).hexdigest()


def _legacy_hash_code(value: str) -> str:
    """历史邀请码按原样哈希，保留兼容。"""
    return hashlib.sha256((value or "").strip().encode()).hexdigest()


def create_invite(
    db: Session, created_by: int, days: int = 7, remark: str | None = None
) -> tuple[str, InviteCode]:
    code = secrets.token_urlsafe(CODE_BYTES)
    invite = InviteCode(
        code_hash=hash_code(code),
        created_by=created_by,
        expires_at=now_shanghai() + timedelta(days=max(int(days), 1)),
        remark=remark,
    )
    db.add(invite)
    db.flush()
    return code, invite


def consume_invite(db: Session, code: str, user_id: int) -> InviteCode:
    value = (code or "").strip()
    if not value:
        raise ApiError(codes.INVALID_INVITE, "请填写邀请码")
    invite = db.scalars(
        select(InviteCode).where(
            InviteCode.code_hash.in_({hash_code(value), _legacy_hash_code(value)})
        )
    ).first()
    now = now_shanghai()
    if invite is None:
        raise ApiError(codes.INVALID_INVITE, "邀请码无效，请向所有者重新获取")
    if invite.used_at is not None:
        raise ApiError(codes.INVALID_INVITE, "邀请码已被使用，请向所有者重新获取")
    if not invite.expires_at or invite.expires_at < now:
        raise ApiError(codes.INVALID_INVITE, "邀请码已过期，请向所有者重新获取")
    invite.used_by = user_id
    invite.used_at = now
    return invite


def list_invites(db: Session, limit: int = 20) -> list[InviteCode]:
    return list(
        db.scalars(select(InviteCode).order_by(InviteCode.id.desc()).limit(limit)).all()
    )

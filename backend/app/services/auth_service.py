from datetime import timedelta

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ComUser, LoginLog, Role, UserRole, UserSession
from ..security.jwt import create_token
from ..services.timeutil import now_shanghai


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def user_agent(request: Request) -> str:
    return (request.headers.get("user-agent") or "")[:255]


def role_code_of(db: Session, user_id: int) -> str:
    row = db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, Role.enable == "Y")
        .order_by(Role.id)
    ).first()
    return row[0] if row else "MEMBER"


def mask_ip(ip: str | None) -> str | None:
    if not ip:
        return ip
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:3] + ["****"])
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.*"
    return ip


def create_session_token(db: Session, user: ComUser, request: Request) -> tuple[str, UserSession]:
    """创建 JWT + 服务端会话登记；超过上限时撤销最旧会话。"""
    role = role_code_of(db, user.id)
    token, jti, expires = create_token(
        user_id=user.id, userid=user.userid, role=role, token_version=user.token_version
    )
    session = UserSession(
        user_id=user.id,
        jti=jti,
        user_agent=user_agent(request),
        ip=client_ip(request),
        expires_at=expires,
    )
    db.add(session)
    db.flush()

    active = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.created_at.asc())
    ).all()
    overflow = len(active) - settings.session_max
    for old in active[: max(overflow, 0)]:
        old.revoked_at = now_shanghai()
    return token, session


def revoke_all_sessions(db: Session, user: ComUser) -> None:
    now = now_shanghai()
    for session in db.scalars(
        select(UserSession).where(
            UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
        )
    ).all():
        session.revoked_at = now
    user.token_version = (user.token_version or 0) + 1


def write_login_log(
    db: Session,
    request: Request,
    *,
    userid: str,
    result: str,
    user_id: int | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        LoginLog(
            user_id=user_id,
            userid=userid[:64],
            ip=client_ip(request),
            user_agent=user_agent(request),
            result=result,
            reason=reason[:128] if reason else None,
        )
    )


def find_user_by_identifier(db: Session, identifier: str) -> ComUser | None:
    value = identifier.strip().lower()
    return db.scalars(
        select(ComUser).where(
            (func.lower(ComUser.userid) == value) | (func.lower(ComUser.email) == value)
        )
    ).first()


def touch_login(db: Session, user: ComUser) -> None:
    user.login_time = now_shanghai().strftime("%Y-%m-%d %H:%M:%S")
    user.failed_login_attempts = 0
    user.locked_until = None


def lock_duration() -> timedelta:
    return timedelta(minutes=15)

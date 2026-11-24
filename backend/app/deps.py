"""请求依赖：JWT 认证、当前用户、权限校验。"""

from dataclasses import dataclass
from datetime import timedelta

import jwt as pyjwt
from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .common import codes
from .common.exceptions import ApiError, forbidden, unauthorized
from .config import settings
from .db import get_db
from .models import ComUser, UserSession
from .security.jwt import create_token, decode_token, seconds_remaining
from .services.auth_service import role_code_of
from .services.timeutil import now_shanghai

COOKIE_NAME = "dr_token"
COOKIE_PATH = "/api"


@dataclass
class UserContext:
    id: int
    userid: str
    username: str
    email: str | None
    user_type: str
    role_code: str
    jti: str
    session_id: int
    token_version: int

    @property
    def is_owner(self) -> bool:
        return self.role_code == "OWNER" or self.user_type == "2"


def _extract_token(request: Request) -> str:
    header = request.headers.get("Authorization") or ""
    token = header.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token and request.url.path.startswith(("/photo", "/immich")):
        token = request.cookies.get(COOKIE_NAME, "")
    return token


def get_current_user(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> UserContext:
    token = _extract_token(request)
    if not token:
        raise unauthorized()
    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError as exc:
        raise unauthorized() from exc

    jti = payload.get("jti") or ""
    session = db.scalars(select(UserSession).where(UserSession.jti == jti)).first()
    if session is None or session.revoked_at is not None:
        raise unauthorized()
    now = now_shanghai()
    if session.expires_at < now:
        raise unauthorized()

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise unauthorized() from exc

    user = db.get(ComUser, user_id)
    if user is None or user.user_active != "Y":
        raise unauthorized()
    if int(payload.get("ver", -1)) != int(user.token_version or 0):
        raise unauthorized()

    if session.last_seen_at is None or now - session.last_seen_at > timedelta(minutes=5):
        session.last_seen_at = now
        db.commit()

    role = role_code_of(db, user.id)
    if seconds_remaining(payload) <= settings.jwt_refresh_threshold_minutes * 60:
        new_token, _, expires = create_token(
            user_id=user.id,
            userid=user.userid,
            role=role,
            token_version=user.token_version,
            jti=jti,
        )
        response.headers["token"] = new_token
        response.set_cookie(
            COOKIE_NAME,
            new_token,
            max_age=settings.jwt_expire_minutes * 60,
            httponly=True,
            secure=settings.env == "prod",
            samesite="lax",
            path=COOKIE_PATH,
        )
        session.expires_at = expires
        db.commit()

    return UserContext(
        id=user.id,
        userid=user.userid,
        username=user.username or user.userid,
        email=user.email,
        user_type=user.user_type,
        role_code=role,
        jti=jti,
        session_id=session.id,
        token_version=user.token_version,
    )


def require_owner(user: UserContext = Depends(get_current_user)) -> UserContext:
    if not user.is_owner:
        raise forbidden("仅所有者可执行该操作")
    return user


__all__ = [
    "COOKIE_NAME",
    "COOKIE_PATH",
    "UserContext",
    "get_current_user",
    "require_owner",
    "codes",
    "ApiError",
]

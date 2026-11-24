"""HS256 JWT 签发与校验，兼容 BigTrans 的 Authorization 原文约定。"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from ..config import settings
from ..services.timeutil import TZ, now_shanghai

ALGORITHM = "HS256"


def create_token(
    *,
    user_id: int,
    userid: str,
    role: str,
    token_version: int,
    jti: str | None = None,
    now: datetime | None = None,
) -> tuple[str, str, datetime]:
    issued = now or now_shanghai()
    jti = jti or uuid.uuid4().hex
    expires = issued + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "userid": userid,
        "role": role,
        "ver": token_version,
        "jti": jti,
        "iat": int(issued.replace(tzinfo=TZ).timestamp()),
        "exp": int(expires.replace(tzinfo=TZ).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, jti, expires


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def seconds_remaining(payload: dict) -> int:
    exp = int(payload.get("exp", 0))
    return max(exp - int(datetime.now(UTC).timestamp()), 0)

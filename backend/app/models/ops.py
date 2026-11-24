from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..common.snowflake import next_id
from ..db import Base
from ..services.timeutil import now_shanghai


class UserSession(Base):
    __tablename__ = "dr_user_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LoginLog(Base):
    __tablename__ = "dr_login_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    userid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, index=True)


class InviteCode(Base):
    __tablename__ = "dr_invite_code"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChangeLog(Base):
    """修改留痕：只追加，不提供更新与删除接口。"""

    __tablename__ = "dr_change_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    operator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operator_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    entry_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    changes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_shanghai, nullable=False, index=True
    )

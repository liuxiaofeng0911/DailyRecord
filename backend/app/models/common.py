from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..common.snowflake import next_id
from ..services.timeutil import now_shanghai


class CommonFields:
    """业务表公共字段，对应设计文档 10.1。"""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    insert_user: Mapped[str | None] = mapped_column(String(64), nullable=True)
    update_user: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    org_id: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)


class IdIntMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)


__all__ = ["CommonFields", "IdIntMixin", "Integer"]

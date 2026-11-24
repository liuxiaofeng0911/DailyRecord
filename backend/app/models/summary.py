from datetime import date

from sqlalchemy import BigInteger, Date, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .common import CommonFields


class DailySummary(CommonFields, Base):
    __tablename__ = "daily_summary"
    __table_args__ = (
        UniqueConstraint("user_id", "period_type", "period_start", name="uq_summary_user_period"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(8), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")

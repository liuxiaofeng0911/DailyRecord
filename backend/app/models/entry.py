from datetime import date

from sqlalchemy import BigInteger, Column, Date, ForeignKey, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .common import CommonFields

entry_tag = Table(
    "entry_tag",
    Base.metadata,
    Column("entry_id", BigInteger, ForeignKey("daily_entry.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", BigInteger, ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)


class DailyEntry(CommonFields, Base):
    __tablename__ = "daily_entry"
    __table_args__ = (UniqueConstraint("user_id", "entry_date", name="uq_daily_entry_user_date"),)

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mood: Mapped[str | None] = mapped_column(String(32), nullable=True)

    tags: Mapped[list["Tag"]] = relationship(secondary=entry_tag, back_populates="entries")
    photos: Mapped[list["Photo"]] = relationship(  # noqa: F821
        back_populates="entry", order_by="Photo.taken_at"
    )


class Tag(CommonFields, Base):
    __tablename__ = "tag"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_tag_user_name"),)

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="tag")
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)

    entries: Mapped[list[DailyEntry]] = relationship(secondary=entry_tag, back_populates="tags")

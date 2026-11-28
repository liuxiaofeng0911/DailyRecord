from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .common import CommonFields


class Photo(CommonFields, Base):
    __tablename__ = "photo"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("daily_entry.id", ondelete="SET NULL"), nullable=True, index=True
    )
    immich_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    storage_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="immich")
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    media_type: Mapped[str] = mapped_column(String(8), nullable=False, default="IMAGE")
    origin: Mapped[str] = mapped_column(String(8), nullable=False, default="upload")
    taken_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    caption_source: Mapped[str] = mapped_column(String(8), nullable=False, default="none")
    ai_state: Mapped[str] = mapped_column(String(12), nullable=False, default="disabled")
    ai_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # AI 关键词数组，PostgreSQL 用 JSONB，开发态 SQLite 退化为 JSON
    ai_keywords: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    is_cover: Mapped[bool] = mapped_column(default=False, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    deleted_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    entry: Mapped["DailyEntry | None"] = relationship(back_populates="photos")  # noqa: F821

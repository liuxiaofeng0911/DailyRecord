from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .common import CommonFields


class ImmichCredential(CommonFields, Base):
    """每个应用账号独立 Immich 凭据，API Key 仅加密存储。"""

    __tablename__ = "dr_immich_credential"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    immich_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    immich_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    api_key_cipher: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_hint: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    album_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provision_source: Mapped[str] = mapped_column(String(8), nullable=False, default="auto")
    provision_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    provision_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_provision_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="disabled")
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provisioned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

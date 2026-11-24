from datetime import date

from pydantic import Field

from .common import CamelModel, DateStr, DateTimeStr, OptDateTimeStr, StrId


class TagOut(CamelModel):
    id: StrId
    name: str
    kind: str


class PhotoOut(CamelModel):
    id: StrId
    entry_id: StrId | None = None
    immich_asset_id: str | None = None
    storage_kind: str = "immich"
    media_type: str
    mime_type: str
    taken_at: OptDateTimeStr = None
    caption: str = ""
    caption_source: str = "none"
    ai_state: str = "disabled"
    is_cover: bool = False
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None


class EntryOut(CamelModel):
    id: StrId
    entry_date: DateStr
    note: str
    mood: str | None = None
    tags: list[TagOut] = Field(default_factory=list)
    photos: list[PhotoOut] = Field(default_factory=list)
    version: int
    update_time: DateTimeStr


class EntryGetRequest(CamelModel):
    date: date
    entry_date: date | None = None


class EntrySaveRequest(CamelModel):
    entry_date: date
    note: str | None = None
    mood: str | None = None
    tags: list[str] | None = None
    photo_ids: list[StrId] | None = None
    cover_photo_id: StrId | None = None
    version: int | None = None


class EntryDeleteRequest(CamelModel):
    entry_date: date


class EntryListRequest(CamelModel):
    page: dict | None = None
    wheres: list[dict] = Field(default_factory=list)
    order_bys: list[dict] = Field(default_factory=list, alias="orderBys")
    page_number: int | None = None
    page_size: int | None = None

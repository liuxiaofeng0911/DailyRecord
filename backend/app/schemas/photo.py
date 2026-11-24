from datetime import date, datetime

from pydantic import Field

from .common import CamelModel, DateTimeStr, StrId


class PhotoUpdateRequest(CamelModel):
    id: StrId
    caption: str | None = None
    taken_at: datetime | None = None
    is_cover: bool | None = None


class PhotoDeleteRequest(CamelModel):
    id: StrId


class PhotoListRequest(CamelModel):
    start: date | None = None
    end: date | None = None
    unattached: bool = False
    entry_id: StrId | None = None
    page_number: int = 1
    page_size: int = 100


class TrashListRequest(CamelModel):
    page: dict | None = None
    page_number: int | None = None
    page_size: int | None = None


class PhotoIdsRequest(CamelModel):
    ids: list[StrId] = Field(default_factory=list)


class UploadError(CamelModel):
    filename: str
    reason: str


class UploadResult(CamelModel):
    photos: list = Field(default_factory=list)
    errors: list[UploadError] = Field(default_factory=list)


class PhotoDescribeRequest(CamelModel):
    id: StrId


class ImmichAsset(CamelModel):
    id: str
    type: str = "IMAGE"
    mime_type: str = ""
    taken_at: DateTimeStr | None = None
    description: str = ""
    original_file_name: str = ""


class ImmichImportRequest(CamelModel):
    date: date
    asset_ids: list[str] | None = None


class ImmichStatusOut(CamelModel):
    enabled: bool
    available: bool
    message: str = ""

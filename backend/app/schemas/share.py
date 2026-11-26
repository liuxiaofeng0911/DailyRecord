from datetime import date

from pydantic import Field

from .common import CamelModel, DateStr, StrId
from .entry import PhotoOut, TagOut


class ShareMembersRequest(CamelModel):
    org_id: StrId | None = None
    include_children: bool = True


class ShareMemberOut(CamelModel):
    id: StrId
    userid: str
    username: str
    role_code: str = "MEMBER"


class ShareEntriesRequest(CamelModel):
    org_id: StrId | None = None
    user_id: StrId | None = None
    include_children: bool = True
    start: date | None = None
    end: date | None = None
    keyword: str | None = None
    page: dict | None = None
    page_number: int | None = None
    page_size: int | None = None


class SharedEntryOut(CamelModel):
    id: StrId
    entry_date: DateStr
    note: str = ""
    mood: str | None = None
    tags: list[TagOut] = Field(default_factory=list)
    photos: list[PhotoOut] = Field(default_factory=list)
    user_id: StrId
    userid: str = ""
    username: str = ""

from datetime import date

from pydantic import Field

from .common import CamelModel


class CalendarRequest(CamelModel):
    year: int | None = None
    start: date | None = None
    end: date | None = None


class SearchRequest(CamelModel):
    keyword: str = ""
    start: date | None = None
    end: date | None = None
    limit: int = Field(default=50, ge=1, le=200)


class ExportRequest(CamelModel):
    format: str = "json"
    start: date | None = None
    end: date | None = None

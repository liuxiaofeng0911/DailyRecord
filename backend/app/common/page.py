"""BigTrans 风格分页请求解析。

请求结构：
{
  "page": {"pageNumber": 1, "pageSize": 20},
  "wheres": [{"column": "entry_date", "condition": "ge", "v1": "2026-01-01"}],
  "orderBys": [{"column": "entry_date", "condition": "desc"}]
}
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

MAX_PAGE_SIZE = 200


class PageParam(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    page_number: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=MAX_PAGE_SIZE)


class WhereItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    column: str
    condition: str = "eq"
    v1: Any = None
    v2: Any = None


class OrderByItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    column: str
    condition: str = "desc"


class ListRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    page: PageParam = Field(default_factory=PageParam)
    wheres: list[WhereItem] = Field(default_factory=list)
    order_bys: list[OrderByItem] = Field(default_factory=list, alias="orderBys")
    columns: list[str] | None = None


def page_payload(items: list[Any], total: int, page_number: int, page_size: int) -> dict:
    return {
        "list": items,
        "totalRow": total,
        "pageNumber": page_number,
        "pageSize": page_size,
    }

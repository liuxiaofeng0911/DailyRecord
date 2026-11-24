from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel

StrId = Annotated[str, BeforeValidator(lambda value: None if value is None else str(value))]
DateStr = Annotated[date, PlainSerializer(lambda value: value.strftime("%Y-%m-%d"), return_type=str)]
DateTimeStr = Annotated[
    datetime, PlainSerializer(lambda value: value.strftime("%Y-%m-%d %H:%M:%S"), return_type=str)
]
OptDateTimeStr = Annotated[
    datetime | None,
    PlainSerializer(
        lambda value: value.strftime("%Y-%m-%d %H:%M:%S") if value else None, return_type=str | None
    ),
]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )

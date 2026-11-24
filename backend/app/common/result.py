from datetime import date, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from . import codes as code_defs


def to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, BaseModel):
        return obj.model_dump(by_alias=True, mode="json")
    if isinstance(obj, (datetime, date)):
        return obj.strftime("%Y-%m-%d %H:%M:%S") if isinstance(obj, datetime) else obj.isoformat()
    if isinstance(obj, list | tuple):
        return [to_jsonable(item) for item in obj]
    if isinstance(obj, dict):
        return {key: to_jsonable(value) for key, value in obj.items()}
    return jsonable_encoder(obj)


def ok(data: Any = None, message: str = "操作成功") -> dict:
    return {"code": code_defs.OK, "message": message, "data": to_jsonable(data)}


def fail(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": to_jsonable(data)}

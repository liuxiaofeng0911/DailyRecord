"""轻量 XSS / SQL 关键字过滤，参考 BigTrans RequestAdvice。

仅过滤 JSON 请求体中的明显攻击载荷；文件上传跳过。
"""

import json
import re

from fastapi import Request

from . import codes
from .exceptions import ApiError

_XSS_PATTERN = re.compile(
    r"(<\s*script|<\s*iframe|<\s*img[^>]+onerror|javascript\s*:|"
    r"on(?:click|error|load|mouseover|focus|submit|change)\s*=)",
    re.IGNORECASE,
)
_SQL_PATTERN = re.compile(
    r"(\bunion\s+select\b|\bdrop\s+table\b|\bdelete\s+from\b|\binsert\s+into\b|--\s|/\*|\*/|;\s*shutdown)",
    re.IGNORECASE,
)

SKIP_PATHS = ("/photo/upload", "/auth/publicKey", "/health", "/ready", "/docs", "/openapi.json")
SKIP_FIELDS = {"password", "confirmPassword", "oldPassword", "newPassword"}


def _check_text(text: str) -> None:
    if _XSS_PATTERN.search(text) or _SQL_PATTERN.search(text):
        raise ApiError(codes.XSS_REJECTED, "请求包含非法字符")


def inspect_payload(payload: object, parent_key: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in SKIP_FIELDS:
                continue
            inspect_payload(value, key)
    elif isinstance(payload, list):
        for item in payload:
            inspect_payload(item, parent_key)
    elif isinstance(payload, str):
        _check_text(payload)


def inspect_body(body: bytes) -> None:
    if not body:
        return
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    inspect_payload(payload)


async def guard(request: Request) -> None:
    """FastAPI 依赖：对 JSON 请求体做 XSS/SQL 关键字过滤。"""
    path = request.url.path
    if path.startswith(SKIP_PATHS) or path in SKIP_PATHS:
        return
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return
    body = await request.body()
    inspect_body(body)

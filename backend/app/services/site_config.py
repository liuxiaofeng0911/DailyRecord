"""可在线修改的业务配置。

值统一存放于 t_switch（字符串），所有者可在「系统设置」页修改并立即生效；
.env 中的同名配置只作为首次初始化的默认值，部署地址、密钥等基础设施参数仍留在 .env。
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError
from ..config import settings
from ..models import Switch

AI_ENABLED = "DAILYRECORD_AI_ENABLED"
UPLOAD_MAX_MB = "DAILYRECORD_UPLOAD_MAX_MB"
TRASH_KEEP_DAYS = "DAILYRECORD_TRASH_KEEP_DAYS"
PURGE_TIME = "DAILYRECORD_PURGE_TIME"
# 仅用于老库首次升级：把“.env AI_ENABLED 生效”的旧行为迁移成前端可改的总开关
AI_INIT_MARK = "DAILYRECORD_AI_INIT_APPLIED"

UPLOAD_MAX_LIMIT = 2048
TRASH_DAYS_LIMIT = 365
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

KEY_LABELS = {
    AI_ENABLED: "AI 总开关",
    UPLOAD_MAX_MB: "上传大小上限(MB)",
    TRASH_KEEP_DAYS: "回收站保留天数",
    PURGE_TIME: "回收站清理时间",
}


def _raw(db: Session, key: str) -> str | None:
    row = db.scalars(select(Switch).where(Switch.switch_key == key)).first()
    return row.enabled if row is not None else None


def _defaults() -> dict[str, str]:
    return {
        AI_ENABLED: "1" if settings.ai_enabled else "N",
        UPLOAD_MAX_MB: str(settings.max_upload_mb),
        TRASH_KEEP_DAYS: "30",
        PURGE_TIME: f"{settings.photo_purge_hour:02d}:{settings.photo_purge_minute:02d}",
    }


def ensure_defaults(db: Session) -> None:
    """老库缺少新增开关时补齐默认值，保证前端总能读到可编辑项。"""
    existing = set(db.scalars(select(Switch.switch_key)).all())
    defaults = _defaults()
    missing = [key for key in defaults if key not in existing]
    if AI_INIT_MARK not in existing:
        db.add(Switch(switch_key=AI_INIT_MARK, switch_name="AI 开关初始化标记", enabled="1"))
        # 旧版本里 .env 的 AI_ENABLED 是真正的开关；升级时一次性沿用，之后以前端配置为准
        if settings.ai_enabled and AI_ENABLED not in missing:
            row = db.scalars(select(Switch).where(Switch.switch_key == AI_ENABLED)).first()
            if row is not None and row.enabled.upper() in ("N", "0", ""):
                row.enabled = "1"
    if not missing and AI_INIT_MARK in existing:
        return
    for key in missing:
        db.add(Switch(switch_key=key, switch_name=KEY_LABELS.get(key), enabled=defaults[key]))
    db.commit()


def _int_value(db: Session, key: str, default: int, minimum: int, maximum: int) -> int:
    raw = _raw(db, key) or str(default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return min(max(value, minimum), maximum)


def upload_max_mb(db: Session) -> int:
    return _int_value(db, UPLOAD_MAX_MB, settings.max_upload_mb, 1, UPLOAD_MAX_LIMIT)


def trash_keep_days(db: Session) -> int:
    return _int_value(db, TRASH_KEEP_DAYS, 30, 1, TRASH_DAYS_LIMIT)


def purge_hour_minute(db: Session) -> tuple[int, int]:
    raw = _raw(db, PURGE_TIME) or _defaults()[PURGE_TIME]
    match = TIME_RE.match(raw.strip())
    if match is None:
        return settings.photo_purge_hour, settings.photo_purge_minute
    return int(match.group(1)), int(match.group(2))


def ai_enabled(db: Session) -> bool:
    raw = (_raw(db, AI_ENABLED) or _defaults()[AI_ENABLED]).strip().upper()
    return raw in ("1", "Y", "ON", "TRUE")


def public_settings(db: Session) -> dict:
    return {
        "upload_max_mb": upload_max_mb(db),
        "trash_keep_days": trash_keep_days(db),
        "ai_enabled": ai_enabled(db),
    }


def normalize(key: str, value: str) -> str:
    """校验并规范化已知业务配置，未知键按原值保存。"""
    text = (value or "").strip()
    if key == AI_ENABLED:
        return "1" if text.upper() in ("1", "Y", "ON", "TRUE") else "N"
    if key == UPLOAD_MAX_MB:
        try:
            number = int(text)
        except (TypeError, ValueError):
            raise ApiError(codes.BAD_REQUEST, "上传大小上限需为整数") from None
        if not 1 <= number <= UPLOAD_MAX_LIMIT:
            raise ApiError(codes.BAD_REQUEST, f"上传大小上限需在 1-{UPLOAD_MAX_LIMIT}MB 之间")
        return str(number)
    if key == TRASH_KEEP_DAYS:
        try:
            number = int(text)
        except (TypeError, ValueError):
            raise ApiError(codes.BAD_REQUEST, "回收站保留天数需为整数") from None
        if not 1 <= number <= TRASH_DAYS_LIMIT:
            raise ApiError(codes.BAD_REQUEST, f"回收站保留天数需在 1-{TRASH_DAYS_LIMIT} 天之间")
        return str(number)
    if key == PURGE_TIME:
        match = TIME_RE.match(text)
        if match is None:
            raise ApiError(codes.BAD_REQUEST, "清理时间格式应为 HH:MM，例如 03:30")
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    return value

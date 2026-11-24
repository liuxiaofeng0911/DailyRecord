"""修改留痕：字段级增量 diff 与日志写入。"""

import uuid
from datetime import date

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import UserContext
from ..models import ChangeLog, DailyEntry, Photo
from .timeutil import DATETIME_FMT, now_shanghai

MAX_TEXT_PIECE = 2000


def _clip(text: str) -> str:
    if len(text) <= MAX_TEXT_PIECE:
        return text
    return text[:MAX_TEXT_PIECE] + "…"


def _common_prefix(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def _common_suffix(left: str, right: str, prefix: int) -> int:
    limit = min(len(left), len(right)) - prefix
    index = 0
    while index < limit and left[-1 - index] == right[-1 - index]:
        index += 1
    return index


def text_change(before: str, after: str) -> dict | None:
    if before == after:
        return None
    prefix = _common_prefix(before, after)
    suffix = _common_suffix(before, after, prefix)
    added = after[prefix : len(after) - suffix]
    removed = before[prefix : len(before) - suffix]
    return {
        "field": "note",
        "op": "update",
        "added": _clip(added),
        "removed": _clip(removed),
        "beforeLength": len(before),
        "afterLength": len(after),
    }


def tag_change(before: list[str], after: list[str]) -> dict | None:
    added = [name for name in after if name not in before]
    removed = [name for name in before if name not in after]
    if not added and not removed:
        return None
    return {"field": "tags", "op": "update", "added": added, "removed": removed}


def replace_change(field: str, before, after) -> dict | None:
    if before == after:
        return None
    return {"field": field, "op": "replace", "before": before, "after": after}


def photos_change(before: list[str], after: list[str]) -> dict | None:
    added = [item for item in after if item not in before]
    removed = [item for item in before if item not in after]
    if not added and not removed:
        return None
    return {"field": "photos", "op": "update", "added": added, "removed": removed}


def entry_snapshot(entry: DailyEntry, photos: list[Photo]) -> dict:
    active = [photo for photo in photos if photo.deleted_at is None]
    cover = next((str(photo.id) for photo in active if photo.is_cover), None)
    return {
        "note": entry.note or "",
        "mood": entry.mood,
        "tags": [tag.name for tag in entry.tags],
        "photos": [str(photo.id) for photo in active],
        "cover": cover,
    }


def snapshot_from_db(db: Session, entry: DailyEntry) -> dict:
    photos = list(
        db.scalars(
            select(Photo).where(
                Photo.entry_id == entry.id,
                Photo.deleted_at.is_(None),
            )
        )
    )
    return entry_snapshot(entry, photos)


def _create_changes(before: dict, after: dict) -> list[dict]:
    changes: list[dict] = []
    if after["note"]:
        changes.append(
            {
                "field": "note",
                "op": "add",
                "added": _clip(after["note"]),
                "beforeLength": 0,
                "afterLength": len(after["note"]),
            }
        )
    if after["mood"]:
        changes.append({"field": "mood", "op": "add", "after": after["mood"]})
    if after["tags"]:
        changes.append({"field": "tags", "op": "add", "added": list(after["tags"])})
    if after["photos"]:
        changes.append({"field": "photos", "op": "add", "added": list(after["photos"])})
    return changes


def diff_entry(before: dict | None, after: dict, created: bool) -> tuple[list[dict], list[str]]:
    if created or before is None:
        changes = _create_changes(before or {}, after)
        fields = [change["field"] for change in changes]
        return changes, fields

    changes = [
        change
        for change in (
            text_change(before["note"], after["note"]),
            replace_change("mood", before["mood"], after["mood"]),
            tag_change(before["tags"], after["tags"]),
            photos_change(before["photos"], after["photos"]),
            replace_change("cover", before["cover"], after["cover"]),
        )
        if change is not None
    ]
    return changes, [change["field"] for change in changes]


def _request_meta(request: Request | None) -> dict:
    if request is None:
        return {"request_id": None, "ip": None, "user_agent": None}
    forwarded = request.headers.get("x-forwarded-for") or ""
    ip = forwarded.split(",")[0].strip() or (
        request.client.host if request.client else None
    )
    return {
        "request_id": request.headers.get("x-request-id") or uuid.uuid4().hex[:32],
        "ip": ip,
        "user_agent": (request.headers.get("user-agent") or "")[:255] or None,
    }


def add_log(
    db: Session,
    *,
    user: UserContext,
    action: str,
    entity_type: str,
    changes: list[dict] | None = None,
    entity_id: int | None = None,
    entry: DailyEntry | None = None,
    entry_date: date | None = None,
    request: Request | None = None,
) -> ChangeLog:
    meta = _request_meta(request)
    log = ChangeLog(
        user_id=user.id,
        operator_id=user.id,
        operator_name=user.username or user.userid,
        entity_type=entity_type,
        entity_id=entity_id or (entry.id if entry else None),
        entry_id=entry.id if entry else None,
        entry_date=entry.entry_date if entry else entry_date,
        action=action,
        changes=changes or [],
        request_id=meta["request_id"],
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        created_at=now_shanghai(),
    )
    db.add(log)
    return log


def serialize_log(log: ChangeLog) -> dict:
    return {
        "id": str(log.id),
        "action": log.action,
        "entityType": log.entity_type,
        "operatorName": log.operator_name,
        "createdAt": log.created_at.strftime(DATETIME_FMT) if log.created_at else None,
        "changes": log.changes or [],
    }

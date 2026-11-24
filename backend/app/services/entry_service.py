"""记录写入辅助：标签归一化、封面唯一、照片归属校验。"""

import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import DailyEntry, Photo, Tag

logger = logging.getLogger(__name__)

MAX_TAGS = 20


def normalize_tags(raw_tags: list[str] | None) -> list[str]:
    if not raw_tags:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_tags:
        name = (raw or "").strip().lstrip("#").strip()
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        result.append(name[:64])
        if len(result) >= MAX_TAGS:
            break
    return result


def resolve_tags(db: Session, user_id: int, names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for name in names:
        tag = db.scalars(
            select(Tag).where(Tag.user_id == user_id, Tag.name == name)
        ).first()
        if tag is None:
            tag = Tag(user_id=user_id, name=name, kind="tag")
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def clear_cover(db: Session, entry_id: int, except_photo_id: int | None = None) -> None:
    stmt = update(Photo).where(Photo.entry_id == entry_id, Photo.is_cover.is_(True))
    if except_photo_id is not None:
        stmt = stmt.where(Photo.id != except_photo_id)
    db.execute(stmt.values(is_cover=False))


def attach_photos(
    db: Session,
    entry: DailyEntry,
    user_id: int,
    photo_ids: list[int],
    cover_photo_id: int | None,
) -> None:
    wanted = set(photo_ids)
    owned = {
        photo.id: photo
        for photo in db.scalars(
            select(Photo).where(Photo.user_id == user_id, Photo.id.in_(wanted))
        ).all()
    }
    missing = wanted - owned.keys()
    if missing:
        logger.warning("忽略不属于当前用户的照片: %s", sorted(missing))

    # 先摘除本记录下不再保留的照片
    for photo in db.scalars(
        select(Photo).where(Photo.entry_id == entry.id, Photo.user_id == user_id)
    ).all():
        if photo.id not in wanted:
            photo.entry_id = None
            photo.is_cover = False

    for photo in owned.values():
        if photo.entry_id is not None and photo.entry_id != entry.id:
            # 每张照片只属于一条记录，先解除旧关联
            old_entry = db.get(DailyEntry, photo.entry_id)
            if old_entry is not None and old_entry.user_id == user_id:
                clear_cover(db, old_entry.id, photo.id)
        photo.entry_id = entry.id

    db.flush()
    clear_cover(db, entry.id)
    chosen = owned.get(cover_photo_id) if cover_photo_id else None
    if chosen is None:
        chosen = next((owned[pid] for pid in photo_ids if pid in owned), None)
    if chosen is not None:
        chosen.is_cover = True
    db.flush()

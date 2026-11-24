"""照片回收站：软删除、恢复与到期清理。"""

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ChangeLog, DailyEntry, Photo
from . import storage
from .immich import ImmichClient, ImmichError
from .timeutil import now_shanghai

logger = logging.getLogger(__name__)

TRASH_DAYS = 30
PURGE_LIMIT = 500


def soft_delete(db: Session, photo: Photo, operator: str) -> None:
    """移入回收站：保留 entry_id 以便恢复时回到原记录，但不再参与展示。"""
    now = now_shanghai()
    photo.deleted_at = now
    photo.deleted_by = operator
    photo.purge_after = now + timedelta(days=TRASH_DAYS)
    photo.is_cover = False
    photo.update_user = operator
    photo.update_time = now
    photo.version = int(photo.version or 0) + 1
    db.add(photo)


def restore(db: Session, photo: Photo, operator: str) -> None:
    photo.deleted_at = None
    photo.deleted_by = None
    photo.purge_after = None
    photo.update_user = operator
    photo.update_time = now_shanghai()
    photo.version = int(photo.version or 0) + 1
    db.add(photo)


def trash_item(photo: Photo, db: Session) -> dict:
    entry = db.get(DailyEntry, photo.entry_id) if photo.entry_id else None
    origin_date = entry.entry_date if entry else (photo.taken_at.date() if photo.taken_at else None)
    days_left = 0
    if photo.purge_after:
        seconds = (photo.purge_after - now_shanghai()).total_seconds()
        days_left = max(0, int(seconds // 86400))
    return {
        "id": str(photo.id),
        "mediaType": photo.media_type,
        "mimeType": photo.mime_type,
        "takenAt": photo.taken_at.strftime("%Y-%m-%d %H:%M:%S") if photo.taken_at else None,
        "entryDate": origin_date.isoformat() if origin_date else None,
        "deletedAt": photo.deleted_at.strftime("%Y-%m-%d %H:%M:%S") if photo.deleted_at else None,
        "deletedBy": photo.deleted_by,
        "purgeAfter": photo.purge_after.strftime("%Y-%m-%d %H:%M:%S") if photo.purge_after else None,
        "daysLeft": days_left,
        "thumbnailUrl": f"/api/photo/thumbnail/{photo.id}",
        "originalUrl": f"/api/photo/original/{photo.id}",
    }


async def purge_photo(db: Session, photo: Photo) -> None:
    """彻底删除：本地文件必删；Immich 仅删除本应用上传的资产。"""
    if photo.storage_kind == "local":
        storage.delete_local(photo)
    elif photo.origin == "upload" and photo.immich_asset_id:
        try:
            await ImmichClient().delete_asset(photo.immich_asset_id)
        except ImmichError as exc:
            # 原图删除失败时不阻塞引用清理，避免回收站无限增长
            logger.warning("删除 Immich 资产失败: %s", exc)
    db.delete(photo)


def expired_photos(db: Session, limit: int = PURGE_LIMIT) -> list[Photo]:
    now = now_shanghai()
    return list(
        db.scalars(
            select(Photo)
            .where(Photo.deleted_at.is_not(None), Photo.purge_after <= now)
            .order_by(Photo.purge_after.asc())
            .limit(limit)
        )
    )


async def purge_expired(db: Session, limit: int = PURGE_LIMIT) -> dict:
    rows = expired_photos(db, limit)
    failed: list[str] = []
    for photo in rows:
        try:
            entry = db.get(DailyEntry, photo.entry_id) if photo.entry_id else None
            db.add(
                ChangeLog(
                    user_id=photo.user_id,
                    operator_id=0,
                    operator_name="system",
                    entity_type="PHOTO",
                    entity_id=photo.id,
                    entry_id=photo.entry_id,
                    entry_date=entry.entry_date if entry else None,
                    action="PURGE",
                    changes=[
                        {
                            "field": "photo",
                            "op": "purge",
                            "mediaType": photo.media_type,
                            "origin": photo.origin,
                        }
                    ],
                    created_at=now_shanghai(),
                )
            )
            await purge_photo(db, photo)
        except Exception as exc:  # pragma: no cover - 防御性
            logger.warning("清理照片 %s 失败: %s", photo.id, exc)
            failed.append(str(photo.id))
    db.commit()
    return {"purged": len(rows) - len(failed), "failed": failed}

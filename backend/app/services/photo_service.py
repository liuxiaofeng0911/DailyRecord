"""照片回收站：软删除、恢复与到期清理。"""

import logging
import math
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ChangeLog, ComUser, DailyEntry, JobRun, Photo
from . import credential_service, storage
from .immich import ImmichError
from .timeutil import now_shanghai, today_shanghai

logger = logging.getLogger(__name__)

TRASH_DAYS = 30
PURGE_LIMIT = 500


def soft_delete(db: Session, photo: Photo, operator: str, days: int | None = None) -> None:
    """移入回收站：保留 entry_id 以便恢复时回到原记录，但不再参与展示。"""
    now = now_shanghai()
    photo.deleted_at = now
    photo.deleted_by = operator
    photo.purge_after = now + timedelta(days=days or TRASH_DAYS)
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
        days_left = max(0, math.ceil(seconds / 86400))
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
        client = credential_service.user_client(db, photo.user_id)
        if client is None:
            logger.warning("照片库凭据不可用，跳过删除 Immich 资产: %s", photo.id)
        else:
            try:
                await client.delete_asset(photo.immich_asset_id)
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


async def migrate_local_to_immich(db: Session) -> dict:
    """把历史本机存储照片迁入各账号自己的 Immich 相册。"""
    rows = list(
        db.scalars(
            select(Photo)
            .where(Photo.storage_kind == "local")
            .order_by(Photo.id.asc())
        ).all()
    )
    clients = {}
    migrated = 0
    failed: list[dict] = []
    for photo in rows:
        try:
            user = db.get(ComUser, photo.user_id)
            if user is None:
                raise RuntimeError("照片所属用户不存在")
            client = clients.get(photo.user_id)
            if client is None:
                client = credential_service.user_client(db, photo.user_id)
                if client is None:
                    await credential_service.ensure_credential(db, user)
                    client = credential_service.user_client(db, photo.user_id)
                if client is None:
                    raise RuntimeError("照片库未开通或凭据不可用")
                clients[photo.user_id] = client
            path = Path(photo.local_path or "")
            if not photo.local_path or not path.is_file():
                raise RuntimeError("本地文件不存在")
            content = path.read_bytes()
            asset = await client.upload_asset(
                f"dailyrecord-{photo.id}{path.suffix or '.jpg'}",
                content,
                photo.mime_type or "application/octet-stream",
                photo.taken_at or now_shanghai(),
                album_id=credential_service.album_of(db, photo.user_id),
            )
            photo.storage_kind = "immich"
            photo.immich_asset_id = asset["id"]
            photo.local_path = None
            photo.origin = "upload"
            db.add(photo)
            db.commit()
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("迁移后删除本地文件失败: %s", path)
            migrated += 1
        except Exception as exc:  # noqa: BLE001 - 单张失败不阻塞其余照片
            db.rollback()
            logger.warning("照片迁移失败: id=%s error=%s", photo.id, exc)
            failed.append({"id": str(photo.id), "error": str(exc)[:200]})
    return {"total": len(rows), "migrated": migrated, "failed": failed}


async def run_purge_job(db: Session, run_key: str | None = None) -> dict:
    """每日清理任务入口：按天幂等，结果写入 dr_job_run。"""
    key = run_key or today_shanghai().isoformat()
    job = db.scalars(
        select(JobRun).where(JobRun.job_name == "photo_purge", JobRun.run_key == key)
    ).first()
    if job is not None and job.status in ("RUNNING", "SUCCESS"):
        return {"skipped": True, "status": job.status, "purged": 0, "failed": []}
    if job is None:
        job = JobRun(job_name="photo_purge", run_key=key, status="RUNNING")
        db.add(job)
    else:
        job.status = "RUNNING"
        job.error = None
    job.started_at = now_shanghai()
    job.finished_at = None
    db.commit()

    try:
        result = await purge_expired(db)
    except Exception as exc:  # pragma: no cover - 防御性
        logger.exception("回收站清理任务失败")
        db.rollback()
        job = db.get(JobRun, job.id)
        if job is not None:
            job.status = "FAILED"
            job.error = str(exc)[:2000]
            job.finished_at = now_shanghai()
            db.commit()
        return {"skipped": False, "status": "FAILED", "purged": 0, "failed": []}

    job = db.get(JobRun, job.id)
    if job is not None:
        job.status = "SUCCESS"
        job.finished_at = now_shanghai()
        job.error = None
        db.commit()
    return {"skipped": False, "status": "SUCCESS", **result}

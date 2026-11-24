import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError, not_found
from ..common.page import MAX_PAGE_SIZE, page_payload
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..config import settings
from ..db import get_db
from ..deps import UserContext, get_current_user
from ..models import ComUser, DailyEntry, Photo
from ..schemas.entry import PhotoOut
from ..schemas.photo import (
    PhotoDeleteRequest,
    PhotoDescribeRequest,
    PhotoIdsRequest,
    PhotoListRequest,
    PhotoUpdateRequest,
    TrashListRequest,
    UploadResult,
)
from ..services import audit, credential_service, photo_service, storage
from ..services.entry_service import clear_cover
from ..services.immich import ImmichError
from ..services.ollama import OllamaError, describe_image
from ..services.timeutil import now_shanghai, parse_datetime

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/photo",
    tags=["photo"],
    dependencies=[Depends(xss_guard), Depends(get_current_user)],
)


@router.post("/upload")
async def upload(
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    form = await request.form()
    entry_date_raw = form.get("entryDate")
    taken_at_raw = form.get("takenAt")
    entry_date: date | None = None
    if entry_date_raw:
        try:
            entry_date = date.fromisoformat(str(entry_date_raw)[:10])
        except ValueError:
            raise ApiError(codes.BAD_REQUEST, "entryDate 格式不正确") from None

    uploads = [
        value
        for key, value in form.multi_items()
        if key in ("files", "files[]") and hasattr(value, "filename")
    ]
    if not uploads:
        raise ApiError(codes.BAD_REQUEST, "请选择要上传的文件")

    entry = None
    if entry_date is not None:
        entry = db.scalars(
            select(DailyEntry).where(
                DailyEntry.user_id == user.id, DailyEntry.entry_date == entry_date
            )
        ).first()

    created: list[Photo] = []
    errors: list[dict] = []
    explicit_taken = parse_datetime(str(taken_at_raw)) if taken_at_raw else None

    entity = db.get(ComUser, user.id)
    credential = await credential_service.ensure_credential(db, entity) if entity else None
    client = credential_service.user_client(db, user.id)
    album_id = (credential.album_id or "") if credential else ""

    for upload_file in uploads:
        filename = upload_file.filename or "upload"
        try:
            content = await storage.read_upload(upload_file)
            stored = await storage.store(
                user_id=user.id,
                filename=filename,
                content=content,
                content_type=upload_file.content_type or "",
                client=client,
                album_id=album_id,
            )
        except ApiError as exc:
            errors.append({"filename": filename, "reason": exc.message})
            continue
        except ImmichError as exc:
            errors.append({"filename": filename, "reason": str(exc)})
            continue

        taken_at = explicit_taken or stored["taken_at"]
        if entry_date is not None and explicit_taken is None:
            taken_at = datetime.combine(entry_date, taken_at.time())
        ai_state = "disabled"
        if settings.ai_enabled:
            ai_state = "pending" if stored["media_type"] == "IMAGE" else "unsupported"

        photo = Photo(
            user_id=user.id,
            entry_id=entry.id if entry else None,
            immich_asset_id=stored["immich_asset_id"],
            storage_kind=stored["storage_kind"],
            local_path=stored["local_path"],
            mime_type=stored["mime_type"],
            media_type=stored["media_type"],
            origin="upload",
            taken_at=taken_at,
            ai_state=ai_state,
            width=stored["width"],
            height=stored["height"],
            duration_ms=stored["duration_ms"],
            insert_user=user.userid,
        )
        db.add(photo)
        created.append(photo)

    if not created:
        db.rollback()
        reason = "；".join(f"{item['filename']}: {item['reason']}" for item in errors)
        raise ApiError(codes.BAD_REQUEST, reason or "上传失败")

    db.flush()
    if entry is not None:
        has_cover = db.scalars(
            select(Photo).where(Photo.entry_id == entry.id, Photo.is_cover.is_(True))
        ).first()
        if has_cover is None and created:
            created[0].is_cover = True
    db.commit()
    return ok(UploadResult(photos=[PhotoOut.model_validate(p) for p in created], errors=errors))


@router.post("/list")
def list_photos(
    payload: PhotoListRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    stmt = (
        select(Photo)
        .where(Photo.user_id == user.id, Photo.deleted_at.is_(None))
        .order_by(Photo.taken_at.desc())
    )
    if payload.entry_id:
        stmt = stmt.where(Photo.entry_id == int(payload.entry_id))
    if payload.unattached:
        stmt = stmt.where(Photo.entry_id.is_(None))
    if payload.start:
        stmt = stmt.where(Photo.taken_at >= datetime.combine(payload.start, datetime.min.time()))
    if payload.end:
        stmt = stmt.where(Photo.taken_at <= datetime.combine(payload.end, datetime.max.time()))
    page_size = min(max(payload.page_size, 1), 200)
    rows = db.scalars(stmt.limit(page_size)).all()
    return ok([PhotoOut.model_validate(row) for row in rows])


@router.get("/thumbnail/{photo_id}")
async def thumbnail(
    photo_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    photo = db.scalars(
        select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id)
    ).first()
    if photo is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "照片不存在"})
    client = credential_service.user_client(db, user.id)
    if photo.storage_kind == "immich" and client is None:
        entity = db.get(ComUser, user.id)
        if entity is not None:
            await credential_service.ensure_credential(db, entity)
            client = credential_service.user_client(db, user.id)
    try:
        content, mime = await storage.read_bytes(photo, size="preview", client=client)
    except (FileNotFoundError, ImmichError):
        return JSONResponse(status_code=404, content={"code": 404, "message": "照片文件不存在"})
    return Response(
        content=content,
        media_type=mime,
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.get("/original/{photo_id}")
async def original(
    photo_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    photo = db.scalars(
        select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id)
    ).first()
    if photo is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "照片不存在"})
    client = credential_service.user_client(db, user.id)
    if photo.storage_kind == "immich" and client is None:
        entity = db.get(ComUser, user.id)
        if entity is not None:
            await credential_service.ensure_credential(db, entity)
            client = credential_service.user_client(db, user.id)
    try:
        content, mime = await storage.read_bytes(photo, size="original", client=client)
    except (FileNotFoundError, ImmichError):
        return JSONResponse(status_code=404, content={"code": 404, "message": "照片文件不存在"})
    return Response(content=content, media_type=mime)


def _photo_entry(db: Session, photo: Photo) -> DailyEntry | None:
    return db.get(DailyEntry, photo.entry_id) if photo.entry_id else None


def _log_photo(
    db: Session,
    photo: Photo,
    user: UserContext,
    action: str,
    changes: list[dict],
    request: Request,
) -> None:
    entry = _photo_entry(db, photo)
    audit.add_log(
        db,
        user=user,
        action=action,
        entity_type="PHOTO",
        changes=changes,
        entity_id=photo.id,
        entry=entry,
        entry_date=entry.entry_date if entry else (photo.taken_at.date() if photo.taken_at else None),
        request=request,
    )


@router.post("/update")
def update_photo(
    payload: PhotoUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    photo = db.scalars(
        select(Photo).where(
            Photo.id == int(payload.id),
            Photo.user_id == user.id,
            Photo.deleted_at.is_(None),
        )
    ).first()
    if photo is None:
        raise not_found("照片不存在")

    changes: list[dict] = []
    if payload.caption is not None:
        before_caption = photo.caption or ""
        photo.caption = payload.caption.strip()[:1000]
        photo.caption_source = "manual"
        photo.ai_state = "manual"
        if before_caption != photo.caption:
            changes.append(
                {
                    "field": "caption",
                    "op": "replace",
                    "before": before_caption,
                    "after": photo.caption,
                }
            )
    if payload.taken_at is not None:
        before_taken = (
            photo.taken_at.strftime("%Y-%m-%d %H:%M:%S") if photo.taken_at else None
        )
        photo.taken_at = payload.taken_at
        after_taken = photo.taken_at.strftime("%Y-%m-%d %H:%M:%S")
        if before_taken != after_taken:
            changes.append(
                {
                    "field": "takenAt",
                    "op": "replace",
                    "before": before_taken,
                    "after": after_taken,
                }
            )
    if payload.is_cover is not None:
        before_cover = bool(photo.is_cover)
        if payload.is_cover and photo.entry_id is None:
            raise ApiError(codes.BAD_REQUEST, "未关联记录的照片不能设为封面")
        if payload.is_cover:
            clear_cover(db, photo.entry_id, photo.id)
        photo.is_cover = payload.is_cover
        if before_cover != photo.is_cover:
            changes.append(
                {
                    "field": "cover",
                    "op": "replace",
                    "before": before_cover,
                    "after": photo.is_cover,
                }
            )
    photo.update_user = user.userid
    photo.update_time = now_shanghai()
    photo.version = int(photo.version or 0) + 1
    if changes:
        _log_photo(db, photo, user, "UPDATE", changes, request)
    db.commit()
    return ok(PhotoOut.model_validate(photo))


@router.post("/delete")
def delete_photo(
    payload: PhotoDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    photo = db.scalars(
        select(Photo).where(
            Photo.id == int(payload.id),
            Photo.user_id == user.id,
            Photo.deleted_at.is_(None),
        )
    ).first()
    if photo is None:
        raise not_found("照片不存在")
    photo_service.soft_delete(db, photo, user.userid)
    item = photo_service.trash_item(photo, db)
    _log_photo(
        db,
        photo,
        user,
        "TRASH",
        [
            {
                "field": "photo",
                "op": "trash",
                "mediaType": photo.media_type,
                "purgeAfter": item["purgeAfter"],
            }
        ],
        request,
    )
    db.commit()
    return ok({"id": str(photo.id), "purgeAfter": item["purgeAfter"]})


def _photo_scope(user: UserContext):
    if user.is_owner:
        return or_(Photo.user_id == user.id, Photo.user_id.is_not(None))
    return Photo.user_id == user.id


@router.post("/trash/list")
def trash_list(
    payload: TrashListRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    page_data = payload.page or {}
    try:
        page_number = max(int(page_data.get("pageNumber") or payload.page_number or 1), 1)
        page_size = min(
            max(int(page_data.get("pageSize") or payload.page_size or 20), 1), MAX_PAGE_SIZE
        )
    except (TypeError, ValueError):
        raise ApiError(codes.BAD_REQUEST, "分页参数不正确") from None

    base = select(Photo).where(Photo.user_id == user.id, Photo.deleted_at.is_not(None))
    total = db.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0
    rows = db.scalars(
        base.order_by(Photo.deleted_at.desc())
        .offset((page_number - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [photo_service.trash_item(row, db) for row in rows]
    return ok(page_payload(items, total, page_number, page_size))


@router.post("/trash/restore")
def trash_restore(
    payload: PhotoIdsRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    ids = [int(item) for item in payload.ids if str(item).isdigit()]
    if not ids:
        raise ApiError(codes.BAD_REQUEST, "请选择要恢复的照片")
    rows = db.scalars(
        select(Photo).where(
            Photo.id.in_(ids), _photo_scope(user), Photo.deleted_at.is_not(None)
        )
    ).all()
    restored: list[str] = []
    failed: list[dict] = []
    found = {photo.id for photo in rows}
    for photo in rows:
        photo_service.restore(db, photo, user.userid)
        _log_photo(
            db,
            photo,
            user,
            "RESTORE",
            [{"field": "photo", "op": "restore", "mediaType": photo.media_type}],
            request,
        )
        restored.append(str(photo.id))
    for photo_id in ids:
        if photo_id not in found:
            failed.append({"id": str(photo_id), "reason": "照片不存在或不在回收站"})
    db.commit()
    return ok({"restored": len(restored), "ids": restored, "failed": failed})


@router.post("/trash/purge")
async def trash_purge(
    payload: PhotoIdsRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    ids = [int(item) for item in payload.ids if str(item).isdigit()]
    if not ids:
        raise ApiError(codes.BAD_REQUEST, "请选择要彻底删除的照片")
    rows = list(
        db.scalars(
            select(Photo).where(
                Photo.id.in_(ids), _photo_scope(user), Photo.deleted_at.is_not(None)
            )
        )
    )
    purged: list[str] = []
    failed: list[dict] = []
    found = {photo.id for photo in rows}
    for photo in rows:
        _log_photo(
            db,
            photo,
            user,
            "PURGE",
            [
                {
                    "field": "photo",
                    "op": "purge",
                    "mediaType": photo.media_type,
                    "origin": photo.origin,
                }
            ],
            request,
        )
        await photo_service.purge_photo(db, photo)
        purged.append(str(photo.id))
    for photo_id in ids:
        if photo_id not in found:
            failed.append({"id": str(photo_id), "reason": "照片不存在或不在回收站"})
    db.commit()
    return ok({"purged": len(purged), "ids": purged, "failed": failed})


@router.post("/describe")
async def describe_photo(
    payload: PhotoDescribeRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    if not settings.ai_enabled:
        raise ApiError(codes.AI_DISABLED, "AI 能力未开启")
    photo = db.scalars(
        select(Photo).where(Photo.id == int(payload.id), Photo.user_id == user.id)
    ).first()
    if photo is None:
        raise not_found("照片不存在")
    if photo.media_type != "IMAGE":
        raise ApiError(codes.AI_DISABLED, "视频暂不支持自动描述")
    if photo.caption_source == "manual":
        return ok(PhotoOut.model_validate(photo))

    try:
        content, _ = await storage.read_bytes(
            photo, size="preview", client=credential_service.user_client(db, user.id)
        )
        note_hint = ""
        if photo.entry_id:
            entry = db.get(DailyEntry, photo.entry_id)
            note_hint = entry.note if entry else ""
        caption = await describe_image(content, note_hint)
    except (OllamaError, ImmichError, FileNotFoundError) as exc:
        photo.ai_state = "failed"
        photo.ai_attempts = int(photo.ai_attempts or 0) + 1
        db.commit()
        raise ApiError(codes.AI_UNAVAILABLE, str(exc)) from exc

    photo.caption = caption[:1000]
    photo.caption_source = "ai"
    photo.ai_state = "done"
    photo.ai_attempts = int(photo.ai_attempts or 0) + 1
    if settings.immich_write_description and photo.immich_asset_id and settings.immich_enabled:
        try:
            client = credential_service.user_client(db, user.id)
            if client is not None:
                await client.update_description(photo.immich_asset_id, photo.caption)
        except ImmichError:
            pass
    db.commit()
    return ok(PhotoOut.model_validate(photo))

import logging
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..config import settings
from ..db import get_db
from ..deps import UserContext, get_current_user
from ..models import ComUser, DailyEntry, Photo
from ..schemas.entry import PhotoOut
from ..schemas.photo import ImmichImportRequest, ImmichStatusOut
from ..services import ai_caption, credential_service
from ..services.immich import ImmichError
from ..services.timeutil import now_shanghai

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/immich",
    tags=["immich"],
    dependencies=[Depends(xss_guard), Depends(get_current_user)],
)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, time.min), datetime.combine(day, time.max)


async def _prepare(db: Session, user: UserContext):
    entity = db.get(ComUser, user.id)
    credential = None
    if entity is not None:
        credential = await credential_service.ensure_credential(db, entity)
    client = credential_service.user_client(db, user.id)
    return credential, client


@router.post("/status")
async def status(db: Session = Depends(get_db), user: UserContext = Depends(get_current_user)):
    credential, client = await _prepare(db, user)
    if not settings.immich_url:
        return ok(
            ImmichStatusOut(
                enabled=False,
                available=False,
                message="照片库未接入",
                provisionStatus="none",
            )
        )
    if credential is None:
        return ok(
            ImmichStatusOut(
                enabled=False,
                available=False,
                message="照片库尚未开通",
                provisionStatus="none",
            )
        )
    if client is None:
        return ok(
            ImmichStatusOut(
                enabled=True,
                available=False,
                bound=False,
                message=credential_service.status_payload(db, user.id)["message"],
                provisionStatus=credential.provision_status,
            )
        )
    try:
        about = await client.about()
        version = (about or {}).get("version") or ""
        return ok(
            ImmichStatusOut(
                enabled=True,
                available=True,
                bound=True,
                message=f"照片库已连接 {version}".strip(),
                provisionStatus=credential.provision_status,
            )
        )
    except ImmichError:
        return ok(
            ImmichStatusOut(
                enabled=True,
                available=False,
                bound=True,
                message="照片库暂时无法连接",
                provisionStatus=credential.provision_status,
            )
        )


@router.post("/credential/get")
def credential_get(db: Session = Depends(get_db), user: UserContext = Depends(get_current_user)):
    return ok(
        {
            "configured": bool(settings.immich_url and settings.immich_admin_api_key),
            **credential_service.status_payload(db, user.id),
        }
    )


@router.post("/credential/retry")
async def credential_retry(
    db: Session = Depends(get_db), user: UserContext = Depends(get_current_user)
):
    entity = db.get(ComUser, user.id)
    if entity is None:
        raise ApiError(codes.NOT_FOUND, "用户不存在")
    credential = credential_service.get_credential(db, user.id)
    if credential is not None:
        credential.provision_attempts = 0
        db.commit()
    credential = await credential_service.provision_user(db, entity)
    if credential is None or credential.status != "active":
        raise ApiError(codes.IMMICH_NOT_BOUND, "照片库开通失败，请稍后重试")
    return ok(credential_service.status_payload(db, user.id))


@router.post("/assets")
async def assets(
    payload: ImmichImportRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    credential, client = await _prepare(db, user)
    if credential is None or client is None:
        raise ApiError(codes.IMMICH_NOT_BOUND, "照片库未开通")
    after, before = _day_bounds(payload.date)
    try:
        items = await client.search_assets(after, before)
    except ImmichError as exc:
        raise ApiError(codes.IMMICH_UNAVAILABLE, "照片库暂时不可用，请稍后重试") from exc

    imported = {
        row
        for row in db.scalars(
            select(Photo.immich_asset_id).where(
                Photo.user_id == user.id, Photo.immich_asset_id.is_not(None)
            )
        ).all()
    }
    return ok(
        [
            {
                "id": item["id"],
                "type": item["type"],
                "mimeType": item["mime_type"],
                "takenAt": item["taken_at"].strftime("%Y-%m-%d %H:%M:%S")
                if item["taken_at"]
                else None,
                "description": item["description"],
                "originalFileName": item["original_file_name"],
                "imported": item["id"] in imported,
            }
            for item in items
            if item["id"]
        ]
    )


@router.get("/thumbnail/{asset_id}")
async def thumbnail(
    asset_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    _, client = await _prepare(db, user)
    if client is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "照片不存在"})
    try:
        content, mime = await client.thumbnail(asset_id, size="thumbnail")
    except ImmichError:
        return JSONResponse(status_code=404, content={"code": 404, "message": "照片不存在"})
    return Response(content=content, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})


@router.post("/import")
async def import_assets(
    payload: ImmichImportRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    credential, client = await _prepare(db, user)
    if credential is None or client is None:
        raise ApiError(codes.IMMICH_NOT_BOUND, "照片库未开通")

    after, before = _day_bounds(payload.date)
    try:
        if payload.asset_ids:
            items = []
            for asset_id in payload.asset_ids[:200]:
                try:
                    items.append(await client.get_asset(asset_id))
                except ImmichError:
                    logger.warning("Immich 资产不存在: %s", asset_id)
        else:
            items = await client.search_assets(after, before)
    except ImmichError as exc:
        raise ApiError(codes.IMMICH_UNAVAILABLE, "照片库暂时不可用，请稍后重试") from exc

    existing = {
        row
        for row in db.scalars(
            select(Photo.immich_asset_id).where(
                Photo.user_id == user.id, Photo.immich_asset_id.is_not(None)
            )
        ).all()
    }
    entry = db.scalars(
        select(DailyEntry).where(
            DailyEntry.user_id == user.id, DailyEntry.entry_date == payload.date
        )
    ).first()

    created: list[Photo] = []
    entity = db.get(ComUser, user.id)
    ai_pending = settings.ai_enabled and entity is not None and entity.ai_caption_enabled
    for item in items:
        if not item["id"] or item["id"] in existing:
            continue
        media_type = "VIDEO" if item["type"] == "VIDEO" else "IMAGE"
        caption = item["description"] or ""
        photo = Photo(
            user_id=user.id,
            entry_id=entry.id if entry else None,
            immich_asset_id=item["id"],
            storage_kind="immich",
            mime_type=item["mime_type"],
            media_type=media_type,
            origin="import",
            taken_at=item["taken_at"] or now_shanghai(),
            caption=caption[:1000],
            caption_source="immich" if caption else "none",
            ai_state="pending" if ai_pending and not caption else "disabled",
            insert_user=user.userid,
        )
        db.add(photo)
        created.append(photo)
        existing.add(item["id"])

    db.flush()
    if entry is not None and created:
        has_cover = db.scalars(
            select(Photo).where(Photo.entry_id == entry.id, Photo.is_cover.is_(True))
        ).first()
        if has_cover is None:
            created[0].is_cover = True
    db.commit()
    ai_caption.enqueue([photo.id for photo in created if photo.ai_state == "pending"])
    return ok({"imported": len(created), "photos": [PhotoOut.model_validate(p) for p in created]})

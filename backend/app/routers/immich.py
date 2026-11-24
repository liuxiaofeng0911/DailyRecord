import logging
from datetime import date, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..config import settings
from ..db import get_db
from ..deps import UserContext, get_current_user
from ..models import DailyEntry, Photo
from ..schemas.entry import PhotoOut
from ..schemas.photo import ImmichImportRequest, ImmichStatusOut
from ..services.immich import ImmichClient, ImmichError
from ..services.timeutil import now_shanghai

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/immich",
    tags=["immich"],
    dependencies=[Depends(xss_guard), Depends(get_current_user)],
)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, time.min), datetime.combine(day, time.max)


@router.post("/status")
async def status():
    if not settings.immich_enabled:
        return ok(ImmichStatusOut(enabled=False, available=False, message="Immich 未配置"))
    try:
        about = await ImmichClient().about()
        version = (about or {}).get("version") or ""
        return ok(
            ImmichStatusOut(enabled=True, available=True, message=f"Immich {version} 可用".strip())
        )
    except ImmichError as exc:
        return ok(ImmichStatusOut(enabled=True, available=False, message=str(exc)))


@router.post("/assets")
async def assets(
    payload: ImmichImportRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    after, before = _day_bounds(payload.date)
    try:
        items = await ImmichClient().search_assets(after, before)
    except ImmichError as exc:
        raise ApiError(codes.IMMICH_UNAVAILABLE, str(exc)) from exc

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


@router.post("/import")
async def import_assets(
    payload: ImmichImportRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    client = ImmichClient()
    if not client.configured:
        raise ApiError(codes.IMMICH_UNAVAILABLE, "Immich 未配置")

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
        raise ApiError(codes.IMMICH_UNAVAILABLE, str(exc)) from exc

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
            ai_state="disabled",
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
    return ok({"imported": len(created), "photos": [PhotoOut.model_validate(p) for p in created]})

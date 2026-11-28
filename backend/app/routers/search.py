from fastapi import APIRouter, Depends
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session, selectinload

from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..db import get_db
from ..deps import UserContext, get_current_user
from ..models import DailyEntry, Photo
from ..routers.entry import _serialize
from ..schemas.stats import SearchRequest

router = APIRouter(tags=["search"], dependencies=[Depends(xss_guard), Depends(get_current_user)])


@router.post("/search")
def search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    stmt = select(DailyEntry).where(DailyEntry.user_id == user.id)
    if payload.start:
        stmt = stmt.where(DailyEntry.entry_date >= payload.start)
    if payload.end:
        stmt = stmt.where(DailyEntry.entry_date <= payload.end)
    keyword = (payload.keyword or "").strip()
    if keyword:
        photo_ids = select(Photo.entry_id).where(
            Photo.user_id == user.id,
            Photo.entry_id.is_not(None),
            Photo.deleted_at.is_(None),
            or_(
                Photo.caption.ilike(f"%{keyword}%"),
                cast(Photo.ai_keywords, String).ilike(f"%{keyword}%"),
            ),
        )
        stmt = stmt.where(
            or_(DailyEntry.note.ilike(f"%{keyword}%"), DailyEntry.id.in_(photo_ids))
        )
    rows = db.scalars(
        stmt.options(selectinload(DailyEntry.tags), selectinload(DailyEntry.photos))
        .order_by(DailyEntry.entry_date.desc())
        .limit(payload.limit)
    ).unique().all()
    return ok({"list": [_serialize(row) for row in rows], "totalRow": len(rows)})

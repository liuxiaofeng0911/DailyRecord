import logging
from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..common import codes
from ..common.exceptions import ApiError, not_found
from ..common.page import MAX_PAGE_SIZE, page_payload
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..db import get_db
from ..deps import UserContext, get_current_user
from ..models import ChangeLog, DailyEntry, Photo, Tag
from ..schemas.entry import (
    EntryDeleteRequest,
    EntryGetRequest,
    EntryHistoryRequest,
    EntryListRequest,
    EntryOut,
    EntrySaveRequest,
    PhotoOut,
    TagOut,
)
from ..schemas.stats import CalendarRequest
from ..services import audit, stats_service
from ..services.entry_service import (
    active_photos,
    attach_photos,
    clear_cover,
    normalize_tags,
    resolve_tags,
)
from ..services.timeutil import now_shanghai, today_shanghai

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/entry",
    tags=["entry"],
    dependencies=[Depends(xss_guard), Depends(get_current_user)],
)


def _load_entry(db: Session, user_id: int, entry_date: date) -> DailyEntry | None:
    return db.scalars(
        select(DailyEntry)
        .where(DailyEntry.user_id == user_id, DailyEntry.entry_date == entry_date)
        .options(selectinload(DailyEntry.tags), selectinload(DailyEntry.photos))
    ).first()


def _load_by_id(db: Session, user_id: int, entry_id: int) -> DailyEntry | None:
    return db.scalars(
        select(DailyEntry)
        .where(DailyEntry.id == entry_id, DailyEntry.user_id == user_id)
        .options(selectinload(DailyEntry.tags), selectinload(DailyEntry.photos))
    ).first()


def _serialize(entry: DailyEntry, changed_fields: list[str] | None = None) -> EntryOut:
    return EntryOut(
        id=entry.id,
        entry_date=entry.entry_date,
        note=entry.note or "",
        mood=entry.mood,
        tags=[TagOut(id=tag.id, name=tag.name, kind=tag.kind) for tag in entry.tags],
        photos=[
            PhotoOut.model_validate(photo)
            for photo in sorted(
                active_photos(list(entry.photos)), key=lambda item: item.taken_at or now_shanghai()
            )
        ],
        version=entry.version or 0,
        update_time=entry.update_time,
        changed_fields=changed_fields or [],
    )


def _parse_page(payload: EntryListRequest) -> tuple[int, int]:
    page_data = payload.page or {}
    raw_number = page_data.get("pageNumber") or payload.page_number or 1
    raw_size = page_data.get("pageSize") or payload.page_size or 20
    try:
        number = max(int(raw_number), 1)
        size = min(max(int(raw_size), 1), MAX_PAGE_SIZE)
    except (TypeError, ValueError):
        raise ApiError(codes.BAD_REQUEST, "分页参数不正确") from None
    return number, size


def _apply_wheres(stmt, wheres: list[dict], user_id: int):
    tag_names: list[str] = []
    media_type: str | None = None
    for item in wheres or []:
        column = str(item.get("column") or "")
        condition = str(item.get("condition") or "eq")
        value = item.get("v1")
        if value is None or value == "":
            continue
        if column in ("entry_date", "entryDate"):
            try:
                parsed = date.fromisoformat(str(value)[:10])
            except ValueError:
                raise ApiError(codes.BAD_REQUEST, "日期格式不正确") from None
            if condition in ("ge", "gte", ">="):
                stmt = stmt.where(DailyEntry.entry_date >= parsed)
            elif condition in ("le", "lte", "<="):
                stmt = stmt.where(DailyEntry.entry_date <= parsed)
            elif condition in ("gt", ">"):
                stmt = stmt.where(DailyEntry.entry_date > parsed)
            elif condition in ("lt", "<"):
                stmt = stmt.where(DailyEntry.entry_date < parsed)
            else:
                stmt = stmt.where(DailyEntry.entry_date == parsed)
        elif column == "mood":
            stmt = stmt.where(DailyEntry.mood == str(value))
        elif column == "note":
            stmt = stmt.where(DailyEntry.note.ilike(f"%{value}%"))
        elif column in ("tag", "tags"):
            tag_names.append(str(value))
        elif column in ("media_type", "mediaType"):
            media_type = str(value)
        # 其他字段忽略，避免任意列注入

    for name in tag_names:
        stmt = stmt.where(
            DailyEntry.id.in_(
                select(DailyEntry.id)
                .join(DailyEntry.tags)
                .where(Tag.user_id == user_id, Tag.name == name)
            )
        )
    if media_type:
        stmt = stmt.where(
            DailyEntry.id.in_(
                select(Photo.entry_id).where(
                    Photo.user_id == user_id,
                    Photo.media_type == media_type,
                    Photo.entry_id.is_not(None),
                )
            )
        )
    return stmt


@router.post("/list")
def list_entries(
    payload: EntryListRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    page_number, page_size = _parse_page(payload)
    base = select(DailyEntry).where(DailyEntry.user_id == user.id)
    base = _apply_wheres(base, payload.wheres, user.id)

    total = db.scalar(
        select(func.count()).select_from(base.order_by(None).subquery())
    ) or 0
    rows = db.scalars(
        base.options(selectinload(DailyEntry.tags), selectinload(DailyEntry.photos))
        .order_by(DailyEntry.entry_date.desc())
        .offset((page_number - 1) * page_size)
        .limit(page_size)
    ).unique().all()
    return ok(page_payload([_serialize(row) for row in rows], total, page_number, page_size))


@router.post("/get")
def get_entry(
    payload: EntryGetRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    entry = _load_entry(db, user.id, payload.date)
    return ok(_serialize(entry) if entry else None)


@router.post("/save")
def save_entry(
    payload: EntrySaveRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    entry = _load_entry(db, user.id, payload.entry_date)
    created = entry is None
    before = None
    if created:
        entry = DailyEntry(
            user_id=user.id,
            entry_date=payload.entry_date,
            note="",
            insert_user=user.userid,
            version=0,
        )
        db.add(entry)
        db.flush()
    else:
        if payload.version is not None and int(payload.version) != int(entry.version or 0):
            raise ApiError(codes.VERSION_CONFLICT, "记录已被修改，请刷新后重试")
        before = audit.entry_snapshot(entry, list(entry.photos))

    if payload.note is not None:
        entry.note = payload.note.strip()
    if payload.mood is not None:
        entry.mood = payload.mood.strip()[:32] or None
    if payload.tags is not None:
        entry.tags = resolve_tags(db, user.id, normalize_tags(payload.tags))

    if payload.photo_ids is not None:
        attach_photos(
            db,
            entry,
            user.id,
            [int(pid) for pid in payload.photo_ids],
            int(payload.cover_photo_id) if payload.cover_photo_id else None,
        )
    elif payload.cover_photo_id:
        cover = db.scalars(
            select(Photo).where(
                Photo.id == int(payload.cover_photo_id),
                Photo.user_id == user.id,
                Photo.entry_id == entry.id,
            )
        ).first()
        if cover is not None:
            clear_cover(db, entry.id)
            cover.is_cover = True

    entry.version = int(entry.version or 0) + 1
    entry.update_user = user.userid
    entry.update_time = now_shanghai()
    db.flush()

    after = audit.snapshot_from_db(db, entry)
    changes, changed_fields = audit.diff_entry(before, after, created)
    if created or changes:
        audit.add_log(
            db,
            user=user,
            action="CREATE" if created else "UPDATE",
            entity_type="ENTRY",
            changes=changes,
            entry=entry,
            request=request,
        )
    db.commit()
    return ok(_serialize(_load_by_id(db, user.id, entry.id), changed_fields))


@router.post("/calendar")
def calendar(
    payload: CalendarRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    if payload.start and payload.end:
        start, end = payload.start, payload.end
    else:
        year = payload.year or today_shanghai().year
        if year < 1970 or year > 2200:
            raise ApiError(codes.BAD_REQUEST, "年份超出范围")
        start, end = date(year, 1, 1), date(year, 12, 31)
    if start > end:
        raise ApiError(codes.BAD_REQUEST, "开始日期不能晚于结束日期")
    return ok(stats_service.calendar(db, user.id, start, end))


@router.post("/delete")
def delete_entry(
    payload: EntryDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    entry = _load_entry(db, user.id, payload.entry_date)
    if entry is None:
        raise not_found("记录不存在")
    photos = active_photos(list(entry.photos))
    summary = [
        {
            "field": "entry",
            "op": "delete",
            "noteLength": len(entry.note or ""),
            "mood": entry.mood,
            "tags": [tag.name for tag in entry.tags],
            "photoCount": len(photos),
        }
    ]
    audit.add_log(
        db,
        user=user,
        action="DELETE",
        entity_type="ENTRY",
        changes=summary,
        entry=entry,
        request=request,
    )
    for photo in photos:
        photo.entry_id = None
        photo.is_cover = False
    db.delete(entry)
    db.commit()
    return ok(None)


@router.post("/history")
def entry_history(
    payload: EntryHistoryRequest,
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

    base = select(ChangeLog).where(
        ChangeLog.user_id == user.id, ChangeLog.entry_date == payload.entry_date
    )
    total = db.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0
    rows = db.scalars(
        base.order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
        .offset((page_number - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [audit.serialize_log(row) for row in rows]
    return ok(page_payload(items, total, page_number, page_size))

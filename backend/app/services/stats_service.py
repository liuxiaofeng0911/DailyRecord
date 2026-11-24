"""日历聚合、连续天数与年度统计。"""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import DailyEntry, Tag, entry_tag
from .entry_service import active_photos
from .timeutil import today_shanghai


def compute_streaks(days: set[date]) -> tuple[int, int]:
    """返回 (当前连续天数, 历史最长连续天数)。"""
    if not days:
        return 0, 0
    ordered = sorted(days)
    longest = 1
    run = 1
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if (current - previous).days == 1:
            run += 1
        else:
            run = 1
        longest = max(longest, run)

    today = today_shanghai()
    cursor = today if today in days else today - timedelta(days=1)
    current_streak = 0
    while cursor in days:
        current_streak += 1
        cursor -= timedelta(days=1)
    return current_streak, longest


def _entries_in_range(db: Session, user_id: int, start: date, end: date) -> list[DailyEntry]:
    return list(
        db.scalars(
            select(DailyEntry)
            .where(
                DailyEntry.user_id == user_id,
                DailyEntry.entry_date >= start,
                DailyEntry.entry_date <= end,
            )
            .options(selectinload(DailyEntry.tags), selectinload(DailyEntry.photos))
            .order_by(DailyEntry.entry_date.asc())
        ).unique()
    )


def _day_row(entry: DailyEntry) -> dict:
    photos = active_photos(list(entry.photos))
    cover = next((photo.id for photo in photos if photo.is_cover), None)
    return {
        "date": entry.entry_date.isoformat(),
        "hasEntry": True,
        "photos": len(photos),
        "mood": entry.mood,
        "tags": [tag.name for tag in entry.tags],
        "coverPhotoId": str(cover) if cover else None,
    }


def calendar(db: Session, user_id: int, start: date, end: date) -> dict:
    entries = _entries_in_range(db, user_id, start, end)
    days = [_day_row(entry) for entry in entries]

    month_days: dict[int, int] = defaultdict(int)
    month_photos: dict[int, int] = defaultdict(int)
    for entry in entries:
        month_days[entry.entry_date.month] += 1
        month_photos[entry.entry_date.month] += len(active_photos(list(entry.photos)))

    months = [
        {"month": month, "days": month_days.get(month, 0), "photos": month_photos.get(month, 0)}
        for month in range(1, 13)
    ]

    all_days = {
        row
        for row in db.scalars(
            select(DailyEntry.entry_date).where(DailyEntry.user_id == user_id)
        ).all()
    }
    current_streak, longest_streak = compute_streaks(all_days)

    return {
        "days": days,
        "months": months,
        "totals": {
            "days": len(days),
            "photos": sum(len(active_photos(list(entry.photos))) for entry in entries),
            "currentStreak": current_streak,
            "longestStreak": longest_streak,
        },
    }


def top_tags(db: Session, user_id: int, start: date, end: date, limit: int = 12) -> list[dict]:
    rows = db.execute(
        select(Tag.name, func.count(entry_tag.c.entry_id).label("count"))
        .join(entry_tag, entry_tag.c.tag_id == Tag.id)
        .join(DailyEntry, DailyEntry.id == entry_tag.c.entry_id)
        .where(
            DailyEntry.user_id == user_id,
            Tag.user_id == user_id,
            DailyEntry.entry_date >= start,
            DailyEntry.entry_date <= end,
        )
        .group_by(Tag.name)
        .order_by(func.count(entry_tag.c.entry_id).desc(), Tag.name.asc())
        .limit(limit)
    ).all()
    return [{"name": name, "count": int(count)} for name, count in rows]


def overview(db: Session, user_id: int, start: date, end: date) -> dict:
    data = calendar(db, user_id, start, end)
    return {
        "totals": data["totals"],
        "months": data["months"],
        "days": data["days"],
        "topTags": top_tags(db, user_id, start, end),
    }

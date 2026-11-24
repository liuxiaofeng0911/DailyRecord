import json
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..common import codes
from ..common.exceptions import ApiError
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..db import get_db
from ..deps import UserContext, get_current_user
from ..models import DailyEntry
from ..schemas.stats import ExportRequest
from ..services.timeutil import now_shanghai, today_shanghai

router = APIRouter(
    prefix="/export",
    tags=["export"],
    dependencies=[Depends(xss_guard), Depends(get_current_user)],
)


def _range(payload: ExportRequest) -> tuple[date, date]:
    start = payload.start or date(1970, 1, 1)
    end = payload.end or today_shanghai()
    if start > end:
        raise ApiError(codes.BAD_REQUEST, "开始日期不能晚于结束日期")
    return start, end


@router.post("")
def export_entries(
    payload: ExportRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    start, end = _range(payload)
    entries = list(
        db.scalars(
            select(DailyEntry)
            .where(
                DailyEntry.user_id == user.id,
                DailyEntry.entry_date >= start,
                DailyEntry.entry_date <= end,
            )
            .options(selectinload(DailyEntry.tags), selectinload(DailyEntry.photos))
            .order_by(DailyEntry.entry_date.asc())
        ).unique()
    )

    fmt = (payload.format or "json").lower()
    if fmt == "json":
        data = {
            "exportedAt": now_shanghai().strftime("%Y-%m-%d %H:%M:%S"),
            "owner": user.userid,
            "entries": [
                {
                    "entryDate": entry.entry_date.isoformat(),
                    "note": entry.note,
                    "mood": entry.mood,
                    "tags": [tag.name for tag in entry.tags],
                    "photos": [
                        {
                            "id": str(photo.id),
                            "mediaType": photo.media_type,
                            "takenAt": photo.taken_at.strftime("%Y-%m-%d %H:%M:%S")
                            if photo.taken_at
                            else None,
                            "caption": photo.caption,
                            "immichAssetId": photo.immich_asset_id,
                        }
                        for photo in entry.photos
                    ],
                }
                for entry in entries
            ],
        }
        content = json.dumps(data, ensure_ascii=False, indent=2)
        mime = "application/json"
        filename = f"dailyrecord-{start.isoformat()}-{end.isoformat()}.json"
    elif fmt in ("markdown", "md"):
        lines = ["# 每日照片记录", ""]
        for entry in entries:
            lines.append(f"## {entry.entry_date.isoformat()}")
            lines.append("")
            if entry.mood:
                lines.append(f"- 情绪：{entry.mood}")
            if entry.tags:
                lines.append(f"- 标签：{'、'.join(tag.name for tag in entry.tags)}")
            if entry.mood or entry.tags:
                lines.append("")
            if entry.note:
                lines.append(entry.note)
                lines.append("")
            for photo in entry.photos:
                caption = photo.caption or photo.media_type
                lines.append(f"- {caption}（{photo.media_type}）")
            lines.append("")
        content = "\n".join(lines)
        mime = "text/markdown"
        filename = f"dailyrecord-{start.isoformat()}-{end.isoformat()}.md"
    else:
        raise ApiError(codes.BAD_REQUEST, "仅支持 json 或 markdown 格式")

    return ok(
        {
            "format": fmt,
            "filename": filename,
            "mimeType": mime,
            "count": len(entries),
            "content": content,
        }
    )

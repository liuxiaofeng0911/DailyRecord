"""标签维护：图标覆盖与改名。"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError, not_found
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..db import get_db
from ..deps import UserContext, get_current_user
from ..models import DailyEntry, Tag, entry_tag
from ..schemas.entry import TagOut, TagSaveRequest, TagSuggestOut
from ..services import audit
from ..services.timeutil import now_shanghai

TOP_TAG_LIMIT = 5

router = APIRouter(
    prefix="/tag",
    tags=["tag"],
    dependencies=[Depends(xss_guard), Depends(get_current_user)],
)


@router.post("/list")
def list_tags(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    rows = db.scalars(
        select(Tag).where(Tag.user_id == user.id).order_by(Tag.name.asc())
    ).all()
    return ok([TagOut(id=row.id, name=row.name, kind=row.kind, icon=row.icon) for row in rows])


@router.post("/suggest")
def suggest_tags(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """按当前用户的标签使用频次返回常用标签，供录入时一键选择。"""
    uses = func.count(entry_tag.c.entry_id)
    last_used = func.max(DailyEntry.entry_date)
    rows = db.execute(
        select(Tag.id, Tag.name, uses.label("uses"))
        .join(entry_tag, entry_tag.c.tag_id == Tag.id)
        .join(DailyEntry, DailyEntry.id == entry_tag.c.entry_id)
        .where(Tag.user_id == user.id, DailyEntry.user_id == user.id)
        .group_by(Tag.id, Tag.name)
        .order_by(uses.desc(), last_used.desc(), Tag.name.asc())
        .limit(TOP_TAG_LIMIT)
    ).all()
    return ok(
        [TagSuggestOut(id=row.id, name=row.name, uses=int(row.uses or 0)) for row in rows]
    )


@router.post("/save")
def save_tag(
    payload: TagSaveRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    tag = db.scalars(
        select(Tag).where(Tag.id == int(payload.id), Tag.user_id == user.id)
    ).first()
    if tag is None:
        raise not_found("标签不存在")

    changes: list[dict] = []
    if payload.name is not None:
        name = payload.name.strip().lstrip("#").strip()[:64]
        if not name:
            raise ApiError(codes.BAD_REQUEST, "标签名不能为空")
        duplicate = db.scalars(
            select(Tag).where(Tag.user_id == user.id, Tag.name == name, Tag.id != tag.id)
        ).first()
        if duplicate is not None:
            raise ApiError(codes.BAD_REQUEST, "标签名已存在")
        if name != tag.name:
            changes.append(
                {"field": "name", "op": "replace", "before": tag.name, "after": name}
            )
            tag.name = name
    if payload.icon is not None:
        icon = payload.icon.strip()[:32] or None
        if icon != tag.icon:
            changes.append(
                {"field": "icon", "op": "replace", "before": tag.icon, "after": icon}
            )
            tag.icon = icon

    if changes:
        tag.update_user = user.userid
        tag.update_time = now_shanghai()
        tag.version = int(tag.version or 0) + 1
        audit.add_log(
            db,
            user=user,
            action="UPDATE",
            entity_type="TAG",
            entity_id=tag.id,
            changes=changes,
            request=request,
        )
    db.commit()
    return ok(TagOut(id=tag.id, name=tag.name, kind=tag.kind, icon=tag.icon))

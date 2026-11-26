"""组织内记录共享：解析组织成员范围并按条件读取成员每日记录。"""

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import ComUser, DailyEntry, Org, UserOrg
from ..schemas.entry import PhotoOut, TagOut
from ..schemas.share import ShareMemberOut, SharedEntryOut
from .auth_service import role_code_of
from .entry_service import active_photos
from .timeutil import now_shanghai


def allowed_org_ids(db: Session, org_id: int | None, include_children: bool = True) -> set[int] | None:
    """返回共享范围内的组织 ID；org_id 为空表示全系统。"""
    if not org_id:
        return None
    if not include_children:
        return {org_id}
    rows = db.scalars(select(Org).order_by(Org.id.asc())).all()
    children: dict[int, list[int]] = {}
    for row in rows:
        children.setdefault(row.pid or 0, []).append(row.id)
    result: set[int] = set()
    stack = [org_id]
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(children.get(current, []))
    return result


def org_members(
    db: Session, org_id: int | None, include_children: bool = True
) -> list[ComUser]:
    org_ids = allowed_org_ids(db, org_id, include_children)
    stmt = select(ComUser).where(ComUser.user_active == "Y")
    if org_ids is not None:
        company_ids = {str(item) for item in org_ids}
        linked_users = select(UserOrg.user_id).where(UserOrg.company_id.in_(company_ids))
        stmt = stmt.where(
            or_(ComUser.org_id.in_(org_ids), ComUser.id.in_(linked_users))
        )
    return list(db.scalars(stmt.order_by(ComUser.id.asc())).all())


def serialize_members(db: Session, members: list[ComUser]) -> list[ShareMemberOut]:
    return [
        ShareMemberOut(
            id=member.id,
            userid=member.userid,
            username=member.username or member.userid,
            role_code=role_code_of(db, member.id),
        )
        for member in members
    ]


def shared_entries(
    db: Session,
    members: list[ComUser],
    *,
    user_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    keyword: str | None = None,
    page_number: int = 1,
    page_size: int = 20,
) -> dict:
    by_id = {member.id: member for member in members}
    if user_id is not None:
        if user_id not in by_id:
            return {"list": [], "totalRow": 0, "pageNumber": page_number, "pageSize": page_size}
        by_id = {user_id: by_id[user_id]}
    if not by_id:
        return {"list": [], "totalRow": 0, "pageNumber": page_number, "pageSize": page_size}

    stmt = select(DailyEntry).where(DailyEntry.user_id.in_(list(by_id)))
    if start is not None:
        stmt = stmt.where(DailyEntry.entry_date >= start)
    if end is not None:
        stmt = stmt.where(DailyEntry.entry_date <= end)
    if keyword:
        stmt = stmt.where(DailyEntry.note.ilike(f"%{keyword.strip()}%"))

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = (
        db.scalars(
            stmt.options(selectinload(DailyEntry.tags), selectinload(DailyEntry.photos))
            .order_by(DailyEntry.entry_date.desc(), DailyEntry.user_id.asc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .all()
    )

    items = []
    for entry in rows:
        author = by_id.get(entry.user_id)
        items.append(
            SharedEntryOut(
                id=entry.id,
                entry_date=entry.entry_date,
                note=entry.note or "",
                mood=entry.mood,
                tags=[
                    TagOut(id=tag.id, name=tag.name, kind=tag.kind, icon=tag.icon)
                    for tag in entry.tags
                ],
                photos=[
                    PhotoOut.model_validate(photo)
                    for photo in sorted(
                        active_photos(list(entry.photos)),
                        key=lambda item: item.taken_at or now_shanghai(),
                    )
                ],
                user_id=entry.user_id,
                userid=author.userid if author else "",
                username=(author.username or author.userid) if author else "",
            )
        )
    return {
        "list": items,
        "totalRow": total,
        "pageNumber": page_number,
        "pageSize": page_size,
    }

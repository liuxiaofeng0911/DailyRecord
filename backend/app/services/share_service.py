"""组织内记录共享：组织成员范围、双向可见配置与共享记录读取。"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..common import codes
from ..common.exceptions import ApiError
from ..models import (
    ComUser,
    DailyEntry,
    Org,
    OrgShareConfig,
    OrgShareRule,
    Role,
    UserOrg,
    UserRole,
)
from ..schemas.entry import PhotoOut, TagOut
from ..schemas.share import MyShareOrgOut, ShareConfigOut, ShareMemberOut, SharedEntryOut
from .auth_service import role_code_of
from .entry_service import active_photos
from .timeutil import now_shanghai

RULE_ALLOW = "ALLOW"
RULE_WATCH = "WATCH"


def _empty_page(page_number: int, page_size: int) -> dict:
    return {"list": [], "totalRow": 0, "pageNumber": page_number, "pageSize": page_size}


def allowed_org_ids(
    db: Session, org_id: int | None, include_children: bool = True
) -> set[int] | None:
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


def _owner_user_ids():
    return select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(
        Role.code == "OWNER"
    )


def org_members(
    db: Session,
    org_id: int | None,
    include_children: bool = True,
    include_owner: bool = False,
) -> list[ComUser]:
    """组织成员以 t_um_user_org 为准；所有者不属于任何组织。"""
    org_ids = allowed_org_ids(db, org_id, include_children)
    stmt = select(ComUser).where(ComUser.user_active == "Y")
    if org_ids is not None:
        company_ids = {str(item) for item in org_ids}
        linked_users = select(UserOrg.user_id).where(UserOrg.company_id.in_(company_ids))
        stmt = stmt.where(ComUser.id.in_(linked_users))
    if not include_owner:
        stmt = stmt.where(ComUser.user_type != "2").where(
            ComUser.id.not_in(_owner_user_ids())
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


def org_share_enabled(db: Session, org_id: int) -> bool:
    row = db.scalars(select(OrgShareConfig).where(OrgShareConfig.org_id == org_id)).first()
    return row is None or row.enabled == "Y"


def org_share_enabled_map(db: Session, org_ids: set[int] | None = None) -> dict[int, bool]:
    stmt = select(OrgShareConfig)
    if org_ids is not None:
        stmt = stmt.where(OrgShareConfig.org_id.in_(org_ids))
    configured = {row.org_id: row.enabled == "Y" for row in db.scalars(stmt).all()}
    if org_ids is None:
        org_ids = set(db.scalars(select(Org.id)).all())
    return {org_id: configured.get(org_id, True) for org_id in org_ids}


def set_org_share_enabled(
    db: Session, org_id: int, enabled: bool, operator: str | None = None
) -> None:
    row = db.scalars(select(OrgShareConfig).where(OrgShareConfig.org_id == org_id)).first()
    value = "Y" if enabled else "N"
    if row is None:
        db.add(OrgShareConfig(org_id=org_id, enabled=value, insert_user=operator))
        return
    row.enabled = value
    row.update_user = operator
    row.update_time = now_shanghai()


def user_org_ids(db: Session, user_id: int) -> set[int]:
    result: set[int] = set()
    for value in db.scalars(select(UserOrg.company_id).where(UserOrg.user_id == user_id)).all():
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result


def user_orgs(db: Session, user_id: int) -> list[Org]:
    ids = user_org_ids(db, user_id)
    if not ids:
        return []
    return list(
        db.scalars(
            select(Org)
            .where(Org.id.in_(ids), Org.status == "Y")
            .order_by(Org.pid.asc(), Org.id.asc())
        ).all()
    )


def my_orgs(db: Session, user_id: int, is_owner: bool) -> list[MyShareOrgOut]:
    if is_owner:
        member_ids: set[int] = set()
        orgs = list(
            db.scalars(
                select(Org).where(Org.status == "Y").order_by(Org.pid.asc(), Org.id.asc())
            ).all()
        )
    else:
        member_ids = user_org_ids(db, user_id)
        orgs = user_orgs(db, user_id)
    enabled = org_share_enabled_map(db, None)
    return [
        MyShareOrgOut(
            id=org.id,
            org_name=org.org_name,
            org_code=org.org_code,
            share_enabled=enabled.get(org.id, True),
            is_member=org.id in member_ids,
        )
        for org in orgs
    ]


def share_config(db: Session, org_id: int, user_id: int, is_owner: bool) -> ShareConfigOut:
    org = db.get(Org, org_id)
    if org is None:
        raise ApiError(codes.NOT_FOUND, "组织不存在")
    member = org_id in user_org_ids(db, user_id)
    members = org_members(db, org_id, include_children=False)
    rows = db.scalars(
        select(OrgShareRule).where(
            OrgShareRule.org_id == org_id, OrgShareRule.user_id == user_id
        )
    ).all()
    allow_ids = [row.target_id for row in rows if row.kind == RULE_ALLOW]
    watch_ids = [row.target_id for row in rows if row.kind == RULE_WATCH]
    return ShareConfigOut(
        id=org.id,
        org_name=org.org_name,
        org_code=org.org_code,
        share_enabled=org_share_enabled(db, org_id),
        is_member=member,
        is_owner=is_owner,
        members=serialize_members(db, members),
        allow_ids=allow_ids,
        watch_ids=watch_ids,
    )


def save_share_config(
    db: Session,
    org_id: int,
    user_id: int,
    allow_ids: list[str],
    watch_ids: list[str],
    operator: str | None = None,
) -> None:
    """保存双向可见配置：允许查看我的人 + 我想查看的人。"""
    if org_id not in user_org_ids(db, user_id):
        raise ApiError(codes.FORBIDDEN, "你不在该组织中，无法配置共享")
    if db.get(Org, org_id) is None:
        raise ApiError(codes.NOT_FOUND, "组织不存在")
    member_ids = {
        member.id for member in org_members(db, org_id, include_children=False)
    } - {user_id}
    allow = {int(item) for item in allow_ids}
    watch = {int(item) for item in watch_ids}
    if (allow | watch) - member_ids:
        raise ApiError(codes.BAD_REQUEST, "存在不属于该组织的人员")

    wanted = {(RULE_ALLOW, target) for target in allow} | {
        (RULE_WATCH, target) for target in watch
    }
    rows = db.scalars(
        select(OrgShareRule).where(
            OrgShareRule.org_id == org_id, OrgShareRule.user_id == user_id
        )
    ).all()
    existing = {(row.kind, row.target_id): row for row in rows}
    for key, row in existing.items():
        if key not in wanted:
            db.delete(row)
    for kind, target in wanted - set(existing):
        db.add(
            OrgShareRule(
                org_id=org_id,
                user_id=user_id,
                target_id=target,
                kind=kind,
                insert_user=operator,
            )
        )


def visible_sharer_ids(db: Session, viewer_id: int, org_id: int | None = None) -> set[int]:
    """返回当前用户可查看记录的人员：对方允许我看 + 我也关注对方，且组织共享开关开启。"""
    if org_id is not None:
        if org_id not in user_org_ids(db, viewer_id):
            return set()
        org_ids = {org_id}
    else:
        org_ids = user_org_ids(db, viewer_id)
    if not org_ids:
        return set()
    enabled = org_share_enabled_map(db, org_ids)
    result: set[int] = set()
    for current in org_ids:
        if not enabled.get(current, True):
            continue
        allowed = set(
            db.scalars(
                select(OrgShareRule.user_id).where(
                    OrgShareRule.org_id == current,
                    OrgShareRule.target_id == viewer_id,
                    OrgShareRule.kind == RULE_ALLOW,
                )
            ).all()
        )
        watched = set(
            db.scalars(
                select(OrgShareRule.target_id).where(
                    OrgShareRule.org_id == current,
                    OrgShareRule.user_id == viewer_id,
                    OrgShareRule.kind == RULE_WATCH,
                )
            ).all()
        )
        candidates = (allowed & watched) - {viewer_id}
        if not candidates:
            continue
        member_ids = {
            member.id for member in org_members(db, current, include_children=False)
        }
        result |= candidates & member_ids
    return result


def can_view_shared_entries(db: Session, viewer_id: int, sharer_id: int) -> bool:
    if viewer_id == sharer_id:
        return True
    return sharer_id in visible_sharer_ids(db, viewer_id)


def _entries_page(
    db: Session,
    members: list[ComUser],
    *,
    start: date | None = None,
    end: date | None = None,
    keyword: str | None = None,
    page_number: int = 1,
    page_size: int = 20,
) -> dict:
    by_id = {member.id: member for member in members}
    if not by_id:
        return _empty_page(page_number, page_size)

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
    """所有者视角：按组织范围查看全部成员记录。"""
    if user_id is not None:
        members = [member for member in members if member.id == user_id]
    return _entries_page(
        db,
        members,
        start=start,
        end=end,
        keyword=keyword,
        page_number=page_number,
        page_size=page_size,
    )


def my_shared_entries(
    db: Session,
    viewer_id: int,
    *,
    is_owner: bool = False,
    org_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    keyword: str | None = None,
    page_number: int = 1,
    page_size: int = 20,
) -> dict:
    """成员视角：只返回双向配置命中且组织共享开启的人员记录；所有者可看全部。"""
    if is_owner:
        members = org_members(db, org_id, include_children=True)
    else:
        sharer_ids = visible_sharer_ids(db, viewer_id, org_id)
        if not sharer_ids:
            return _empty_page(page_number, page_size)
        members = list(
            db.scalars(
                select(ComUser).where(
                    ComUser.id.in_(sharer_ids), ComUser.user_active == "Y"
                )
            ).all()
        )
    return _entries_page(
        db,
        members,
        start=start,
        end=end,
        keyword=keyword,
        page_number=page_number,
        page_size=page_size,
    )

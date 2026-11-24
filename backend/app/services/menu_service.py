"""菜单树与角色菜单授权。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Resource, Role, RoleResource, UserRole


def _enabled_resources(db: Session) -> list[Resource]:
    return list(
        db.scalars(
            select(Resource)
            .where(Resource.enable == "Y")
            .order_by(Resource.sort.asc(), Resource.id.asc())
        ).all()
    )


def _assigned_ids(db: Session, user_id: int) -> set[int]:
    role_ids = [
        row
        for row in db.scalars(select(UserRole.role_id).where(UserRole.user_id == user_id)).all()
    ]
    if not role_ids:
        return set()
    return {
        row
        for row in db.scalars(
            select(RoleResource.resource_id).where(RoleResource.role_id.in_(role_ids))
        ).all()
    }


def _with_ancestors(resources: list[Resource], allowed: set[int]) -> set[int]:
    by_id = {row.id: row for row in resources}
    result = set(allowed)
    for resource_id in list(allowed):
        current = by_id.get(resource_id)
        while current is not None and current.pid:
            parent = by_id.get(current.pid)
            if parent is None or parent.id in result:
                break
            result.add(parent.id)
            current = parent
    return result


def build_tree(resources: list[Resource]) -> list[dict]:
    by_id = {row.id: row for row in resources}
    children: dict[int, list[Resource]] = {}
    roots: list[Resource] = []
    for row in resources:
        if row.pid and row.pid in by_id:
            children.setdefault(row.pid, []).append(row)
        else:
            roots.append(row)

    def node(row: Resource) -> dict:
        return {
            "id": str(row.id),
            "name": row.name,
            "path": row.web_url or "",
            "icon": row.icon_name or "",
            "pid": str(row.pid or 0),
            "sort": row.sort,
            "enable": row.enable,
            "children": [node(item) for item in children.get(row.id, [])],
        }

    def walk(rows: list[Resource]) -> list[dict]:
        result = []
        for row in rows:
            item = node(row)
            # 空分组不展示
            if not item["path"] and not item["children"]:
                continue
            result.append(item)
        return result

    return walk(roots)


def full_tree(db: Session) -> list[dict]:
    rows = list(
        db.scalars(select(Resource).order_by(Resource.sort.asc(), Resource.id.asc())).all()
    )
    return build_tree(rows)


def menu_tree_for_user(db: Session, user_id: int, is_owner: bool) -> list[dict]:
    rows = _enabled_resources(db)
    if not is_owner:
        allowed = _assigned_ids(db, user_id)
        allowed = _with_ancestors(rows, allowed)
        rows = [row for row in rows if row.id in allowed]
    return build_tree(rows)


def role_menu_ids(db: Session, role_id: int) -> list[str]:
    rows = db.scalars(
        select(RoleResource.resource_id).where(RoleResource.role_id == role_id)
    ).all()
    return [str(row) for row in rows]


def save_role_menus(db: Session, role_id: int, resource_ids: list[int]) -> None:
    role = db.get(Role, role_id)
    if role is None:
        return
    valid = {
        row
        for row in db.scalars(
            select(Resource.id).where(Resource.id.in_(resource_ids))
        ).all()
    }
    for row in db.scalars(
        select(RoleResource).where(RoleResource.role_id == role_id)
    ).all():
        db.delete(row)
    db.flush()
    for resource_id in valid:
        db.add(RoleResource(role_id=role_id, resource_id=resource_id))

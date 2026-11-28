import re

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError, bad_request, forbidden, not_found
from ..common.page import MAX_PAGE_SIZE, ListRequest
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..db import get_db
from ..deps import UserContext, get_current_user, require_owner
from ..models import (
    ComUser,
    GeneralCode,
    Org,
    Resource,
    Role,
    RoleResource,
    Switch,
    UserOrg,
    UserRole,
    UserSession,
)
from ..schemas.system import (
    DictListRequest,
    DictOut,
    DictSaveRequest,
    InviteCreateRequest,
    InviteOut,
    MenuIdRequest,
    MenuSaveRequest,
    OrgIdRequest,
    OrgMembersSaveRequest,
    OrgOut,
    OrgSaveRequest,
    OrgShareSwitchRequest,
    ResetPasswordRequest,
    RoleMenusRequest,
    RoleMenusSaveRequest,
    RoleOut,
    RoleSaveRequest,
    SwitchSaveRequest,
    SystemUserOut,
    UserIdRequest,
    UserOrgOut,
    UserSaveRequest,
)
from ..security import rsa
from ..security.password import hash_password, validate_password_strength
from ..services import invite_service, menu_service, share_service, site_config
from ..services.auth_service import revoke_all_sessions, role_code_of
from ..services.bootstrap import has_users
from ..services.timeutil import now_shanghai

router = APIRouter(
    prefix="/system",
    tags=["system"],
    dependencies=[Depends(xss_guard), Depends(get_current_user), Depends(require_owner)],
)

USERID_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]{2,32}$")
USERID_RULE = "登录账号需为 2-32 位字母、数字、下划线或中文"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_orgs_map(db: Session, user_ids: list[int]) -> dict[int, list[UserOrgOut]]:
    """批量读取用户所属组织，支持同一用户存在多个组织。"""
    if not user_ids:
        return {}
    rows = db.scalars(select(UserOrg).where(UserOrg.user_id.in_(user_ids))).all()
    org_ids: set[int] = set()
    for row in rows:
        try:
            org_ids.add(int(row.company_id))
        except (TypeError, ValueError):
            continue
    orgs = {
        org.id: org for org in db.scalars(select(Org).where(Org.id.in_(org_ids))).all()
    } if org_ids else {}
    result: dict[int, list[UserOrgOut]] = {}
    for row in rows:
        try:
            org = orgs.get(int(row.company_id))
        except (TypeError, ValueError):
            org = None
        if org is not None:
            result.setdefault(row.user_id, []).append(
                UserOrgOut(id=org.id, name=org.org_name, code=org.org_code)
            )
    return result


@router.post("/user/list")
def user_list(
    payload: ListRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    stmt = select(ComUser)
    keyword: str | None = None
    for item in payload.wheres:
        value = item.v1
        if value is None or value == "":
            continue
        if item.column == "keyword":
            keyword = str(value).lower()
        elif item.column in ("userid", "username", "email"):
            column = getattr(ComUser, item.column)
            stmt = stmt.where(func.lower(column).like(f"%{str(value).lower()}%"))
        elif item.column == "user_active":
            stmt = stmt.where(ComUser.user_active == str(value))
    if keyword:
        stmt = stmt.where(
            or_(
                func.lower(ComUser.userid).like(f"%{keyword}%"),
                func.lower(ComUser.username).like(f"%{keyword}%"),
                func.lower(ComUser.email).like(f"%{keyword}%"),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    page_number = payload.page.page_number
    page_size = min(payload.page.page_size, MAX_PAGE_SIZE)
    rows = db.scalars(
        stmt.order_by(ComUser.insert_time.desc())
        .offset((page_number - 1) * page_size)
        .limit(page_size)
    ).all()
    orgs_map = _user_orgs_map(db, [row.id for row in rows])
    data = [
        SystemUserOut(
            id=row.id,
            userid=row.userid,
            username=row.username,
            email=row.email,
            user_active=row.user_active,
            user_type=row.user_type,
            role_code=role_code_of(db, row.id),
            login_time=row.login_time,
            insert_time=row.insert_time,
            locked_until=row.locked_until,
            orgs=orgs_map.get(row.id, []),
        )
        for row in rows
    ]
    return ok(
        {"list": data, "totalRow": total, "pageNumber": page_number, "pageSize": page_size}
    )


@router.post("/user/get")
def user_get(
    payload: UserIdRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    row = db.get(ComUser, int(payload.id))
    if row is None:
        raise not_found("用户不存在")
    return ok(
        SystemUserOut(
            id=row.id,
            userid=row.userid,
            username=row.username,
            email=row.email,
            user_active=row.user_active,
            user_type=row.user_type,
            role_code=role_code_of(db, row.id),
            login_time=row.login_time,
            insert_time=row.insert_time,
            locked_until=row.locked_until,
            orgs=_user_orgs_map(db, [row.id]).get(row.id, []),
        )
    )


def _validate_unique(db: Session, userid: str, email: str, exclude_id: int | None) -> None:
    stmt = select(ComUser).where(
        (func.lower(ComUser.userid) == userid.lower())
        | (func.lower(ComUser.email) == email.lower())
    )
    if exclude_id:
        stmt = stmt.where(ComUser.id != exclude_id)
    if db.scalars(stmt).first() is not None:
        raise ApiError(codes.DUPLICATE_REGISTER, "账号或邮箱已存在")


def _assign_role(db: Session, user_id: int, role_code: str, operator: str) -> None:
    role = db.scalars(select(Role).where(Role.code == role_code)).first()
    if role is None:
        raise bad_request("角色不存在")
    for row in db.scalars(select(UserRole).where(UserRole.user_id == user_id)).all():
        db.delete(row)
    db.flush()
    db.add(UserRole(user_id=user_id, role_id=role.id, insert_user=operator))


@router.post("/user/save")
def user_save(
    payload: UserSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    userid = payload.userid.strip()
    email = payload.email.strip().lower()
    if not USERID_RE.match(userid):
        raise bad_request(USERID_RULE)
    if not EMAIL_RE.match(email):
        raise bad_request("邮箱格式不正确")
    _validate_unique(db, userid, email, int(payload.id) if payload.id else None)

    if payload.id:
        entity = db.get(ComUser, int(payload.id))
        if entity is None:
            raise not_found("用户不存在")
        if entity.id == user.id and payload.user_active != "Y":
            raise forbidden("不能禁用当前登录账号")
        entity.userid = userid
        entity.username = payload.username.strip()
        entity.email = email
        if payload.user_active != entity.user_active:
            entity.user_active = payload.user_active
            if payload.user_active != "Y":
                revoke_all_sessions(db, entity)
        if payload.password:
            plain = rsa.decrypt(payload.password)
            try:
                validate_password_strength(plain)
            except ValueError as exc:
                raise bad_request(str(exc)) from exc
            entity.password = hash_password(plain)
            entity.password_algo = "argon2id"
            revoke_all_sessions(db, entity)
        _assign_role(db, entity.id, payload.role_code, user.userid)
        entity.update_user = user.userid
        entity.update_time = now_shanghai()
        entity.version = int(entity.version or 0) + 1
    else:
        if not payload.password:
            raise bad_request("新增用户必须设置密码")
        plain = rsa.decrypt(payload.password)
        try:
            validate_password_strength(plain)
        except ValueError as exc:
            raise bad_request(str(exc)) from exc
        entity = ComUser(
            userid=userid,
            username=payload.username.strip(),
            email=email,
            password=hash_password(plain),
            password_algo="argon2id",
            user_active=payload.user_active,
            user_type="1",
            org_id=1,
            insert_user=user.userid,
        )
        db.add(entity)
        db.flush()
        _assign_role(db, entity.id, payload.role_code, user.userid)
        db.add(UserOrg(user_id=entity.id, company_id="1", insert_user=user.userid))
    db.commit()
    return ok({"id": str(entity.id)})


@router.post("/user/resetPassword")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    entity = db.get(ComUser, int(payload.id))
    if entity is None:
        raise not_found("用户不存在")
    plain = rsa.decrypt(payload.password)
    try:
        validate_password_strength(plain)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    entity.password = hash_password(plain)
    entity.password_algo = "argon2id"
    entity.failed_login_attempts = 0
    entity.locked_until = None
    revoke_all_sessions(db, entity)
    db.commit()
    return ok(None, "密码已重置，该用户所有会话已失效")


@router.post("/user/delete")
def delete_user(
    payload: UserIdRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    entity = db.get(ComUser, int(payload.id))
    if entity is None:
        raise not_found("用户不存在")
    if entity.id == user.id:
        raise forbidden("不能删除当前登录账号")
    entity.user_active = "N"
    revoke_all_sessions(db, entity)
    db.commit()
    return ok(None, "用户已禁用")


@router.post("/role/list")
def role_list(
    payload: ListRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    rows = db.scalars(select(Role).order_by(Role.id.asc())).all()
    data = [
        RoleOut(id=row.id, code=row.code, name=row.name, enable=row.enable, description=row.description)
        for row in rows
    ]
    return ok({"list": data, "totalRow": len(data), "pageNumber": 1, "pageSize": len(data)})


@router.post("/role/save")
def role_save(
    payload: RoleSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    code = payload.code.strip().upper()
    if payload.id:
        entity = db.get(Role, int(payload.id))
        if entity is None:
            raise not_found("角色不存在")
        if entity.code in ("OWNER", "MEMBER") and code != entity.code:
            raise forbidden("内置角色编码不可修改")
        entity.code = code
        entity.name = payload.name.strip()
        entity.enable = payload.enable
        entity.description = payload.description
        entity.update_user = user.userid
        entity.update_time = now_shanghai()
    else:
        duplicated = db.scalars(select(Role).where(Role.code == code)).first()
        if duplicated is not None:
            raise ApiError(codes.DUPLICATE_REGISTER, "角色编码已存在")
        entity = Role(
            code=code,
            name=payload.name.strip(),
            enable=payload.enable,
            description=payload.description,
            insert_user=user.userid,
        )
        db.add(entity)
    db.commit()
    return ok({"id": str(entity.id)})


@router.post("/org/tree")
def org_tree(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    rows = db.scalars(select(Org).order_by(Org.pid.asc(), Org.id.asc())).all()
    enabled = share_service.org_share_enabled_map(db, None)
    data = [
        OrgOut(
            id=row.id,
            org_code=row.org_code,
            org_name=row.org_name,
            status=row.status,
            pid=str(row.pid or 0),
            remark=row.remark,
            share_enabled=enabled.get(row.id, True),
        )
        for row in rows
    ]
    return ok(data)


def _org_would_cycle(db: Session, org_id: int, pid: int) -> bool:
    cursor = pid
    guard = 0
    while cursor and guard < 50:
        if cursor == org_id:
            return True
        parent = db.get(Org, cursor)
        if parent is None:
            break
        cursor = parent.pid
        guard += 1
    return False


@router.post("/org/save")
def org_save(
    payload: OrgSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    code = payload.org_code.strip()
    name = payload.org_name.strip()
    pid = int(payload.pid or 0)
    if pid != 0 and db.get(Org, pid) is None:
        raise bad_request("上级组织不存在")
    duplicated = db.scalars(
        select(Org).where(func.lower(Org.org_code) == code.lower())
    ).all()
    if payload.id:
        entity = db.get(Org, int(payload.id))
        if entity is None:
            raise not_found("组织不存在")
        if pid == entity.id or _org_would_cycle(db, entity.id, pid):
            raise bad_request("上级组织不能是自身或自己的下级")
        if any(row.id != entity.id for row in duplicated):
            raise ApiError(codes.DUPLICATE_REGISTER, "组织编码已存在")
        entity.org_code = code
        entity.org_name = name
        entity.pid = pid
        entity.status = payload.status
        entity.remark = payload.remark
        entity.update_user = user.userid
        entity.update_time = now_shanghai()
    else:
        if duplicated:
            raise ApiError(codes.DUPLICATE_REGISTER, "组织编码已存在")
        entity = Org(
            org_code=code,
            org_name=name,
            pid=pid,
            status=payload.status,
            remark=payload.remark,
            insert_user=user.userid,
        )
        db.add(entity)
    db.commit()
    return ok({"id": str(entity.id)})


@router.post("/org/delete")
def org_delete(
    payload: OrgIdRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    org_id = int(payload.id)
    entity = db.get(Org, org_id)
    if entity is None:
        raise not_found("组织不存在")
    if org_id == 1:
        raise forbidden("默认组织不可删除")
    if db.scalar(select(Org.id).where(Org.pid == org_id).limit(1)) is not None:
        raise bad_request("请先处理该组织的下级组织")
    if (
        db.scalar(
            select(UserOrg.id).where(UserOrg.company_id == str(org_id)).limit(1)
        )
        is not None
    ):
        raise bad_request("该组织下仍有用户，不能删除")
    db.delete(entity)
    db.commit()
    return ok(None, "组织已删除")


@router.post("/org/members")
def org_members(
    payload: OrgIdRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    org_id = int(payload.id)
    if db.get(Org, org_id) is None:
        raise not_found("组织不存在")
    members = share_service.org_members(db, org_id, include_children=False)
    candidates = share_service.org_members(db, None, include_children=True)
    return ok(
        {
            "orgId": str(org_id),
            "memberIds": [str(member.id) for member in members],
            "candidates": share_service.serialize_members(db, candidates),
        }
    )


@router.post("/org/members/save")
def org_members_save(
    payload: OrgMembersSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    org_id = int(payload.id)
    if db.get(Org, org_id) is None:
        raise not_found("组织不存在")
    try:
        wanted = {int(item) for item in payload.user_ids}
    except (TypeError, ValueError):
        raise bad_request("成员参数不正确") from None
    available = {member.id for member in share_service.org_members(db, None)}
    if wanted - available:
        raise bad_request("存在不可用或不存在的人员")

    existing = {
        row.user_id: row
        for row in db.scalars(
            select(UserOrg).where(UserOrg.company_id == str(org_id))
        ).all()
    }
    for user_id, row in existing.items():
        if user_id not in wanted:
            db.delete(row)
    for user_id in wanted - set(existing):
        db.add(
            UserOrg(
                user_id=user_id,
                company_id=str(org_id),
                insert_user=user.userid,
            )
        )
    db.commit()
    return ok({"orgId": str(org_id), "memberIds": [str(item) for item in sorted(wanted)]})


@router.post("/org/shareSwitch")
def org_share_switch(
    payload: OrgShareSwitchRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    org_id = int(payload.id)
    if db.get(Org, org_id) is None:
        raise not_found("组织不存在")
    share_service.set_org_share_enabled(db, org_id, payload.enabled, user.userid)
    db.commit()
    return ok(
        {
            "orgId": str(org_id),
            "shareEnabled": share_service.org_share_enabled(db, org_id),
        }
    )


@router.post("/menu/tree")
def menu_tree(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return ok(menu_service.full_tree(db))


def _menu_would_cycle(db: Session, menu_id: int, pid: int) -> bool:
    cursor = pid
    guard = 0
    while cursor and guard < 50:
        if cursor == menu_id:
            return True
        parent = db.get(Resource, cursor)
        if parent is None:
            break
        cursor = parent.pid
        guard += 1
    return False


@router.post("/menu/save")
def menu_save(
    payload: MenuSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    name = payload.name.strip()
    path = (payload.path or "").strip()
    pid = int(payload.pid or 0)
    if path and not path.startswith("/"):
        raise bad_request("菜单路径需以 / 开头")
    if pid != 0 and db.get(Resource, pid) is None:
        raise bad_request("上级菜单不存在")
    menu_id = int(payload.id) if payload.id else None
    if menu_id and (pid == menu_id or _menu_would_cycle(db, menu_id, pid)):
        raise bad_request("上级菜单不能是自身或自己的下级")
    if path:
        duplicated = db.scalars(
            select(Resource).where(Resource.web_url == path)
        ).all()
        if any(row.id != menu_id for row in duplicated):
            raise bad_request("菜单路径已存在")

    if menu_id:
        entity = db.get(Resource, menu_id)
        if entity is None:
            raise not_found("菜单不存在")
        entity.name = name
        entity.web_url = path
        entity.icon_name = (payload.icon or "").strip() or None
        entity.pid = pid
        entity.sort = payload.sort
        entity.enable = payload.enable
        entity.update_time = now_shanghai()
    else:
        entity = Resource(
            name=name,
            web_url=path,
            icon_name=(payload.icon or "").strip() or None,
            pid=pid,
            sort=payload.sort,
            enable=payload.enable,
        )
        db.add(entity)
    db.commit()
    return ok({"id": str(entity.id)})


@router.post("/menu/delete")
def menu_delete(
    payload: MenuIdRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    menu_id = int(payload.id)
    entity = db.get(Resource, menu_id)
    if entity is None:
        raise not_found("菜单不存在")
    if db.scalar(select(Resource.id).where(Resource.pid == menu_id).limit(1)) is not None:
        raise bad_request("请先删除该菜单下的子菜单")
    for row in db.scalars(
        select(RoleResource).where(RoleResource.resource_id == menu_id)
    ).all():
        db.delete(row)
    db.delete(entity)
    db.commit()
    return ok(None, "菜单已删除")


@router.post("/role/menus")
def role_menus(
    payload: RoleMenusRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    role_id = int(payload.role_id)
    if db.get(Role, role_id) is None:
        raise not_found("角色不存在")
    return ok(menu_service.role_menu_ids(db, role_id))


@router.post("/role/menus/save")
def role_menus_save(
    payload: RoleMenusSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    role_id = int(payload.role_id)
    role = db.get(Role, role_id)
    if role is None:
        raise not_found("角色不存在")
    if role.code == "OWNER":
        raise forbidden("所有者固定拥有全部菜单")
    ids = [int(item) for item in payload.menu_ids]
    menu_service.save_role_menus(db, role_id, ids)
    db.commit()
    return ok(menu_service.role_menu_ids(db, role_id))


@router.post("/dict/list")
def dict_list(
    payload: DictListRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    stmt = select(GeneralCode).order_by(GeneralCode.codeid.asc(), GeneralCode.code.asc())
    if payload.codeid:
        stmt = stmt.where(GeneralCode.codeid == payload.codeid)
    rows = db.scalars(stmt).all()
    return ok(
        [
            DictOut(
                id=row.id,
                codeid=row.codeid,
                code=row.code,
                name=row.codename_c,
                remark=row.remark,
            )
            for row in rows
        ]
    )


@router.post("/dict/save")
def dict_save(
    payload: DictSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    if payload.id:
        entity = db.get(GeneralCode, int(payload.id))
        if entity is None:
            raise not_found("字典项不存在")
        entity.codeid = payload.codeid
        entity.code = payload.code
        entity.codename_c = payload.name
        entity.remark = payload.remark
        entity.update_user = user.userid
        entity.update_time = now_shanghai()
    else:
        duplicated = db.scalars(
            select(GeneralCode).where(
                GeneralCode.codeid == payload.codeid, GeneralCode.code == payload.code
            )
        ).first()
        if duplicated is not None:
            raise ApiError(codes.DUPLICATE_REGISTER, "字典编码已存在")
        entity = GeneralCode(
            codeid=payload.codeid,
            code=payload.code,
            codename_c=payload.name,
            remark=payload.remark,
            insert_user=user.userid,
        )
        db.add(entity)
    db.commit()
    return ok({"id": str(entity.id)})


@router.post("/switch/get")
def switch_get(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    site_config.ensure_defaults(db)
    return ok({row.switch_key: row.enabled for row in db.scalars(select(Switch)).all()})


@router.post("/switch/save")
def switch_save(
    payload: SwitchSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    row = db.scalars(select(Switch).where(Switch.switch_key == payload.key)).first()
    value = site_config.normalize(payload.key, payload.enabled)
    if row is None:
        if payload.key not in site_config.KEY_LABELS:
            raise not_found("开关不存在")
        row = Switch(
            switch_key=payload.key,
            switch_name=site_config.KEY_LABELS.get(payload.key),
            enabled=value,
        )
        db.add(row)
    else:
        row.enabled = value
    row.update_user = user.userid
    row.update_time = now_shanghai()
    db.commit()
    return ok({row.switch_key: row.enabled})


@router.post("/invite/list")
def invite_list(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    now = now_shanghai()
    rows = invite_service.list_invites(db)
    data = [
        InviteOut(
            id=row.id,
            created_at=row.insert_time,
            expires_at=row.expires_at,
            used=row.used_at is not None,
            used_at=row.used_at,
            expired=row.used_at is None and bool(row.expires_at and row.expires_at < now),
            remark=row.remark,
        )
        for row in rows
    ]
    return ok(data)


@router.post("/invite/create")
def invite_create(
    payload: InviteCreateRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    code, invite = invite_service.create_invite(
        db, user.id, days=payload.days, remark=payload.remark
    )
    db.commit()
    return ok(
        {
            "id": str(invite.id),
            "code": code,
            "expiresAt": invite.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


__all__ = ["router", "has_users", "UserSession"]

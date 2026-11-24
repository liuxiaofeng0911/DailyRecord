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
from ..models import ComUser, GeneralCode, Org, Role, Switch, UserOrg, UserRole, UserSession
from ..schemas.system import (
    DictListRequest,
    DictOut,
    DictSaveRequest,
    OrgOut,
    ResetPasswordRequest,
    RoleOut,
    RoleSaveRequest,
    SwitchSaveRequest,
    SystemUserOut,
    UserIdRequest,
    UserSaveRequest,
)
from ..security import rsa
from ..security.password import hash_password, validate_password_strength
from ..services.auth_service import revoke_all_sessions, role_code_of
from ..services.bootstrap import has_users
from ..services.timeutil import now_shanghai

router = APIRouter(
    prefix="/system",
    tags=["system"],
    dependencies=[Depends(xss_guard), Depends(get_current_user), Depends(require_owner)],
)

USERID_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
        raise bad_request("登录账号需为 3-32 位字母、数字或下划线")
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
    rows = db.scalars(select(Org).order_by(Org.id.asc())).all()
    data = [
        OrgOut(
            id=row.id,
            org_code=row.org_code,
            org_name=row.org_name,
            status=row.status,
            pid=str(row.pid or 0),
        )
        for row in rows
    ]
    return ok(data)


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
    return ok({row.switch_key: row.enabled for row in db.scalars(select(Switch)).all()})


@router.post("/switch/save")
def switch_save(
    payload: SwitchSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    row = db.scalars(select(Switch).where(Switch.switch_key == payload.key)).first()
    if row is None:
        raise not_found("开关不存在")
    row.enabled = payload.enabled
    row.update_user = user.userid
    row.update_time = now_shanghai()
    db.commit()
    return ok({row.switch_key: row.enabled})


__all__ = ["router", "has_users", "UserSession"]

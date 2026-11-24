import hashlib
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError, bad_request, not_found
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..config import settings
from ..db import get_db
from ..deps import COOKIE_NAME, COOKIE_PATH, UserContext, get_current_user
from ..models import ComUser, InviteCode, Role, Switch, UserOrg, UserRole, UserSession
from ..schemas.auth import (
    ChangePasswordRequest,
    LoginData,
    LoginRequest,
    MeData,
    RegisterRequest,
    SessionOut,
    SessionRevokeRequest,
    UserInfo,
)
from ..security import rsa
from ..security.jwt import create_token
from ..security.password import (
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from ..services import credential_service, menu_service, ratelimit
from ..services.auth_service import (
    client_ip,
    create_session_token,
    find_user_by_identifier,
    lock_duration,
    mask_ip,
    revoke_all_sessions,
    role_code_of,
    touch_login,
    write_login_log,
)
from ..services.bootstrap import has_users
from ..services.timeutil import now_shanghai

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(xss_guard)])

USERID_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_FAILED = 5


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.env == "prod",
        samesite="lax",
        path=COOKIE_PATH,
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)


def _get_switch(db: Session, key: str) -> str | None:
    row = db.scalars(select(Switch).where(Switch.switch_key == key)).first()
    return row.enabled if row else None


def _set_switch(db: Session, key: str, value: str) -> None:
    row = db.scalars(select(Switch).where(Switch.switch_key == key)).first()
    if row is not None:
        row.enabled = value


def _user_info(db: Session, user: ComUser, role: str) -> UserInfo:
    return UserInfo(
        id=user.id,
        userid=user.userid,
        username=user.username or user.userid,
        email=user.email,
        user_type=user.user_type,
        role_code=role,
        create_time=user.insert_time,
    )


def _consume_invite(db: Session, code: str, user_id: int) -> None:
    if not code:
        raise ApiError(codes.INVALID_INVITE, "邀请码无效")
    code_hash = hashlib.sha256(code.strip().encode()).hexdigest()
    invite = db.scalars(select(InviteCode).where(InviteCode.code_hash == code_hash)).first()
    now = now_shanghai()
    if invite is None or invite.used_at is not None or invite.expires_at < now:
        raise ApiError(codes.INVALID_INVITE, "邀请码无效")
    invite.used_by = user_id
    invite.used_at = now


@router.get("/publicKey")
def public_key(db: Session = Depends(get_db)):
    mode = (_get_switch(db, "DAILYRECORD_REGISTER_MODE") or "CLOSED").upper()
    return ok(
        {
            "publicKey": rsa.public_key_base64(),
            "publicKeyPem": rsa.public_key_pem(),
            "registerMode": mode,
            "canRegister": (not has_users(db)) or mode != "CLOSED",
        }
    )


@router.post("/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    if not ratelimit.allow(f"register:{client_ip(request)}", limit=3, window_seconds=3600):
        raise ApiError(codes.BAD_REQUEST, "注册过于频繁，请稍后再试")

    userid = payload.userid.strip()
    email = payload.email.strip().lower()
    if not USERID_RE.match(userid):
        raise bad_request("登录账号需为 3-32 位字母、数字或下划线")
    if not EMAIL_RE.match(email):
        raise bad_request("邮箱格式不正确")

    first_user = not has_users(db)
    if not first_user:
        mode = (_get_switch(db, "DAILYRECORD_REGISTER_MODE") or "CLOSED").upper()
        if mode == "CLOSED":
            raise ApiError(codes.REGISTER_CLOSED, "注册已关闭")
        if mode == "INVITE" and not payload.invite_code:
            raise ApiError(codes.INVALID_INVITE, "请填写邀请码")

    plain = rsa.decrypt(payload.password)
    confirm = rsa.decrypt(payload.confirm_password)
    if plain != confirm:
        raise bad_request("两次输入的密码不一致")
    try:
        validate_password_strength(plain)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc

    duplicated = db.scalars(
        select(ComUser).where(
            (func.lower(ComUser.userid) == userid.lower())
            | (func.lower(ComUser.email) == email)
        )
    ).first()
    if duplicated is not None:
        raise ApiError(codes.DUPLICATE_REGISTER, "账号或邮箱已被注册")

    role_code = "OWNER" if first_user else "MEMBER"
    role = db.scalars(select(Role).where(Role.code == role_code)).first()
    user = ComUser(
        userid=userid,
        username=payload.username.strip()[:64],
        email=email,
        password=hash_password(plain),
        password_algo="argon2id",
        user_active="Y",
        user_type="2" if first_user else "1",
        org_id=1,
        insert_user=userid,
    )
    db.add(user)
    db.flush()

    if role is not None:
        db.add(UserRole(user_id=user.id, role_id=role.id, insert_user=userid))
    db.add(UserOrg(user_id=user.id, company_id="1", insert_user=userid))
    db.flush()

    if not first_user and (_get_switch(db, "DAILYRECORD_REGISTER_MODE") or "").upper() == "INVITE":
        _consume_invite(db, payload.invite_code, user.id)

    if first_user:
        _set_switch(db, "DAILYRECORD_REGISTER_MODE", "CLOSED")
        _set_switch(db, "DAILYRECORD_BOOTSTRAP_DONE", "Y")

    token, _session = create_session_token(db, user, request)
    touch_login(db, user)
    write_login_log(db, request, userid=user.userid, result="SUCCESS", user_id=user.id, reason="register")
    db.commit()

    try:
        await credential_service.provision_user(db, user)
    except Exception:  # noqa: BLE001 - 开通失败不影响账号与登录
        db.rollback()

    _set_cookie(response, token)
    return ok(LoginData(token=token, user_info=_user_info(db, user, role_code)))


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    if not ratelimit.allow(f"login:{ip}", limit=10, window_seconds=60):
        raise ApiError(codes.BAD_REQUEST, "登录过于频繁，请稍后再试")

    identifier = payload.identifier.strip()
    user = find_user_by_identifier(db, identifier)

    if user is None:
        write_login_log(db, request, userid=identifier, result="FAILED", reason="user not found")
        db.commit()
        raise ApiError(codes.INVALID_CREDENTIALS, "账号或密码错误")

    now = now_shanghai()
    if user.locked_until is not None and user.locked_until > now:
        write_login_log(db, request, userid=user.userid, result="LOCKED", user_id=user.id)
        db.commit()
        raise ApiError(codes.ACCOUNT_LOCKED, "登录失败次数过多，账号已锁定，请 15 分钟后再试")

    plain = rsa.decrypt(payload.password)
    if user.user_active != "Y":
        write_login_log(db, request, userid=user.userid, result="FAILED", user_id=user.id, reason="inactive")
        db.commit()
        raise ApiError(codes.INVALID_CREDENTIALS, "账号或密码错误")

    if not verify_password(user.password, plain):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED:
            user.locked_until = now + lock_duration()
            write_login_log(
                db, request, userid=user.userid, result="LOCKED", user_id=user.id, reason="too many failures"
            )
            db.commit()
            raise ApiError(codes.ACCOUNT_LOCKED, "登录失败次数过多，账号已锁定，请 15 分钟后再试")
        write_login_log(
            db, request, userid=user.userid, result="FAILED", user_id=user.id, reason="bad password"
        )
        db.commit()
        raise ApiError(codes.INVALID_CREDENTIALS, "账号或密码错误")

    if needs_rehash(user.password):
        user.password = hash_password(plain)
        user.password_algo = "argon2id"

    touch_login(db, user)
    token, _session = create_session_token(db, user, request)
    role = role_code_of(db, user.id)
    write_login_log(db, request, userid=user.userid, result="SUCCESS", user_id=user.id)
    db.commit()

    _set_cookie(response, token)
    return ok(LoginData(token=token, user_info=_user_info(db, user, role)))


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    session = db.get(UserSession, user.session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = now_shanghai()
    db.commit()
    _clear_cookie(response)
    return ok(None)


@router.post("/me")
def me(db: Session = Depends(get_db), user: UserContext = Depends(get_current_user)):
    entity = db.get(ComUser, user.id)
    switches = {row.switch_key: row.enabled for row in db.scalars(select(Switch)).all()}
    return ok(
        MeData(
            user_info=_user_info(db, entity, user.role_code),
            switches=switches,
            menus=menu_service.menu_tree_for_user(db, user.id, user.is_owner),
        )
    )


@router.post("/changePassword")
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    entity = db.get(ComUser, user.id)
    old_plain = rsa.decrypt(payload.old_password)
    new_plain = rsa.decrypt(payload.new_password)
    confirm = rsa.decrypt(payload.confirm_password)
    if not verify_password(entity.password, old_plain):
        raise bad_request("原密码不正确")
    if new_plain != confirm:
        raise bad_request("两次输入的新密码不一致")
    if old_plain == new_plain:
        raise bad_request("新密码不能与原密码相同")
    try:
        validate_password_strength(new_plain)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc

    entity.password = hash_password(new_plain)
    entity.password_algo = "argon2id"
    revoke_all_sessions(db, entity)
    db.commit()
    _clear_cookie(response)
    return ok(None, "密码修改成功，请重新登录")


@router.post("/session/list")
def session_list(
    db: Session = Depends(get_db), user: UserContext = Depends(get_current_user)
):
    rows = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.last_seen_at.desc())
    ).all()
    data = [
        SessionOut(
            id=row.id,
            user_agent=row.user_agent or "未知设备",
            ip=mask_ip(row.ip),
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            current=row.id == user.session_id,
        )
        for row in rows
    ]
    return ok(data)


@router.post("/session/revoke")
def session_revoke(
    payload: SessionRevokeRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    session = db.get(UserSession, int(payload.id))
    if session is None or session.user_id != user.id:
        raise not_found("会话不存在")
    if session.revoked_at is None:
        session.revoked_at = now_shanghai()
        db.commit()
    return ok(None)


@router.post("/session/revokeAll")
def session_revoke_all(
    response: Response,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    entity = db.get(ComUser, user.id)
    revoke_all_sessions(db, entity)
    db.commit()
    _clear_cookie(response)
    return ok(None, "已退出全部设备")


@router.post("/refresh")
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    entity = db.get(ComUser, user.id)
    token, _, expires = create_token(
        user_id=entity.id,
        userid=entity.userid,
        role=user.role_code,
        token_version=entity.token_version,
        jti=user.jti,
    )
    session = db.get(UserSession, user.session_id)
    if session is not None:
        session.expires_at = expires
    db.commit()
    _set_cookie(response, token)
    expires_in = int(timedelta(minutes=settings.jwt_expire_minutes).total_seconds())
    return ok({"token": token, "expiresIn": expires_in})

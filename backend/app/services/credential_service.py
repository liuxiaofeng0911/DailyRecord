"""Immich 每账号凭据：自动开通、加密存储、按用户取客户端。"""

import logging
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ComUser, ImmichCredential
from . import credential_crypto
from .immich import ImmichClient, ImmichError
from .timeutil import now_shanghai

logger = logging.getLogger(__name__)

USER_PERMISSIONS = [
    "asset.read",
    "asset.view",
    "asset.download",
    "asset.upload",
    "asset.update",
    "asset.delete",
    "album.read",
    "album.create",
    "album.update",
    "album.addAsset",
    "album.removeAsset",
    "timeline.read",
]

MAX_ATTEMPTS = 3


def admin_client() -> ImmichClient:
    return ImmichClient(base_url=settings.immich_url, api_key=settings.immich_admin_api_key)


def _email_of(user: ComUser) -> str:
    return (user.email or f"{user.userid}@dailyrecord.local").lower()


def get_credential(db: Session, user_id: int) -> ImmichCredential | None:
    return db.scalars(
        select(ImmichCredential).where(ImmichCredential.user_id == user_id)
    ).first()


def user_client(db: Session, user_id: int) -> ImmichClient | None:
    credential = get_credential(db, user_id)
    if credential is None or credential.status != "active" or not credential.api_key_cipher:
        return None
    try:
        key = credential_crypto.decrypt_secret(user_id, credential.api_key_cipher)
    except credential_crypto.CredentialCryptoError:
        logger.warning("Immich 凭据解密失败: user=%s", user_id)
        return None
    return ImmichClient(
        base_url=credential.base_url or settings.immich_url, api_key=key
    )


def album_of(db: Session, user_id: int) -> str:
    credential = get_credential(db, user_id)
    return (credential.album_id or "") if credential else ""


def status_payload(db: Session, user_id: int) -> dict:
    credential = get_credential(db, user_id)
    if credential is None:
        return {
            "bound": False,
            "provisionStatus": "none",
            "status": "disabled",
            "message": "照片库尚未开通",
        }
    return {
        "bound": credential.status == "active",
        "provisionStatus": credential.provision_status,
        "status": credential.status,
        "immichUserId": credential.immich_user_id,
        "albumId": credential.album_id,
        "apiKeyHint": credential.api_key_hint,
        "lastCheckedAt": credential.provisioned_at,
        "lastError": credential.last_provision_error or credential.last_error,
        "message": _message_for(credential),
    }


def _message_for(credential: ImmichCredential) -> str:
    if credential.provision_status == "active":
        return "照片库已开通"
    if credential.provision_status == "failed":
        return "照片库开通失败，请稍后重试"
    return "照片库开通中"


def _mark_failed(credential: ImmichCredential, message: str) -> None:
    credential.status = "disabled"
    credential.provision_status = "failed"
    credential.last_provision_error = message[:255]
    credential.provision_attempts = int(credential.provision_attempts or 0) + 1


async def provision_user(db: Session, user: ComUser) -> ImmichCredential | None:
    """为新账号创建独立 Immich 用户、API Key 与相册。"""
    if not settings.immich_provision_enabled:
        return None
    if not credential_crypto.has_key():
        logger.warning("未配置 CREDENTIAL_ENCRYPTION_KEY，跳过 Immich 开通")
        return None

    credential = get_credential(db, user.id)
    if credential is None:
        active_count = db.scalar(
            select(func.count())
            .select_from(ImmichCredential)
            .where(ImmichCredential.provision_status == "active")
        ) or 0
        if active_count >= settings.immich_provision_quota:
            logger.warning("Immich 自动开通配额已满: %s", active_count)
            return None
        credential = ImmichCredential(
            user_id=user.id,
            base_url=settings.immich_url,
            provision_source="auto",
            provision_status="pending",
            status="disabled",
        )
        db.add(credential)
        db.flush()

    if credential.status == "active" and credential.api_key_cipher:
        return credential
    if int(credential.provision_attempts or 0) >= MAX_ATTEMPTS:
        return credential

    admin = admin_client()
    temp_password = secrets.token_urlsafe(32)
    final_password = secrets.token_urlsafe(32)
    email = _email_of(user)
    credential.provision_attempts = int(credential.provision_attempts or 0) + 1
    credential.provision_status = "pending"
    credential.last_provision_error = None
    credential.base_url = settings.immich_url
    credential.immich_email = email
    db.commit()

    try:
        immich_user_id = credential.immich_user_id
        if not immich_user_id:
            try:
                created = await admin.create_admin_user(
                    email, (user.username or user.userid)[:64], temp_password
                )
                immich_user_id = created.get("id")
                credential.immich_user_id = immich_user_id
                db.commit()
            except ImmichError as exc:
                detail = str(exc).lower()
                if "exist" in detail or "duplicate" in detail:
                    _mark_failed(credential, "Immich 已存在同邮箱用户，请管理员处理")
                    db.commit()
                    return credential
                raise

        try:
            login = await admin.login(email, temp_password)
        except ImmichError:
            await admin.update_admin_user(immich_user_id, temp_password)
            login = await admin.login(email, temp_password)
        token = login.get("accessToken")
        if not token:
            raise ImmichError("Immich 未返回登录令牌")

        secret = await admin.create_api_key(
            token, f"dailyrecord-{user.userid}"[:60], USER_PERMISSIONS
        )
        credential.api_key_cipher = credential_crypto.encrypt_secret(user.id, secret)
        credential.api_key_hint = credential_crypto.hint_of(secret)

        try:
            album = await ImmichClient(
                base_url=settings.immich_url, api_key=secret
            ).create_album(f"每日记录-{user.userid}"[:120])
            credential.album_id = album.get("id")
        except ImmichError:
            credential.album_id = None

        await admin.update_admin_user(immich_user_id, final_password)

        credential.status = "active"
        credential.provision_status = "active"
        credential.last_provision_error = None
        credential.provisioned_at = now_shanghai()
        db.commit()
        logger.info("Immich 照片库开通成功: user=%s", user.userid)
        return credential
    except (ImmichError, credential_crypto.CredentialCryptoError) as exc:
        logger.warning("Immich 照片库开通失败: user=%s error=%s", user.userid, exc)
        _mark_failed(credential, str(exc))
        db.commit()
        return credential


async def ensure_credential(db: Session, user: ComUser, retry: bool = True) -> ImmichCredential | None:
    credential = get_credential(db, user.id)
    if credential is not None and credential.status == "active":
        return credential
    if not retry:
        return credential
    return await provision_user(db, user)

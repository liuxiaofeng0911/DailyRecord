"""Immich 凭据加解密：AES-256-GCM，按用户绑定 AAD。"""

import base64
import binascii

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import settings


class CredentialCryptoError(RuntimeError):
    pass


def _key() -> bytes:
    raw = (settings.credential_encryption_key or "").strip()
    if not raw:
        raise CredentialCryptoError("未配置 CREDENTIAL_ENCRYPTION_KEY")
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (binascii.Error, ValueError) as exc:
        raise CredentialCryptoError("CREDENTIAL_ENCRYPTION_KEY 不是有效的 Base64") from exc
    if len(key) != 32:
        raise CredentialCryptoError("CREDENTIAL_ENCRYPTION_KEY 必须为 32 字节 Base64")
    return key


def _aad(user_id: int) -> bytes:
    return f"immich:user:{user_id}".encode()


def encrypt_secret(user_id: int, secret: str) -> str:
    from os import urandom

    nonce = urandom(12)
    cipher = AESGCM(_key()).encrypt(nonce, secret.encode(), _aad(user_id))
    nonce_b64 = base64.urlsafe_b64encode(nonce).decode()
    cipher_b64 = base64.urlsafe_b64encode(cipher).decode()
    return f"v1:{nonce_b64}:{cipher_b64}"


def decrypt_secret(user_id: int, payload: str | None) -> str:
    if not payload:
        raise CredentialCryptoError("凭据为空")
    try:
        version, nonce_b64, cipher_b64 = payload.split(":", 2)
        if version != "v1":
            raise CredentialCryptoError("凭据版本不支持")
        nonce = base64.urlsafe_b64decode(nonce_b64)
        cipher = base64.urlsafe_b64decode(cipher_b64)
        return AESGCM(_key()).decrypt(nonce, cipher, _aad(user_id)).decode()
    except (ValueError, binascii.Error, InvalidTag) as exc:
        raise CredentialCryptoError("凭据解密失败") from exc


def hint_of(secret: str) -> str:
    return f"****{secret[-4:]}" if len(secret) >= 4 else "****"


def has_key() -> bool:
    try:
        _key()
        return True
    except CredentialCryptoError:
        return False

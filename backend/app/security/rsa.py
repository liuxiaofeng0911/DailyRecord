"""RSA-2048 PKCS#1 v1.5 传输加密（兼容前端 jsencrypt）。"""

import base64
import binascii
import logging
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ..common import codes
from ..common.exceptions import ApiError
from ..config import settings

logger = logging.getLogger(__name__)


def _read_key(raw: str, path: str) -> bytes | None:
    if raw:
        value = raw.strip()
        if "BEGIN" in value:
            return value.encode()
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            return value.encode()
    if path:
        file_path = Path(path)
        if file_path.exists():
            return file_path.read_bytes()
    return None


@lru_cache
def _generate_dev_keypair() -> tuple[bytes, bytes]:
    logger.warning("未配置 RSA 密钥，使用开发用临时密钥对（生产环境必须配置 RSA_PRIVATE_KEY）")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


@lru_cache
def _keys() -> tuple[rsa.RSAPrivateKey, bytes]:
    private_bytes = _read_key(settings.rsa_private_key, settings.rsa_private_key_path)
    public_bytes = _read_key(settings.rsa_public_key, settings.rsa_public_key_path)
    if private_bytes is None:
        private_bytes, generated_public = _generate_dev_keypair()
        public_bytes = public_bytes or generated_public
    private_key = serialization.load_pem_private_key(private_bytes, password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise RuntimeError("RSA 私钥格式不正确")
    if public_bytes is None:
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    return private_key, public_bytes


def public_key_pem() -> str:
    return _keys()[1].decode()


def public_key_base64() -> str:
    return base64.b64encode(_keys()[1]).decode()


def decrypt(cipher_text: str) -> str:
    """解密前端 Base64 密文；失败统一抛参数错误，不暴露细节。"""
    if not cipher_text:
        raise ApiError(codes.BAD_REQUEST, "密码不能为空")
    try:
        data = base64.b64decode(cipher_text, validate=True)
        plain = _keys()[0].decrypt(data, padding.PKCS1v15())
        return plain.decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise ApiError(codes.BAD_REQUEST, "密码解密失败") from exc
    except Exception as exc:  # cryptography 的解密异常类型不固定
        raise ApiError(codes.BAD_REQUEST, "密码解密失败") from exc


__all__ = ["decrypt", "public_key_pem", "public_key_base64", "hashes"]

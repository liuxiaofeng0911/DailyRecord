"""Argon2id 密码哈希与密码策略。"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

from ..config import settings

_WEAK_PASSWORDS = {
    "1234567890",
    "123456789",
    "password",
    "password1",
    "password123",
    "qwertyuiop",
    "1111111111",
    "0000000000",
    "abcd123456",
    "admin12345",
    "iloveyou123",
    "6666666666",
    "8888888888",
    "1231231231",
    "a123456789",
    "1qaz2wsx3edc",
}


def _hasher() -> PasswordHasher:
    return PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_kib,
        parallelism=settings.argon2_parallelism,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )


def hash_password(plain: str) -> str:
    return _hasher().hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    try:
        return _hasher().verify(stored_hash, plain)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _hasher().check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True


def validate_password_strength(plain: str) -> None:
    if not (10 <= len(plain) <= 128):
        raise ValueError("密码长度需为 10-128 位")
    if plain.lower() in _WEAK_PASSWORDS:
        raise ValueError("密码过于简单，请更换")
    if len(set(plain)) < 4:
        raise ValueError("密码过于简单，请更换")

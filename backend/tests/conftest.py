import base64
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_data/diary_test.db")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("AUTO_CREATE", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-key-with-at-least-32-characters-long")

Path("./test_data").mkdir(parents=True, exist_ok=True)

import pytest  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Switch  # noqa: E402
from app.security import rsa  # noqa: E402
from app.services import ratelimit  # noqa: E402
from app.services.bootstrap import ensure_seed_data  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    ratelimit.reset()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_seed_data(db)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture(scope="session")
def public_key():
    pem = rsa.public_key_pem().encode()
    return serialization.load_pem_public_key(pem)


def encrypt(public_key, value: str) -> str:
    cipher = public_key.encrypt(value.encode(), padding.PKCS1v15())
    return base64.b64encode(cipher).decode()


@pytest.fixture
def crypt(public_key):
    def _encrypt(value: str) -> str:
        return encrypt(public_key, value)

    return _encrypt


def register_user(client, crypt, userid="owner", email="owner@example.com", password="StrongPass123"):
    payload = {
        "userid": userid,
        "username": userid,
        "email": email,
        "password": crypt(password),
        "confirmPassword": crypt(password),
        "inviteCode": "",
    }
    return client.post("/auth/register", json=payload)


def login(client, crypt, identifier="owner", password="StrongPass123"):
    return client.post(
        "/auth/login",
        json={"identifier": identifier, "password": crypt(password), "rememberMe": False},
    )


def auth_headers(token: str) -> dict:
    return {"Authorization": token}


def set_switch(db, key: str, value: str) -> None:
    row = db.scalars(select(Switch).where(Switch.switch_key == key)).first()
    row.enabled = value
    db.commit()

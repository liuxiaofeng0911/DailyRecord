import asyncio
import base64
import secrets

import pytest

from app.config import settings
from app.db import SessionLocal
from app.models import ComUser, ImmichCredential
from app.services import credential_crypto, credential_service
from app.services.immich import ImmichError
from tests.conftest import auth_headers, register_user


def enable_immich(monkeypatch):
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setattr(settings, "immich_url", "http://immich-test:2283")
    monkeypatch.setattr(settings, "immich_admin_api_key", "admin-key")
    monkeypatch.setattr(settings, "credential_encryption_key", key)
    monkeypatch.setattr(settings, "immich_auto_provision", True)
    monkeypatch.setattr(settings, "immich_provision_quota", 20)


class FakeAdmin:
    def __init__(self, duplicate=False):
        self.duplicate = duplicate
        self.created = None

    async def create_admin_user(self, email, name, password):
        if self.duplicate:
            raise ImmichError("Immich POST /api/admin/users 返回 400: user already exists")
        self.created = {"email": email, "name": name, "password": password}
        return {"id": "immich-user-1"}

    async def login(self, email, password):
        return {"accessToken": "session-token"}

    async def create_api_key(self, token, name, permissions):
        assert token == "session-token"
        assert "asset.upload" in permissions
        return "secret-key-1234"

    async def update_admin_user(self, user_id, password):
        return {"id": user_id}


def test_credential_roundtrip_and_aad(monkeypatch):
    enable_immich(monkeypatch)
    payload = credential_crypto.encrypt_secret(1, "my-secret-key")
    assert payload.startswith("v1:")
    assert credential_crypto.decrypt_secret(1, payload) == "my-secret-key"
    with pytest.raises(credential_crypto.CredentialCryptoError):
        credential_crypto.decrypt_secret(2, payload)
    assert credential_crypto.hint_of("my-secret-key") == "****-key"


def test_provision_user_creates_encrypted_credential(client, crypt, db, monkeypatch):
    token = register_user(client, crypt).json()["data"]["token"]
    assert token
    enable_immich(monkeypatch)
    fake = FakeAdmin()
    monkeypatch.setattr(credential_service, "admin_client", lambda: fake)

    async def fake_album(self, name):
        return {"id": "album-1"}

    monkeypatch.setattr(credential_service.ImmichClient, "create_album", fake_album)

    with SessionLocal() as session:
        entity = session.query(ComUser).filter_by(userid="owner").first()
        result = asyncio.run(credential_service.provision_user(session, entity))
        assert result is not None
        assert result.status == "active"
        assert result.provision_status == "active"
        assert result.immich_user_id == "immich-user-1"
        assert result.album_id == "album-1"
        assert result.api_key_hint == "****1234"
        assert "secret-key-1234" not in (result.api_key_cipher or "")
        assert credential_crypto.decrypt_secret(entity.id, result.api_key_cipher) == "secret-key-1234"
        assert fake.created["password"] != "secret-key-1234"
        client_obj = credential_service.user_client(session, entity.id)
        assert client_obj is not None


def test_provision_duplicate_email_marks_failed(client, crypt, db, monkeypatch):
    register_user(client, crypt)
    enable_immich(monkeypatch)
    fake = FakeAdmin(duplicate=True)
    monkeypatch.setattr(credential_service, "admin_client", lambda: fake)

    with SessionLocal() as session:
        entity = session.query(ComUser).filter_by(userid="owner").first()
        result = asyncio.run(credential_service.provision_user(session, entity))
        assert result is not None
        assert result.status == "disabled"
        assert result.provision_status == "failed"
        assert "已存在同邮箱" in (result.last_provision_error or "")
        assert session.query(ImmichCredential).count() == 1


def test_credential_status_is_scoped_to_user(client, crypt, db, monkeypatch):
    first = register_user(client, crypt).json()["data"]["token"]
    enable_immich(monkeypatch)
    status = client.post("/immich/credential/get", headers=auth_headers(first)).json()["data"]
    assert status["configured"] is True
    assert status["provisionStatus"] in ("none", "failed", "pending")

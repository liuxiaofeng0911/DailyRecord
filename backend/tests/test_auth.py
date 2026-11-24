from datetime import timedelta

from sqlalchemy import select

from app.models import ComUser, UserRole, UserSession
from app.security.jwt import create_token
from app.services.timeutil import now_shanghai
from tests.conftest import auth_headers, login, register_user, set_switch


def test_public_key_and_register_mode(client, crypt, db):
    first = client.get("/auth/publicKey").json()["data"]
    assert first["canRegister"] is True
    register_user(client, crypt)
    closed = client.get("/auth/publicKey").json()["data"]
    assert closed["registerMode"] == "CLOSED"
    assert closed["canRegister"] is False
    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    opened = client.get("/auth/publicKey").json()["data"]
    assert opened["canRegister"] is True


def test_public_key(client):
    body = client.get("/auth/publicKey").json()
    assert body["code"] == 200
    assert "BEGIN PUBLIC KEY" in body["data"]["publicKeyPem"]


def test_register_first_user_becomes_owner(client, crypt, db):
    response = register_user(client, crypt)
    body = response.json()
    assert body["code"] == 200
    info = body["data"]["userInfo"]
    assert info["userType"] == "2"
    assert info["roleCode"] == "OWNER"
    assert body["data"]["token"]

    user = db.scalars(select(ComUser).where(ComUser.userid == "owner")).first()
    assert user.password.startswith("$argon2id$")
    assert user.password != "StrongPass123"
    role_row = db.scalars(select(UserRole).where(UserRole.user_id == user.id)).first()
    assert role_row is not None


def test_register_closed_after_first_user(client, crypt):
    assert register_user(client, crypt).json()["code"] == 200
    body = register_user(client, crypt, userid="second", email="second@example.com").json()
    assert body["code"] == 1007


def test_register_duplicate_when_open(client, crypt, db):
    register_user(client, crypt)
    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    body = register_user(
        client, crypt, userid="owner", email="other@example.com", password="AnotherPass123"
    ).json()
    assert body["code"] == 1005


def test_weak_password_rejected(client, crypt, db):
    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    body = register_user(client, crypt, password="1234567890").json()
    assert body["code"] == 400


def test_login_success_and_me(client, crypt):
    register_user(client, crypt)
    body = login(client, crypt).json()
    assert body["code"] == 200
    token = body["data"]["token"]
    me = client.post("/auth/me", headers=auth_headers(token)).json()
    assert me["code"] == 200
    assert me["data"]["userInfo"]["userid"] == "owner"
    assert "DAILYRECORD_REGISTER_MODE" in me["data"]["switches"]


def test_login_lock_after_five_failures(client, crypt, db):
    register_user(client, crypt)
    for attempt in range(4):
        body = login(client, crypt, password="WrongPass123").json()
        assert body["code"] == 1002, attempt
    body = login(client, crypt, password="WrongPass123").json()
    assert body["code"] == 1006

    user = db.scalars(select(ComUser).where(ComUser.userid == "owner")).first()
    db.refresh(user)
    assert user.locked_until is not None
    # 正确密码在锁定期内也拒绝
    assert login(client, crypt).json()["code"] == 1006


def test_unauthenticated_request_rejected(client):
    assert client.post("/auth/me").json()["code"] == 1003


def test_session_revoke_invalidates_token(client, crypt, db):
    register_user(client, crypt)
    token = login(client, crypt).json()["data"]["token"]
    sessions = client.post("/auth/session/list", headers=auth_headers(token)).json()["data"]
    assert len(sessions) >= 1
    current = next(item for item in sessions if item["current"])
    revoke = client.post(
        "/auth/session/revoke", headers=auth_headers(token), json={"id": current["id"]}
    ).json()
    assert revoke["code"] == 200
    assert client.post("/auth/me", headers=auth_headers(token)).json()["code"] == 1003


def test_change_password_invalidates_all_sessions(client, crypt):
    register_user(client, crypt)
    token = login(client, crypt).json()["data"]["token"]
    body = client.post(
        "/auth/changePassword",
        headers=auth_headers(token),
        json={
            "oldPassword": crypt("StrongPass123"),
            "newPassword": crypt("NewStrongPass456"),
            "confirmPassword": crypt("NewStrongPass456"),
        },
    ).json()
    assert body["code"] == 200
    assert client.post("/auth/me", headers=auth_headers(token)).json()["code"] == 1003
    assert login(client, crypt, password="NewStrongPass456").json()["code"] == 200


def test_revoke_all_sessions(client, crypt):
    register_user(client, crypt)
    token_a = login(client, crypt).json()["data"]["token"]
    token_b = login(client, crypt).json()["data"]["token"]
    assert client.post("/auth/session/revokeAll", headers=auth_headers(token_a)).json()["code"] == 200
    assert client.post("/auth/me", headers=auth_headers(token_a)).json()["code"] == 1003
    assert client.post("/auth/me", headers=auth_headers(token_b)).json()["code"] == 1003


def test_token_renewed_when_near_expiry(client, crypt, db):
    register_user(client, crypt)
    user = db.scalars(select(ComUser).where(ComUser.userid == "owner")).first()
    old_now = now_shanghai() - timedelta(minutes=450)
    token, jti, expires = create_token(
        user_id=user.id,
        userid=user.userid,
        role="OWNER",
        token_version=user.token_version,
        now=old_now,
    )
    db.add(
        UserSession(
            user_id=user.id,
            jti=jti,
            user_agent="pytest",
            ip="127.0.0.1",
            created_at=now_shanghai() - timedelta(hours=7),
            last_seen_at=now_shanghai(),
            expires_at=expires,
        )
    )
    db.commit()
    response = client.post("/auth/me", headers=auth_headers(token))
    assert response.json()["code"] == 200
    assert response.headers.get("token")
    assert response.headers["token"] != token


def test_xss_payload_rejected(client, crypt):
    register_user(client, crypt)
    token = login(client, crypt).json()["data"]["token"]
    body = client.post(
        "/auth/me", headers=auth_headers(token), json={"note": "<script>alert(1)</script>"}
    ).json()
    assert body["code"] == 1004

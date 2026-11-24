from tests.conftest import auth_headers, login, register_user, set_switch


def owner_token(client, crypt):
    return register_user(client, crypt).json()["data"]["token"]


def create_user(client, crypt, token, userid="member", email="member@example.com", password="MemberPass123"):
    return client.post(
        "/system/user/save",
        headers=auth_headers(token),
        json={
            "userid": userid,
            "username": userid,
            "email": email,
            "password": crypt(password),
            "userActive": "Y",
            "roleCode": "MEMBER",
        },
    ).json()


def test_non_owner_cannot_access_system(client, crypt, db):
    owner_token(client, crypt)
    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    member = register_user(
        client, crypt, userid="member", email="member@example.com"
    ).json()["data"]["token"]
    body = client.post("/system/user/list", headers=auth_headers(member), json={}).json()
    assert body["code"] == 403


def test_user_management_flow(client, crypt):
    token = owner_token(client, crypt)
    created = create_user(client, crypt, token)
    assert created["code"] == 200
    user_id = created["data"]["id"]

    listing = client.post("/system/user/list", headers=auth_headers(token), json={}).json()
    assert listing["data"]["totalRow"] == 2
    member_row = next(item for item in listing["data"]["list"] if item["userid"] == "member")
    assert member_row["roleCode"] == "MEMBER"

    searched = client.post(
        "/system/user/list",
        headers=auth_headers(token),
        json={"wheres": [{"column": "keyword", "condition": "eq", "v1": "member@example"}]},
    ).json()
    assert searched["data"]["totalRow"] == 1

    member_token = login(client, crypt, identifier="member", password="MemberPass123").json()[
        "data"
    ]["token"]
    assert client.post("/auth/me", headers=auth_headers(member_token)).json()["code"] == 200

    reset = client.post(
        "/system/user/resetPassword",
        headers=auth_headers(token),
        json={"id": user_id, "password": crypt("ResetPass1234")},
    ).json()
    assert reset["code"] == 200
    assert client.post("/auth/me", headers=auth_headers(member_token)).json()["code"] == 1003
    assert (
        login(client, crypt, identifier="member", password="ResetPass1234").json()["code"]
        == 200
    )

    disabled = client.post(
        "/system/user/delete", headers=auth_headers(token), json={"id": user_id}
    ).json()
    assert disabled["code"] == 200
    assert (
        login(client, crypt, identifier="member", password="ResetPass1234").json()["code"]
        == 1002
    )


def test_cannot_disable_self(client, crypt):
    token = owner_token(client, crypt)
    me = client.post("/auth/me", headers=auth_headers(token)).json()["data"]["userInfo"]
    body = client.post(
        "/system/user/save",
        headers=auth_headers(token),
        json={
            "id": me["id"],
            "userid": "owner",
            "username": "owner",
            "email": "owner@example.com",
            "userActive": "N",
            "roleCode": "OWNER",
        },
    ).json()
    assert body["code"] == 403


def test_role_dict_switch_org(client, crypt):
    token = owner_token(client, crypt)

    roles = client.post("/system/role/list", headers=auth_headers(token), json={}).json()["data"]
    assert {row["code"] for row in roles["list"]} >= {"OWNER", "MEMBER"}

    created_role = client.post(
        "/system/role/save",
        headers=auth_headers(token),
        json={"code": "VIEWER", "name": "只读", "enable": "Y"},
    ).json()
    assert created_role["code"] == 200

    dicts = client.post(
        "/system/dict/list", headers=auth_headers(token), json={"codeid": "MOOD"}
    ).json()["data"]
    assert any(row["name"] == "平静" for row in dicts)

    saved_dict = client.post(
        "/system/dict/save",
        headers=auth_headers(token),
        json={"codeid": "MOOD", "code": "惊喜", "name": "惊喜"},
    ).json()
    assert saved_dict["code"] == 200

    switches = client.post("/system/switch/get", headers=auth_headers(token)).json()["data"]
    assert switches["DAILYRECORD_REGISTER_MODE"] == "CLOSED"
    saved = client.post(
        "/system/switch/save",
        headers=auth_headers(token),
        json={"key": "DAILYRECORD_REGISTER_MODE", "enabled": "OPEN"},
    ).json()
    assert saved["code"] == 200
    assert saved["data"]["DAILYRECORD_REGISTER_MODE"] == "OPEN"

    tree = client.post("/system/org/tree", headers=auth_headers(token)).json()["data"]
    assert tree[0]["orgCode"] == "DEFAULT"

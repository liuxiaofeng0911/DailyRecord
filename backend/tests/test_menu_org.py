from tests.conftest import auth_headers, register_user, set_switch


def bearer(client, crypt, userid="owner", email="owner@example.com"):
    return register_user(client, crypt, userid=userid, email=email).json()["data"]["token"]


def menus(client, token):
    return client.post("/auth/me", headers=auth_headers(token)).json()["data"]["menus"]


def flatten(nodes):
    result = []
    for node in nodes:
        result.append(node)
        result.extend(flatten(node.get("children") or []))
    return result


def role_id_by_code(client, token, code):
    roles = client.post("/system/role/list", headers=auth_headers(token), json={}).json()["data"]
    return next(row["id"] for row in roles["list"] if row["code"] == code)


def test_owner_and_member_default_menus(client, crypt, db):
    owner = bearer(client, crypt)
    owner_menus = menus(client, owner)
    assert [node["name"] for node in owner_menus] == ["今天", "时间线", "统计", "系统管理"]
    system = next(node for node in owner_menus if node["name"] == "系统管理")
    assert {child["name"] for child in system["children"]} == {
        "账户设置",
        "系统设置",
        "用户管理",
        "角色管理",
        "组织管理",
        "菜单管理",
        "字典管理",
    }

    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    member = bearer(client, crypt, userid="member", email="member@example.com")
    member_menus = menus(client, member)
    assert [node["name"] for node in member_menus] == ["今天", "时间线", "统计", "系统管理"]
    member_system = next(node for node in member_menus if node["name"] == "系统管理")
    assert [child["name"] for child in member_system["children"]] == ["账户设置"]


def test_role_menu_permission_changes_member_menu(client, crypt, db):
    owner = bearer(client, crypt)
    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    member = bearer(client, crypt, userid="member", email="member@example.com")
    member_role = role_id_by_code(client, owner, "MEMBER")
    all_menus = flatten(menus(client, owner))
    wanted = {
        item["id"]
        for item in all_menus
        if item["path"] in ("/Main/Today", "/Main/Timeline", "/Main/Stats", "/System/User")
        or item["name"] == "系统管理"
    }
    saved = client.post(
        "/system/role/menus/save",
        headers=auth_headers(owner),
        json={"roleId": member_role, "menuIds": sorted(wanted)},
    ).json()
    assert saved["code"] == 200

    updated = menus(client, member)
    system = next(node for node in updated if node["name"] == "系统管理")
    assert [child["name"] for child in system["children"]] == ["用户管理"]

    owner_save = client.post(
        "/system/role/menus/save",
        headers=auth_headers(owner),
        json={"roleId": role_id_by_code(client, owner, "OWNER"), "menuIds": []},
    ).json()
    assert owner_save["code"] == 403


def test_menu_crud_and_member_visibility(client, crypt, db):
    owner = bearer(client, crypt)
    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    member = bearer(client, crypt, userid="member", email="member@example.com")
    system = next(node for node in menus(client, owner) if node["name"] == "系统管理")

    created = client.post(
        "/system/menu/save",
        headers=auth_headers(owner),
        json={
            "name": "访客页面",
            "path": "/System/Guest",
            "icon": "lucide:user",
            "pid": system["id"],
            "sort": 99,
            "enable": "Y",
        },
    ).json()
    assert created["code"] == 200
    new_id = created["data"]["id"]

    member_role = role_id_by_code(client, owner, "MEMBER")
    current = client.post(
        "/system/role/menus", headers=auth_headers(owner), json={"roleId": member_role}
    ).json()["data"]
    client.post(
        "/system/role/menus/save",
        headers=auth_headers(owner),
        json={"roleId": member_role, "menuIds": [*current, new_id]},
    )
    assert any(node["name"] == "访客页面" for node in flatten(menus(client, member)))

    blocked = client.post(
        "/system/menu/delete", headers=auth_headers(owner), json={"id": system["id"]}
    ).json()
    assert blocked["code"] == 400

    removed = client.post(
        "/system/menu/delete", headers=auth_headers(owner), json={"id": new_id}
    ).json()
    assert removed["code"] == 200
    assert not any(node["name"] == "访客页面" for node in flatten(menus(client, member)))

    forbidden = client.post("/system/menu/tree", headers=auth_headers(member), json={}).json()
    assert forbidden["code"] == 403


def test_org_crud_and_guards(client, crypt):
    token = bearer(client, crypt)
    created = client.post(
        "/system/org/save",
        headers=auth_headers(token),
        json={"orgCode": "LAB", "orgName": "实验室", "pid": "0", "status": "Y"},
    ).json()
    assert created["code"] == 200
    org_id = created["data"]["id"]

    child = client.post(
        "/system/org/save",
        headers=auth_headers(token),
        json={"orgCode": "LAB-A", "orgName": "小组 A", "pid": org_id, "status": "Y"},
    ).json()
    assert child["code"] == 200
    child_id = child["data"]["id"]

    duplicate = client.post(
        "/system/org/save",
        headers=auth_headers(token),
        json={"orgCode": "lab", "orgName": "重复", "pid": "0"},
    ).json()
    assert duplicate["code"] == 1005

    cycle = client.post(
        "/system/org/save",
        headers=auth_headers(token),
        json={"id": org_id, "orgCode": "LAB", "orgName": "实验室", "pid": child_id},
    ).json()
    assert cycle["code"] == 400

    blocked = client.post(
        "/system/org/delete", headers=auth_headers(token), json={"id": org_id}
    ).json()
    assert blocked["code"] == 400

    default_blocked = client.post(
        "/system/org/delete", headers=auth_headers(token), json={"id": "1"}
    ).json()
    assert default_blocked["code"] == 403

    assert (
        client.post("/system/org/delete", headers=auth_headers(token), json={"id": child_id}).json()[
            "code"
        ]
        == 200
    )
    assert (
        client.post("/system/org/delete", headers=auth_headers(token), json={"id": org_id}).json()[
            "code"
        ]
        == 200
    )

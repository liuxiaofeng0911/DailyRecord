from tests.conftest import auth_headers, register_user, set_switch
from tests.test_entry_photo import save_entry


def bearer(client, crypt, userid="owner", email="owner@example.com"):
    return register_user(client, crypt, userid=userid, email=email).json()["data"]["token"]


def test_tag_icon_override(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token, tags=[" #散步 ", "散步"])

    tags = client.post("/tag/list", headers=auth_headers(token)).json()["data"]
    assert [item["name"] for item in tags] == ["散步"]
    assert tags[0]["icon"] is None

    saved = client.post(
        "/tag/save",
        headers=auth_headers(token),
        json={"id": tags[0]["id"], "icon": "lucide:footprints", "name": "江边散步"},
    ).json()
    assert saved["data"]["icon"] == "lucide:footprints"
    assert saved["data"]["name"] == "江边散步"

    entry = client.post(
        "/entry/get", headers=auth_headers(token), json={"date": "2026-11-22"}
    ).json()["data"]
    assert entry["tags"][0]["name"] == "江边散步"
    assert entry["tags"][0]["icon"] == "lucide:footprints"


def test_tag_isolation(client, crypt, db):
    token_a = bearer(client, crypt)
    save_entry(client, token_a, tags=["散步"])
    tag_id = client.post("/tag/list", headers=auth_headers(token_a)).json()["data"][0]["id"]

    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    token_b = bearer(client, crypt, userid="other", email="other@example.com")
    assert client.post("/tag/list", headers=auth_headers(token_b)).json()["data"] == []
    result = client.post(
        "/tag/save", headers=auth_headers(token_b), json={"id": tag_id, "icon": "lucide:x"}
    ).json()
    assert result["code"] == 404

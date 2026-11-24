from tests.conftest import auth_headers, register_user, set_switch
from tests.test_entry_photo import save_entry, upload_photo


def bearer(client, crypt, userid="owner", email="owner@example.com"):
    return register_user(client, crypt, userid=userid, email=email).json()["data"]["token"]


def history(client, token, entry_date="2026-11-22"):
    return client.post(
        "/entry/history", headers=auth_headers(token), json={"entryDate": entry_date}
    ).json()["data"]


def test_create_update_and_changed_fields(client, crypt):
    token = bearer(client, crypt)
    created = save_entry(client, token, note="下午去了江边", mood="平静", tags=["散步", "江边"])
    assert set(created["data"]["changedFields"]) == {"note", "mood", "tags"}

    logs = history(client, token)
    assert logs["totalRow"] == 1
    create = logs["list"][0]
    assert create["action"] == "CREATE"
    assert create["operatorName"] == "owner"
    fields = {item["field"]: item for item in create["changes"]}
    assert fields["note"]["added"] == "下午去了江边"
    assert fields["tags"]["added"] == ["散步", "江边"]
    assert fields["mood"]["after"] == "平静"

    updated = save_entry(
        client,
        token,
        note="下午去了江边，傍晚下了小雨",
        mood="平静",
        tags=["散步", "江边"],
        version=1,
    )
    assert updated["data"]["changedFields"] == ["note"]
    note_change = history(client, token)["list"][0]["changes"][0]
    assert note_change["field"] == "note"
    assert note_change["op"] == "update"
    assert "傍晚下了小雨" in note_change["added"]
    assert note_change["removed"] == ""
    assert note_change["beforeLength"] == 6
    assert note_change["afterLength"] == 13


def test_tag_only_update_has_no_text_piece(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token, note="保持不变的正文", tags=["散步"], version=None)
    save_entry(client, token, note="保持不变的正文", tags=["散步", "雨天"], version=1)
    changes = history(client, token)["list"][0]["changes"]
    assert [item["field"] for item in changes] == ["tags"]
    tags = changes[0]
    assert tags["added"] == ["雨天"]
    assert tags["removed"] == []


def test_noop_save_writes_no_log(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token, note="同样内容", tags=["散步"])
    body = save_entry(client, token, note="同样内容", tags=["散步"], version=1)
    assert body["data"]["changedFields"] == []
    assert history(client, token)["totalRow"] == 1


def test_version_conflict_does_not_write_log(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token, note="第一版")
    conflict = save_entry(client, token, note="冲突版本", version=99)
    assert conflict["code"] == 1009
    assert history(client, token)["totalRow"] == 1


def test_photo_association_changes_are_logged(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token)
    photo_id = upload_photo(client, token)["data"]["photos"][0]["id"]

    attached = save_entry(
        client, token, note="下午去了江边", photo_ids=[photo_id], cover_photo_id=photo_id, version=1
    )
    assert "photos" in attached["data"]["changedFields"]
    changes = {item["field"]: item for item in history(client, token)["list"][0]["changes"]}
    assert changes["photos"]["added"] == [photo_id]

    save_entry(client, token, note="下午去了江边", photo_ids=[], version=2)
    changes = {item["field"]: item for item in history(client, token)["list"][0]["changes"]}
    assert changes["photos"]["removed"] == [photo_id]
    assert changes["cover"]["before"] == photo_id
    assert changes["cover"]["after"] is None


def test_delete_entry_keeps_history(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token, note="将被删除", tags=["生活"])
    client.post("/entry/delete", headers=auth_headers(token), json={"entryDate": "2026-11-22"})
    logs = history(client, token)
    actions = [item["action"] for item in logs["list"]]
    assert actions[0] == "DELETE"
    delete_log = logs["list"][0]
    assert delete_log["changes"][0]["op"] == "delete"
    assert delete_log["changes"][0]["noteLength"] == 4
    assert "生活" in delete_log["changes"][0]["tags"]


def test_history_isolation(client, crypt, db):
    token_a = bearer(client, crypt)
    save_entry(client, token_a, note="A 的内容")
    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    token_b = bearer(client, crypt, userid="other", email="other@example.com")
    assert history(client, token_b)["totalRow"] == 0


def test_photo_trash_restore_purge_are_logged(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token)
    photo_id = upload_photo(client, token, entry_date="2026-11-22")["data"]["photos"][0]["id"]

    client.post("/photo/delete", headers=auth_headers(token), json={"id": photo_id})
    assert history(client, token)["list"][0]["action"] == "TRASH"

    client.post("/photo/trash/restore", headers=auth_headers(token), json={"ids": [photo_id]})
    assert history(client, token)["list"][0]["action"] == "RESTORE"

    client.post("/photo/delete", headers=auth_headers(token), json={"id": photo_id})
    client.post("/photo/trash/purge", headers=auth_headers(token), json={"ids": [photo_id]})
    assert history(client, token)["list"][0]["action"] == "PURGE"

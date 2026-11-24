import io

import pytest
from PIL import Image

from app.config import settings
from tests.conftest import auth_headers, register_user, set_switch


def bearer(client, crypt, userid="owner", email="owner@example.com"):
    return register_user(client, crypt, userid=userid, email=email).json()["data"]["token"]


def make_jpeg(color=(120, 160, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def save_entry(client, token, entry_date="2026-11-22", **kwargs):
    payload = {"entryDate": entry_date, "note": "下午去了江边", **kwargs}
    return client.post("/entry/save", headers=auth_headers(token), json=payload).json()


def upload_photo(client, token, entry_date=None, filename="a.jpg", content=None, mime="image/jpeg"):
    data = {"entryDate": entry_date} if entry_date else {}
    return client.post(
        "/photo/upload",
        headers=auth_headers(token),
        data=data,
        files=[("files[]", (filename, content or make_jpeg(), mime))],
    ).json()


def test_save_get_and_optimistic_lock(client, crypt):
    token = bearer(client, crypt)
    created = save_entry(client, token, note="第一条")
    assert created["code"] == 200
    entry = created["data"]
    assert entry["version"] == 1
    assert entry["updateTime"].count(":") == 2

    updated = save_entry(client, token, note="第二条", version=1)
    assert updated["data"]["version"] == 2
    assert updated["data"]["note"] == "第二条"

    conflict = save_entry(client, token, note="旧版本", version=1)
    assert conflict["code"] == 1009

    got = client.post(
        "/entry/get", headers=auth_headers(token), json={"date": "2026-11-22"}
    ).json()
    assert got["data"]["note"] == "第二条"


def test_tag_normalization(client, crypt):
    token = bearer(client, crypt)
    body = save_entry(client, token, tags=[" #散步 ", "散步", ""])
    names = [tag["name"] for tag in body["data"]["tags"]]
    assert names == ["散步"]


def test_user_isolation(client, crypt, db):
    token_a = bearer(client, crypt)
    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    token_b = bearer(client, crypt, userid="other", email="other@example.com")

    save_entry(client, token_a, note="A 的记录")
    got_b = client.post(
        "/entry/get", headers=auth_headers(token_b), json={"date": "2026-11-22"}
    ).json()
    assert got_b["data"] is None

    list_b = client.post("/entry/list", headers=auth_headers(token_b), json={}).json()
    assert list_b["data"]["totalRow"] == 0


def test_upload_thumbnail_and_cover(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token)
    body = upload_photo(client, token, entry_date="2026-11-22")
    assert body["code"] == 200
    photo = body["data"]["photos"][0]
    assert photo["mediaType"] == "IMAGE"
    assert photo["isCover"] is True
    assert photo["takenAt"].count(":") == 2

    second = upload_photo(client, token, entry_date="2026-11-22")
    assert second["data"]["photos"][0]["isCover"] is False

    thumb = client.get(f"/photo/thumbnail/{photo['id']}", headers=auth_headers(token))
    assert thumb.status_code == 200
    assert thumb.headers["content-type"].startswith("image/")

    # Cookie 鉴权（<img> 场景）
    cookie_thumb = client.get(f"/photo/thumbnail/{photo['id']}", cookies={"dr_token": token})
    assert cookie_thumb.status_code == 200

    original = client.get(f"/photo/original/{photo['id']}", headers=auth_headers(token))
    assert original.status_code == 200

    entry = client.post(
        "/entry/get", headers=auth_headers(token), json={"date": "2026-11-22"}
    ).json()["data"]
    assert len(entry["photos"]) == 2


def test_photo_isolation(client, crypt, db):
    token_a = bearer(client, crypt)
    save_entry(client, token_a)
    photo_id = upload_photo(client, token_a, entry_date="2026-11-22")["data"]["photos"][0]["id"]

    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    token_b = bearer(client, crypt, userid="other", email="other@example.com")
    response = client.get(f"/photo/thumbnail/{photo_id}", headers=auth_headers(token_b))
    assert response.status_code == 404


def test_reject_invalid_image(client, crypt):
    token = bearer(client, crypt)
    body = upload_photo(client, token, filename="fake.jpg", content=b"not an image")
    assert body["code"] == 400


def test_image_with_octet_stream_content_type(client, crypt):
    token = bearer(client, crypt)
    body = upload_photo(
        client, token, filename="微信图片_20261122174229.jpg", mime="application/octet-stream"
    )
    assert body["code"] == 200
    assert body["data"]["photos"][0]["mimeType"] == "image/jpeg"


def test_video_with_octet_stream_content_type(client, crypt):
    token = bearer(client, crypt)
    video = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 128
    body = upload_photo(
        client, token, filename="clip.mp4", content=video, mime="application/octet-stream"
    )
    assert body["code"] == 200
    photo = body["data"]["photos"][0]
    assert photo["mediaType"] == "VIDEO"
    assert photo["mimeType"] == "video/mp4"


def test_unknown_image_format_converted_to_jpeg(client, crypt):
    token = bearer(client, crypt)
    buffer = io.BytesIO()
    Image.new("RGBA", (32, 32), (10, 20, 30, 255)).save(buffer, format="ICO")
    body = upload_photo(
        client, token, filename="icon.ico", content=buffer.getvalue(), mime="image/x-icon"
    )
    assert body["code"] == 200
    assert body["data"]["photos"][0]["mimeType"] == "image/jpeg"


def test_heic_image_converted_to_jpeg(client, crypt):
    pytest.importorskip("pillow_heif")
    from pillow_heif import register_heif_opener

    register_heif_opener()
    buffer = io.BytesIO()
    Image.new("RGB", (48, 32), (200, 100, 50)).save(buffer, format="HEIF", quality=80)
    body = upload_photo(
        client,
        token=bearer(client, crypt),
        filename="IMG_0001.HEIC",
        content=buffer.getvalue(),
        mime="image/heic",
    )
    assert body["code"] == 200
    assert body["data"]["photos"][0]["mimeType"] == "image/jpeg"


def test_upload_size_limit(client, crypt, monkeypatch):
    token = bearer(client, crypt)
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    body = upload_photo(client, token, content=make_jpeg())
    assert body["code"] == 400


def test_delete_entry_keeps_photo(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token)
    photo_id = upload_photo(client, token, entry_date="2026-11-22")["data"]["photos"][0]["id"]
    deleted = client.post(
        "/entry/delete", headers=auth_headers(token), json={"entryDate": "2026-11-22"}
    ).json()
    assert deleted["code"] == 200

    photos = client.post(
        "/photo/list", headers=auth_headers(token), json={"unattached": True}
    ).json()["data"]
    assert [item["id"] for item in photos] == [photo_id]


def test_update_caption_marks_manual_and_cover(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token)
    ids = [
        upload_photo(client, token, entry_date="2026-11-22")["data"]["photos"][0]["id"],
        upload_photo(client, token, entry_date="2026-11-22")["data"]["photos"][0]["id"],
    ]
    body = client.post(
        "/photo/update",
        headers=auth_headers(token),
        json={"id": ids[1], "caption": "江边的风", "isCover": True},
    ).json()
    assert body["code"] == 200
    assert body["data"]["captionSource"] == "manual"
    assert body["data"]["aiState"] == "manual"
    assert body["data"]["isCover"] is True

    entry = client.post(
        "/entry/get", headers=auth_headers(token), json={"date": "2026-11-22"}
    ).json()["data"]
    covers = [photo["id"] for photo in entry["photos"] if photo["isCover"]]
    assert covers == [ids[1]]


def test_delete_photo(client, crypt):
    token = bearer(client, crypt)
    photo_id = upload_photo(client, token)["data"]["photos"][0]["id"]
    assert (
        client.post("/photo/delete", headers=auth_headers(token), json={"id": photo_id}).json()[
            "code"
        ]
        == 200
    )
    assert (
        client.post("/photo/list", headers=auth_headers(token), json={}).json()["data"] == []
    )


def test_list_pagination_structure(client, crypt):
    token = bearer(client, crypt)
    for day in range(1, 4):
        save_entry(client, token, entry_date=f"2026-11-0{day}", note=f"第{day}天")
    body = client.post(
        "/entry/list",
        headers=auth_headers(token),
        json={
            "page": {"pageNumber": 1, "pageSize": 2},
            "wheres": [
                {"column": "entry_date", "condition": "ge", "v1": "2026-11-01"},
                {"column": "note", "condition": "andLike", "v1": "天"},
            ],
            "orderBys": [{"column": "entry_date", "condition": "desc"}],
        },
    ).json()
    assert body["data"]["totalRow"] == 3
    assert body["data"]["pageSize"] == 2
    assert len(body["data"]["list"]) == 2
    assert body["data"]["list"][0]["entryDate"] == "2026-11-03"

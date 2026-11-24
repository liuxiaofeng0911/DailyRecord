import asyncio
from datetime import timedelta
from pathlib import Path

from app.db import SessionLocal
from app.models import Photo
from app.services import photo_service
from app.services.timeutil import now_shanghai
from tests.conftest import auth_headers, register_user
from tests.test_entry_photo import save_entry, upload_photo


def bearer(client, crypt):
    return register_user(client, crypt).json()["data"]["token"]


def get_entry(client, token, entry_date="2026-11-22"):
    return client.post(
        "/entry/get", headers=auth_headers(token), json={"date": entry_date}
    ).json()["data"]


def test_trash_soft_delete_and_entry_visibility(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token)
    photo = upload_photo(client, token, entry_date="2026-11-22")["data"]["photos"][0]
    assert photo["origin"] == "upload"

    deleted = client.post(
        "/photo/delete", headers=auth_headers(token), json={"id": photo["id"]}
    ).json()
    assert deleted["code"] == 200
    assert deleted["data"]["purgeAfter"]

    entry = get_entry(client, token)
    assert entry["photos"] == []

    listed = client.post("/photo/list", headers=auth_headers(token), json={}).json()["data"]
    assert listed == []

    trash = client.post("/photo/trash/list", headers=auth_headers(token), json={}).json()
    assert trash["data"]["totalRow"] == 1
    item = trash["data"]["list"][0]
    assert item["id"] == photo["id"]
    assert item["entryDate"] == "2026-11-22"
    assert item["daysLeft"] == 30

    # 回收站内仍可查看缩略图
    thumb = client.get(f"/photo/thumbnail/{photo['id']}", headers=auth_headers(token))
    assert thumb.status_code == 200


def test_restore_returns_to_original_entry(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token)
    photo = upload_photo(client, token, entry_date="2026-11-22")["data"]["photos"][0]
    client.post("/photo/delete", headers=auth_headers(token), json={"id": photo["id"]})

    restored = client.post(
        "/photo/trash/restore", headers=auth_headers(token), json={"ids": [photo["id"]]}
    ).json()
    assert restored["data"]["restored"] == 1
    entry = get_entry(client, token)
    assert [item["id"] for item in entry["photos"]] == [photo["id"]]
    # 封面不自动恢复
    assert entry["photos"][0]["isCover"] is False
    assert (
        client.post("/photo/trash/list", headers=auth_headers(token), json={}).json()["data"][
            "totalRow"
        ]
        == 0
    )


def test_purge_removes_local_file_and_row(client, crypt):
    token = bearer(client, crypt)
    photo = upload_photo(client, token)["data"]["photos"][0]
    client.post("/photo/delete", headers=auth_headers(token), json={"id": photo["id"]})

    with SessionLocal() as db:
        row = db.get(Photo, int(photo["id"]))
        local_path = row.local_path

    body = client.post(
        "/photo/trash/purge", headers=auth_headers(token), json={"ids": [photo["id"]]}
    ).json()
    assert body["data"]["purged"] == 1
    with SessionLocal() as db:
        assert db.get(Photo, int(photo["id"])) is None
    if local_path:
        assert not Path(local_path).exists()


def test_purge_expired_only_removes_due_rows(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token)
    due = upload_photo(client, token, entry_date="2026-11-22")["data"]["photos"][0]
    later = upload_photo(client, token, entry_date="2026-11-22")["data"]["photos"][0]
    for photo_id in (due["id"], later["id"]):
        client.post("/photo/delete", headers=auth_headers(token), json={"id": photo_id})

    with SessionLocal() as db:
        db.get(Photo, int(due["id"])).purge_after = now_shanghai() - timedelta(minutes=1)
        db.get(Photo, int(later["id"])).purge_after = now_shanghai() + timedelta(days=10)
        db.commit()
        result = asyncio.run(photo_service.purge_expired(db))
        assert result["purged"] == 1

    with SessionLocal() as db:
        assert db.get(Photo, int(due["id"])) is None
        assert db.get(Photo, int(later["id"])) is not None


def test_purge_job_is_idempotent_per_day(client, crypt):
    token = bearer(client, crypt)
    photo = upload_photo(client, token)["data"]["photos"][0]
    client.post("/photo/delete", headers=auth_headers(token), json={"id": photo["id"]})
    with SessionLocal() as db:
        db.get(Photo, int(photo["id"])).purge_after = now_shanghai() - timedelta(minutes=1)
        db.commit()
        first = asyncio.run(photo_service.run_purge_job(db, "2026-11-24"))
        assert first["skipped"] is False
        assert first["purged"] == 1
        second = asyncio.run(photo_service.run_purge_job(db, "2026-11-24"))
        assert second["skipped"] is True
        assert second["status"] == "SUCCESS"


def test_stats_excludes_trashed_photos(client, crypt):
    token = bearer(client, crypt)
    save_entry(client, token)
    first = upload_photo(client, token, entry_date="2026-11-22")["data"]["photos"][0]
    upload_photo(client, token, entry_date="2026-11-22")
    client.post("/photo/delete", headers=auth_headers(token), json={"id": first["id"]})

    overview = client.post(
        "/stats/overview", headers=auth_headers(token), json={"year": 2026}
    ).json()["data"]
    assert overview["totals"]["photos"] == 1
    assert overview["days"][0]["photos"] == 1

    client.post(
        "/photo/trash/restore", headers=auth_headers(token), json={"ids": [first["id"]]}
    )
    overview = client.post(
        "/stats/overview", headers=auth_headers(token), json={"year": 2026}
    ).json()["data"]
    assert overview["totals"]["photos"] == 2


class FakeImmichUserClient:
    def __init__(self):
        self.uploads = []

    async def upload_asset(self, filename, content, mime_type, taken_at, album_id=""):
        self.uploads.append({"filename": filename, "album": album_id, "size": len(content)})
        return {"id": "asset-migrated-1"}


def test_migrate_local_photos_to_immich(client, crypt, monkeypatch):
    token = bearer(client, crypt)
    photo = upload_photo(client, token)["data"]["photos"][0]
    with SessionLocal() as db:
        row = db.get(Photo, int(photo["id"]))
        assert row.storage_kind == "local"
        local_path = Path(row.local_path)
        assert local_path.exists()

        fake = FakeImmichUserClient()
        monkeypatch.setattr(
            photo_service.credential_service, "user_client", lambda db, user_id: fake
        )
        monkeypatch.setattr(
            photo_service.credential_service, "album_of", lambda db, user_id: "album-1"
        )
        result = asyncio.run(photo_service.migrate_local_to_immich(db))
        assert result == {"total": 1, "migrated": 1, "failed": []}
        assert fake.uploads[0]["album"] == "album-1"

        row = db.get(Photo, int(photo["id"]))
        assert row.storage_kind == "immich"
        assert row.immich_asset_id == "asset-migrated-1"
        assert row.local_path is None
        assert row.origin == "upload"
        assert not local_path.exists()

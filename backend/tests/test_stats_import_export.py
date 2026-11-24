from datetime import date

from app.services import stats_service
from tests.conftest import auth_headers, register_user


def bearer(crypt, client, userid="owner", email="owner@example.com"):
    return register_user(client, crypt, userid=userid, email=email).json()["data"]["token"]


def save(client, token, day, note="", mood=None, tags=None, version=None):
    payload = {"entryDate": day, "note": note}
    if mood:
        payload["mood"] = mood
    if tags:
        payload["tags"] = tags
    if version is not None:
        payload["version"] = version
    return client.post("/entry/save", headers=auth_headers(token), json=payload).json()


def test_compute_streaks_cross_year(monkeypatch):
    monkeypatch.setattr(stats_service, "today_shanghai", lambda: date(2026, 1, 1))
    days = {date(2025, 12, 30), date(2025, 12, 31), date(2026, 1, 1)}
    current, longest = stats_service.compute_streaks(days)
    assert current == 3
    assert longest == 3


def test_calendar_and_overview_consistency(client, crypt):
    token = bearer(crypt, client)
    save(client, token, "2026-11-20", note="跑步", mood="开心", tags=["运动", "晨间"])
    save(client, token, "2026-11-21", note="读书", mood="平静", tags=["运动"])
    save(client, token, "2026-12-01", note="跨月", mood="平静", tags=["冬天"])

    calendar = client.post(
        "/entry/calendar", headers=auth_headers(token), json={"year": 2026}
    ).json()["data"]
    assert calendar["totals"]["days"] == 3
    assert calendar["months"][10]["days"] == 2
    assert calendar["months"][11]["days"] == 1
    assert len(calendar["days"]) == 3

    overview = client.post(
        "/stats/overview", headers=auth_headers(token), json={"year": 2026}
    ).json()["data"]
    assert overview["totals"] == calendar["totals"]
    assert overview["months"] == calendar["months"]
    assert overview["topTags"][0] == {"name": "运动", "count": 2}


def test_calendar_leap_year(client, crypt):
    token = bearer(crypt, client)
    save(client, token, "2028-02-29", note="闰年")
    body = client.post(
        "/entry/calendar", headers=auth_headers(token), json={"year": 2028}
    ).json()
    assert body["code"] == 200
    assert body["data"]["months"][1]["days"] == 1
    assert len(body["data"]["months"]) == 12


def test_stats_isolation(client, crypt, db):
    from tests.conftest import set_switch

    token_a = bearer(crypt, client)
    save(client, token_a, "2026-11-20", note="A")
    set_switch(db, "DAILYRECORD_REGISTER_MODE", "OPEN")
    token_b = bearer(crypt, client, userid="other", email="other@example.com")
    body = client.post(
        "/stats/overview", headers=auth_headers(token_b), json={"year": 2026}
    ).json()
    assert body["data"]["totals"]["days"] == 0


def test_immich_status_and_unavailable(client, crypt):
    token = bearer(crypt, client)
    status = client.post("/immich/status", headers=auth_headers(token)).json()["data"]
    assert status["enabled"] is False

    assets = client.post(
        "/immich/assets", headers=auth_headers(token), json={"date": "2026-11-20"}
    ).json()
    assert assets["code"] == 1010

    imported = client.post(
        "/immich/import", headers=auth_headers(token), json={"date": "2026-11-20"}
    ).json()
    assert imported["code"] == 1010


def test_export_json_and_markdown(client, crypt):
    token = bearer(crypt, client)
    save(client, token, "2026-11-20", note="第一条记录", mood="开心", tags=["生活"])
    save(client, token, "2026-11-21", note="第二条记录")

    json_body = client.post(
        "/export",
        headers=auth_headers(token),
        json={"format": "json", "start": "2026-11-01", "end": "2026-11-30"},
    ).json()["data"]
    assert json_body["count"] == 2
    assert '"第一条记录"' in json_body["content"]

    md_body = client.post(
        "/export",
        headers=auth_headers(token),
        json={"format": "markdown", "start": "2026-11-01", "end": "2026-11-30"},
    ).json()["data"]
    assert "## 2026-11-20" in md_body["content"]
    assert "第一条记录" in md_body["content"]


def test_search_note_and_caption(client, crypt):
    token = bearer(crypt, client)
    save(client, token, "2026-11-20", note="江边的风很大")
    save(client, token, "2026-11-21", note="在家读书")
    body = client.post(
        "/search", headers=auth_headers(token), json={"keyword": "江边"}
    ).json()
    assert body["data"]["totalRow"] == 1
    assert body["data"]["list"][0]["note"] == "江边的风很大"

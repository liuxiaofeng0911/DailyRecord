from app.config import settings


def test_health_reports_version(client, monkeypatch):
    monkeypatch.setattr(settings, "app_version", "9.9.9")
    body = client.get("/health").json()
    assert body["code"] == 200
    assert body["data"]["status"] == "ok"
    assert body["data"]["version"] == "9.9.9"

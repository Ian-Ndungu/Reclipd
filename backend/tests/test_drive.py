from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select

from app import drive, main
from app.config import settings
from app.models import DriveConnection, Project, User


def configure(monkeypatch):
    monkeypatch.setattr(settings(), "google_drive_client_id", "client-id")
    monkeypatch.setattr(settings(), "google_drive_client_secret", "client-secret")
    monkeypatch.setattr(settings(), "app_url", "https://studio.example.test")


def test_drive_is_unavailable_without_server_credentials(signed):
    status = signed.get("/api/integrations/google-drive/status")
    assert status.status_code == 200
    assert status.json() == {"enabled": False, "connected": False}
    assert signed.post("/api/integrations/google-drive/authorize").status_code == 503


def test_authorize_uses_signed_state_and_exact_callback(signed, monkeypatch):
    configure(monkeypatch)
    result = signed.post("/api/integrations/google-drive/authorize")
    assert result.status_code == 200
    url = result.json()["authorization_url"]
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert query["redirect_uri"] == ["https://studio.example.test/api/integrations/google-drive/callback"]
    assert query["scope"] == [drive.SCOPE]
    assert query["state"]


def test_callback_encrypts_tokens_and_project_uses_selected_drive_file(signed, db, monkeypatch):
    configure(monkeypatch)
    state = parse_qs(urlsplit(signed.post("/api/integrations/google-drive/authorize").json()["authorization_url"]).query)["state"][0]
    monkeypatch.setattr(drive, "exchange_code", lambda code: {"refresh_token": "refresh", "access_token": "access", "expires_in": 3600})
    callback = signed.get("/api/integrations/google-drive/callback", params={"state": state, "code": "code"}, follow_redirects=False)
    assert callback.status_code == 303
    user = db.scalar(select(User))
    connection = db.get(DriveConnection, user.id)
    assert connection and connection.refresh_token != "refresh"
    assert drive.reveal(connection.refresh_token) == "refresh"
    monkeypatch.setattr(drive, "file_metadata", lambda *args: {"id": "abc_123", "name": "Original.mp4", "mimeType": "video/mp4", "size": 42})
    enqueued = []
    monkeypatch.setattr(main, "enqueue_project", lambda _db, project: enqueued.append(project.id))
    response = signed.post("/api/integrations/google-drive/projects", json={
        "file_id": "abc_123", "name": "Drive project", "rights_confirmed": True,
        "config": {"workflow": "ai", "clip_count": 3, "min_duration": 10, "max_duration": 30},
    })
    assert response.status_code == 201
    project = db.get(Project, response.json()["id"])
    assert project.import_url == "gdrive://abc_123"
    assert project.id in enqueued


def test_drive_file_listing_never_exposes_credentials(signed, db, monkeypatch):
    configure(monkeypatch)
    user = db.scalar(select(User))
    db.add(DriveConnection(user_id=user.id, refresh_token=drive.protect("refresh")))
    db.commit()
    monkeypatch.setattr(drive, "drive_request", lambda *args, **kwargs: type("Response", (), {"status_code": 200, "json": lambda self: {"files": [{"id": "abc", "name": "Source.mp4", "mimeType": "video/mp4", "size": "12"}]}})())
    result = signed.get("/api/integrations/google-drive/files")
    assert result.status_code == 200
    assert result.json() == [{"id": "abc", "name": "Source.mp4", "size": 12, "mime_type": "video/mp4", "duration_ms": None, "supported": True}]
    assert "refresh" not in result.text

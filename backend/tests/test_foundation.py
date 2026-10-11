from app.models import Project, User, Clip
from app.schemas import ProjectConfig, EditDecision
from app.security import validate_url
from app.config import settings
from app.storage import storage
from pydantic import ValidationError
import pytest


def test_auth_cookie_logout_and_uniqueness(client):
    payload = {
        "name": "Alex",
        "email": "Alex@example.com",
        "password": "secure-test-password",
    }
    result = client.post("/api/auth/register", json=payload)
    assert result.status_code == 201
    assert "HttpOnly" in result.headers["set-cookie"]
    assert "password_hash" not in result.json()
    assert client.get("/api/me").json()["email"] == "alex@example.com"
    assert client.post("/api/auth/register", json=payload).status_code == 409
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={**payload, "password": "wrong-password"}
        ).status_code
        == 401
    )
    assert client.post("/api/auth/login", json=payload).status_code == 200


def test_upload_rights_type_and_persistence(signed):
    assert (
        signed.post(
            "/api/projects/upload",
            data={"name": "X", "rights_confirmed": "false"},
            files={"file": ("x.mp4", b"media")},
        ).status_code
        == 422
    )
    assert (
        signed.post(
            "/api/projects/upload",
            data={"name": "X", "rights_confirmed": "true"},
            files={"file": ("x.exe", b"media")},
        ).status_code
        == 415
    )
    result = signed.post(
        "/api/projects/upload",
        data={"name": "Interview", "rights_confirmed": "true"},
        files={"file": ("../../x.mp4", b"media")},
    )
    assert result.status_code == 201
    p = result.json()
    assert p["status"] == "queued"
    assert signed.get("/api/projects/" + p["id"]).json()["name"] == "Interview"
    assert len(signed.get("/api/projects").json()) == 1


def test_owner_isolation(signed, db):
    other = User(email="other@example.com", name="Other", password_hash="unused")
    db.add(other)
    db.flush()
    p = Project(user_id=other.id, name="Private", rights_confirmed=True)
    db.add(p)
    db.commit()
    assert signed.get("/api/projects/" + p.id).status_code == 404
    assert signed.get("/api/projects/" + p.id + "/media").status_code == 404
    assert signed.post("/api/projects/" + p.id + "/retry").status_code == 404
    assert signed.get("/api/admin").status_code == 403


def test_csrf(signed):
    assert (
        signed.post(
            "/api/auth/logout", headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_url_rejects_private_and_unapproved(monkeypatch):
    with pytest.raises(ValueError):
        validate_url("https://youtube.com/watch?v=abc")
    monkeypatch.setattr(settings(), "import_allowed_hosts", ["media.example"])
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))]
    )
    with pytest.raises(ValueError):
        validate_url("https://media.example/video.mp4")
    with pytest.raises(ValueError):
        validate_url("https://user:pass@media.example/video.mp4")


def test_traversal_and_configuration():
    with pytest.raises(ValueError):
        storage.path("../secret")
    with pytest.raises(ValidationError):
        ProjectConfig(min_duration=60, max_duration=15)
    with pytest.raises(ValidationError):
        EditDecision(segments=[{"start": 20, "end": 10}])


def test_concurrent_edit_revision(signed, db):
    uid = signed.get("/api/me").json()["id"]
    p = Project(
        user_id=uid, name="Test", rights_confirmed=True, media={"duration": 100}
    )
    db.add(p)
    db.flush()
    c = Clip(
        project_id=p.id,
        title="clip",
        start=0,
        end=30,
        score=50,
        description="test",
        edits={},
    )
    db.add(c)
    db.commit()
    payload = {"revision": 0, "edits": {"segments": [{"start": 1, "end": 20}]}}
    assert signed.put("/api/clips/" + c.id, json=payload).status_code == 200
    assert signed.put("/api/clips/" + c.id, json=payload).status_code == 409
    payload["revision"] = 1
    payload["edits"]["segments"][0]["end"] = 101
    assert signed.put("/api/clips/" + c.id, json=payload).status_code == 422


def test_upload_rejects_anonymous_before_parsing(client):
    assert (
        client.post(
            "/api/projects/upload",
            content=b"not multipart",
            headers={"content-type": "multipart/form-data"},
        ).status_code
        == 401
    )


def test_nonfinite_edit_decisions_are_rejected():
    with pytest.raises(ValidationError):
        EditDecision(segments=[{"start": 0, "end": float("inf")}])

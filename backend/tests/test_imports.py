import pytest
from sqlalchemy import select
from app import imports, main, media
from app.config import settings
from app.models import Project


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abcdefghijk",
        "https://youtu.be/abcdefghijk?si=shared",
        "https://www.youtube.com/shorts/abcdefghijk",
    ],
)
def test_supported_youtube_formats(url):
    assert imports.youtube_id(url) == "abcdefghijk"


@pytest.mark.parametrize(
    "url",
    [
        "http://youtu.be/abcdefghijk",
        "https://youtu.be/short",
        "https://www.youtube.com/playlist?list=x",
        "https://www.youtube.com/watch?v=abcdefghijk&v=12345678901",
        "https://user:password@youtu.be/abcdefghijk",
        "https://youtu.be:444/abcdefghijk",
    ],
)
def test_invalid_youtube_formats(url):
    with pytest.raises(ValueError):
        imports.youtube_id(url)


def test_metadata_uses_official_fixed_endpoint_and_does_not_grant_media(monkeypatch):
    monkeypatch.setattr(settings(), "youtube_api_key", "test-key")

    def get(self, url, **kwargs):
        assert url == "https://www.googleapis.com/youtube/v3/videos"
        assert kwargs["params"]["id"] == "abcdefghijk"
        import httpx

        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "snippet": {
                            "title": "Test title",
                            "channelTitle": "Test channel",
                            "thumbnails": {
                                "medium": {
                                    "url": "https://i.ytimg.com/vi/abcdefghijk/mqdefault.jpg"
                                }
                            },
                        },
                        "contentDetails": {"duration": "PT1H2M3S"},
                    }
                ]
            },
        )

    monkeypatch.setattr(imports.httpx.Client, "get", get)
    result = imports.inspect_import("https://youtu.be/abcdefghijk")
    assert result["duration"] == 3723 and result["title"] == "Test title"
    assert not result["available"]
    assert "metadata only" in result["message"]


def test_missing_key_and_unsupported_sources(signed, monkeypatch):
    monkeypatch.setattr(settings(), "youtube_api_key", "")
    preview = signed.post(
        "/api/imports/preview", json={"url": "https://youtu.be/abcdefghijk"}
    )
    assert preview.status_code == 200
    assert not preview.json()["available"]
    assert "YOUTUBE_API_KEY" in preview.json()["metadata_error"]
    response = signed.post(
        "/api/projects/import",
        json={
            "name": "Test",
            "url": "https://youtu.be/abcdefghijk",
            "rights_confirmed": True,
        },
    )
    assert response.status_code == 422
    for url in [
        "https://youtube.com.evil.test/watch?v=abcdefghijk",
        "https://127.0.0.1/video.mp4",
    ]:
        assert not signed.post("/api/imports/preview", json={"url": url}).json()[
            "available"
        ]


def test_authorized_source_creates_existing_pipeline_job(signed, db, monkeypatch):
    monkeypatch.setattr(settings(), "youtube_api_key", "")
    monkeypatch.setattr(settings(), "import_allowed_hosts", ["media.example.test"])
    monkeypatch.setattr(
        "app.security.socket.getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    checks = []
    monkeypatch.setattr(
        imports, "download_authorized", lambda url, path, check_only: checks.append(url)
    )
    enqueued = []
    monkeypatch.setattr(main, "enqueue_project", lambda db, p: enqueued.append(p.id))
    for url, source in [
        ("https://youtu.be/abcdefghijk", "https://media.example.test/source.mp4"),
        ("https://media.example.test/direct.mp4", None),
    ]:
        data = {"url": url, "source_url": source}
        preview = signed.post("/api/imports/preview", json=data)
        assert preview.status_code == 200 and preview.json()["available"]
        response = signed.post(
            "/api/projects/import",
            json={**data, "name": "Authorized source", "rights_confirmed": True},
        )
        assert response.status_code == 201
        p = db.get(Project, response.json()["id"])
        assert p.import_url == (source or url)
        assert p.id in enqueued and p.status == "queued"
    assert len(checks) == 2


def test_head_preflight_and_download_use_same_pinned_transport(tmp_path, monkeypatch):
    monkeypatch.setattr(
        media, "validate_url", lambda url: ("media.example.test", ["93.184.216.34"])
    )
    requests = []

    class Response:
        status = 200

        def getheader(self, key, default=""):
            return {"Content-Type": "video/mp4", "Content-Length": "5"}.get(
                key, default
            )

        def read(self, n):
            if getattr(self, "done", False):
                return b""
            self.done = True
            return b"video"

    monkeypatch.setattr(
        media.http.client.HTTPSConnection,
        "request",
        lambda self, method, path, headers: requests.append(method),
    )
    monkeypatch.setattr(
        media.http.client.HTTPSConnection, "getresponse", lambda self: Response()
    )
    monkeypatch.setattr(media.http.client.HTTPSConnection, "close", lambda self: None)
    media.download_authorized(
        "https://media.example.test/source.mp4", None, check_only=True
    )
    output = tmp_path / "source.mp4"
    media.download_authorized("https://media.example.test/source.mp4", output)
    assert requests == ["HEAD", "GET"] and output.read_bytes() == b"video"


def test_connected_original_is_owner_scoped_and_reuses_pipeline(
    signed, db, monkeypatch
):
    from app.models import User
    from app.storage import storage

    user = db.scalar(select(User))
    original = Project(
        user_id=user.id,
        name="My original",
        rights_confirmed=True,
        status="ready",
        source_key="sources/connected-original.mp4",
        media={"duration": 20},
    )
    db.add(original)
    db.commit()
    storage.path(original.source_key).write_bytes(b"owned source")
    url = "https://youtu.be/abcdefghijk"
    connected = signed.put(
        "/api/imports/connection",
        json={"url": url, "project_id": original.id, "rights_confirmed": True},
    )
    assert connected.status_code == 200
    monkeypatch.setattr(settings(), "youtube_api_key", "")
    preview = signed.post("/api/imports/preview", json={"url": url}).json()
    assert preview["available"] and preview["provider"] == "connected-original"
    response = signed.post(
        "/api/projects/import",
        json={"name": "Connected import", "url": url, "rights_confirmed": True},
    )
    assert response.status_code == 201
    imported = db.get(Project, response.json()["id"])
    assert imported.source_key == original.source_key and imported.import_url is None
    signed.post("/api/auth/logout")
    signed.post(
        "/api/auth/register",
        json={
            "name": "Other",
            "email": "connection-other@example.com",
            "password": "safe-password-123",
        },
    )
    assert not signed.post("/api/imports/preview", json={"url": url}).json()[
        "available"
    ]
    assert (
        signed.put(
            "/api/imports/connection",
            json={"url": url, "project_id": original.id, "rights_confirmed": True},
        ).status_code
        == 404
    )


def test_missing_connected_source_does_not_claim_success(signed, db, monkeypatch):
    from app.models import User, SourceConnection

    user = db.scalar(select(User))
    p = Project(
        user_id=user.id,
        name="Missing",
        rights_confirmed=True,
        status="ready",
        source_key="sources/missing-connection.mp4",
    )
    db.add(p)
    db.flush()
    db.add(SourceConnection(user_id=user.id, video_id="abcdefghijk", project_id=p.id))
    db.commit()
    monkeypatch.setattr(settings(), "youtube_api_key", "")
    preview = signed.post(
        "/api/imports/preview", json={"url": "https://youtu.be/abcdefghijk"}
    ).json()
    assert not preview["available"] and "unavailable" in preview["message"]

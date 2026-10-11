import pytest
from app.youtube import validate_public, download
from app.config import settings
from app import imports


def public_info(**changes):
    return dict(id="abcdefghijk", availability="public", age_limit=0,
                duration=20, live_status="not_live", **changes)


def test_public_video_policy():
    validate_public(public_info(), "abcdefghijk", 60)
    for field, value in [("availability", "private"), ("availability", "unlisted"),
                         ("availability", "subscriber_only"), ("availability", None),
                         ("age_limit", 18), ("has_drm", True), ("duration", 100),
                         ("live_status", "is_live"), ("id", "wrong")]:
        info = public_info()
        info[field] = value
        with pytest.raises(ValueError):
            validate_public(info, "abcdefghijk", 60)


def test_provider_flag_and_preflight(monkeypatch):
    class DB:
        def get(self, *args): return None
    monkeypatch.setattr(settings(), "youtube_download_enabled", True)
    monkeypatch.setattr(imports, "metadata", lambda _: {"title": "Public example"})
    monkeypatch.setattr(imports, "download_authorized", lambda *a, **k: pytest.fail("YouTube must not enter direct importer"))
    result = imports.inspect_import("https://youtu.be/abcdefghijk", user_id="owner", db=DB())
    assert result["available"] and result["provider"] == "youtube-public"
    assert "attempted" in result["message"]
    monkeypatch.setattr(settings(), "youtube_download_enabled", False)
    assert not imports.inspect_import("https://youtu.be/abcdefghijk", user_id="owner", db=DB())["available"]


def test_download_policy_and_success_adapter(monkeypatch, tmp_path):
    import yt_dlp
    import json
    info = public_info()
    info["formats"] = [
        {"url": "https://rr1.googlevideo.com/video", "protocol": "https"},
        {"url": "http://127.0.0.1/private", "protocol": "http"},
        {"url": "https://evil.example/video", "protocol": "https"},
        {"url": "https://rr1.googlevideo.com/drm", "protocol": "https", "has_drm": True},
    ]
    class YDL:
        def __init__(self, options):
            self.hook = options["progress_hooks"][0]
            assert options["cookiefile"] is None and not options["usenetrc"]
            assert not options["geo_bypass"] and not options["allow_unplayable_formats"]
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, url, download):
            assert url == "https://www.youtube.com/watch?v=abcdefghijk" and not download
            return info
        def process_ie_result(self, selected, download):
            assert len(selected["formats"]) == 1 and download
            self.hook({"filename": "video", "downloaded_bytes": 2 * 1024 * 1024})
            self.hook({"filename": "audio", "downloaded_bytes": 1024 * 1024})
            self.hook({"filename": "video", "downloaded_bytes": 2 * 1024 * 1024})
            (tmp_path / "source.mp4").write_bytes(b"fixture media")
    monkeypatch.setattr(yt_dlp, "YoutubeDL", YDL)
    download("abcdefghijk", str(tmp_path), 4 * 1024 * 1024, 60)
    assert json.loads((tmp_path / "result.json").read_text())["file"] == "source.mp4"
    assert "3 MB" in json.loads((tmp_path / "progress.json").read_text())["stage"]
    info["availability"] = "private"
    with pytest.raises(ValueError):
        download("abcdefghijk", str(tmp_path), 1024, 60)


def test_retrieve_moves_source_and_cleans_temporary_files(monkeypatch, tmp_path):
    from app import youtube
    import json
    from pathlib import Path
    monkeypatch.setattr(settings(), "youtube_download_enabled", True)
    class Process:
        returncode = 0
        def __init__(self, args, **kwargs):
            assert kwargs["start_new_session"] is True
            folder = Path(args[4])
            (folder / "source.mp4").write_bytes(b"test media")
            (folder / "result.json").write_text(json.dumps({"file": "source.mp4"}))
        def poll(self): return 0
    monkeypatch.setattr(youtube.subprocess, "Popen", Process)
    target = tmp_path / "video.mp4"
    youtube.retrieve("abcdefghijk", target, lambda *a: None)
    assert target.read_bytes() == b"test media"
    assert list(tmp_path.iterdir()) == [target]


def test_retrieve_timeout_kills_group_and_cleans(monkeypatch, tmp_path):
    from app import youtube
    monkeypatch.setattr(settings(), "youtube_download_enabled", True)
    monkeypatch.setattr(settings(), "youtube_download_timeout", 30)
    killed = []
    class Process:
        pid = 123456
        def __init__(self, *a, **kw): pass
        def poll(self): return None
        def wait(self): pass
    ticks = iter([0, 31])
    monkeypatch.setattr(youtube.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(youtube.subprocess, "Popen", Process)
    monkeypatch.setattr(youtube.os, "killpg", lambda *a: killed.append(a))
    with pytest.raises(youtube.MediaError, match="timed out"):
        youtube.retrieve("abcdefghijk", tmp_path / "video.mp4", lambda *a: None)
    assert killed and not list(tmp_path.iterdir())


def test_import_requires_rights_and_queues_canonical_url(signed, db, monkeypatch):
    from app.models import Project
    monkeypatch.setattr(settings(), "youtube_download_enabled", True)
    body = {"name": "Public source", "url": "https://youtu.be/abcdefghijk?list=ignored", "rights_confirmed": False}
    assert signed.post("/api/projects/import", json=body).status_code == 422
    body["rights_confirmed"] = True
    response = signed.post("/api/projects/import", json=body)
    assert response.status_code == 201
    project = db.get(Project, response.json()["id"])
    assert project.import_url == "https://www.youtube.com/watch?v=abcdefghijk"
    assert project.rights_confirmed and project.source_key is None

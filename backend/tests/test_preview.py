from sqlalchemy import select
from app.models import Project, Clip, User
from app.schemas import EditDecision
from app.storage import storage
from app import media


def test_preview_cache_ranges_and_ownership(signed, db, monkeypatch):
    user = db.scalar(select(User))
    p = Project(
        user_id=user.id,
        name="Preview",
        rights_confirmed=True,
        source_key="sources/preview-test.mp4",
        media={"duration": 300},
    )
    db.add(p)
    db.flush()
    c = Clip(
        project_id=p.id,
        title="Clip",
        start=20,
        end=30,
        score=50,
        description="",
        reasons=[],
        headlines=[],
        edits=EditDecision(segments=[{"start": 20, "end": 30}]).model_dump(),
    )
    db.add(c)
    db.commit()
    storage.path(p.source_key).write_bytes(b"source")
    calls = []

    def encode(source, output, start, end):
        calls.append((start, end))
        output.write_bytes(b"0123456789")

    monkeypatch.setattr(media, "browser_preview", encode)
    url = f"/api/clips/{c.id}/preview?start=20&end=30"
    assert signed.get(url).content == b"0123456789"
    response = signed.get(url, headers={"Range": "bytes=2-5"})
    assert response.status_code == 206 and response.content == b"2345"
    assert calls == [(20, 30)]
    for query in [
        "start=nan&end=30",
        "start=-1&end=30",
        "start=0&end=181",
        "start=299&end=301",
    ]:
        assert signed.get(f"/api/clips/{c.id}/preview?{query}").status_code == 422
    signed.post("/api/auth/logout")
    assert signed.get(url).status_code == 401
    signed.post(
        "/api/auth/register",
        json={
            "name": "Other",
            "email": "other-preview@example.com",
            "password": "test-password-123",
        },
    )
    assert signed.get(url).status_code == 404


def test_browser_preview_encodes_exact_short_range(tmp_path):
    import shutil
    import pytest

    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg required")
    source = tmp_path / "source.mkv"
    output = tmp_path / "preview.mp4"
    media.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=15",
            "-t",
            "4",
            "-c:v",
            "ffv1",
            str(source),
        ]
    )
    media.browser_preview(source, output, 1, 3)
    result = media.probe(output)
    assert result["codec"] == "h264"
    assert abs(result["duration"] - 2) < 0.2
    data = output.read_bytes()
    assert data.index(b"moov") < data.index(b"mdat")

from io import BytesIO
from PIL import Image
from app.models import Asset, User, BrandKit


def test_logo_upload_is_normalized_and_owned(signed, db):
    content = BytesIO()
    Image.new("RGB", (20, 20), "blue").save(content, "JPEG")
    result = signed.post(
        "/api/assets",
        data={"kind": "logo", "rights_confirmed": "true"},
        files={"file": ("../../logo.jpg", content.getvalue(), "image/jpeg")},
    )
    assert result.status_code == 201
    asset = result.json()
    assert asset["name"] == "logo.jpg"
    downloaded = signed.get("/api/assets/" + asset["id"])
    assert downloaded.status_code == 200 and downloaded.content.startswith(b"\x89PNG")
    other = User(email="outsider@example.com", name="Other", password_hash="unused")
    db.add(other)
    db.flush()
    db.get(Asset, asset["id"]).user_id = other.id
    db.commit()
    assert signed.get("/api/assets/" + asset["id"]).status_code == 404
    assert (
        signed.post(
            "/api/brands", json={"name": "Bad kit", "logo_asset_id": asset["id"]}
        ).status_code
        == 404
    )


def test_invalid_font_and_rights_rejected(signed):
    result = signed.post(
        "/api/assets",
        data={"kind": "font", "rights_confirmed": "true"},
        files={"file": ("bad.ttf", b"not a font")},
    )
    assert result.status_code == 422
    result = signed.post(
        "/api/assets",
        data={"kind": "logo", "rights_confirmed": "false"},
        files={"file": ("image.png", b"bad")},
    )
    assert result.status_code == 422


def test_admin_retry_is_protected(signed):
    assert signed.post("/api/admin/projects/missing/retry").status_code == 403


def test_builtin_font_endpoint_is_allowlisted(signed):
    assert signed.get("/api/fonts/not-a-font").status_code == 404
    assert signed.get("/api/fonts/..%2F..%2Fetc%2Fpasswd").status_code == 404

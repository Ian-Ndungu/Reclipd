from app.uploads import CHUNK
from app.models import Project
from sqlalchemy import select

def begin(client, **overrides):
    return client.post("/api/uploads", json=dict(
        name="Test", filename="test.mp4", size=10, fingerprint="a"*64,
        rights_confirmed=True, config={"workflow":"manual"}, **overrides))

def test_resume_idempotency_and_completion(signed, db):
    first = begin(signed).json()
    url = "/api/uploads/" + first["id"]
    assert signed.put(url+"/0", files={"file":("chunk", b"12345")}).json()["offset"] == 5
    assert begin(signed).json()["offset"] == 5
    assert signed.put(url+"/0", files={"file":("chunk", b"12345")}).json()["offset"] == 5
    assert signed.put(url+"/0", files={"file":("chunk", b"wrong")}).status_code == 409
    assert signed.post(url+"/complete").status_code == 409
    assert signed.put(url+"/5", files={"file":("chunk", b"67890")}).status_code == 200
    a = signed.post(url+"/complete")
    b = signed.post(url+"/complete")
    assert a.status_code == b.status_code == 200
    assert a.json()["id"] == b.json()["id"] == first["id"]
    assert len(list(db.scalars(select(Project)))) == 1

def test_ownership_and_bounds(signed):
    session = begin(signed).json()["id"]
    url = "/api/uploads/" + session
    assert signed.put(url+"/0", files={"file":("chunk", b"x"*11)}).status_code == 413
    assert signed.put(url+"/0", files={"file":("chunk", b"x"*(CHUNK+1))}).status_code == 413
    signed.post("/api/auth/logout")
    signed.post("/api/auth/register", json={"name":"Other","email":"other@example.com","password":"another-password"})
    assert signed.get(url).status_code == 404
    assert signed.post(url+"/complete").status_code == 404

def test_expiration_cleanup(signed):
    import time
    from app.uploads import locked, cleanup_uploads, save
    from app.storage import storage
    session = begin(signed).json()["id"]
    signed.put(f"/api/uploads/{session}/0", files={"file":("chunk", b"123")})
    path = next(storage.path("uploads/lock").parent.glob(f"*/{session}.json"))
    import json
    data = json.loads(path.read_text())
    data["expires"] = time.time()-1
    save(path, data)
    assert signed.get(f"/api/uploads/{session}").status_code == 410
    cleanup_uploads()
    assert not path.exists()
    assert not path.with_suffix(".part").exists()

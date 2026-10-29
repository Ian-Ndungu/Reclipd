"""Bounded, owner-scoped resumable uploads on the existing shared local storage."""
import fcntl
import hashlib
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import Project, User
from .schemas import ProjectConfig
from .security import current_user
from .storage import storage

router = APIRouter(prefix="/api/uploads")
CHUNK = 8 * 1024 * 1024
TTL = 24 * 3600


class Start(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    rights_confirmed: bool
    config: ProjectConfig = Field(default_factory=ProjectConfig)


@contextmanager
def locked(user_id):
    root = storage.path(f"uploads/{user_id}/lock").parent
    with (root / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield root


def save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


def purge(root):
    for path in root.glob("*.json"):
        data = json.loads(path.read_text())
        if data["expires"] < time.time():
            path.with_suffix(".part").unlink(missing_ok=True)
            path.unlink()


def cleanup_uploads():
    root = storage.path("uploads/lock").parent
    for directory in root.iterdir():
        if directory.is_dir():
            with locked(directory.name) as folder:
                purge(folder)


def read(root, upload_id):
    path = root / f"{upload_id}.json"
    if not path.exists():
        raise HTTPException(404, "Upload expired. Select the file again to restart.")
    data = json.loads(path.read_text())
    if data["expires"] < time.time():
        raise HTTPException(410, "Upload expired. Select the file again to restart.")
    return path, data


def state(root, data):
    part = root / f'{data["id"]}.part'
    return {"id": data["id"], "offset": part.stat().st_size if part.exists() else 0,
            "chunk_size": CHUNK, "project_id": data.get("project_id")}


@router.post("")
def start(body: Start, user: User = Depends(current_user)):
    if not body.rights_confirmed:
        raise HTTPException(422, "Confirm that you have the rights to use this media")
    if body.size > settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "Upload exceeds size limit")
    if Path(body.filename).suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise HTTPException(415, "Use MP4, MOV, MKV or WebM")
    payload = body.model_dump()
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with locked(user.id) as root:
        purge(root)
        sessions = [json.loads(p.read_text()) for p in root.glob("*.json")]
        for data in sessions:
            if data["signature"] == signature and not data.get("project_id"):
                return state(root, data)
        if sum(not s.get("project_id") for s in sessions) >= 2:
            raise HTTPException(429, "Two uploads are already saved. Resume one or wait 24 hours for it to expire.")
        data = dict(payload, id=str(uuid.uuid4()), signature=signature, expires=time.time()+TTL)
        save(root / f'{data["id"]}.json', data)
        return state(root, data)


@router.get("/{upload_id}")
def status(upload_id: uuid.UUID, user: User = Depends(current_user)):
    with locked(user.id) as root:
        _, data = read(root, upload_id)
        return state(root, data)


@router.put("/{upload_id}/{offset}")
def chunk(upload_id: uuid.UUID, offset: int, file: UploadFile = File(...),
          user: User = Depends(current_user)):
    try:
        content = file.file.read(CHUNK + 1)
    finally:
        file.file.close()
    if not content or len(content) > CHUNK or offset < 0:
        raise HTTPException(413, "Invalid upload chunk size")
    with locked(user.id) as root:
        path, data = read(root, upload_id)
        if data.get("project_id"):
            return state(root, data)
        part = path.with_suffix(".part")
        actual = part.stat().st_size if part.exists() else 0
        if offset < actual:
            with part.open("rb") as stream:
                stream.seek(offset)
                if stream.read(len(content)) == content and offset+len(content) <= actual:
                    return state(root, data)
        if offset != actual:
            raise HTTPException(409, "Upload offset changed. Resume from saved progress.")
        if actual + len(content) > data["size"]:
            raise HTTPException(413, "Upload exceeds declared file size")
        with part.open("ab") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        data["expires"] = time.time() + TTL
        save(path, data)
        return state(root, data)


@router.post("/{upload_id}/complete")
def complete(upload_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .main import admission, enqueue_project, project_out
    with locked(user.id) as root:
        path, data = read(root, upload_id)
        existing = db.get(Project, str(upload_id))
        if existing:
            if existing.user_id != user.id:
                raise HTTPException(404)
            return project_out(existing)
        part = path.with_suffix(".part")
        key = f"sources/{upload_id}{Path(data['filename']).suffix.lower()}"
        target = storage.path(key)
        source = part if part.exists() else target
        if not source.exists() or source.stat().st_size != data["size"]:
            raise HTTPException(409, "Upload is incomplete. Resume uploading before creating the project.")
        admission(db, user, charge=data["config"]["workflow"] != "manual")
        if source == part:
            os.replace(part, target)
        project = Project(id=str(upload_id), user_id=user.id, name=data["name"],
                          rights_confirmed=True, config=data["config"], source_key=key)
        db.add(project)
        db.commit()
        data["project_id"] = project.id
        save(path, data)
        enqueue_project(db, project)
        return project_out(project)

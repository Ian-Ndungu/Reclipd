"""Google Drive OAuth and selected-video import.

Only OAuth-authorized files are accessed. Tokens are encrypted at rest using the
application secret and are never returned by an API response.
"""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .media import MediaError
from .models import DriveConnection, Project, User
from .security import current_user

router = APIRouter(prefix="/api/integrations/google-drive", tags=["google-drive"])
SCOPE = "https://www.googleapis.com/auth/drive.readonly"
FILES_URL = "https://www.googleapis.com/drive/v3/files"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def configured():
    cfg = settings()
    return bool(cfg.google_drive_client_id and cfg.google_drive_client_secret)


def redirect_uri():
    return settings().app_url.rstrip("/") + "/api/integrations/google-drive/callback"


def crypt():
    material = hashlib.sha256(settings().secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def protect(value: str):
    return crypt().encrypt(value.encode()).decode()


def reveal(value: str):
    try:
        return crypt().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        raise HTTPException(409, "Your Google Drive connection needs to be reconnected.")


def state_for(user_id: str):
    return jwt.encode(
        {
            "sub": user_id,
            "purpose": "google-drive",
            "nonce": secrets.token_urlsafe(24),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings().secret_key,
        algorithm="HS256",
    )


def require_configured():
    if not configured():
        raise HTTPException(
            503,
            "Google Drive is not configured yet. Add the server-side Google OAuth client ID and secret first.",
        )


def exchange_code(code: str):
    cfg = settings()
    with httpx.Client(timeout=20, trust_env=False) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": cfg.google_drive_client_id,
                "client_secret": cfg.google_drive_client_secret,
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
    if response.status_code != 200:
        raise HTTPException(422, "Google Drive could not complete authorization. Try connecting again.")
    data = response.json()
    if not isinstance(data.get("refresh_token"), str) or not isinstance(data.get("access_token"), str):
        raise HTTPException(422, "Google Drive did not provide reusable access. Reconnect and approve access again.")
    return data


def access_token(db: Session, user_id: str):
    connection = db.get(DriveConnection, user_id)
    if not connection:
        raise HTTPException(409, "Connect Google Drive before choosing a video.")
    now = datetime.now(timezone.utc)
    expires = connection.access_expires_at
    if connection.access_token and expires and expires > now + timedelta(seconds=60):
        return reveal(connection.access_token)
    cfg = settings()
    with httpx.Client(timeout=20, trust_env=False) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "client_id": cfg.google_drive_client_id,
                "client_secret": cfg.google_drive_client_secret,
                "refresh_token": reveal(connection.refresh_token),
                "grant_type": "refresh_token",
            },
        )
    if response.status_code != 200:
        raise HTTPException(409, "Google Drive access expired or was revoked. Reconnect Drive and try again.")
    data = response.json()
    token = data.get("access_token")
    if not isinstance(token, str):
        raise HTTPException(409, "Google Drive returned an invalid access response. Reconnect and try again.")
    connection.access_token = protect(token)
    connection.access_expires_at = now + timedelta(seconds=max(60, int(data.get("expires_in", 3600))))
    db.commit()
    return token


def drive_request(db: Session, user_id: str, method: str, url: str, **kwargs):
    token = access_token(db, user_id)
    headers = {"Authorization": "Bearer " + token, **kwargs.pop("headers", {})}
    with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
        response = client.request(method, url, headers=headers, **kwargs)
    if response.status_code in {401, 403}:
        raise HTTPException(409, "Google Drive denied access to this file. Reconnect Drive or select another video.")
    return response


def file_metadata(db: Session, user_id: str, file_id: str):
    if not file_id or not all(char.isalnum() or char in "-_" for char in file_id):
        raise HTTPException(422, "Invalid Google Drive file reference")
    response = drive_request(
        db,
        user_id,
        "GET",
        f"{FILES_URL}/{file_id}",
        params={"fields": "id,name,mimeType,size,videoMediaMetadata"},
    )
    if response.status_code != 200:
        raise HTTPException(422, "That Google Drive file is no longer available.")
    data = response.json()
    if not str(data.get("mimeType", "")).startswith("video/"):
        raise HTTPException(422, "Choose a video file from Google Drive.")
    size = int(data.get("size") or 0)
    if size <= 0 or size > settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "This Drive video exceeds the upload size limit.")
    return data


class DriveImportIn(BaseModel):
    file_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=200)
    rights_confirmed: bool
    config: dict


@router.get("/status")
def status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"enabled": configured(), "connected": bool(db.get(DriveConnection, user.id))}


@router.post("/authorize")
def authorize(user: User = Depends(current_user)):
    require_configured()
    params = {
        "client_id": settings().google_drive_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state_for(user.id),
    }
    return {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


@router.get("/callback")
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    destination = settings().app_url.rstrip("/") + "/studio/new"
    if error or not code or not state:
        return RedirectResponse(destination + "?drive=cancelled", status_code=303)
    try:
        payload = jwt.decode(state, settings().secret_key, algorithms=["HS256"])
        if payload.get("purpose") != "google-drive" or payload.get("sub") != user.id:
            raise ValueError()
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(400, "Google Drive authorization state expired. Start the connection again.")
    require_configured()
    data = exchange_code(code)
    connection = db.get(DriveConnection, user.id)
    if not connection:
        connection = DriveConnection(user_id=user.id, refresh_token=protect(data["refresh_token"]))
        db.add(connection)
    else:
        connection.refresh_token = protect(data["refresh_token"])
    connection.access_token = protect(data["access_token"])
    connection.access_expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, int(data.get("expires_in", 3600))))
    db.commit()
    return RedirectResponse(destination + "?drive=connected", status_code=303)


@router.get("/files")
def files(user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_configured()
    response = drive_request(
        db,
        user.id,
        "GET",
        FILES_URL,
        params={
            "q": "trashed = false and mimeType contains 'video/'",
            "orderBy": "modifiedTime desc",
            "pageSize": 50,
            "fields": "files(id,name,mimeType,size,modifiedTime,videoMediaMetadata)",
        },
    )
    if response.status_code != 200:
        raise HTTPException(422, "Could not list Google Drive videos. Try reconnecting Drive.")
    limit = settings().max_upload_mb * 1024 * 1024
    return [
        {
            "id": item["id"], "name": item.get("name", "Untitled video"),
            "size": int(item.get("size") or 0),
            "mime_type": item.get("mimeType", ""),
            "duration_ms": item.get("videoMediaMetadata", {}).get("durationMillis"),
            "supported": 0 < int(item.get("size") or 0) <= limit,
        }
        for item in response.json().get("files", []) if isinstance(item.get("id"), str)
    ]


@router.delete("")
def disconnect(user: User = Depends(current_user), db: Session = Depends(get_db)):
    connection = db.get(DriveConnection, user.id)
    if connection:
        db.delete(connection)
        db.commit()
    return {"ok": True}


def download_video(db: Session, user_id: str, file_id: str, output: Path, progress):
    """Download a user-selected Drive blob inside the existing worker pipeline."""
    metadata = file_metadata(db, user_id, file_id)
    expected = int(metadata["size"])
    token = access_token(db, user_id)
    temp = output.with_suffix(output.suffix + ".part")
    temp.unlink(missing_ok=True)
    try:
        # Keep a client open for the complete stream. This also ensures the worker
        # ignores environment proxy settings for a user-authorized Drive download.
        with httpx.Client(timeout=60, trust_env=False) as client:
            with client.stream(
                "GET", f"{FILES_URL}/{file_id}", params={"alt": "media"},
                headers={"Authorization": "Bearer " + token},
            ) as response:
                if response.status_code != 200:
                    raise MediaError("Google Drive could not download this source. Reconnect Drive and retry.")
                received = 0
                with temp.open("wb") as target:
                    for chunk in response.iter_bytes(1024 * 1024):
                        received += len(chunk)
                        if received > expected or received > settings().max_upload_mb * 1024 * 1024:
                            raise MediaError("Google Drive source exceeds the upload size limit.")
                        target.write(chunk)
                        progress(min(10, 4 + int(6 * received / expected)), "Importing Google Drive video")
        if received != expected:
            raise MediaError("Google Drive returned an incomplete source. Retry the import.")
        temp.replace(output)
    except httpx.HTTPError:
        raise MediaError("Google Drive could not download this source. Retry the import.")
    finally:
        temp.unlink(missing_ok=True)


@router.post("/projects", status_code=201)
def create_project(data: DriveImportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .main import admission, enqueue_project, project_out
    from .schemas import ProjectConfig
    if not data.rights_confirmed:
        raise HTTPException(422, "Confirm that you have the rights to use this media")
    config = ProjectConfig.model_validate(data.config)
    if config.workflow != "ai":
        raise HTTPException(422, "Google Drive imports currently start AI clipping projects.")
    metadata = file_metadata(db, user.id, data.file_id)
    admission(db, user)
    project = Project(
        user_id=user.id,
        name=data.name.strip() or metadata.get("name", "Google Drive video"),
        import_url="gdrive://" + data.file_id,
        rights_confirmed=True,
        config=config.model_dump(),
    )
    db.add(project)
    db.commit()
    enqueue_project(db, project)
    return project_out(project)

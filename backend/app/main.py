import math
import hashlib
import fcntl
import threading
import json
import logging
import time
import uuid
from pathlib import Path
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response,
    UploadFile,
    File,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError
from .config import settings
from .billing import allowance
from . import credits
from .db import get_db
from .models import User, Project, Clip, Export, BrandKit, Asset
from .schemas import (
    AuthIn,
    UserOut,
    ProjectConfig,
    ImportIn,
    SaveEdits,
    BrandIn,
    HeadlineIn,
    ProfileIn,
    EditDecision,
)
from .schemas import (
    ProjectOut,
    ProjectDetail,
    ClipOut,
    ClipDetail,
    ExportOut,
    BrandOut,
    UsageOut,
    HeadlineOut,
)
from .security import passwords, token, current_user, validate_url
import jwt
from .storage import storage

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("reclipd")
app = FastAPI(title="RECLIPD AI Studio", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def safety(request: Request, call_next):
    started = time.monotonic()
    if (
        (request.url.path in ("/api/projects/upload", "/api/assets") and request.method == "POST")
        or (request.url.path.startswith("/api/uploads/") and request.method == "PUT")
    ):
        try:
            jwt.decode(
                request.cookies.get("session", ""),
                settings().secret_key,
                algorithms=["HS256"],
            )
        except jwt.PyJWTError:
            return JSONResponse(
                {"detail": "Please sign in before uploading"}, status_code=401
            )
        raw_length = request.headers.get("content-length")
        if not raw_length or not raw_length.isdigit():
            return JSONResponse(
                {"detail": "A Content-Length header is required for uploads"},
                status_code=411,
            )
        limit = (
            (settings().max_upload_mb + 1) * 1024 * 1024
            if request.url.path.endswith("upload")
            else 9 * 1024 * 1024 if request.url.path.startswith("/api/uploads/")
            else 11 * 1024 * 1024
        )
        if int(raw_length) > limit:
            return JSONResponse(
                {"detail": "Upload exceeds size limit"}, status_code=413
            )
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in settings().cors_origins:
            return JSONResponse({"detail": "Untrusted request origin"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(
                {"detail": "Cross-site request rejected"}, status_code=403
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    log.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    return response


def own_project(db, user, project_id):
    p = db.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id).with_for_update()
    )
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def own_clip(db, user, clip_id):
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    return clip, own_project(db, user, clip.project_id)


def enqueue_project(db, project):
    from .worker import process_project

    try:
        process_project.delay(project.id)
    except Exception:
        project.status = "failed"
        project.error = (
            "The processing queue is unavailable. Retry when the worker is online."
        )
        db.commit()


@app.get("/api/upload-limits")
def upload_limits():
    return {"max_bytes": settings().max_upload_mb * 1024 * 1024, "max_seconds": settings().max_media_seconds}


@app.get("/health")
def health():
    return {"status": "ok"}


def auth_rate_limit(request):
    from redis import Redis

    try:
        r = Redis.from_url(
            settings().redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        key = (
            "auth:"
            + (request.client.host if request.client else "unknown")
            + ":"
            + str(int(time.time() // 60))
        )
        count = r.incr(key)
        if count == 1:
            r.expire(key, 120)
        if count > 20:
            raise HTTPException(429, "Too many requests. Try again in a minute.")
        if request.url.path == "/api/auth/register":
            daily = "signup:" + (request.client.host if request.client else "unknown") + ":" + str(int(time.time() // 86400))
            attempts = r.incr(daily)
            if attempts == 1: r.expire(daily, 172800)
            if attempts > 10:
                raise HTTPException(429, "Signup limit reached for this network. Please try again tomorrow.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Authentication service temporarily unavailable")


def session_response(response, user):
    response.set_cookie(
        "session",
        token(user.id, user.session_version),
        httponly=True,
        secure=settings().cookie_secure,
        samesite="lax",
        max_age=43200,
        path="/",
    )
    return user


@app.post("/api/auth/register", response_model=UserOut, status_code=201)
def register(
    data: AuthIn, request: Request, response: Response, db: Session = Depends(get_db)
):
    auth_rate_limit(request)
    user = User(
        email=data.email, name=data.name, password_hash=passwords.hash(data.password),
        preferences={"onboarding_completed": False}
    )
    user.credit_identity = credits.identity(data.email)
    db.add(user)
    try:
        db.flush()
        credits.sync(db,user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email or mailbox identity already exists")
    return session_response(response, user)


@app.post("/api/auth/login", response_model=UserOut)
def login(
    data: AuthIn, request: Request, response: Response, db: Session = Depends(get_db)
):
    auth_rate_limit(request)
    user = db.scalar(select(User).where(User.email == data.email))
    # Verify a dummy hash as well to reduce account enumeration timing differences.
    valid = passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or user.deleted or not valid:
        raise HTTPException(401, "Email or password is incorrect")
    return session_response(response, user)


DUMMY_HASH = passwords.hash("unused-dummy-password")


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"ok": True}


@app.get("/api/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@app.put("/api/me", response_model=UserOut)
def profile(
    data: ProfileIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    user.name = data.name
    db.commit()
    return user


@app.get("/api/usage")
def usage(user: User = Depends(current_user), db: Session = Depends(get_db)):
    result=credits.balance(db,user)
    from .models import CreditReservation
    history=list(db.scalars(select(CreditReservation).where(CreditReservation.user_id==user.id).order_by(CreditReservation.created_at.desc()).limit(50)))
    result.update({"used_seconds":user.used_seconds,"limit_seconds":None if result['unlimited'] else user.used_seconds+result['available_seconds'],"billing_enabled":False,
        "processing_history":[{"project_id":r.project_id,"name":r.name,"seconds":r.seconds,"status":r.status,"created_at":r.created_at} for r in history]})
    db.commit()
    return result


@app.get("/api/projects", response_model=list[ProjectOut])
def projects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [
        project_out(p)
        for p in db.scalars(
            select(Project)
            .where(Project.user_id == user.id)
            .order_by(Project.created_at.desc())
            .limit(200)
        )
    ]


def project_out(p):
    return {
        "id": p.id,
        "name": p.name,
        "status": p.status,
        "progress": p.progress,
        "stage": p.stage,
        "error": p.error,
        "media": p.media,
        "config": p.config,
        "analysis": p.analysis,
        "created_at": p.created_at,
    }


def admission(db, user, charge=True):
    # Lock user row so concurrent submissions cannot bypass active job limits.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    active = db.scalar(
        select(func.count())
        .select_from(Project)
        .where(Project.user_id == user.id, Project.status.in_(["queued", "processing", "cancelling"]))
    )
    if active >= 2:
        raise HTTPException(429, "You can process two projects at a time")
    if charge and user.id not in settings().unlimited_user_ids and user.used_seconds >= allowance(db, user):
        raise HTTPException(402, "Development processing allowance reached")


@app.post("/api/projects/upload", status_code=201, response_model=ProjectOut)
def upload(
    name: str = Form(..., min_length=1, max_length=200),
    rights_confirmed: bool = Form(...),
    config: str = Form("{}"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not rights_confirmed:
        raise HTTPException(422, "Confirm that you have the rights to use this media")
    try:
        cfg = ProjectConfig.model_validate_json(config)
    except ValidationError as e:
        raise HTTPException(422, str(e))
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise HTTPException(415, "Use MP4, MOV, MKV or WebM")
    admission(db, user, charge=cfg.workflow != "manual")
    project = Project(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name=name,
        rights_confirmed=True,
        config=cfg.model_dump(),
    )
    key = f"sources/{project.id}{extension}"
    path = storage.path(key)
    size = 0
    try:
        with path.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > settings().max_upload_mb * 1024 * 1024:
                    raise HTTPException(413, "Upload exceeds size limit")
                output.write(chunk)
        if not size:
            raise HTTPException(422, "File is empty")
        project.source_key = key
        db.add(project)
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()
    enqueue_project(db, project)
    return project_out(project)


from .imports import inspect_import, resolve_source, resolve_media, youtube_id
from .schemas import ImportPreviewIn, ImportPreviewOut, ConnectSourceIn
from .models import SourceConnection


@app.post("/api/imports/preview", response_model=ImportPreviewOut)
def preview_import(
    data: ImportPreviewIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    auth_rate_limit(request)
    try:
        return inspect_import(data.url, data.source_url, user.id, db)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc))


@app.put("/api/imports/connection")
def connect_source(
    data: ConnectSourceIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    try:
        video = youtube_id(data.url)
        if not video:
            raise ValueError("Use a YouTube reference URL")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    project = own_project(db, user, data.project_id)
    if (
        project.status != "ready"
        or not project.source_key
        or not storage.path(project.source_key).is_file()
    ):
        raise HTTPException(
            422, "Choose a successfully processed original from your projects"
        )
    connection = db.get(SourceConnection, (user.id, video))
    if connection is None:
        connection = SourceConnection(
            user_id=user.id, video_id=video, project_id=project.id
        )
        db.add(connection)
    else:
        connection.project_id = project.id
    db.commit()
    return {
        "video_id": video,
        "project_id": project.id,
        "provider": "connected-original",
    }


@app.post("/api/projects/import", status_code=201, response_model=ProjectOut)
def import_media(
    data: ImportIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    if data.config.workflow == "manual":
        raise HTTPException(422, "Upload a source file to start a manual project")
    try:
        resolved = resolve_media(data.url, data.source_url, user.id, db)
    except (ValueError, OSError) as e:
        raise HTTPException(422, str(e))
    admission(db, user)
    p = Project(
        user_id=user.id,
        name=data.name,
        import_url=resolved.url,
        source_key=resolved.source_key,
        rights_confirmed=True,
        config=data.config.model_dump(),
    )
    db.add(p)
    db.commit()
    enqueue_project(db, p)
    return project_out(p)


@app.get("/api/projects/{project_id}", response_model=ProjectDetail)
def project(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    p = own_project(db, user, project_id)
    return {
        **project_out(p),
        "transcript": p.transcript,
        "clips": list(
            db.scalars(
                select(Clip).where(Clip.project_id == p.id).order_by(Clip.score.desc())
            )
        ),
    }


@app.post("/api/projects/{project_id}/cancel", response_model=ProjectOut)
def cancel_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = own_project(db, user, project_id)
    if p.status not in {"queued", "processing", "cancelling"}:
        raise HTTPException(409, "This project is no longer processing")
    p.status = "cancelled" if p.status == "queued" else "cancelling"
    p.stage = "Clipping cancelled" if p.status == "cancelled" else "Stopping at the next safe checkpoint"
    db.commit()
    return project_out(p)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = own_project(db, user, project_id)
    if p.status not in {"ready", "failed", "cancelled"}:
        raise HTTPException(409, "Wait for processing to finish before deleting this project")
    clips = list(db.scalars(select(Clip).where(Clip.project_id == p.id)))
    exports = list(db.scalars(select(Export).where(Export.clip_id.in_([c.id for c in clips]))))
    if any(e.status in {"queued", "processing"} for e in exports):
        raise HTTPException(409, "Wait for this project's exports to finish before deleting it")
    keys = [e.output_key for e in exports if e.output_key]
    # Connected projects can share the same original; keep it until its last reference is deleted.
    if p.source_key and not db.scalar(select(Project.id).where(Project.source_key == p.source_key, Project.id != p.id).limit(1)):
        keys.append(p.source_key)
    for connection in db.scalars(select(SourceConnection).where(SourceConnection.project_id == p.id)):
        db.delete(connection)
    for e in exports:
        db.delete(e)
    db.flush()
    for c in clips:
        db.delete(c)
    db.flush()
    db.delete(p)
    db.commit()
    for key in keys:
        try:
            storage.delete(key)
        except OSError:
            log.exception("Deleted project media cleanup failed", extra={"project_id": project_id})
    return {"deleted": True}


@app.post("/api/projects/{project_id}/retry", response_model=ProjectOut)
def retry(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    p = own_project(db, user, project_id)
    if p.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "Only failed or cancelled projects can be retried")
    admission(db, user, charge=p.config.get("workflow") != "manual")
    p.status = "queued"
    p.progress = 0
    p.error = None
    db.commit()
    enqueue_project(db, p)
    return project_out(p)


@app.get("/api/projects/{project_id}/media")
def source(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    p = own_project(db, user, project_id)
    if not p.source_key or not storage.path(p.source_key).exists():
        raise HTTPException(404, "Media not available")
    return FileResponse(storage.path(p.source_key))


_preview_slots = threading.BoundedSemaphore(2)


@app.get("/api/clips/{clip_id}/preview")
def clip_preview(
    clip_id: str,
    start: float,
    end: float,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    from .media import browser_preview, MediaError
    from .processing_gate import processing_slot, ProcessingBusy

    c, p = own_clip(db, user, clip_id)
    if (
        not math.isfinite(start)
        or not math.isfinite(end)
        or start < 0
        or end > p.media.get("duration", 0)
        or not 0 < end - start <= 180
    ):
        raise HTTPException(422, "Preview must be a source range of up to 180 seconds")
    if not p.source_key or not storage.path(p.source_key).exists():
        raise HTTPException(404, "Source media unavailable")
    key = hashlib.sha256(
        f"{p.source_key}:{start:.6f}:{end:.6f}:v1".encode()
    ).hexdigest()
    output = storage.path(f"previews/{user.id}/{key}.mp4")
    if not output.exists():
        if not _preview_slots.acquire(blocking=False):
            raise HTTPException(503, "Other previews are preparing. Try again shortly.")
        try:
            with output.with_suffix(".lock").open("w") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise HTTPException(
                        503, "This preview is preparing. Try again shortly."
                    )
                if not output.exists():
                    temporary = output.with_suffix(".partial.mp4")
                    try:
                        with processing_slot(wait=False):
                            browser_preview(
                                storage.path(p.source_key), temporary, start, end
                            )
                        temporary.replace(output)
                    except ProcessingBusy as exc:
                        raise HTTPException(503, str(exc))
                    except MediaError as exc:
                        raise HTTPException(422, str(exc))
                    finally:
                        temporary.unlink(missing_ok=True)
        finally:
            _preview_slots.release()
    return FileResponse(output, media_type="video/mp4")


@app.get("/api/clips/{clip_id}", response_model=ClipDetail)
def get_clip(
    clip_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    c, p = own_clip(db, user, clip_id)
    return {"clip": c, "project": project_out(p)}


@app.put("/api/clips/{clip_id}", response_model=ClipOut)
def save_clip(
    clip_id: str,
    data: SaveEdits,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    c, p = own_clip(db, user, clip_id)
    c = db.scalar(
        select(Clip)
        .where(Clip.id == c.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if c.revision != data.revision:
        raise HTTPException(
            409, "This clip changed in another tab. Reload before saving."
        )
    duration = p.media.get("duration", 0)
    if any(s.end > duration for s in data.edits.segments):
        raise HTTPException(422, "Trim exceeds source duration")
    if sum(s.end - s.start for s in data.edits.segments) > 180:
        raise HTTPException(422, "Exports are limited to 180 seconds")
    if any(w.end > duration for w in data.edits.words):
        raise HTTPException(422, "Caption exceeds source duration")
    if data.edits.brand_kit_id:
        kit = db.get(BrandKit, data.edits.brand_kit_id)
        if not kit or kit.user_id != user.id:
            raise HTTPException(404, "Brand kit not found")
    validate_assets(
        db, user, data.edits.captions.custom_font_id, data.edits.logo_asset_id
    )
    c.edits = data.edits.model_dump()
    c.revision += 1
    db.commit()
    return c


@app.post("/api/clips/{clip_id}/headlines", response_model=list[HeadlineOut])
def headlines(
    clip_id: str,
    data: HeadlineIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    from .ranking import generate_headlines

    c, p = own_clip(db, user, clip_id)
    segments = c.edits.get("segments", [])
    words = [w for w in c.edits.get("words", [])
             if any(w["start"] < s["end"] and w["end"] > s["start"] for s in segments)]
    if not words:
        raise HTTPException(422, "This clip has no retained transcript. Add or correct its transcript in the editor before generating headlines.")
    c.headlines = generate_headlines(
        " ".join(w["word"] for w in words), data.tone, data.count, data.max_characters
    )
    db.commit()
    return c.headlines


@app.post("/api/clips/{clip_id}/export-quote")
def export_quote(clip_id: str, edits: EditDecision, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c, p = own_clip(db, user, clip_id)
    payload = credits.export_edits(db, user, edits)
    reused = any(EditDecision.model_validate({**e.edits, "watermark": e.edits.get("watermark", False), "watermark_version": e.edits.get("watermark_version", 1)}).model_dump() == payload and (e.status != "complete" or
        (e.output_key and storage.path(e.output_key).exists())) for e in db.scalars(
        select(Export).where(Export.clip_id == c.id, Export.user_id == user.id,
                            Export.status.in_(["queued", "processing", "complete"]))))
    charged = p.config.get("workflow") == "manual" and not reused and user.id not in settings().unlimited_user_ids
    return {"seconds": credits.export_seconds(payload) if charged else 0, "reused": reused,
            "can_remove_watermark": credits.can_remove_watermark(db, user)}


@app.post("/api/clips/{clip_id}/exports", status_code=201, response_model=ExportOut)
def export(
    clip_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    from .worker import render_export

    c, p = own_clip(db, user, clip_id)
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    edits = credits.export_edits(db, user, c.edits)
    # Project/user locks serialize reuse and reservation for concurrent requests.
    for existing in db.scalars(select(Export).where(
        Export.clip_id == c.id, Export.user_id == user.id,
        Export.status.in_(["queued", "processing", "complete"])
    ).order_by(Export.created_at.desc())):
        if EditDecision.model_validate({**existing.edits, "watermark": existing.edits.get("watermark", False), "watermark_version": existing.edits.get("watermark_version", 1)}).model_dump() == edits and (existing.status != "complete" or
                (existing.output_key and storage.path(existing.output_key).exists())):
            return existing
    pending = db.scalar(
        select(func.count())
        .select_from(Export)
        .where(Export.user_id == user.id, Export.status.in_(["queued", "processing"]))
    )
    if pending >= 3:
        raise HTTPException(429, "Wait for an export to finish before starting another")
    e = Export(
        user_id=user.id,
        clip_id=c.id,
        id=str(uuid.uuid4()),
        edits=edits,
    )
    db.add(e)
    if p.config.get("workflow") == "manual":
        try:
            credits.reserve(db, credits.export_account(db, e, "Manual export · " + p.name), credits.export_seconds(edits))
        except ValueError as exc:
            db.rollback()
            raise HTTPException(402, str(exc))
    db.commit()
    try:
        render_export.delay(e.id)
    except Exception:
        e.status = "failed"
        credits.refund(db, credits.export_account(db, e))
        e.error = "Export queue unavailable. Start a new export when it is online."
        db.commit()
    return e


@app.get("/api/exports", response_model=list[ExportOut])
def exports(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list(
        db.scalars(
            select(Export)
            .where(Export.user_id == user.id)
            .order_by(Export.created_at.desc())
            .limit(200)
        )
    )


@app.get("/api/exports/{export_id}/download")
def download(
    export_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    e = db.scalar(
        select(Export).where(Export.id == export_id, Export.user_id == user.id)
    )
    if not e or e.status != "complete" or not e.output_key:
        raise HTTPException(404, "Export not ready")
    return FileResponse(
        storage.path(e.output_key),
        media_type="video/mp4",
        filename=f"reclipd-{e.id[:8]}.mp4",
    )


@app.get("/api/brands", response_model=list[BrandOut])
def brands(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list(db.scalars(select(BrandKit).where(BrandKit.user_id == user.id)))


@app.post("/api/brands", status_code=201, response_model=BrandOut)
def brand(
    data: BrandIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    validate_assets(db, user, data.captions.custom_font_id, data.logo_asset_id)
    kit = BrandKit(
        user_id=user.id, name=data.name, config=data.model_dump(exclude={"name"})
    )
    db.add(kit)
    db.commit()
    return kit


@app.put("/api/brands/{kit_id}", response_model=BrandOut)
def update_brand(kit_id: str, data: BrandIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    kit = db.scalar(select(BrandKit).where(BrandKit.id == kit_id, BrandKit.user_id == user.id).with_for_update())
    if not kit:
        raise HTTPException(404, "Brand kit not found")
    validate_assets(db, user, data.captions.custom_font_id, data.logo_asset_id)
    kit.name = data.name
    kit.config = data.model_dump(exclude={"name"})
    db.commit()
    return kit


@app.delete("/api/brands/{kit_id}")
def delete_brand(
    kit_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    kit = db.get(BrandKit, kit_id)
    if not kit or kit.user_id != user.id:
        raise HTTPException(404, "Brand kit not found")
    db.delete(kit)
    db.commit()
    return {"ok": True}


@app.get("/api/admin")
def admin(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(403, "Administrator access required")
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "projects": [
            project_out(p)
            for p in db.scalars(
                select(Project).order_by(Project.created_at.desc()).limit(100)
            )
        ],
        "exports": list(
            db.scalars(select(Export).order_by(Export.created_at.desc()).limit(100))
        ),
    }


def validate_assets(db, user, font_id, logo_id):
    for asset_id, kind in [(font_id, "font"), (logo_id, "logo")]:
        if asset_id:
            asset = db.get(Asset, asset_id)
            if not asset or asset.user_id != user.id or asset.kind != kind:
                raise HTTPException(404, "Brand asset not found")


@app.get("/api/assets")
def assets(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [
        {"id": a.id, "name": a.name, "kind": a.kind, "family": a.family}
        for a in db.scalars(select(Asset).where(Asset.user_id == user.id))
    ]


@app.get("/api/assets/{asset_id}")
def asset_file(
    asset_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    asset = db.get(Asset, asset_id)
    if not asset or asset.user_id != user.id:
        raise HTTPException(404, "Asset not found")
    return FileResponse(
        storage.path(asset.key),
        media_type="image/png" if asset.kind == "logo" else "font/ttf",
    )


@app.post("/api/assets", status_code=201)
def upload_asset(
    kind: str = Form(...),
    rights_confirmed: bool = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    from io import BytesIO
    import re

    if not rights_confirmed:
        raise HTTPException(422, "Confirm you have permission to use this asset")
    if kind not in ("font", "logo"):
        raise HTTPException(422, "Choose a font or logo")
    if (
        db.scalar(
            select(func.count()).select_from(Asset).where(Asset.user_id == user.id)
        )
        >= 30
    ):
        raise HTTPException(429, "Maximum 30 assets per workspace")
    raw = file.file.read(10 * 1024 * 1024 + 1)
    file.file.close()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "Brand assets must be under 10 MB")
    asset = Asset(
        id=str(uuid.uuid4()),
        user_id=user.id,
        kind=kind,
        name=Path(file.filename or "Asset").name[:100],
    )
    asset.key = f"assets/{asset.id}." + ("png" if kind == "logo" else "ttf")
    try:
        if kind == "logo":
            from PIL import Image

            Image.MAX_IMAGE_PIXELS = 16000000
            with Image.open(BytesIO(raw)) as img:
                if img.width > 4096 or img.height > 4096:
                    raise ValueError()
                img.convert("RGBA").save(storage.path(asset.key), "PNG")
        else:
            from fontTools.ttLib import TTFont

            if Path(file.filename or "").suffix.lower() not in (".ttf", ".otf"):
                raise ValueError()
            with TTFont(BytesIO(raw), lazy=False) as font:
                if font.flavor:
                    raise ValueError()
                # Respect embedded font licensing restriction flags.
                if "OS/2" in font and font["OS/2"].fsType & 0x0002:
                    raise HTTPException(422, "This font prohibits embedding")
                family = font["name"].getDebugName(1) or ""
                if not re.fullmatch(r"[a-zA-Z0-9 _-]{1,80}", family):
                    raise ValueError()
                asset.family = family
                font.save(storage.path(asset.key))
    except HTTPException:
        raise
    except Exception:
        storage.delete(asset.key)
        raise HTTPException(422, "Invalid, unsupported, or oversized asset")
    db.add(asset)
    db.commit()
    return {
        "id": asset.id,
        "name": asset.name,
        "kind": asset.kind,
        "family": asset.family,
    }


@app.post("/api/admin/projects/{project_id}/retry", response_model=ProjectOut)
def admin_retry(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    if not user.is_admin:
        raise HTTPException(403, "Administrator access required")
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    if p.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "Only failed or cancelled projects can be retried")
    owner = db.get(User, p.user_id)
    admission(db, owner)
    p.status = "queued"
    p.error = None
    p.progress = 0
    db.commit()
    enqueue_project(db, p)
    return project_out(p)


BUILTIN_FONTS = {
    "inter-400": "/usr/share/fonts/truetype/reclipd/inter-400.ttf",
    "inter-700": "/usr/share/fonts/truetype/reclipd/inter-700.ttf",
    "poppins-400": "/usr/share/fonts/truetype/reclipd/poppins-400.ttf",
    "poppins-700": "/usr/share/fonts/truetype/reclipd/poppins-700.ttf",
    "montserrat-400": "/usr/share/fonts/truetype/reclipd/montserrat-400.ttf",
    "montserrat-700": "/usr/share/fonts/truetype/reclipd/montserrat-700.ttf",
    "anton-400": "/usr/share/fonts/truetype/reclipd/anton-400.ttf",
    "anton-700": "/usr/share/fonts/truetype/reclipd/anton-700.ttf",
    "bebasneue-400": "/usr/share/fonts/truetype/reclipd/bebasneue-400.ttf",
    "bebasneue-700": "/usr/share/fonts/truetype/reclipd/bebasneue-700.ttf",
    "oswald-400": "/usr/share/fonts/truetype/reclipd/oswald-400.ttf",
    "oswald-700": "/usr/share/fonts/truetype/reclipd/oswald-700.ttf",
    "dmsans-400": "/usr/share/fonts/truetype/reclipd/dmsans-400.ttf",
    "dmsans-700": "/usr/share/fonts/truetype/reclipd/dmsans-700.ttf",
    "dejavu-serif-regular": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "dejavu-serif-bold": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "dejavu-mono-regular": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "dejavu-mono-bold": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "lato-regular": "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
    "lato-bold": "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
    "free-sans-regular": "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "free-sans-bold": "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "free-serif-regular": "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "free-serif-bold": "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
    "free-mono-regular": "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "free-mono-bold": "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
    "carlito-regular": "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
    "carlito-bold": "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
    "caladea-regular": "/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf",
    "caladea-bold": "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf",
    "dejavu-sans-regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "dejavu-sans-bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "liberation-sans-regular": "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "liberation-sans-bold": "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "liberation-serif-regular": "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "liberation-serif-bold": "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "liberation-mono-regular": "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "liberation-mono-bold": "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
}


@app.get("/api/fonts/{font_slug}")
def builtin_font(font_slug: str):
    filename = BUILTIN_FONTS.get(font_slug)
    if not filename or not Path(filename).is_file():
        raise HTTPException(404, "Built-in font unavailable; use the Docker image")
    return FileResponse(filename, media_type="font/ttf")

from .billing import router as billing_router
app.include_router(billing_router)

from .accounts import router as account_router
app.include_router(account_router)

from .paypal import router as paypal_router
app.include_router(paypal_router)

from .uploads import router as uploads_router
app.include_router(uploads_router)
from .drive import router as drive_router
app.include_router(drive_router)

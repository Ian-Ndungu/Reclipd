import logging
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, update
from .config import settings
from .db import SessionLocal
from .models import Project, User, Clip, Export, Asset
from .schemas import EditDecision, CaptionStyle, CAPTION_PRESETS
from .storage import storage
from .media import (
    probe,
    download_authorized,
    extract_audio,
    audio_energy,
    transcribe,
    detect_scenes,
    render,
    MediaError,
)
from .ranking import rank_candidates, generate_headlines
from .speakers import speaker_changes

log = logging.getLogger("reclipd.worker")
celery = Celery("reclipd", broker=settings().redis_url, backend=settings().redis_url)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_soft_time_limit=3500,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 7200},
    result_expires=86400,
    task_always_eager=settings().task_always_eager,
    beat_schedule={
        "recover-stale-jobs": {"task": "app.worker.cleanup", "schedule": 300}
    },
)


def reserve_quota(db, p, duration):
    if p.quota_reserved:
        return
    user = db.scalar(select(User).where(User.id == p.user_id).with_for_update())
    if user.used_seconds + duration > settings().free_minutes * 60:
        raise MediaError(
            "This video exceeds your remaining processing allowance. Try a shorter video."
        )
    user.used_seconds += duration
    p.quota_reserved = duration
    db.commit()


def refund_quota(db, p):
    if p.quota_reserved:
        user = db.scalar(select(User).where(User.id == p.user_id).with_for_update())
        user.used_seconds = max(0, user.used_seconds - p.quota_reserved)
        p.quota_reserved = 0


def failure_message(exc):
    if isinstance(exc, MediaError):
        return str(exc)
    if isinstance(exc, SoftTimeLimitExceeded):
        return "Processing exceeded the worker time limit. Try a shorter video."
    return "Processing could not finish. Check worker logs and model availability, then retry. Your original media is preserved."


@celery.task(name="app.worker.process_project")
def process_project(project_id):
    with SessionLocal() as db:
        result = db.execute(
            update(Project)
            .where(Project.id == project_id, Project.status == "queued")
            .values(status="processing", stage="Inspecting your video", progress=3)
        )
        db.commit()
        if result.rowcount != 1:
            return
        p = db.get(Project, project_id)

        def progress(value, stage=None):
            p.progress = value
            if stage:
                p.stage = stage
            db.commit()

        try:
            if not p.source_key:
                progress(4, "Importing authorized media")
                key = f"sources/{p.id}.mp4"
                from .imports import youtube_id
                from .youtube import retrieve
                video_id = youtube_id(p.import_url)
                if video_id:
                    if not p.rights_confirmed:
                        raise ValueError("Media rights confirmation is required.")
                    retrieve(video_id, storage.path(key), progress)
                else:
                    download_authorized(p.import_url, storage.path(key))
                p.source_key = key
                p.import_url = None
                db.commit()
            source = storage.path(p.source_key)
            media = probe(source)
            p.media = media
            reserve_quota(db, p, media["duration"])
            progress(12, "Preparing audio")
            warnings = []
            words = []
            energy = []
            turns = []
            with tempfile.TemporaryDirectory(prefix="reclipd-process-") as directory:
                if media["has_audio"]:
                    audio = Path(directory) / "audio.wav"
                    extract_audio(source, audio)
                    energy = audio_energy(audio)
                    progress(20, "Transcribing speech (model loads on first use)")
                    words, language = transcribe(
                        audio,
                        media["duration"],
                        p.config.get("language"),
                        lambda value: progress(
                            value,
                            "Transcribing speech · "
                            + str(round((value - 20) / 38 * 100))
                            + "% of source analyzed",
                        ),
                    )
                    p.media = {**media, "language": language}
                    turns, speaker_warning = speaker_changes(audio)
                    if speaker_warning:
                        warnings.append(speaker_warning)
                    if not words:
                        warnings.append(
                            "No speech detected. Highlights use available visual and audio signals; captions are empty."
                        )
                else:
                    warnings.append(
                        "Source has no audio. Highlights use scene and timing signals; captions are empty."
                    )
            p.transcript = words
            progress(62, "Detecting scene boundaries")
            try:
                scenes = detect_scenes(source)
            except Exception:
                scenes = []
                warnings.append(
                    "Scene analysis was unavailable; ranking used the remaining signals."
                )
            progress(78, "Ranking highlight candidates")
            candidates = rank_candidates(
                words, scenes, energy, media["duration"], p.config, turns
            )
            if len(candidates) < p.config.get("clip_count", 5):
                warnings.append(
                    "Fewer distinct candidates than requested fit this source and duration range."
                )
            p.analysis = {
                "speaker_changes": turns,
                "scenes": scenes,
                "audio_rms": energy,
                "warnings": warnings,
                "ranking_method": "Editorial heuristic: speech 30%, lexical variety 20%, audio intensity 20%, scene changes 10%, ending completeness 20%. Configured speaker changes contribute 10% when detected (speech and lexical weights reduce by 5% each). Optional local LLM assessment is identified per clip.",
            }
            existing = list(db.scalars(select(Clip).where(Clip.project_id == p.id)))
            if existing:
                raise MediaError(
                    "Project already has clips. Create a new project to avoid overwriting edits."
                )
            for index, c in enumerate(candidates):
                hs = generate_headlines(" ".join(w["word"] for w in c["words"]))
                edits = EditDecision(
                    segments=[{"start": c["start"], "end": c["end"]}],
                    words=c["words"],
                    captions=CaptionStyle(
                        **CAPTION_PRESETS[p.config.get("caption_preset", "bold")]
                    ),
                    headline=hs[0]["text"],
                ).model_dump()
                db.add(
                    Clip(
                        project_id=p.id,
                        title=c["title"],
                        start=c["start"],
                        end=c["end"],
                        score=c["score"],
                        description=c["description"],
                        reasons=c["reasons"],
                        headlines=hs,
                        edits=edits,
                    )
                )
            p.status = "ready"
            p.stage = "Your highlights are ready"
            p.progress = 100
            p.error = None
            db.commit()
        except Exception as exc:
            db.rollback()
            p = db.get(Project, project_id)
            refund_quota(db, p)
            p.status = "failed"
            p.stage = "Processing paused"
            p.error = failure_message(exc)
            db.commit()
            log.error(
                json.dumps(
                    {
                        "event": "project_failed",
                        "project_id": project_id,
                        "exception": type(exc).__name__,
                    }
                )
            )


@celery.task(name="app.worker.render_export", soft_time_limit=1700, time_limit=1800)
def render_export(export_id):
    with SessionLocal() as db:
        result = db.execute(
            update(Export)
            .where(Export.id == export_id, Export.status == "queued")
            .values(status="processing", progress=3)
        )
        db.commit()
        if result.rowcount != 1:
            return
        e = db.get(Export, export_id)
        clip = db.get(Clip, e.clip_id)
        p = db.get(Project, clip.project_id)
        key = f"exports/{e.id}.mp4"
        output = storage.path(key)

        def progress(value):
            e.progress = value
            db.commit()

        try:
            font = (
                db.get(Asset, e.edits["captions"].get("custom_font_id"))
                if e.edits["captions"].get("custom_font_id")
                else None
            )
            logo = (
                db.get(Asset, e.edits.get("logo_asset_id"))
                if e.edits.get("logo_asset_id")
                else None
            )
            if any(a and a.user_id != e.user_id for a in (font, logo)):
                raise MediaError("Brand asset access denied.")
            render(
                storage.path(p.source_key),
                output,
                e.edits,
                p.media,
                progress,
                custom_font=(storage.path(font.key), font.family) if font else None,
                logo=storage.path(logo.key) if logo else None,
            )
            e.output_key = key
            e.status = "complete"
            e.progress = 100
            db.commit()
        except Exception as exc:
            db.rollback()
            output.unlink(missing_ok=True)
            e = db.get(Export, export_id)
            e.status = "failed"
            e.error = failure_message(exc)
            db.commit()
            log.error("export_failed id=%s exception=%s", export_id, type(exc).__name__)


@celery.task(name="app.worker.cleanup")
def cleanup():
    # Reclaim failed hard-timeout jobs. Never delete user source media or finished exports.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    with SessionLocal() as db:
        for p in db.scalars(
            select(Project)
            .where(
                Project.status.in_(["processing", "queued"]),
                Project.updated_at < cutoff,
            )
            .with_for_update()
        ):
            refund_quota(db, p)
            p.status = "failed"
            p.error = (
                "Worker was interrupted or unavailable. You can retry this project."
            )
        for e in db.scalars(
            select(Export)
            .where(
                Export.status.in_(["processing", "queued"]), Export.updated_at < cutoff
            )
            .with_for_update()
        ):
            e.status = "failed"
            e.error = (
                "Export worker was interrupted. Start another export from the editor."
            )
            storage.delete(f"exports/{e.id}.mp4")
        db.commit()
    # Only known worker scratch directories older than a day are cleaned.
    import shutil, time

    for directory in Path(tempfile.gettempdir()).glob("reclipd-*"):
        if (
            directory.is_dir()
            and not directory.is_symlink()
            and directory.name.startswith(("reclipd-process-", "reclipd-render-"))
            and time.time() - directory.stat().st_mtime > 86400
        ):
            shutil.rmtree(directory)

    # Disposable preview cache only; source media and exports are retained.
    preview_dir = storage.path("previews/.keep").parent
    for preview in preview_dir.glob("*.mp4"):
        if time.time() - preview.stat().st_mtime > 7 * 86400:
            preview.unlink(missing_ok=True)

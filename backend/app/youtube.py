"""Public, rights-confirmed YouTube retrieval; isolated from the clipping engine."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from .config import settings
from .media import MediaError

UNAVAILABLE = "YouTube retrieval failed. The video may be restricted, unavailable, or blocked by YouTube. Upload your authorized original instead; no login or restriction bypass is attempted."


def validate_public(info, video_id, max_seconds):
    if info.get("id") != video_id or info.get("_type", "video") != "video":
        raise ValueError("Only a single YouTube video is supported.")
    if info.get("availability") != "public" or info.get("age_limit", 0) != 0:
        raise ValueError("Only public, unrestricted videos are supported. Upload your authorized original.")
    if info.get("live_status") not in (None, "not_live", "was_live") or info.get("is_live"):
        raise ValueError("Live and upcoming videos are not supported.")
    if info.get("has_drm") or not info.get("duration") or not 0 < info["duration"] <= max_seconds:
        raise ValueError("Video is protected, has unknown duration, or exceeds the processing duration limit.")


def retrieve(video_id, target, progress):
    cfg = settings()
    if not cfg.youtube_download_enabled:
        raise MediaError("Public YouTube retrieval is disabled. Upload your original.")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="youtube-", dir=target.parent) as directory:
        proc = subprocess.Popen(
            [sys.executable, "-m", "app.youtube", video_id, directory,
             str(cfg.max_upload_mb * 1024 * 1024), str(cfg.max_media_seconds)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        started = time.monotonic()
        last = None
        try:
            while proc.poll() is None:
                if time.monotonic() - started > cfg.youtube_download_timeout:
                    raise MediaError("YouTube retrieval timed out. Retry or upload your original.")
                paths = list(Path(directory).glob("*"))
                if sum(p.stat().st_size for p in paths if p.is_file()) > cfg.max_upload_mb * 1024 * 1024 * 2:
                    raise MediaError("YouTube retrieval exceeded the storage limit.")
                status = Path(directory) / "progress.json"
                if status.exists():
                    try:
                        data = json.loads(status.read_text())
                        stage = data["stage"]
                        if stage != last:
                            progress(5, stage)
                            last = stage
                    except (ValueError, KeyError):
                        pass
                time.sleep(0.5)
            result = Path(directory) / "result.json"
            data = json.loads(result.read_text()) if result.exists() else {}
            if proc.returncode != 0 or not data.get("file"):
                raise MediaError(data.get("error", UNAVAILABLE))
            source = Path(directory) / data["file"]
            if source.parent != Path(directory) or not source.is_file() or source.stat().st_size > cfg.max_upload_mb * 1024 * 1024:
                raise MediaError("Retrieved video exceeds limits or is missing.")
            source.replace(target)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()


def download(video_id, directory, limit, max_seconds):
    from yt_dlp import YoutubeDL
    from urllib.parse import urlsplit
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Invalid YouTube ID")
    root = Path(directory)
    def report(stage):
        temporary = root / "progress.tmp"
        temporary.write_text(json.dumps({"stage": stage}))
        temporary.replace(root / "progress.json")
    received = {}
    def hook(data):
        name = str(data.get("filename", "source"))
        received[name] = max(received.get(name, 0), data.get("downloaded_bytes", 0))
        size = sum(received.values())
        if size > limit:
            raise ValueError("Video exceeds the upload size limit.")
        report(f"Retrieving YouTube video · {size // (1024 * 1024)} MB received")
    options = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "cachedir": False, "usenetrc": False, "cookiefile": None,
        "geo_bypass": False, "allow_unplayable_formats": False,
        "allowed_extractors": ["youtube"], "socket_timeout": 20,
        "retries": 2, "fragment_retries": 2, "max_filesize": limit,
        "format": "best[height<=1080][protocol=https]/bestvideo[height<=1080][protocol=https]+bestaudio[protocol=https]",
        "outtmpl": str(root / "source.%(ext)s"), "merge_output_format": "mp4",
        "progress_hooks": [hook], "remote_components": [],
        "js_runtimes": {"node": {}},
    }
    report("Checking public YouTube availability")
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        validate_public(info, video_id, max_seconds)
        # Only direct HTTPS media on YouTube's media CDN; no generic URLs/manifests.
        formats = []
        for fmt in info.get("formats", []):
            url = urlsplit(fmt.get("url", ""))
            if (fmt.get("protocol") == "https" and not fmt.get("has_drm")
                    and url.scheme == "https" and (url.hostname or "").endswith(".googlevideo.com")
                    and not url.username and not url.password and url.port in (None, 443)):
                formats.append(fmt)
        if not formats:
            raise ValueError(UNAVAILABLE)
        info["formats"] = formats
        for name in ("requested_formats", "requested_downloads", "url", "format_id"):
            info.pop(name, None)
        ydl.process_ie_result(info, download=True)
    files = [p for p in root.glob("source.*") if p.suffix in (".mp4", ".webm", ".mkv")]
    if len(files) != 1:
        raise ValueError(UNAVAILABLE)
    (root / "result.json").write_text(json.dumps({"file": files[0].name}))


if __name__ == "__main__":
    try:
        download(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    except Exception:
        # Extractor exceptions may include signed URLs; do not persist or expose them.
        (Path(sys.argv[2]) / "result.json").write_text(json.dumps({"error": UNAVAILABLE}))
        sys.exit(1)

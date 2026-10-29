"""Bounded cloud retrieval for rights-confirmed public YouTube videos."""
import http.client
import ipaddress
import json
import math
from pathlib import Path
import re
import socket
import sqlite3
import ssl
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit

import httpx
from .config import settings
from .media import MediaError, probe, run, INPUT_GUARD

BASE = "https://gate.apiscrape.net:16262"
STORAGE_HOST = "s3.fr-par.scw.cloud"


def select_formats(formats, limit):
    usable = [f for f in formats if f.get("protocol") == "https" and not f.get("has_drm")
              and re.fullmatch(r"[A-Za-z0-9_-]+", str(f.get("format_id", "")))]
    videos = [f for f in usable if str(f.get("vcodec", "")).startswith("avc1")
              and 0 < (f.get("height") or 0) <= 1080 and f.get("ext") == "mp4"]
    if not videos:
        raise MediaError("No compatible high-quality video is available from the provider.")
    video = max(videos, key=lambda f: (f.get("height") or 0, f.get("fps") or 0, f.get("tbr") or 0))
    chosen = [video]
    if video.get("acodec") in (None, "none"):
        audio = [f for f in usable if f.get("vcodec") == "none"
                 and str(f.get("acodec", "")).startswith("mp4a")]
        if not audio:
            raise MediaError("The provider did not offer compatible audio. Upload your original.")
        chosen.append(max(audio, key=lambda f: (f.get("language_preference") or -1, f.get("abr") or 0, "-drc" not in f["format_id"])))
    # Reserve conservatively before provider tasks; do not silently lower resolution.
    sizes = [f.get("filesize") or f.get("filesize_approx") for f in chosen]
    if any(not isinstance(s, (int, float)) or not math.isfinite(s) or s <= 0 for s in sizes):
        raise MediaError("The provider could not estimate download size safely.")
    ceilings = [math.ceil(s * 1.25) for s in sizes]
    if sum(ceilings) > limit:
        raise MediaError("This video exceeds the cloud import size limit. Upload your original.")
    return chosen, ceilings


def reserve_bandwidth(amount):
    root = Path(settings().storage_root)
    root.mkdir(parents=True, exist_ok=True)
    # Transactional across worker processes; never reset automatically or refund
    # failed tasks because the provider may already have transferred footage.
    with sqlite3.connect(root / ".videoscale-budget.sqlite", timeout=15) as db:
        db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY, used INTEGER NOT NULL)")
        db.execute("INSERT OR IGNORE INTO budget VALUES (1, 0)")
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        used = db.execute("SELECT used FROM budget WHERE id=1").fetchone()[0]
        if used + amount > settings().videoscale_budget_bytes:
            raise MediaError("Cloud import allowance is exhausted. Upload your original video to continue.")
        db.execute("UPDATE budget SET used=used+? WHERE id=1", (amount,))


def request(client, path, data=None):
    try:
        response = client.request("POST" if data else "GET", BASE + path, json=data)
        if response.status_code in (401, 403):
            raise MediaError("Cloud video access could not be authorized. Contact support or upload your original.")
        if response.status_code in (402, 429):
            raise MediaError("Cloud video import allowance is unavailable. Retry later or upload your original.")
        # Download creation is asynchronous: 202 is a successful queued task.
        if response.status_code not in ((200, 201, 202) if data else (200,)):
            raise MediaError("Cloud video retrieval is temporarily unavailable. Retry or upload your original.")
        if len(response.content) > 2_000_000:
            raise MediaError("Cloud video provider returned an invalid response.")
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise MediaError("Cloud video provider did not respond correctly. Retry or upload your original.") from None



def connect_storage(addresses):
    # Some cloud hosts resolve IPv6 but have no IPv6 route. Try validated
    # addresses individually, keeping TLS hostname verification on each attempt.
    last = None
    for address in sorted(addresses, key=lambda a: ipaddress.ip_address(a).version):
        sock = None
        try:
            sock = socket.create_connection((address, 443), timeout=10)
            return ssl.create_default_context().wrap_socket(sock, server_hostname=STORAGE_HOST)
        except OSError as exc:
            last = exc
            if sock is not None:
                sock.close()
    raise MediaError("Cloud media storage could not be reached. Retry later.") from last

def download_file(url, path, ceiling, deadline, progress):
    parts = urlsplit(url)
    if (parts.scheme not in ("http", "https") or parts.hostname != STORAGE_HOST
            or parts.username or parts.password or parts.port not in (None, 443) or parts.fragment):
        raise MediaError("Cloud provider returned an unsupported file destination.")
    # Provider currently emits HTTP signed links; always fetch the same object via TLS.
    addresses = sorted({a[4][0] for a in socket.getaddrinfo(STORAGE_HOST, 443, type=socket.SOCK_STREAM)})
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise MediaError("Cloud media destination is unavailable.")
    class Pinned(http.client.HTTPSConnection):
        def connect(self):
            self.sock = connect_storage(addresses)
    connection = Pinned(STORAGE_HOST, timeout=30)
    try:
        connection.request("GET", urlunsplit(("", "", parts.path, parts.query, "")))
        response = connection.getresponse()
        if response.status != 200:  # Never forward auth or follow redirects.
            raise MediaError("Cloud media file is unavailable. Retry the import.")
        if int(response.getheader("Content-Length", "0")) > ceiling:
            raise MediaError("Cloud media exceeded the reserved size limit.")
        size = 0
        with path.open("wb") as output:
            while True:
                if time.monotonic() > deadline:
                    raise MediaError("Cloud video retrieval timed out.")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > ceiling:
                    raise MediaError("Cloud media exceeded the reserved size limit.")
                output.write(chunk)
                progress(7, f"Downloading source media · {size // (1024 * 1024)} MB")
        if not size:
            raise MediaError("Cloud provider returned an empty file.")
    finally:
        connection.close()


def retrieve(video_id, target, progress):
    cfg = settings()
    if not cfg.videoscale_enabled or not cfg.videoscale_auth_header:
        raise MediaError("Cloud video import is not configured.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise MediaError("Invalid YouTube video ID.")
    from .imports import metadata
    info = metadata(video_id)
    if not info.get("public_unrestricted") or not info.get("duration") or info["duration"] > cfg.max_media_seconds:
        raise MediaError("Only public, unrestricted videos within the duration limit can be imported.")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + cfg.youtube_download_timeout
    try:
        with httpx.Client(headers={"Authorization": cfg.videoscale_auth_header},
                          timeout=45, follow_redirects=False, trust_env=False) as client:
            progress(5, "Finding source video and audio")
            formats = request(client, f"/api/formats?video_url=https%3A%2F%2Fyoutu.be%2F{video_id}")
            if not isinstance(formats, list):
                raise MediaError("Cloud provider returned invalid formats.")
            chosen, ceilings = select_formats(formats, min(cfg.max_upload_mb * 1024**2, cfg.videoscale_max_import_mb * 1024**2))
            reserve_bandwidth(sum(ceilings))
            with tempfile.TemporaryDirectory(prefix="cloud-import-", dir=target.parent) as folder:
                files = []
                for index, (fmt, ceiling) in enumerate(zip(chosen, ceilings)):
                    progress(6, f"Retrieving source {'video' if index == 0 else 'audio'}")
                    result = request(client, "/api/download", {"url": f"https://www.youtube.com/watch?v={video_id}", "format_id": fmt["format_id"]})
                    task = result.get("task_id")
                    if not isinstance(task, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task):
                        raise MediaError("Cloud provider did not return a valid task.")
                    while True:
                        if time.monotonic() > deadline:
                            raise MediaError("Cloud video retrieval timed out. Upload your original or retry later.")
                        status = request(client, "/api/status/" + task)
                        progress(6, f"Retrieving source {'video' if index == 0 else 'audio'} · {str(status.get('status', '')).replace('_', ' ')[:40]}" if status.get("status") in {"queued", "processing", "trying_combination", "downloading", "completed"} else "Retrieving source media")
                        if status.get("status") == "completed":
                            break
                        if status.get("status") in ("failed", "error"):
                            raise MediaError("Cloud provider could not retrieve this video. Upload your authorized original.")
                        time.sleep(3)
                    result = request(client, "/api/download/" + task)
                    path = Path(folder) / f"stream-{index}.mp4"
                    download_file(result["download_url"], path, ceiling, deadline, progress)
                    files.append(path)
                progress(9, "Combining video and audio")
                output = Path(folder) / "source.mp4"
                args = ["ffmpeg", "-v", "error", "-y", *INPUT_GUARD, "-i", str(files[0])]
                if len(files) == 2:
                    args += [*INPUT_GUARD, "-i", str(files[1]), "-map", "0:v:0", "-map", "1:a:0"]
                else:
                    args += ["-map", "0:v:0", "-map", "0:a:0"]
                run([*args, "-c", "copy", "-movflags", "+faststart", str(output)], timeout=180)
                media = probe(output)
                if not media["has_audio"] or output.stat().st_size > cfg.max_upload_mb * 1024**2:
                    raise MediaError("Retrieved source did not contain valid video and audio within limits.")
                output.replace(target)
    except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError):
        raise MediaError("Cloud import could not finish safely. Retry or upload your original.") from None

"""Metadata discovery is separate from permission to retrieve audiovisual media."""

import re
from urllib.parse import urlsplit, parse_qs
import httpx
from .config import settings
from .media import download_authorized, MediaError
from .security import validate_url

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


def youtube_id(url: str) -> str | None:
    try:
        p = urlsplit(url)
        if p.scheme != "https" or p.username or p.password or p.port not in (None, 443):
            raise ValueError("Use an HTTPS URL without credentials or a custom port.")
        host = (p.hostname or "").lower()
        if host not in YOUTUBE_HOSTS:
            return None
        if host.endswith("youtu.be"):
            video = p.path.removeprefix("/")
        elif p.path == "/watch":
            values = parse_qs(p.query).get("v", [])
            video = values[0] if len(values) == 1 else ""
        elif p.path.startswith("/shorts/"):
            video = p.path[len("/shorts/") :]
        else:
            video = ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
            raise ValueError(
                "Use a YouTube watch, youtu.be, or Shorts link with a valid video ID."
            )
        return video
    except (ValueError, TypeError):
        raise ValueError(
            "Invalid video URL. Use a valid HTTPS YouTube watch, Shorts, or direct video link."
        )


def metadata(video_id: str) -> dict:
    if not settings().youtube_api_key:
        raise ValueError(
            "YouTube metadata is not configured. The operator must set YOUTUBE_API_KEY; you can still upload your authorized source file."
        )
    try:
        # Fixed official destination; the supplied URL is never fetched.
        with httpx.Client(timeout=12, follow_redirects=False) as client:
            response = client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "snippet,contentDetails,status", "id": video_id},
                headers={"X-Goog-Api-Key": settings().youtube_api_key},
            )
        if response.status_code != 200:
            raise ValueError(
                "YouTube metadata is temporarily unavailable. Check API configuration/quota and retry, or upload your source file."
            )
        items = response.json().get("items", [])
        if not items:
            raise ValueError(
                "YouTube video was not found or its metadata is private/unavailable."
            )
        item = items[0]
        snippet = item["snippet"]
        duration = item.get("contentDetails", {}).get("duration", "")
        match = re.fullmatch(
            r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration
        )
        seconds = (
            sum(
                int(v or 0) * unit
                for v, unit in zip(match.groups(), [86400, 3600, 60, 1])
            )
            if match
            else None
        )
        thumbnail = snippet.get("thumbnails", {}).get("medium", {}).get("url")
        if thumbnail and urlsplit(thumbnail).hostname != "i.ytimg.com":
            thumbnail = None
        return {
            "public_unrestricted": (item.get("status", {}).get("privacyStatus") == "public"
                and snippet.get("liveBroadcastContent", "none") == "none"
                and not item.get("contentDetails", {}).get("contentRating")
                and not item.get("contentDetails", {}).get("regionRestriction")),
            "title": snippet["title"],
            "channel": snippet["channelTitle"],
            "thumbnail": thumbnail,
            "duration": seconds,
        }
    except (httpx.HTTPError, KeyError, TypeError):
        raise ValueError(
            "Could not load YouTube metadata. Retry or upload your authorized source file."
        )


def resolve_source(url: str, source_url: str | None = None) -> str:
    video = youtube_id(url)
    if video:
        if not source_url:
            raise ValueError(
                "This YouTube link provides metadata only. Supply an authorized direct source URL from an approved host, or upload the source file."
            )
        if youtube_id(source_url):
            raise ValueError(
                "The authorized source must be a direct media file, not another YouTube page."
            )
        source = source_url
    else:
        if source_url:
            raise ValueError(
                "An alternate source is only supported with a YouTube reference link."
            )
        source = url
    validate_url(source)
    return source


def inspect_import(
    url: str, source_url: str | None = None, user_id=None, db=None
) -> dict:
    video = youtube_id(url)
    result = {
        "kind": "youtube" if video else "direct",
        "video_id": video,
        "title": None,
        "channel": None,
        "thumbnail": None,
        "duration": None,
        "available": False,
        "message": "",
        "metadata_error": None,
    }
    if video:
        try:
            result.update(metadata(video))
        except ValueError as exc:
            result["metadata_error"] = str(exc)
    try:
        resolved = (
            resolve_media(url, source_url, user_id, db)
            if db is not None
            else RetrievedSource(url=resolve_source(url, source_url))
        )
        if resolved.url and resolved.provider != "youtube-public":
            download_authorized(resolved.url, None, check_only=True)
        result["provider"] = resolved.provider
        result["available"] = True
        result["message"] = (
            "Authorized source is available. Confirm your rights to generate clips with RECLIPD’s own engine."
        )
    except (ValueError, OSError, MediaError) as exc:
        result["message"] = str(exc)
    if result.get("provider") == "youtube-public":
        result["message"] = "Public video retrieval can be attempted after rights confirmation. Availability is checked by the worker; restricted or blocked videos require an original file."
    return result


# Providers supply sources to our existing pipeline, never a second clipping engine.
from dataclasses import dataclass
from typing import Protocol
from .models import SourceConnection, Project
from .storage import storage


@dataclass(frozen=True)
class RetrievedSource:
    source_key: str | None = None
    url: str | None = None
    provider: str = "direct-https"


class YouTubeMediaProvider(Protocol):
    def resolve(self, video_id: str, user_id: str, db) -> RetrievedSource | None: ...


class ConnectedOriginalProvider:
    def resolve(self, video_id, user_id, db):
        connection = db.get(SourceConnection, (user_id, video_id))
        if connection is None:
            return None
        project = db.get(Project, connection.project_id)
        if (
            not project
            or project.user_id != user_id
            or not project.source_key
            or not storage.path(project.source_key).is_file()
        ):
            raise ValueError(
                "The connected original is unavailable. Reconnect an authorized source file."
            )
        return RetrievedSource(
            source_key=project.source_key, provider="connected-original"
        )


YOUTUBE_PROVIDERS: tuple[YouTubeMediaProvider, ...] = (ConnectedOriginalProvider(),)


def resolve_media(url, source_url, user_id, db):
    video = youtube_id(url)
    if video and not source_url:
        for provider in YOUTUBE_PROVIDERS:
            result = provider.resolve(video, user_id, db)
            if result is not None:
                if result.url:
                    validate_url(result.url)
                return result
    if video and not source_url and (settings().youtube_download_enabled or settings().videoscale_enabled):
        return RetrievedSource(url=f"https://www.youtube.com/watch?v={video}", provider="youtube-public")
    return RetrievedSource(url=resolve_source(url, source_url))

import http.client
import logging
import json
import math
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
import wave
from .config import settings
from .security import validate_url


class MediaError(RuntimeError):
    pass


def run(args, timeout=300):
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise MediaError("Media operation timed out; use a shorter source and retry.")
    except FileNotFoundError:
        raise MediaError(f"{args[0]} is not installed in the worker.")
    if result.returncode:
        logging.getLogger("reclipd.media").error(
            json.dumps(
                {
                    "event": "media_command_failed",
                    "tool": args[0],
                    "diagnostic": result.stderr.decode("utf-8", errors="replace")[
                        -3000:
                    ],
                }
            )
        )
        # Do not expose paths, signed URLs, or the full FFmpeg diagnostic to clients.
        raise MediaError(
            f"{args[0]} could not process this media. Verify the file is a valid, unprotected video."
        )
    return result.stdout


INPUT_GUARD = [
    "-protocol_whitelist",
    "file,pipe",
    "-format_whitelist",
    "mov,matroska,webm,wav",
]


def probe(path: Path):
    data = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                *INPUT_GUARD,
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            timeout=30,
        )
    )
    videos = [
        s
        for s in data.get("streams", [])
        if s.get("codec_type") == "video"
        and not s.get("disposition", {}).get("attached_pic")
    ]
    if not videos:
        raise MediaError("No video stream found. Upload a video file.")
    v = videos[0]
    duration = float(data.get("format", {}).get("duration", 0))
    width, height = int(v.get("width", 0)), int(v.get("height", 0))
    if (
        not math.isfinite(duration)
        or not 0.5 <= duration <= settings().max_media_seconds
    ):
        raise MediaError(
            f"Video must be between 0.5 and {settings().max_media_seconds} seconds."
        )
    if not 16 <= width <= 7680 or not 16 <= height <= 7680 or width * height > 34000000:
        raise MediaError("Source resolution is unsupported (maximum 8K).")
    rotation = next(
        (
            int(s.get("rotation", 0))
            for s in v.get("side_data_list", [])
            if "rotation" in s
        ),
        0,
    )
    if abs(rotation) % 180 == 90:
        width, height = height, width
    return {
        "duration": duration,
        "width": width,
        "height": height,
        "has_audio": any(s.get("codec_type") == "audio" for s in data["streams"]),
        "codec": v.get("codec_name"),
        "rotation": rotation,
    }


def download_authorized(url: str, output: Path | None, check_only=False):
    # Resolve once, validate every address, then connect to a pinned address with original TLS SNI.
    # Redirects are deliberately not followed, preventing redirect-based SSRF.
    host, addresses = validate_url(url)
    parts = urlsplit(url)

    class PinnedHTTPS(http.client.HTTPSConnection):
        def connect(self):
            self.sock = socket.create_connection((addresses[0], 443), timeout=30)
            self.sock = ssl.create_default_context().wrap_socket(
                self.sock, server_hostname=host
            )

    connection = PinnedHTTPS(host, timeout=30)
    try:
        connection.request(
            "HEAD" if check_only else "GET",
            parts.path + ("?" + parts.query if parts.query else ""),
            headers={
                "Host": host,
                "User-Agent": "RECLIPD/0.1",
                "Accept": "video/*,application/octet-stream",
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            raise MediaError(
                "Media host did not return a direct file. Redirects are not supported."
            )
        content_type = response.getheader("Content-Type", "").split(";")[0]
        if not (
            content_type.startswith("video/")
            or content_type == "application/octet-stream"
        ):
            raise MediaError("The link did not return a video file.")
        limit = settings().max_upload_mb * 1024 * 1024
        if int(response.getheader("Content-Length", "0")) > limit:
            raise MediaError("Remote video exceeds upload limit.")
        if check_only:
            return
        total = 0
        deadline = time.monotonic() + 300
        with output.open("wb") as target:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > limit or time.monotonic() > deadline:
                    raise MediaError("Remote download exceeded size or time limit.")
                target.write(chunk)
        if not total:
            raise MediaError("Remote file is empty.")
    except Exception:
        if output is not None:
            output.unlink(missing_ok=True)
        raise
    finally:
        connection.close()


def extract_audio(source: Path, output: Path):
    run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            *INPUT_GUARD,
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output),
        ],
        timeout=600,
    )


def audio_energy(path: Path):
    import numpy as np

    with wave.open(str(path), "rb") as reader:
        values = []
        while data := reader.readframes(reader.getframerate()):
            a = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768
            values.append(float(np.sqrt(np.mean(a * a))))
    return values


_whisper = None


def transcribe(path: Path, duration: float, language, progress):
    global _whisper
    from faster_whisper import WhisperModel

    cfg = settings()
    if _whisper is None:
        _whisper = WhisperModel(
            cfg.whisper_model,
            device=cfg.whisper_device,
            compute_type=cfg.whisper_compute_type,
            cpu_threads=cfg.whisper_cpu_threads,
        )
    segments, info = _whisper.transcribe(
        str(path),
        word_timestamps=True,
        vad_filter=True,
        language=language,
        beam_size=cfg.whisper_beam_size,
        best_of=1,
    )
    words = []
    for segment in segments:
        for w in segment.words or []:
            start = max(0, float(w.start))
            end = min(duration, float(w.end))
            if end > start and w.word.strip():
                words.append(
                    {
                        "word": w.word.strip(),
                        "start": round(start, 3),
                        "end": round(end, 3),
                    }
                )
        progress(min(58, 20 + int(38 * segment.end / max(1, duration))))
    return words, info.language


def detect_scenes(source: Path):
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector

    video = open_video(str(source))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=27))
    manager.auto_downscale = True
    manager.detect_scenes(video=video, frame_skip=2)
    return [start.get_seconds() for start, end in manager.get_scene_list()]


def face_track(source: Path, start: float, end: float, fallback=0.5):
    import cv2

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    cap = cv2.VideoCapture(str(source))
    points = []
    smoothed = fallback
    try:
        for second in range(int(start), math.ceil(end), 2):
            cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            height, width = frame.shape[:2]
            small = cv2.resize(frame, (480, max(1, int(height * 480 / width))))
            boxes = cascade.detectMultiScale(
                cv2.cvtColor(small, cv2.COLOR_BGR2GRAY),
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(25, 25),
            )
            if len(boxes):
                x, y, w, h = max(boxes, key=lambda b: int(b[2]) * int(b[3]))
                focus = (float(x) + float(w) / 2) / 480
                smoothed = 0.35 * smoothed + 0.65 * focus
            points.append((max(0, second - start), round(smoothed, 4)))
    finally:
        cap.release()
    return points


def output_size(media, resolution):
    # Avoid enlarging cropped source. Both dimensions remain even and exactly 9:16.
    units = max(
        1, min(resolution // 18, int(media["width"]) // 18, int(media["height"]) // 32)
    )
    return units * 18, units * 32


def crop_filter(media, width, height, mode, focus, tracking=None):
    if mode == "fit":
        return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    # Dynamic expression sampled every two seconds. Crop center follows the largest face.
    expr = str(focus)
    if tracking:
        expr = str(tracking[-1][1])
        for (t, x), (next_t, next_x) in reversed(list(zip(tracking, tracking[1:]))):
            interpolation = f"({x}+({next_x}-{x})*(t-{t})/{max(.01,next_t-t)})"
            expr = f"if(lt(t,{next_t}),{interpolation},{expr})"
    return f"crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='max(0,min(iw-ow,iw*({expr})-ow/2))':y='(ih-oh)/2',scale={width}:{height},setsar=1"


def retime_words(words, segments):
    result = []
    offset = 0
    for segment in segments:
        start, end = segment["start"], segment["end"]
        for word in words:
            a, b = max(start, word["start"]), min(end, word["end"])
            if b > a:
                result.append(
                    {**word, "start": a - start + offset, "end": b - start + offset}
                )
        offset += end - start
    return sorted(result, key=lambda w: w["start"])


def ass_time(value):
    cs = round(value * 100)
    return f"{cs//360000}:{(cs//6000)%60:02d}:{(cs//100)%60:02d}.{cs%100:02d}"


def ass_color(value):
    return "&H00" + value[5:7] + value[3:5] + value[1:3]


def safe_ass(text):
    return (
        text.replace("\\", "")
        .replace("{", "")
        .replace("}", "")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def write_ass(path, words, style, width, height, headline="", duration=0):
    scale = height / 1920
    alignment = {"bottom": 2, "center": 5, "top": 8}[style["placement"]]
    border = 3 if style["preset"] == "boxed" or style.get("background") else 1
    outline = ass_color(
        style.get("background_color", "#111827")
        if border == 3
        else style.get("stroke_color", "#000000")
    )
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style['font']},{style['size']*scale},{ass_color(style['color'])},{ass_color(style['emphasis_color'])},{outline},&H80000000,{-1 if style['weight']==700 else 0},0,0,0,100,100,{style.get("letter_spacing", 0)*scale},0,{border},{style['stroke']*scale},{style['shadow']*scale},{alignment},{int(width*.06)},{int(width*.06)},{int(height*.1)},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for index in range(0, len(words), 5):
        group = words[index : index + 5]
        if style["animation"] == "highlight":
            for active, w in enumerate(group):
                content = " ".join(
                    (
                        (
                            "{\\c"
                            + ass_color(style["emphasis_color"])
                            + "&}"
                            + safe_ass(x["word"])
                            + "{\\c"
                            + ass_color(style["color"])
                            + "&}"
                        )
                        if j == active
                        else safe_ass(x["word"])
                    )
                    for j, x in enumerate(group)
                )
                events.append(
                    f"Dialogue: 0,{ass_time(w['start'])},{ass_time(w['end'])},Default,,0,0,0,,{content}"
                )
        else:
            content = " ".join(safe_ass(w["word"]) for w in group)
            if style["animation"] == "fade":
                content = "{\\fad(100,100)}" + content
            events.append(
                f"Dialogue: 0,{ass_time(group[0]['start'])},{ass_time(group[-1]['end'])},Default,,0,0,0,,{content}"
            )
    if headline:
        headline_style = f"Style: Headline,{style['font']},{58*scale},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{2*scale},0,8,{int(width*.08)},{int(width*.08)},{int(height*.06)},1\n"
        header = header.replace("[Events]", headline_style + "[Events]")
        events.append(
            f"Dialogue: 1,0:00:00.00,{ass_time(duration)},Headline,,0,0,0,,{safe_ass(headline)}"
        )
    path.write_text(header + "\n".join(events), encoding="utf-8")


def render(
    source: Path, output: Path, edits, media, progress, custom_font=None, logo=None
):
    width, height = output_size(media, edits["resolution"])
    with tempfile.TemporaryDirectory(prefix="reclipd-render-") as temp:
        folder = Path(temp)
        parts = []
        for index, segment in enumerate(edits["segments"]):
            start, end = segment["start"], segment["end"]
            tracking = (
                face_track(source, start, end, edits["focus_x"])
                if edits["reframe"] == "auto"
                else None
            )
            vf = crop_filter(
                media, width, height, edits["reframe"], edits["focus_x"], tracking
            )
            part = folder / f"part{index}.mp4"
            args = [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-y",
                *INPUT_GUARD,
                "-ss",
                str(start),
                "-i",
                str(source),
                "-t",
                str(end - start),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                vf,
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-map_metadata",
                "-1",
                str(part),
            ]
            run(args, timeout=600)
            parts.append(part)
            progress(10 + int(55 * (index + 1) / len(edits["segments"])))
        listing = folder / "concat.txt"
        listing.write_text("\n".join(f"file '{p.name}'" for p in parts))
        joined = folder / "joined.mp4"
        run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                str(listing),
                "-c",
                "copy",
                str(joined),
            ],
            timeout=120,
        )
        progress(70)
        if logo:
            branded = folder / "branded.mp4"
            logo_width = max(16, int(width * 0.18))
            run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(joined),
                    "-i",
                    str(logo),
                    "-filter_complex",
                    f"[1:v]scale={logo_width}:-1[logo];[0:v][logo]overlay=W-w-20:20:format=auto[v]",
                    "-map",
                    "[v]",
                    "-map",
                    "0:a?",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "copy",
                    str(branded),
                ],
                timeout=600,
            )
            joined = branded
        if media.get("has_audio") and edits.get("volume", 1) != 1:
            adjusted = folder / "audio-adjusted.mp4"
            run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(joined),
                    "-c:v",
                    "copy",
                    "-af",
                    f"volume={float(edits['volume'])}",
                    "-c:a",
                    "aac",
                    str(adjusted),
                ],
                timeout=300,
            )
            joined = adjusted
        caption_style = dict(edits["captions"])
        font_option = ""
        if custom_font:
            fonts = folder / "fonts"
            fonts.mkdir()
            shutil.copyfile(custom_font[0], fonts / "custom.ttf")
            caption_style["font"] = custom_font[1]
            font_option = f":fontsdir='{fonts}'"
        words = retime_words(edits["words"], edits["segments"])
        headline = edits.get("headline", "") if edits.get("show_headline") else ""
        if (edits["captions"]["enabled"] and words) or headline:
            ass = folder / "captions.ass"
            write_ass(
                ass,
                words if edits["captions"]["enabled"] else [],
                caption_style,
                width,
                height,
                headline,
                sum(s["end"] - s["start"] for s in edits["segments"]),
            )
            # Generated temporary directory name only; no user-controlled filter paths.
            escaped = (
                str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            )
            run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(joined),
                    "-vf",
                    f"ass=filename='{escaped}'{font_option}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(output),
                ],
                timeout=600,
            )
        else:
            run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(joined),
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(output),
                ],
                timeout=120,
            )
        progress(98)
    return {"width": width, "height": height}


def browser_preview(source: Path, output: Path, start: float, end: float):
    """Small seekable browser proxy; original media remains untouched."""
    run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-threads",
            "2",
            "-ss",
            str(start),
            "-i",
            str(source),
            "-t",
            str(end - start),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale=640:640:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "2",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(output),
        ],
        timeout=110,
    )

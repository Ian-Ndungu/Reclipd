from .edit_timing import transition_overlap, timeline_seconds
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
    if settings().low_memory_mode and Path(args[0]).name == "ffmpeg":
        args = [args[0], "-threads", "1", "-filter_threads", "1",
                "-filter_complex_threads", "1", *args[1:-1], "-threads", "1", args[-1]]
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
    try:
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
    finally:
        if cfg.low_memory_mode:
            _whisper = None
            import gc
            gc.collect()



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
    from .tracking import SubjectTracker, simplify, deduplicate

    frontal = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    if frontal.empty() or profile.empty():
        raise MediaError("Face detector is unavailable. Try manual crop or fit mode.")
    cap = cv2.VideoCapture(str(source))
    tracker = SubjectTracker(fallback)
    points = []
    previous = None
    previous_hist = None
    clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8))
    try:
        # Exact clip-relative positions: never inspect frames before a fractional trim.
        for index in range(max(1, math.ceil((end-start)*4))):
            relative = index / 4
            cap.set(cv2.CAP_PROP_POS_MSEC, (start + relative) * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            height, width = frame.shape[:2]
            small = cv2.resize(frame, (640, max(1, round(height * 640 / width))))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            thumbnail = cv2.resize(gray, (64, 36))
            hist = cv2.calcHist([gray], [0], None, [32], [0, 256])
            cv2.normalize(hist, hist)
            cut = (previous is not None and
                   cv2.compareHist(previous_hist, hist, cv2.HISTCMP_BHATTACHARYYA) > .5 and
                   float(cv2.absdiff(previous, thumbnail).mean()) / 255 > .18)
            previous, previous_hist = thumbnail, hist
            gray = clahe.apply(gray)
            boxes = list(frontal.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=6, minSize=(24, 24)))
            # Profiles in both directions improve coverage when a person turns away.
            for mirrored in (False, True):
                image = cv2.flip(gray, 1) if mirrored else gray
                for x, y, w, h in profile.detectMultiScale(image, scaleFactor=1.1, minNeighbors=6, minSize=(28, 28)):
                    boxes.append((640-x-w if mirrored else x, y, w, h))
            normalized = deduplicate([(float(x)/640,float(y)/gray.shape[0],float(w)/640,float(h)/gray.shape[0]) for x,y,w,h in boxes])
            old = tracker.focus
            focus = tracker.update(normalized, relative, cut)
            if cut and points and relative > points[-1][0]:
                points.append((relative-.001, old))
            points.append((relative, focus))
    finally:
        cap.release()
    if not points:
        return [(0, fallback)]
    if points[0][0] > 0:
        points.insert(0, (0, fallback))
    points.append((end-start, points[-1][1]))
    return simplify(points)


def output_size(media, resolution):
    # Avoid enlarging cropped source. Both dimensions remain even and exactly 9:16.
    units = max(
        1, min(resolution // 18, int(media["width"]) // 18, int(media["height"]) // 32)
    )
    return units * 18, units * 32


def tempo_filter(speed):
    # Chain supported factors to preserve pitch even at 0.25x and 4x.
    factors = []
    while speed < 0.5:
        factors.append("atempo=0.5")
        speed /= 0.5
    while speed > 2:
        factors.append("atempo=2")
        speed /= 2
    factors.append(f"atempo={speed}")
    return ",".join(factors)


def adjustment_filter(edits):
    # Numeric values are validated by EditDecision before reaching the renderer.
    filters = []
    if edits.get("flip_horizontal", False):
        filters.append("hflip")
    brightness = float(edits.get("brightness", 1))
    contrast = float(edits.get("contrast", 1))
    saturation = float(edits.get("saturation", 1))
    if brightness != 1:
        filters.append(f"colorchannelmixer=rr={brightness}:gg={brightness}:bb={brightness}")
    if contrast != 1 or saturation != 1:
        filters.append(f"eq=contrast={contrast}:saturation={saturation}")
    return ",".join(filters)


def crop_filter(media, width, height, mode, focus, tracking=None):
    if mode == "fit":
        return f"scale={width}:{height}:flags=lanczos:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    # Smoothed, bounded keyframes follow a consistent detected subject.
    expr = str(focus)
    if tracking:
        # A balanced expression avoids FFmpeg's recursive parser depth limit.
        def interval_expression(intervals):
            if len(intervals) == 1:
                (t, x), (next_t, next_x) = intervals[0]
                return f"({x:.5f}+({next_x-x:.5f})*clip((t-{t:.5f})/{max(.000001,next_t-t):.6f},0,1))"
            middle = len(intervals) // 2
            boundary = intervals[middle][0][0]
            return f"if(lt(t,{boundary:.5f}),{interval_expression(intervals[:middle])},{interval_expression(intervals[middle:])})"
        intervals = list(zip(tracking, tracking[1:]))
        expr = interval_expression(intervals) if intervals else str(tracking[0][1])
    return f"crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)':x='max(0,min(iw-ow,iw*({expr})-ow/2))':y='(ih-oh)/2',scale={width}:{height}:flags=lanczos,setsar=1"


def retime_words(words, segments, overlap=0):
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
        offset += end - start - overlap
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


def watermark_filter(width, height, path, duration=10):
    """Montserrat wordmark with eased cut/reveal, flip and landing rebounds."""
    size = max(14, round(width * .037))
    x, y = round(width * .045), round(height * .035)
    # ASS vector geometry avoids dependence on emoji or symbol font coverage.
    scissors = (
        "m 5 17 b 0 17 0 25 5 25 b 10 25 10 17 5 17 "
        "m 5 19 b 8 19 8 23 5 23 b 2 23 2 19 5 19 "
        "m 19 17 b 14 17 14 25 19 25 b 24 25 24 17 19 17 "
        "m 19 19 b 22 19 22 23 19 23 b 16 23 16 19 19 19 "
        "m 7 18 l 17 2 20 0 12 17 9 20 "
        "m 17 18 l 7 2 4 0 12 17 15 20"
    )
    scale = size / 25
    # Separate vector and text events share a fixed top-left safe area.
    content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Mark,Montserrat,{size},&H00FFFFFF,&H00FFFFFF,&H80201409,&H90000000,-1,0,0,0,100,100,{size*.045},0,1,{max(1,size*.05)},{size*.025},7,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    import math
    def stamp(seconds):
        cs = max(0, round(seconds * 100))
        return f"{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}"
    def event(start, end, text, layer=1):
        nonlocal content
        if end > start:
            content += f"Dialogue: {layer},{stamp(start)},{stamp(end)},Mark,,0,0,0,,{text}\n"
    starts = [0.0] + ([duration / 2] if duration > 15 else [])
    label_x = x + size * 1.8
    travel = size * 5.7
    puff = "m 0 5 b 0 0 10 0 10 5 b 10 10 0 10 0 5"
    for cycle, start in enumerate(starts):
        end = starts[cycle+1] if cycle+1 < len(starts) else duration
        # Short frame events allow acceleration, suspension-like bobbing and braking.
        for frame in range(60):
            t = frame / 30
            u = min(1, t / 1.4)
            eased = u*u*u*(u*(u*6-15)+10)
            sx = x + travel*eased
            sy = y + math.sin(u*math.pi*6)*size*.07*(1-u)
            angle = -90 + math.sin(u*math.pi*4)*8*(1-u)
            if t > 1.4:
                v = min(1, (t-1.4)/.6)
                ease_back = v*v*v*(v*(v*6-15)+10)
                sx = x + travel*(1-ease_back)
                sy = y-size*.65*math.sin(v*math.pi)
                angle = -90*(1-ease_back)
            pop = 1 + .12*math.sin(min(1,t/.3)*math.pi)
            icon = (rf"{{\an7\pos({sx:.2f},{sy:.2f})\frz{angle:.2f}"
                    rf"\fscx{scale*100*pop:.2f}\fscy{scale*100*pop:.2f}\p1}}{scissors}")
            event(start+t, min(end,start+t+1/30), icon, 3)
            # Reveal the word along the scissors' cutting path.
            edge = round(max(label_x, x + travel*eased + size))
            label = rf"{{\an7\pos({label_x},{y})\clip({round(label_x)},{y-5},{edge},{y+size*2})}}RECLIPD"
            event(start+t, min(end,start+t+1/30), label, 2)

        # Cyan dashed seam follows the cutting edge, then disperses.
        for dash in range(10):
            dx = label_x + dash*size*.32
            appears = .35 + dash*.085
            line = f"m 0 0 l {size*.19:.2f} 0 {size*.19:.2f} {max(1,size*.045):.2f} 0 {max(1,size*.045):.2f}"
            event(start+appears,min(end,start+1.8),
                  rf"{{\an7\pos({dx:.2f},{y+size*.55:.2f})\1c&HFFD17D&\bord0\shad0\fad(60,300)\p1}}{line}",4)
        # The WORD jumps independently of the parked scissors. Explicit
        # ballistic arcs and landing compression keep the bounce readable.
        for frame in range(54):
            t = frame/30
            bounce = 0.0
            rotation = 360.0
            stretch_x, stretch_y = 100.0, 100.0
            tilt = 0.0
            arcs = [(0, .80, 1.20), (.92, .40, .60), (1.42, .26, .25)]
            for launch, flight, height_factor in arcs:
                if launch <= t < launch+flight:
                    u = (t-launch)/flight
                    bounce = size*height_factor*4*u*(1-u)
                    stretch_y = 100+12*math.sin(math.pi*u)
                    stretch_x = 100-5*math.sin(math.pi*u)
                    if launch == 0:
                        rotation = 360*(u*u*u*(u*(u*6-15)+10))
                        tilt = -7*math.sin(2*math.pi*u)
                    break
            for landing, span, strength in [(.80,.12,.24),(1.32,.10,.15),(1.68,.12,.07)]:
                if landing <= t < landing+span:
                    compression = strength*math.sin(math.pi*(t-landing)/span)
                    stretch_x, stretch_y = 100*(1+compression),100*(1-compression)
            # Keep the baseline anchored during squash, rather than scaling
            # downward through it. Clamp motion inside the top safe area.
            ty = max(4,y-bounce+size*(1-stretch_y/100))
            tag = (rf"{{\an7\pos({label_x},{ty:.2f})"
                   rf"\org({label_x+size*1.7:.2f},{ty+size*.5:.2f})"
                   rf"\frx{rotation:.2f}\frz{tilt:.2f}"
                   rf"\fscx{stretch_x:.2f}\fscy{stretch_y:.2f}}}")
            event(start+2+t,min(end,start+2+t+1/30),tag+"RECLIPD",2)
        # Individual smoke puffs drift back/up, expand and dissolve.
        for n in range(10):
            t = .12+n*.11
            u = t/1.4
            sx = x+travel*(u*u*u*(u*(u*6-15)+10))
            sy = y+size*.7
            puff_scale = size*2
            tags = (rf"{{\an5\move({sx:.2f},{sy:.2f},{sx-size*.8:.2f},{sy-size*.5:.2f})"
                    rf"\1c&HCCD5E0&\alpha&H80&\bord0\shad0\blur1"
                    rf"\fscx{puff_scale}\fscy{puff_scale}"
                    rf"\t(0,650,\fscx{puff_scale*2.8}\fscy{puff_scale*2.8}\alpha&HFF&)\p1}}")
            event(start+t,min(end,start+t+.65),tags+puff,0)
        event(start+2,end,rf"{{\an7\pos({x},{y})\fscx{scale*100}\fscy{scale*100}\p1}}{scissors}",3)
        event(start+3.8,end,rf"{{\an7\pos({label_x},{y})}}RECLIPD",2)
    path.write_text(content, encoding="utf-8")
    escaped = str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"ass=filename='{escaped}'"


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
            adjustments = adjustment_filter(edits)
            if adjustments:
                vf += "," + adjustments
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
                "medium",
                "-crf",
                "17",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac", "-b:a", "192k",
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
        overlap = transition_overlap(edits)
        if overlap:
            previous = parts[0]
            length = edits["segments"][0]["end"] - edits["segments"][0]["start"]
            for index, part in enumerate(parts[1:], 1):
                transitioned = folder / f"transition{index}.mp4"
                offset = length - overlap
                graph = (f"[0:v]setpts=PTS-STARTPTS,fps=30,settb=AVTB[v0];"
                         f"[1:v]setpts=PTS-STARTPTS,fps=30,settb=AVTB[v1];"
                         f"[v0][v1]xfade=transition={edits['transition']}:duration={overlap}:offset={offset},format=yuv420p[v]")
                args = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(previous), "-i", str(part)]
                if media.get("has_audio"):
                    graph += f";[0:a][1:a]acrossfade=d={overlap}:c1=tri:c2=tri[a]"
                args += ["-filter_complex_threads", "1", "-filter_complex", graph, "-map", "[v]"]
                if media.get("has_audio"):
                    args += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
                args += ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30", str(transitioned)]
                run(args, timeout=600)
                previous = transitioned
                length += edits["segments"][index]["end"] - edits["segments"][index]["start"] - overlap
            joined = previous
        else:
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
                    "-preset", "medium", "-crf", "17",
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
                    "aac", "-b:a", "192k",
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
        words = retime_words(edits["words"], edits["segments"], overlap)
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
                timeline_seconds(edits),
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
                    "medium",
                    "-crf",
                    "17",
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
        speed = float(edits.get("speed", 1))
        length = timeline_seconds(edits) / speed
        fade_in = min(float(edits.get("fade_in", 0)), length / 2)
        fade_out = min(float(edits.get("fade_out", 0)), length / 2)
        if speed != 1 or fade_in or fade_out or edits.get("watermark", True):
            timed = folder / "timed.mp4"
            vf = [f"setpts=(PTS-STARTPTS)/{speed}"]
            af = ["asetpts=PTS-STARTPTS", tempo_filter(speed)]
            for kind, seconds, start in [("in", fade_in, 0), ("out", fade_out, length - fade_out)]:
                if seconds:
                    vf.append(f"fade=t={kind}:st={start}:d={seconds}")
                    af.append(f"afade=t={kind}:st={start}:d={seconds}")
            if edits.get("watermark", True):
                vf.append(watermark_filter(width, height, folder / "watermark.ass", length))
            args = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(output),
                    "-vf", ",".join(vf), "-r", "30", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "17", "-pix_fmt", "yuv420p"]
            if media.get("has_audio"):
                args += ["-af", ",".join(af), "-c:a", "aac", "-b:a", "192k"]
            args += ["-movflags", "+faststart", str(timed)]
            run(args, timeout=600)
            shutil.copyfile(timed, output)
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

"""Run inside the worker image to create a synthetic fixture and verify transcription.
No user's media or external footage is used.
"""

from pathlib import Path
import json
from app.media import run, probe, transcribe, extract_audio

source = Path("/data/qa-fixtures/reclipd-synthetic.mp4")
source.parent.mkdir(parents=True, exist_ok=True)
audio = source.with_suffix(".wav")
speech = "Welcome to Reclipd Studio. This is a short demonstration of automatic video clipping. A good story has a clear beginning and a useful ending. Find the moment that matters, make the words easy to read, and share your own perspective. Your original video stays safe while you create something new."
speech_file = Path("/tmp/reclipd-qa-speech.txt")
speech_file.write_text(speech)
run(
    [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x360:rate=30",
        "-f",
        "lavfi",
        "-i",
        f"flite=textfile={speech_file}:voice=slt",
        "-t",
        "22",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(source),
    ],
    timeout=120,
)
media = probe(source)
extract_audio(source, audio)
words, language = transcribe(
    audio,
    media["duration"],
    "en",
    lambda p: print(json.dumps({"transcription_progress": p}), flush=True),
)
assert len(words) > 10, f"Expected spoken words; got {len(words)}"
assert all(w["end"] > w["start"] for w in words)
print(
    json.dumps(
        {
            "fixture": str(source),
            "duration": media["duration"],
            "word_count": len(words),
            "language": language,
            "excerpt": " ".join(w["word"] for w in words[:12]),
        }
    ),
    flush=True,
)
audio.unlink(missing_ok=True)

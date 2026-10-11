"""Optional genuine speaker diarization from a provisioned local Pyannote model.

Disabled unless explicitly configured: no fabricated speaker labels or changes.
"""

from pathlib import Path
from .config import settings

_pipeline = None


def speaker_changes(audio: Path):
    global _pipeline
    model = settings().speaker_model_path
    if not model:
        return (
            [],
            "Speaker diarization is not configured; speaker-change signals are excluded.",
        )
    try:
        from pyannote.audio import Pipeline

        if _pipeline is None:
            _pipeline = Pipeline.from_pretrained(model)
        result = _pipeline(str(audio))
        annotation = getattr(result, "speaker_diarization", result)
        turns = sorted(
            (segment.start, segment.end, speaker)
            for segment, _, speaker in annotation.itertracks(yield_label=True)
        )
        changes = [
            float(current[0])
            for previous, current in zip(turns, turns[1:])
            if current[2] != previous[2]
        ]
        return changes, None
    except Exception:
        return (
            [],
            "Local speaker model unavailable; speaker-change signals are excluded.",
        )

import math
from pathlib import Path
import shutil
import pytest
from app.ranking import rank_candidates, generate_headlines
from app.media import (
    retime_words,
    write_ass,
    safe_ass,
    probe,
    run,
    render,
    MediaError,
    output_size,
)
from app.schemas import EditDecision, CaptionStyle


def words():
    return [
        {"start": i, "end": i + 0.8, "word": f"word{i}" + ("." if i % 9 == 8 else "")}
        for i in range(90)
    ]


def test_ranking_is_deterministic_grounded_and_nonoverlapping():
    cfg = {"clip_count": 3, "min_duration": 10, "max_duration": 25}
    first = rank_candidates(words(), [0, 20, 40, 60], [0.3] * 90, 90, cfg)
    assert first == rank_candidates(words(), [0, 20, 40, 60], [0.3] * 90, 90, cfg)
    assert len(first) == 3
    for c in first:
        assert 10 <= c["end"] - c["start"] <= 25
        assert 0 <= c["score"] <= 100
        assert len(c["reasons"]) == 5
        assert c["title"].startswith("word")
    for a, b in zip(first, first[1:]):
        assert (
            max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
            / min(a["end"] - a["start"], b["end"] - b["start"])
            < 0.35
        )


def test_silent_short_source_and_count_limit():
    candidates = rank_candidates(
        [], [], [], 4, {"clip_count": 10, "min_duration": 15, "max_duration": 60}
    )
    assert len(candidates) == 1
    assert candidates[0]["end"] == 4
    assert "no spoken transcript" in candidates[0]["description"]


@pytest.mark.parametrize(
    "tone", ["concise", "funny", "dramatic", "informative", "viral"]
)
def test_headlines_are_labeled_templates(tone):
    result = generate_headlines("We planted trees in our garden yesterday.", tone, 10)
    assert len(result) == 10
    assert all(
        "We planted trees" in h["text"]
        and h["source"] == "deterministic transcript template"
        for h in result
    )


def test_retime_cut_captions_preserves_correct_relative_time():
    result = retime_words(
        [{"start": 9, "end": 11, "word": "a"}, {"start": 21, "end": 22, "word": "b"}],
        [{"start": 10, "end": 12}, {"start": 20, "end": 23}],
    )
    assert result == [
        {"start": 0, "end": 1, "word": "a"},
        {"start": 3, "end": 4, "word": "b"},
    ]


def test_ass_injection_and_word_highlight(tmp_path):
    out = tmp_path / "captions.ass"
    write_ass(
        out,
        [{"start": 0, "end": 1, "word": r"{\pos(0,0)}hi"}],
        CaptionStyle().model_dump(),
        1080,
        1920,
    )
    content = out.read_text()
    assert r"{\pos" not in content
    assert "0:00:00.00,0:00:01.00" in content
    assert "PlayResX: 1080" in content


def test_output_does_not_upscale_and_is_vertical():
    w, h = output_size({"width": 1920, "height": 1080}, 1080)
    assert w / h == 9 / 16 and h <= 1080
    assert output_size({"width": 1080, "height": 1920}, 1080) == (1080, 1920)


@pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="FFmpeg integration runs in Docker worker"
)
def test_real_ffmpeg_inspect_split_caption_render(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "final.mp4"
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
            "sine=frequency=440:sample_rate=48000",
            "-t",
            "4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source),
        ]
    )
    media = probe(source)
    assert media["has_audio"] and media["width"] == 640
    edits = EditDecision(
        segments=[{"start": 0, "end": 1}, {"start": 2, "end": 4}],
        reframe="manual",
        show_headline=True,
        headline="Rendered headline",
        volume=0.25,
        captions=CaptionStyle(font="Inter", background=True, background_color="#112233", letter_spacing=2),
        words=[
            {"start": 0.1, "end": 0.8, "word": "RECLIPD"},
            {"start": 2.2, "end": 3.5, "word": "Studio"},
        ],
    ).model_dump()
    progress = []
    render(source, output, edits, media, progress.append)
    info = probe(output)
    assert info["width"] / info["height"] == 9 / 16
    assert abs(info["duration"] - 3) < 0.2
    assert progress[-1] == 98
    assert output.stat().st_size > 1000


@pytest.mark.skipif(
    not shutil.which("ffprobe"), reason="FFmpeg integration runs in Docker worker"
)
def test_invalid_media_rejected(tmp_path):
    path = tmp_path / "fake.mp4"
    path.write_bytes(b"not actually a video")
    with pytest.raises(MediaError):
        probe(path)


@pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="FFmpeg integration runs in Docker worker"
)
def test_auto_reframe_with_custom_font_and_logo(tmp_path):
    from PIL import Image

    source = tmp_path / "source.mp4"
    out = tmp_path / "branded.mp4"
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (40, 20), (50, 120, 255, 255)).save(logo)
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
            "-t",
            "3",
            "-c:v",
            "libx264",
            str(source),
        ]
    )
    media = probe(source)
    edits = EditDecision(
        segments=[{"start": 0, "end": 3}],
        reframe="auto",
        words=[{"start": 0, "end": 2, "word": "Branded"}],
    ).model_dump()
    edits["captions"]["animation"] = "fade"
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    render(
        source,
        out,
        edits,
        media,
        lambda p: None,
        custom_font=(font, "DejaVu Sans") if font.exists() else None,
        logo=logo,
    )
    assert out.exists() and probe(out)["height"] > probe(out)["width"]


def test_headline_length_and_distinct_source_angles(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings(), 'llm_base_url', '')
    result = generate_headlines('We tested the camera in heavy rain. The microphone stopped recording after ten minutes.', 'informative', 5, 60)
    assert all(len(h['text']) <= 60 for h in result)
    assert any('camera' in h['text'] for h in result)
    assert any('microphone' in h['text'] for h in result)


def test_invalid_llm_headlines_fall_back(monkeypatch):
    from app.config import settings
    from app.ranking import LocalLLM
    monkeypatch.setattr(settings(), 'llm_base_url', 'http://local-model/v1')
    for values in [['Repeated'] * 3, ['A' * 100, 'Valid', 'Another'], ['Won 100 dollars', 'A test', 'The result']]:
        import json
        monkeypatch.setattr(LocalLLM, 'complete', lambda self, prompt: json.dumps(values))
        result = generate_headlines('We tested a camera in the rain.', 'concise', 3, 60)
        assert all(h['source'] == 'deterministic transcript template' for h in result)


def test_headlines_use_only_retained_speech(signed, db, monkeypatch):
    from sqlalchemy import select
    from app.models import User, Project, Clip
    from app import ranking
    user = db.scalar(select(User))
    project = Project(user_id=user.id, name='Headline test', rights_confirmed=True)
    db.add(project); db.flush()
    clip = Clip(project_id=project.id, title='Test', start=0, end=20, score=50, description='', edits={
        'segments': [{'start':10, 'end':20}],
        'words': [{'start':0,'end':1,'word':'removed'}, {'start':11,'end':12,'word':'retained'}]})
    db.add(clip); db.commit()
    calls = []
    def generate(text, tone, count, max_characters):
        calls.append((text, max_characters))
        return [{'text':'Retained', 'tone':tone, 'source':'test'}] * count
    monkeypatch.setattr(ranking, 'generate_headlines', generate)
    response = signed.post(f'/api/clips/{clip.id}/headlines', json={'max_characters':60})
    assert response.status_code == 200 and calls == [('retained', 60)]
    clip.edits = {'segments':[{'start':30,'end':40}], 'words':clip.edits['words']}
    db.commit()
    assert signed.post(f'/api/clips/{clip.id}/headlines', json={}).status_code == 422

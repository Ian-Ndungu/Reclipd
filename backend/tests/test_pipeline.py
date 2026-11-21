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
        assert len(c["reasons"]) == 6
        assert c["title"].startswith("word")
    for a, b in zip(first, first[1:]):
        assert (
            max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
            / min(a["end"] - a["start"], b["end"] - b["start"])
            < 0.35
        )


def test_ranking_explains_real_opening_signals_and_pause_boundaries():
    source = [
        {"start": 0, "end": .5, "word": "Why?"},
        {"start": .6, "end": 1.1, "word": "You"},
        {"start": 1.2, "end": 1.7, "word": "need"},
        {"start": 1.8, "end": 2.3, "word": "this."},
        {"start": 3.5, "end": 4.0, "word": "But"},
        {"start": 4.1, "end": 4.6, "word": "only"},
        {"start": 4.7, "end": 5.2, "word": "today."},
    ]
    candidates = rank_candidates(source, [], [.2] * 8, 8, {"clip_count": 2, "min_duration": 3, "max_duration": 4})
    reasons = [reason for candidate in candidates for reason in candidate["reasons"]]
    assert any(reason.startswith("Opening clarity signals:") for reason in reasons)
    assert any("speech pause" in reason for reason in reasons)


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
@pytest.mark.parametrize("speed,transition", [(0.5,"none"), (1,"none"), (2,"none"), (2,"fade"), (1,"dissolve"), (1,"slideleft"), (1,"slideright"), (1,"wipeleft"), (1,"wiperight")])
def test_real_ffmpeg_inspect_split_caption_render(tmp_path, speed, transition):
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
        speed=speed,
        transition=transition,
        transition_duration=.3,
        fade_in=.2,
        fade_out=.2,
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
    assert abs(info["duration"] - (3 if transition == "none" else 2.7) / speed) < 0.25
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


def test_headlines_have_generation_date_but_reject_invented_recency(monkeypatch):
    import json
    from datetime import datetime, timezone
    from app.config import settings
    from app.ranking import LocalLLM
    monkeypatch.setattr(settings(), 'llm_base_url', 'http://local-model/v1')
    prompts = []
    def complete(self, prompt):
        prompts.append(prompt)
        return json.dumps(['Camera test today', 'Breaking camera news', 'Latest camera results'])
    monkeypatch.setattr(LocalLLM, 'complete', complete)
    result = generate_headlines('We tested the camera in heavy rain.', count=3)
    assert datetime.now(timezone.utc).date().isoformat() in prompts[0]
    assert 'NOT the recording or event date' in prompts[0]
    assert all(h['source'] == 'deterministic transcript template' for h in result)
    assert result[0]['text'] == 'We tested the camera in heavy rain.'


def test_headlines_accept_specific_grounded_model_copy(monkeypatch):
    import json
    from app.config import settings
    from app.ranking import LocalLLM
    monkeypatch.setattr(settings(), 'llm_base_url', 'http://local-model/v1')
    titles = ['Testing a camera in heavy rain', 'The microphone stopped recording', 'Rain test: camera versus microphone']
    monkeypatch.setattr(LocalLLM, 'complete', lambda self, prompt: json.dumps(titles))
    result = generate_headlines('We tested the camera in heavy rain. The microphone stopped recording.', count=3)
    assert [h['text'] for h in result] == titles


def test_picture_adjustments_validation_and_filters():
    from app.media import adjustment_filter
    from pydantic import ValidationError
    assert adjustment_filter({}) == ''
    edits = EditDecision(segments=[{'start': 0, 'end': 5}], brightness=1.1, contrast=1.2, saturation=0, flip_horizontal=True)
    filters = adjustment_filter(edits.model_dump())
    assert 'hflip' in filters
    assert 'rr=1.1' in filters
    assert 'contrast=1.2:saturation=0.0' in filters
    for key, value in [('brightness', 3), ('contrast', -1), ('saturation', 4)]:
        with pytest.raises(ValidationError):
            EditDecision(segments=[{'start': 0, 'end': 5}], **{key: value})


def test_speed_limits_and_audio_tempo():
    from app.media import tempo_filter
    from pydantic import ValidationError
    assert tempo_filter(.25) == 'atempo=0.5,atempo=0.5'
    assert tempo_filter(4) == 'atempo=2,atempo=2.0'
    for key, value in [('speed', 0), ('speed', 5), ('fade_in', -1), ('fade_out', 3)]:
        with pytest.raises(ValidationError):
            EditDecision(segments=[{'start': 0, 'end': 5}], **{key: value})


def test_transition_timing_matches_captions_and_billing():
    from app.edit_timing import transition_overlap, timeline_seconds
    from app.credits import export_seconds
    edits = EditDecision(segments=[{'start':0,'end':1},{'start':5,'end':8}], transition='fade',transition_duration=1,speed=2).model_dump()
    assert transition_overlap(edits)==.5
    assert timeline_seconds(edits)==3.5
    assert export_seconds(edits)==1.75
    words=retime_words([{'start':5,'end':6,'word':'Next'}], edits['segments'],transition_overlap(edits))
    assert words[0]['start']==.5


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg integration runs in Docker worker')
def test_transitions_with_three_cuts_and_silent_source(tmp_path):
    source=tmp_path/'silent.mp4';output=tmp_path/'export.mp4'
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=24','-t','4','-c:v','libx264',str(source)])
    media=probe(source)
    edits=EditDecision(segments=[{'start':0,'end':1},{'start':1,'end':2},{'start':2,'end':4}], reframe='fit',transition='fade',transition_duration=.3,captions=CaptionStyle(enabled=False)).model_dump()
    render(source,output,edits,media,lambda _:None)
    result=probe(output)
    assert not result['has_audio']
    assert abs(result['duration']-3.4)<.2

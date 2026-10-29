import pytest
from app.brief import parse_brief
from app.ranking import rank_candidates


def candidates(brief):
    words = [dict(start=i, end=i + .8, word=('sponsorship.' if i < 15 else 'launch.')) for i in range(45)]
    return rank_candidates(words, [], [.2] * 45, 45, dict(instructions=brief, min_duration=5, max_duration=10, clip_count=2))


def test_parse_exclusion_and_range():
    positive, excluded, ranges = parse_brief('Focus on launch. Avoid sponsorships. 01:00–02:00')
    assert positive == {'launch'}
    assert excluded == [{'sponsorship'}]
    assert ranges == [(60, 120)]


def test_relevance_and_exclusion(monkeypatch):
    monkeypatch.setattr('app.ranking.settings', lambda: type('Settings', (), {'llm_base_url': ''})())
    clips = candidates('Focus on launch. Avoid sponsorship.')
    assert clips and all(c['start'] >= 15 for c in clips)
    assert all('Instruction topic coverage' in ' '.join(c['reasons']) for c in clips)


def test_timestamp_constraints():
    clips = candidates('00:20–00:35')
    assert clips and all(c['start'] >= 20 and c['end'] <= 35 for c in clips)


def test_impossible_range():
    with pytest.raises(ValueError, match='No clips fit'):
        candidates('00:40–00:42')
    with pytest.raises(ValueError, match='end after'):
        candidates('00:30–00:10')


def test_unmatched_brief(monkeypatch):
    monkeypatch.setattr('app.ranking.settings', lambda: type('Settings', (), {'llm_base_url': ''})())
    with pytest.raises(ValueError, match='No transcript keywords'):
        candidates('astronomy')

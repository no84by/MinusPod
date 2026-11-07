"""Whisper hallucination-loop guard: detection, and the validator hold."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ad_validator import AdValidator, Decision
from config import HOLD_REASON_TRANSCRIPT_LOOP
from transcript_loop import drop_loop_cues, find_loop_runs

FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'transcript_loop_cues.json')


def _cues(rows):
    return [{'start': a, 'end': b, 'text': t} for a, b, t in rows]


def _loop(start, n, step=1.0):
    return _cues([(start + i * step, start + (i + 1) * step,
                   'line A' if i % 2 == 0 else 'line B') for i in range(n)])


def _speech(start, n):
    words = ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot']
    return _cues([(start + i * 3.0, start + i * 3.0 + 2.5,
                   f'{words[i % 6]} sentence number {i * 7919} about the show')
                  for i in range(n)])


def _held(segments, start, end):
    ad = {'start': start, 'end': end, 'confidence': 0.95, 'category': 'cross_promo',
          'detection_stage': 'verification', 'reason': 'promo for another show'}
    out = AdValidator(episode_duration=2000.0, segments=segments).validate([ad]).ads[0]
    return out


def test_synthetic_loop_is_one_run():
    runs = find_loop_runs(_loop(100.0, 40))
    assert runs == [(100.0, 140.0, 40)]


def test_identical_cues_loop():
    segs = _cues([(i, i + 1.0, 'watch the full episode') for i in range(10)])
    assert len(find_loop_runs(segs)) == 1


def test_clean_transcript_has_no_runs():
    segs = _speech(0.0, 200)
    assert find_loop_runs(segs) == []
    assert drop_loop_cues(segs) is segs


def test_short_run_and_long_cues_are_not_loops():
    assert find_loop_runs(_loop(0.0, 7)) == []
    long_cues = _cues([(i * 6.0, i * 6.0 + 5.0, 'same words again') for i in range(12)])
    assert find_loop_runs(long_cues) == []


def test_economist_fixture_run_covers_the_loop():
    with open(FIXTURE) as f:
        segs = _cues(json.load(f))
    runs = find_loop_runs(segs)
    assert runs and runs[-1][0] <= 692.0 and runs[-1][1] >= 1229.0
    assert not any(c['text'].startswith('show line') for c in drop_loop_cues(segs)
                   if c['start'] > 700 and c['end'] < 1229)


def test_marker_coverage_threshold_holds_never_cuts():
    segs = _speech(0.0, 20) + _loop(60.0, 40) + _speech(100.0, 20)
    held = _held(segs, 76.0, 126.0)    # 24 of 50 s = 48%: not held
    assert held.get('hold_reason') != HOLD_REASON_TRANSCRIPT_LOOP
    held = _held(segs, 70.0, 120.0)    # 30 of 50 s = 60%: held
    assert held['hold_reason'] == HOLD_REASON_TRANSCRIPT_LOOP
    assert held['held_for_review'] and held['validation']['decision'] == Decision.REVIEW.value
    held = _held(segs, 92.0, 132.0)    # 8 of 40 s = 20%: not held
    assert held.get('hold_reason') != HOLD_REASON_TRANSCRIPT_LOOP


def test_clean_transcript_marker_not_held_for_loop():
    ad = _held(_speech(0.0, 100), 50.0, 110.0)
    assert ad.get('hold_reason') != HOLD_REASON_TRANSCRIPT_LOOP

"""Detect Whisper hallucination loops: runs of near-identical short cues."""
import re
from difflib import SequenceMatcher

LOOP_MIN_CUES = 8            # shortest run that counts as a loop
LOOP_MAX_CUE_SECONDS = 4.0   # a loop cue is shorter than this
LOOP_SIMILARITY = 0.9        # normalised-text ratio that counts as a repeat
LOOP_PERIOD = 2              # a cue repeats one of the previous two (A,B,A,B loops)
LOOP_MIN_COVERAGE = 0.5      # share of a marker inside loops that makes it unprovable

_NON_WORD_RE = re.compile(r'[^\w ]')


def _norm(text: str) -> str:
    return _NON_WORD_RE.sub('', (text or '').lower()).strip()


def _short(seg: dict) -> bool:
    return 0 <= seg['end'] - seg['start'] < LOOP_MAX_CUE_SECONDS


def find_loop_runs(segments: list[dict]) -> list[tuple[float, float, int]]:
    """Return (start, end, cue_count) per run of >= LOOP_MIN_CUES repeating short cues."""
    norms = [_norm(s.get('text')) for s in segments]
    flags = [False] * len(segments)
    for i, seg in enumerate(segments):
        for k in range(1, LOOP_PERIOD + 1):
            if (norms[i] and i - k >= 0 and _short(seg) and _short(segments[i - k])
                    and SequenceMatcher(None, norms[i], norms[i - k]).ratio() >= LOOP_SIMILARITY):
                flags[i] = flags[i - k] = True   # the repeated cue seeds the run too
                break
    runs, i = [], 0
    while i < len(segments):
        if not flags[i]:
            i += 1
            continue
        j = i
        while j < len(segments) and flags[j]:
            j += 1
        if j - i >= LOOP_MIN_CUES:
            runs.append((segments[i]['start'], segments[j - 1]['end'], j - i))
        i = j
    return runs


def loop_coverage(runs: list[tuple[float, float, int]], start: float, end: float) -> float:
    """Fraction of [start, end] inside loop runs."""
    if end <= start:
        return 0.0
    return sum(max(0.0, min(b, end) - max(a, start)) for a, b, _ in runs) / (end - start)


def drop_loop_cues(segments: list[dict], runs=None) -> list[dict]:
    """Segments without cues inside a loop run: they are no evidence either way."""
    runs = find_loop_runs(segments) if runs is None else runs
    if not runs:
        return segments
    return [s for s in segments if not any(a <= s['start'] and s['end'] <= b for a, b, _ in runs)]

"""SPECS.md §7.4 speech metrics — pure functions over a transcript + timing data.

Deliberately computed server-side rather than in the browser: the metric
definitions have to stay identical when the voice layer is swapped from the Web
Speech API to a server-side streaming provider (Deepgram / Gemini Live), or
reports generated before and after the swap stop being comparable. Callers hand
in a normalized envelope (transcript, duration, optional segments) — nothing in
here knows which provider produced it.

No I/O, so this is unit-testable directly like matching_service.py and
interview_state_machine.py.
"""

import re

from app.schemas.interview import TranscriptSegment

# §7.4's list verbatim. Multi-word entries are matched as phrases.
FILLER_PHRASES = ("um", "uh", "like", "you know", "sort of")

_WORD_RE = re.compile(r"[a-z0-9']+")


def _words(transcript: str) -> list[str]:
    return _WORD_RE.findall(transcript.lower())


def count_fillers(transcript: str) -> int:
    """Total filler occurrences, phrases included. Matched on word boundaries so
    'like' doesn't fire inside 'unlike' and 'um' doesn't fire inside 'umbrella'."""
    normalized = " ".join(_words(transcript))
    if not normalized:
        return 0
    return sum(
        len(re.findall(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized)) for phrase in FILLER_PHRASES
    )


def longest_pause_ms(segments: list[TranscriptSegment] | None) -> float | None:
    """Longest silence *between* spoken segments. Returns None when the caller
    supplied no segments — §7.4 allows approximating from provider timing events,
    but a fabricated number is worse than an absent one, so this stays null and
    the report simply omits it.

    The gap before the first segment is excluded on purpose: that's the
    candidate thinking before they start, not a pause mid-answer.
    """
    if not segments or len(segments) < 2:
        return None

    ordered = sorted(segments, key=lambda s: s.start_ms)
    gaps = [
        max(0.0, later.start_ms - earlier.end_ms)
        for earlier, later in zip(ordered, ordered[1:], strict=False)
    ]
    return max(gaps) if gaps else None


def compute_speech_metrics(
    transcript: str,
    duration_seconds: float,
    segments: list[TranscriptSegment] | None = None,
    source: str = "browser_speech",
) -> dict | None:
    """Per-turn metrics. Returns None for an empty transcript (a skipped or
    silent turn has nothing to measure) so the caller can leave the column NULL."""
    words = _words(transcript)
    if not words:
        return None

    wpm = (len(words) / (duration_seconds / 60)) if duration_seconds > 0 else None

    return {
        "word_count": len(words),
        "duration_seconds": duration_seconds,
        "wpm": round(wpm, 1) if wpm is not None else None,
        "filler_count": count_fillers(transcript),
        "longest_pause_ms": longest_pause_ms(segments),
        # Which voice provider produced this transcript. Kept so a report spanning
        # the eventual provider swap is still interpretable.
        "source": source,
    }


def aggregate_speech_metrics(per_turn: list[dict | None]) -> dict | None:
    """Session-level rollup for the report. avg_wpm is total words over total
    speaking time — not a mean of per-turn WPMs, which would over-weight short
    answers."""
    metrics = [m for m in per_turn if m]
    if not metrics:
        return None

    total_words = sum(m.get("word_count") or 0 for m in metrics)
    total_seconds = sum(m.get("duration_seconds") or 0 for m in metrics)
    pauses = [m["longest_pause_ms"] for m in metrics if m.get("longest_pause_ms") is not None]

    return {
        "avg_wpm": round(total_words / (total_seconds / 60), 1) if total_seconds > 0 else None,
        "total_words": total_words,
        "total_speaking_seconds": round(total_seconds, 1),
        "total_filler_count": sum(m.get("filler_count") or 0 for m in metrics),
        "longest_pause_ms": max(pauses) if pauses else None,
        "turns_measured": len(metrics),
    }

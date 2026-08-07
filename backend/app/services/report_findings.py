"""Post-interview findings — the contents of the report's "Strengths" and
"Areas to Improve" columns.

Pure functions over turns that are already in the database. No I/O, no LLM call:
every input here was paid for during the interview itself (per-dimension scores
from `evaluate_answer`, speech metrics from `speech_metrics.py`), and a report
must be re-derivable offline for the backfill script to work.

**Patterns, not per-question lists.** With 5-8 turns x 3 dimensions, "specificity
averaged 2.3 across 6 answers, and here is what to do about it" is far more
actionable than a list of question titles — and the per-question view already
exists on the same page in `TurnBreakdown`. This supersedes SPECS.md §7.5's
"turns scoring 4-5 across the board"; see docs/decisions.md.

**Findings are facts plus a stable `code`, never prose.** The frontend owns every
user-visible word (`components/interview/report-findings.tsx`). Wording gets
iterated on; re-running a data backfill for a copy tweak would not be tolerable.
"""

from app.models.interview import InterviewTurn
from app.services.speech_metrics import aggregate_speech_metrics

# Key order of the `score` dict, and the render order in TurnBreakdown. Reused
# here as the tie-break so a third arbitrary ordering never enters the product.
DIMENSIONS = ("structure", "specificity", "relevance")

# Same weighting as `interview_service.aggregate_report`'s overall_score. Sharing
# it is what makes the three dimension averages reconcile with the headline
# number: with complete scores, mean(dimension averages) == overall_score. A user
# who sees 3.4 overall beside 3.0/3.0/3.0 stops trusting every number on the page.
TURN_WEIGHT = {"main": 1.0, "follow_up": 0.5}

STRONG_AVERAGE = 3.5
WEAK_AVERAGE = 2.5

# Relative ranking is a *bounded* fallback, used only when no dimension clears an
# absolute threshold. Relative-best is not a strength: someone averaging
# 1.7/1.6/1.8 must never be congratulated on relevance. One fake line poisons
# every real number on the page, so the floor is non-negotiable.
RELATIVE_STRENGTH_FLOOR = 3.0
RELATIVE_IMPROVEMENT_CEILING = 4.0

# Delivery needs enough speech to mean anything. Without this floor a 24-word
# session gets told it speaks too slowly.
MIN_WORDS_FOR_DELIVERY = 50
MIN_WORDS_FOR_FILLER_PRAISE = 100

# `SpeechMetricsCard` calls 120-160 wpm comfortable and says so on the same page.
# The flag thresholds sit outside that band on purpose: the 110-120 and 160-170
# dead zones guarantee the page never praises a pace in one card and scolds it in
# the other, and nobody gets nagged at 118 wpm.
COMFORTABLE_WPM = (120.0, 160.0)
SLOW_WPM = 110.0
FAST_WPM = 170.0

# Rate, not count — a long interview would otherwise always look worse than a
# short one. Generous, because FILLER_PHRASES includes a bare "like", which
# over-counts ordinary use ("companies like Stripe").
LOW_FILLER_RATE = 1.0
HIGH_FILLER_RATE = 3.0

LONG_PAUSE_MS = 5000.0

_DELIVERY_STRENGTHS = frozenset({"pace_comfortable", "fillers_low"})


def _dim(turn: InterviewTurn, dimension: str) -> int | None:
    """One dimension's score, or None if it isn't a usable integer.

    Deliberately not `turn.score[dimension]`. `AnswerEvaluation` guarantees all
    three keys today, but the backfill runs over rows written by older code, and
    a KeyError inside a batch job is a bad way to discover that.
    """
    value = (turn.score or {}).get(dimension)
    return value if isinstance(value, int) else None


def turn_weight(turn: InterviewTurn) -> float:
    """Public because `interview_service.aggregate_report` weights the headline
    `overall_score` with the same function. Two copies of this drifting apart is
    exactly what `TURN_WEIGHT` above exists to prevent."""
    return TURN_WEIGHT.get(turn.question_type, 1.0)


def turn_average(turn: InterviewTurn) -> float | None:
    """Mean of the dimensions that are actually usable, or None if none are.

    Averaging over *present* dimensions rather than skipping the whole turn keeps
    a partially-scored row contributing what it legitimately can. Shared with
    `aggregate_report` for the same reason as `turn_weight`.
    """
    scores = [s for d in DIMENSIONS if (s := _dim(turn, d)) is not None]
    return sum(scores) / len(scores) if scores else None


def _finding(
    kind: str,
    code: str,
    *,
    basis: str | None = None,
    dimension: str | None = None,
    average: float | None = None,
    turns_counted: int = 0,
    metric: dict | None = None,
    exemplar: dict | None = None,
) -> dict:
    """Every finding carries all eight keys, nulls included — a fixed shape is far
    easier to narrow in TypeScript and to assert in tests than an optional bag."""
    return {
        "kind": kind,
        "code": code,
        "basis": basis,
        "dimension": dimension,
        "average": round(average, 1) if average is not None else None,
        "turns_counted": turns_counted,
        "metric": metric,
        "exemplar": exemplar,
    }


def _dimension_averages(scored: list[InterviewTurn]) -> dict[str, tuple[float, int]]:
    """`{dimension: (unrounded average, turns behind it)}`, omitting dimensions
    no turn scored. Unrounded because ordering derives from these — sorting on
    rounded values makes the ranking flip on a 0.001 change."""
    averages: dict[str, tuple[float, int]] = {}
    for dimension in DIMENSIONS:
        contributing = [t for t in scored if _dim(t, dimension) is not None]
        weight_total = sum(turn_weight(t) for t in contributing)
        if not contributing or weight_total == 0:
            continue
        weighted = sum(_dim(t, dimension) * turn_weight(t) for t in contributing)
        averages[dimension] = (weighted / weight_total, len(contributing))
    return averages


def _exemplar(turn: InterviewTurn, dimension: str | None) -> dict:
    return {
        "turn_number": turn.turn_number,
        "question_text": turn.question_text,
        "score": _dim(turn, dimension) if dimension else None,
        "targets_gap": turn.targets_gap,
    }


def _pick_exemplar(
    scored: list[InterviewTurn], dimension: str, *, best: bool
) -> dict | None:
    """The single turn that best demonstrates this dimension being strong (or weak).

    A main question is preferred over a follow-up because follow-up text is often
    a fragment ("Can you say more about the rollback?") that reads badly quoted
    out of context. The test is `!= "follow_up"` rather than `== "main"` on
    purpose: `question_type` is nullable and the LLM has emitted junk categories
    before, and junk should sort as a main question, not as a follow-up.
    """
    candidates = [t for t in scored if _dim(t, dimension) is not None]
    if not candidates:
        return None

    sign = -1 if best else 1

    def sort_key(turn: InterviewTurn):
        return (
            sign * _dim(turn, dimension),
            turn.question_type == "follow_up",
            turn.targets_gap is None,
            sign * (turn_average(turn) or 0.0),
            turn.turn_number,
        )

    return _exemplar(min(candidates, key=sort_key), dimension)


def _delivery_findings(speech: dict | None) -> tuple[list[dict], list[dict]]:
    """(strengths, improvements) derived from the session speech rollup."""
    if not speech or not speech.get("turns_measured"):
        return [], []

    total_words = speech.get("total_words") or 0
    if total_words < MIN_WORDS_FOR_DELIVERY:
        return [], []

    filler_count = speech.get("total_filler_count") or 0
    filler_rate = filler_count / total_words * 100
    wpm = speech.get("avg_wpm")
    pause = speech.get("longest_pause_ms")

    metric = {
        "avg_wpm": wpm,
        "fillers_per_100_words": round(filler_rate, 1),
        "total_filler_count": filler_count,
        "total_words": total_words,
        "longest_pause_ms": pause,
    }

    pace: dict | None = None
    fillers: dict | None = None
    long_pause: dict | None = None

    if wpm is not None:
        if COMFORTABLE_WPM[0] <= wpm <= COMFORTABLE_WPM[1]:
            pace = _finding("delivery", "pace_comfortable", metric=metric)
        elif wpm > FAST_WPM:
            pace = _finding("delivery", "pace_fast", metric=metric)
        elif wpm < SLOW_WPM:
            pace = _finding("delivery", "pace_slow", metric=metric)

    if filler_rate >= HIGH_FILLER_RATE:
        fillers = _finding("delivery", "fillers_high", metric=metric)
    elif filler_rate < LOW_FILLER_RATE and total_words >= MIN_WORDS_FOR_FILLER_PRAISE:
        fillers = _finding("delivery", "fillers_low", metric=metric)

    if pause is not None and pause >= LONG_PAUSE_MS:
        long_pause = _finding("delivery", "long_pause", metric=metric)

    strengths = [f for f in (pace, fillers) if f and f["code"] in _DELIVERY_STRENGTHS]
    # A filler habit is the most fixable of the three; a single long silence is
    # the least diagnostic, so it sorts last.
    improvements = [
        f for f in (fillers, pace, long_pause) if f and f["code"] not in _DELIVERY_STRENGTHS
    ]

    # Delivery findings carry no exemplar: per-turn wpm on a short answer is noise.
    return strengths, improvements


def build_findings(turns: list[InterviewTurn]) -> dict[str, list[dict]]:
    """The two report columns, as `{"strengths": [...], "improvement_areas": [...]}`.

    Ordered most-important-first; every qualifying finding is emitted and the
    frontend decides how many to show. Capping here would bake a presentation
    decision into stored data.
    """
    answered = [t for t in turns if t.answer_transcript is not None]
    skipped = [t for t in answered if t.answer_transcript == ""]
    scored = [t for t in answered if t.score]
    unscored = [t for t in answered if t.answer_transcript != "" and not t.score]

    speech = aggregate_speech_metrics([t.speech_metrics for t in turns])
    delivery_strengths, delivery_improvements = _delivery_findings(speech)

    if not scored:
        # Nothing was scored: every answer was skipped, or every evaluation
        # failed. Saying so plainly beats two empty columns, and a `questions_
        # skipped` finding alongside it would just restate the same fact.
        return {
            "strengths": delivery_strengths,
            "improvement_areas": [
                _finding(
                    "participation",
                    "no_scored_answers",
                    metric={
                        "answered": len(answered),
                        "skipped": len(skipped),
                        "unscored": len(unscored),
                    },
                )
            ],
        }

    averages = _dimension_averages(scored)

    by_average_desc = sorted(averages, key=lambda d: (-averages[d][0], DIMENSIONS.index(d)))
    by_average_asc = sorted(averages, key=lambda d: (averages[d][0], DIMENSIONS.index(d)))

    strong = [(d, "absolute") for d in by_average_desc if averages[d][0] >= STRONG_AVERAGE]
    if not strong and by_average_desc:
        best = by_average_desc[0]
        if averages[best][0] >= RELATIVE_STRENGTH_FLOOR:
            strong = [(best, "relative")]

    # A dimension may never appear in both columns. Without this, a uniform 3.0
    # session reports "strongest: structure" and "weakest: structure".
    claimed = {d for d, _ in strong}
    weak = [
        (d, "absolute")
        for d in by_average_asc
        if averages[d][0] <= WEAK_AVERAGE and d not in claimed
    ]
    if not weak:
        remaining = [d for d in by_average_asc if d not in claimed]
        if remaining and averages[remaining[0]][0] <= RELATIVE_IMPROVEMENT_CEILING:
            weak = [(remaining[0], "relative")]

    def dimension_finding(dimension: str, basis: str, *, best: bool) -> dict:
        average, count = averages[dimension]
        return _finding(
            "dimension",
            f"{dimension}_{'strong' if best else 'weak'}",
            basis=basis,
            dimension=dimension,
            average=average,
            turns_counted=count,
            exemplar=_pick_exemplar(scored, dimension, best=best),
        )

    strengths = [dimension_finding(d, basis, best=True) for d, basis in strong]
    improvements = [dimension_finding(d, basis, best=False) for d, basis in weak]

    skipped_finding = (
        _finding(
            "participation",
            "questions_skipped",
            metric={"skipped": len(skipped), "answered": len(answered)},
            exemplar=_exemplar(skipped[0], None) if skipped else None,
        )
        if skipped
        else None
    )

    if skipped_finding and len(skipped) * 2 >= len(answered):
        # Skipping four of six questions is the headline; skipping one of six is
        # a footnote. Position says which one this is.
        improvements.insert(0, skipped_finding)
    elif skipped_finding:
        improvements.append(skipped_finding)

    improvements.extend(delivery_improvements)

    if len(answered) >= 2 and not skipped and not unscored:
        strengths.append(_finding("participation", "all_questions_answered",
                                  metric={"answered": len(answered)}))
    strengths.extend(delivery_strengths)

    return {"strengths": strengths, "improvement_areas": improvements}

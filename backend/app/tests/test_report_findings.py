"""Pure tests for report_findings.build_findings — no DB, no HTTP, no LLM.

Same in-memory style as test_interview_state_machine.py: ORM objects constructed
directly, never persisted.
"""

import json

import pytest

from app.models.interview import InterviewTurn
from app.services import report_findings as rf
from app.services.interview_service import aggregate_report


def make_turn(
    turn_number: int,
    scores: tuple[int, int, int] | dict | None = (3, 3, 3),
    *,
    question_type: str = "main",
    targets_gap: str | None = None,
    answered: bool = True,
    skipped: bool = False,
    speech: dict | None = None,
) -> InterviewTurn:
    if skipped:
        transcript = ""
    elif answered:
        transcript = "an answer"
    else:
        transcript = None

    if scores is None or skipped or not answered:
        score = None
    elif isinstance(scores, dict):
        score = scores
    else:
        score = dict(zip(rf.DIMENSIONS, scores, strict=True))

    return InterviewTurn(
        turn_number=turn_number,
        question_text=f"Q{turn_number}",
        question_type=question_type,
        targets_gap=targets_gap,
        answer_transcript=transcript,
        score=score,
        speech_metrics=speech,
    )


def codes(findings: list[dict]) -> list[str]:
    return [f["code"] for f in findings]


def make_speech(
    *, word_count: int, duration_seconds: float, filler_count: int = 0, pause: float | None = None
) -> dict:
    return {
        "word_count": word_count,
        "duration_seconds": duration_seconds,
        "wpm": round(word_count / (duration_seconds / 60), 1),
        "filler_count": filler_count,
        "longest_pause_ms": pause,
        "source": "server_stt",
    }


# --------------------------------------------------------------------------
# Dimension selection
# --------------------------------------------------------------------------


def test_all_fives_reports_three_absolute_strengths_and_no_weak_dimension():
    result = rf.build_findings([make_turn(i, (5, 5, 5)) for i in range(1, 7)])

    dimension_strengths = [f for f in result["strengths"] if f["kind"] == "dimension"]
    assert codes(dimension_strengths) == ["structure_strong", "specificity_strong", "relevance_strong"]
    assert all(f["basis"] == "absolute" for f in dimension_strengths)
    assert all(f["average"] == 5.0 and f["turns_counted"] == 6 for f in dimension_strengths)
    assert [f for f in result["improvement_areas"] if f["kind"] == "dimension"] == []


def test_all_ones_never_invents_a_strength():
    """The anti-fake-strength guard. Relative-best is not a strength: someone
    averaging 1.0 across the board must not be congratulated on anything."""
    result = rf.build_findings([make_turn(i, (1, 1, 1)) for i in range(1, 7)])

    assert [f for f in result["strengths"] if f["kind"] == "dimension"] == []
    assert codes([f for f in result["improvement_areas"] if f["kind"] == "dimension"]) == [
        "structure_weak",
        "specificity_weak",
        "relevance_weak",
    ]


def test_uniform_threes_produce_one_relative_item_per_column_on_different_dimensions():
    """The reported bug: 3/3/3 cleared no absolute threshold, so both columns
    came back empty and the page said nothing at all."""
    result = rf.build_findings([make_turn(i, (3, 3, 3)) for i in range(1, 7)])

    strong = [f for f in result["strengths"] if f["kind"] == "dimension"]
    weak = [f for f in result["improvement_areas"] if f["kind"] == "dimension"]

    assert len(strong) == 1 and len(weak) == 1
    assert strong[0]["basis"] == "relative" and weak[0]["basis"] == "relative"
    assert strong[0]["dimension"] != weak[0]["dimension"]


def test_mixed_scores_use_absolute_thresholds_and_leave_the_middle_out():
    result = rf.build_findings([make_turn(i, (5, 2, 3)) for i in range(1, 5)])

    strong = [f for f in result["strengths"] if f["kind"] == "dimension"]
    weak = [f for f in result["improvement_areas"] if f["kind"] == "dimension"]

    assert codes(strong) == ["structure_strong"]
    assert codes(weak) == ["specificity_weak"]
    assert strong[0]["basis"] == "absolute" and weak[0]["basis"] == "absolute"
    # relevance at 3.0 falls between the thresholds, so it is reported as neither
    # rather than being padded into a column to fill space.
    assert "relevance" not in {f["dimension"] for f in strong + weak}


@pytest.mark.parametrize(
    "scores",
    [
        (1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4), (5, 5, 5),
        (1, 3, 5), (5, 3, 1), (2, 4, 3), (4, 2, 4), (3, 5, 2), (1, 5, 3), (4, 4, 1),
    ],
)
def test_no_dimension_ever_appears_in_both_columns(scores):
    result = rf.build_findings([make_turn(i, scores) for i in range(1, 4)])

    strong = {f["dimension"] for f in result["strengths"] if f["kind"] == "dimension"}
    weak = {f["dimension"] for f in result["improvement_areas"] if f["kind"] == "dimension"}
    assert strong & weak == set()


def test_dimension_strengths_are_ordered_by_unrounded_average():
    # 3.4999 vs 3.5001 — identical once rounded to one decimal, so ordering must
    # not be derived from the rounded value.
    turns = [make_turn(1, (5, 4, 4)), make_turn(2, (4, 4, 5)), make_turn(3, (5, 5, 5))]
    result = rf.build_findings(turns)

    averages = [f["average"] for f in result["strengths"] if f["kind"] == "dimension"]
    assert averages == sorted(averages, reverse=True)


# --------------------------------------------------------------------------
# Numeric agreement with the headline score
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "turns_spec",
    [
        [(1, (5, 4, 3), "main"), (2, (2, 3, 4), "main")],
        [(1, (5, 5, 5), "main"), (2, (1, 1, 1), "follow_up"), (3, (3, 4, 2), "main")],
        [(1, (4, 2, 3), "follow_up"), (2, (2, 5, 1), "follow_up")],
    ],
)
def test_dimension_averages_reconcile_with_overall_score(turns_spec):
    """mean(dimension averages) == overall_score exactly, for complete scores.

    They share `TURN_WEIGHT` precisely so the page never shows 3.4 overall beside
    three dimension averages that don't average to 3.4.
    """
    turns = [make_turn(n, s, question_type=qt) for n, s, qt in turns_spec]
    averages = rf._dimension_averages(turns)
    assert len(averages) == 3

    mean_of_dimensions = sum(a for a, _ in averages.values()) / 3
    assert mean_of_dimensions == pytest.approx(aggregate_report(turns, [])["overall_score"], abs=1e-9)


def test_follow_up_turns_count_half_as_much_as_main_turns():
    turns = [make_turn(1, (5, 5, 5), question_type="main"),
             make_turn(2, (1, 1, 1), question_type="follow_up")]
    # (5*1.0 + 1*0.5) / 1.5
    assert rf._dimension_averages(turns)["structure"][0] == pytest.approx(11 / 3)


# --------------------------------------------------------------------------
# Exemplars
# --------------------------------------------------------------------------


def test_exemplar_for_a_strength_is_the_highest_scoring_turn_on_that_dimension():
    turns = [make_turn(1, (3, 5, 5)), make_turn(2, (5, 5, 5)), make_turn(3, (4, 5, 5))]
    strength = next(f for f in rf.build_findings(turns)["strengths"] if f["dimension"] == "structure")

    assert strength["exemplar"]["turn_number"] == 2
    assert strength["exemplar"]["question_text"] == "Q2"
    assert strength["exemplar"]["score"] == 5


def test_exemplar_for_a_weakness_is_the_lowest_scoring_turn():
    turns = [make_turn(1, (2, 1, 1)), make_turn(2, (1, 1, 1)), make_turn(3, (2, 1, 1))]
    weakness = next(
        f for f in rf.build_findings(turns)["improvement_areas"] if f["dimension"] == "structure"
    )
    assert weakness["exemplar"]["turn_number"] == 2


def test_exemplar_prefers_a_main_question_over_a_follow_up_at_equal_score():
    turns = [
        make_turn(1, (5, 5, 5), question_type="follow_up"),
        make_turn(2, (5, 5, 5), question_type="main"),
    ]
    strength = next(f for f in rf.build_findings(turns)["strengths"] if f["dimension"] == "structure")
    assert strength["exemplar"]["turn_number"] == 2


def test_exemplar_treats_a_null_or_junk_question_type_as_a_main_question():
    turns = [
        make_turn(1, (5, 5, 5), question_type="follow_up"),
        make_turn(2, (5, 5, 5), question_type=None),
        make_turn(3, (5, 5, 5), question_type="Technical Deep Dive"),
    ]
    strength = next(f for f in rf.build_findings(turns)["strengths"] if f["dimension"] == "structure")
    assert strength["exemplar"]["turn_number"] == 2


def test_exemplar_prefers_a_gap_bearing_turn_when_score_and_type_tie():
    turns = [make_turn(1, (5, 5, 5)), make_turn(2, (5, 5, 5), targets_gap="Kubernetes")]
    strength = next(f for f in rf.build_findings(turns)["strengths"] if f["dimension"] == "structure")

    assert strength["exemplar"]["turn_number"] == 2
    assert strength["exemplar"]["targets_gap"] == "Kubernetes"


def test_delivery_findings_carry_no_exemplar():
    turns = [make_turn(1, (3, 3, 3), speech=make_speech(word_count=600, duration_seconds=180))]
    result = rf.build_findings(turns)

    delivery = [f for f in result["strengths"] + result["improvement_areas"] if f["kind"] == "delivery"]
    assert delivery
    assert all(f["exemplar"] is None for f in delivery)


# --------------------------------------------------------------------------
# Delivery
# --------------------------------------------------------------------------


def test_delivery_is_silent_below_the_minimum_word_count():
    """The existing interview fixture answers with four words per turn. Without
    the floor it would be told to speak faster on the strength of 24 words."""
    turns = [
        make_turn(i, (3, 3, 3), speech=make_speech(word_count=4, duration_seconds=30))
        for i in range(1, 7)
    ]
    result = rf.build_findings(turns)

    assert [f for f in result["strengths"] + result["improvement_areas"] if f["kind"] == "delivery"] == []


def test_fast_pace_is_flagged():
    turns = [make_turn(1, (3, 3, 3), speech=make_speech(word_count=600, duration_seconds=180))]
    assert "pace_fast" in codes(rf.build_findings(turns)["improvement_areas"])


def test_slow_pace_is_flagged():
    turns = [make_turn(1, (3, 3, 3), speech=make_speech(word_count=100, duration_seconds=120))]
    assert "pace_slow" in codes(rf.build_findings(turns)["improvement_areas"])


def test_comfortable_pace_and_low_fillers_are_strengths():
    turns = [make_turn(1, (3, 3, 3), speech=make_speech(word_count=150, duration_seconds=64.3))]
    strengths = codes(rf.build_findings(turns)["strengths"])

    assert "pace_comfortable" in strengths
    assert "fillers_low" in strengths


def test_pace_between_the_bands_is_neither_praised_nor_flagged():
    """115 wpm sits in the deliberate dead zone, so the Delivery card and these
    columns can never contradict each other."""
    turns = [make_turn(1, (3, 3, 3), speech=make_speech(word_count=115, duration_seconds=60))]
    result = rf.build_findings(turns)

    all_codes = codes(result["strengths"]) + codes(result["improvement_areas"])
    assert "pace_comfortable" not in all_codes
    assert "pace_slow" not in all_codes
    assert "pace_fast" not in all_codes


def test_high_filler_rate_is_flagged_as_a_rate_not_a_count():
    turns = [
        make_turn(1, (3, 3, 3), speech=make_speech(word_count=500, duration_seconds=214, filler_count=25))
    ]
    finding = next(f for f in rf.build_findings(turns)["improvement_areas"] if f["code"] == "fillers_high")
    assert finding["metric"]["fillers_per_100_words"] == 5.0


def test_low_filler_praise_requires_enough_words():
    # 4 fillers in 60 words is under the rate threshold, but 60 words is too few
    # to call someone's filler habit good.
    turns = [make_turn(1, (3, 3, 3), speech=make_speech(word_count=60, duration_seconds=26, filler_count=0))]
    assert "fillers_low" not in codes(rf.build_findings(turns)["strengths"])


def test_long_pause_is_flagged_and_sorts_last():
    turns = [
        make_turn(1, (3, 3, 3),
                  speech=make_speech(word_count=600, duration_seconds=180, filler_count=30, pause=6200))
    ]
    improvement_codes = codes(rf.build_findings(turns)["improvement_areas"])

    assert improvement_codes[-1] == "long_pause"
    assert improvement_codes.index("fillers_high") < improvement_codes.index("pace_fast")


# --------------------------------------------------------------------------
# Participation
# --------------------------------------------------------------------------


def test_answering_everything_is_a_strength():
    turns = [make_turn(i, (3, 3, 3)) for i in range(1, 4)]
    assert "all_questions_answered" in codes(rf.build_findings(turns)["strengths"])


def test_a_single_skipped_question_is_a_footnote_not_the_headline():
    turns = [make_turn(i, (3, 3, 3)) for i in range(1, 6)] + [make_turn(6, skipped=True)]
    improvement_codes = codes(rf.build_findings(turns)["improvement_areas"])

    assert improvement_codes[0] != "questions_skipped"
    assert "questions_skipped" in improvement_codes
    assert "all_questions_answered" not in codes(rf.build_findings(turns)["strengths"])


def test_skipping_half_the_interview_leads_the_column():
    turns = [make_turn(i, (3, 3, 3)) for i in range(1, 4)] + [
        make_turn(i, skipped=True) for i in range(4, 7)
    ]
    result = rf.build_findings(turns)

    assert codes(result["improvement_areas"])[0] == "questions_skipped"
    assert result["improvement_areas"][0]["metric"] == {"skipped": 3, "answered": 6}


def test_an_unanswered_pending_turn_does_not_count_as_skipped():
    turns = [make_turn(1, (3, 3, 3)), make_turn(2, (3, 3, 3)), make_turn(3, answered=False)]
    result = rf.build_findings(turns)

    assert "questions_skipped" not in codes(result["improvement_areas"])
    assert "all_questions_answered" in codes(result["strengths"])


# --------------------------------------------------------------------------
# Edge cases
# --------------------------------------------------------------------------


def test_all_answers_skipped_says_so_plainly():
    turns = [make_turn(i, skipped=True) for i in range(1, 4)]
    result = rf.build_findings(turns)

    assert codes(result["improvement_areas"]) == ["no_scored_answers"]
    assert result["improvement_areas"][0]["metric"] == {"answered": 3, "skipped": 3, "unscored": 0}
    # `questions_skipped` alongside it would restate the same fact.
    assert "questions_skipped" not in codes(result["improvement_areas"])
    assert result["strengths"] == []


def test_every_evaluation_failing_is_reported_as_unscored_not_skipped():
    turns = [make_turn(i, None) for i in range(1, 4)]
    finding = rf.build_findings(turns)["improvement_areas"][0]

    assert finding["code"] == "no_scored_answers"
    assert finding["metric"] == {"answered": 3, "skipped": 0, "unscored": 3}


def test_a_session_with_nothing_answered_at_all():
    turns = [make_turn(1, answered=False)]
    finding = rf.build_findings(turns)["improvement_areas"][0]

    assert finding["code"] == "no_scored_answers"
    assert finding["metric"]["answered"] == 0


def test_a_single_scored_turn_reports_its_real_denominator():
    result = rf.build_findings([make_turn(1, (5, 5, 5))])
    assert all(f["turns_counted"] == 1 for f in result["strengths"] if f["kind"] == "dimension")


def test_turns_whose_evaluation_failed_are_excluded_from_the_denominator():
    turns = [make_turn(1, (5, 5, 5)), make_turn(2, (5, 5, 5)), make_turn(3, None), make_turn(4, None)]
    result = rf.build_findings(turns)

    dimension_findings = [f for f in result["strengths"] if f["kind"] == "dimension"]
    assert dimension_findings
    assert all(f["turns_counted"] == 2 for f in dimension_findings)
    # Copy must never claim "across 4 answers" when only 2 were scored.
    assert "all_questions_answered" not in codes(result["strengths"])


def test_a_partial_score_dict_does_not_raise():
    turns = [make_turn(1, {"structure": 5}), make_turn(2, (5, 5, 5))]
    result = rf.build_findings(turns)

    structure = next(f for f in result["strengths"] if f["dimension"] == "structure")
    specificity = next(f for f in result["strengths"] if f["dimension"] == "specificity")
    assert structure["turns_counted"] == 2
    assert specificity["turns_counted"] == 1


def test_a_non_integer_score_is_ignored():
    turns = [make_turn(1, {"structure": "5", "specificity": None, "relevance": 5})]
    result = rf.build_findings(turns)

    assert {f["dimension"] for f in result["strengths"] if f["kind"] == "dimension"} == {"relevance"}


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


EXPECTED_KEYS = {
    "kind", "code", "basis", "dimension", "average", "turns_counted", "metric", "exemplar",
}


@pytest.mark.parametrize(
    "turns",
    [
        [make_turn(i, (5, 5, 5)) for i in range(1, 4)],
        [make_turn(i, (1, 1, 1)) for i in range(1, 4)],
        [make_turn(i, (3, 3, 3)) for i in range(1, 4)],
        [make_turn(1, skipped=True)],
        [make_turn(1, (2, 5, 3), targets_gap="Redis",
                   speech=make_speech(word_count=600, duration_seconds=180, filler_count=40, pause=7000))],
    ],
)
def test_every_finding_has_the_full_shape_and_survives_json_round_trip(turns):
    result = rf.build_findings(turns)
    findings = result["strengths"] + result["improvement_areas"]

    for finding in findings:
        assert set(finding) == EXPECTED_KEYS, finding["code"]

    assert json.loads(json.dumps(result)) == result


# --------------------------------------------------------------------------
# aggregate_report tolerates the same malformed rows build_findings does
#
# `score` is JSONB — nothing in the database enforces its shape. These two
# functions run back to back inside POST /complete, so a row that one survives
# and the other raises on loses the user their entire report.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_score",
    [
        {"structure": 4},                                    # missing two keys
        {"structure": 4, "specificity": 3},                  # missing one
        {"structure": "4", "specificity": None, "relevance": 3},  # wrong types
        {},                                                  # empty dict
        {"structure": None, "specificity": None, "relevance": None},
    ],
)
def test_aggregate_report_does_not_raise_on_a_malformed_score(bad_score):
    turns = [make_turn(1, bad_score), make_turn(2, (4, 4, 4))]

    result = aggregate_report(turns, [])

    assert result["overall_score"] is not None


def test_aggregate_report_ignores_a_turn_with_no_usable_dimension():
    """A row scored on nothing must not drag the average toward zero."""
    only_good = aggregate_report([make_turn(1, (4, 4, 4))], [])
    with_junk = aggregate_report([make_turn(1, (4, 4, 4)), make_turn(2, {})], [])

    assert with_junk["overall_score"] == only_good["overall_score"] == 4.0


def test_aggregate_report_averages_over_the_dimensions_that_are_present():
    """Matches turn_average: a partial row contributes what it legitimately can,
    rather than being dropped or counted as zero."""
    result = aggregate_report([make_turn(1, {"structure": 5, "relevance": 3})], [])

    assert result["overall_score"] == 4.0


def test_a_malformed_score_still_counts_toward_gap_coverage():
    """The gap a turn addressed shouldn't disappear because one key is missing."""
    turns = [make_turn(1, {"structure": 5, "specificity": 4}, targets_gap="Redis")]

    result = aggregate_report(turns, [{"skill": "Redis"}])

    assert result["gap_coverage"]["addressed"] == ["Redis"]
    assert result["gap_coverage"]["still_open"] == []


# --------------------------------------------------------------------------
# Per-dimension averages are persisted, not derived from the findings
#
# The findings only name a dimension when it qualified as a strength or a
# weakness, so a flat session left nothing to plot a trend from.
# --------------------------------------------------------------------------


def test_dimension_averages_cover_dimensions_the_findings_never_mention():
    """The gap this closes.

    structure is absolutely strong and relevance absolutely weak, so both get a
    finding. specificity sits between the thresholds and gets none — and because
    an absolute strength exists, the relative fallback never runs either. Its
    average still has to be plottable.
    """
    turns = [make_turn(1, (5, 3, 2)), make_turn(2, (4, 3, 2))]

    findings = rf.build_findings(turns)
    mentioned = {
        f["dimension"] for f in findings["strengths"] + findings["improvement_areas"] if f["dimension"]
    }
    assert "specificity" not in mentioned

    averages = rf.dimension_averages(turns)
    assert averages == {"structure": 4.5, "specificity": 3.0, "relevance": 2.0}


def test_dimension_averages_omit_a_dimension_nothing_scored():
    averages = rf.dimension_averages([make_turn(1, {"structure": 4})])
    assert set(averages) == {"structure"}


def test_dimension_averages_are_empty_for_an_unscored_session():
    assert rf.dimension_averages([make_turn(1, skipped=True)]) == {}


def test_dimension_averages_weight_follow_ups_like_the_headline_score():
    """Same weighting as overall_score, or the two numbers disagree on the page."""
    turns = [make_turn(1, (4, 4, 4), question_type="main"),
             make_turn(2, (2, 2, 2), question_type="follow_up")]

    averages = rf.dimension_averages(turns)
    overall = aggregate_report(turns, [])["overall_score"]

    assert averages["structure"] == round(overall, 2)


def test_the_report_persists_dimension_averages():
    report = aggregate_report([make_turn(1, (5, 4, 3))], [])
    assert report["dimension_averages"] == {"structure": 5.0, "specificity": 4.0, "relevance": 3.0}

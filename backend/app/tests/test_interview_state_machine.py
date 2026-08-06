from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.models.interview import InterviewSession, InterviewTurn
from app.services import interview_state_machine as sm

settings = get_settings()

QUESTION_PLAN = [
    {"question_text": f"Question {i}", "targets_gap": f"gap-{i}", "based_on": f"resume bullet {i}"}
    for i in range(1, 7)  # 6 main questions
]


def make_session(started_at: datetime | None = None) -> InterviewSession:
    return InterviewSession(
        started_at=started_at or datetime.now(UTC),
        question_plan=QUESTION_PLAN,
    )


def make_turn(turn_number: int, question_type: str, targets_gap: str | None = None, answered: bool = True) -> InterviewTurn:
    return InterviewTurn(
        turn_number=turn_number,
        question_text=f"Q{turn_number}",
        question_type=question_type,
        targets_gap=targets_gap,
        answer_transcript="an answer" if answered else None,
    )


def test_main_question_count_only_counts_answered_main_turns():
    turns = [
        make_turn(1, "main"),
        make_turn(2, "follow_up"),
        make_turn(3, "main"),
        make_turn(4, "main", answered=False),  # not yet answered
    ]
    assert sm.main_question_count(turns) == 2


def test_followups_since_last_main_resets_after_main():
    turns = [
        make_turn(1, "main"),
        make_turn(2, "follow_up"),
        make_turn(3, "follow_up"),
        make_turn(4, "main"),
        make_turn(5, "follow_up"),
    ]
    assert sm.followups_since_last_main(turns) == 1


def test_is_hard_capped_by_question_count():
    session = make_session()
    turns = [make_turn(i, "main") for i in range(1, settings.interview_hard_cap_questions + 1)]
    assert sm.is_hard_capped(session, turns) is True


def test_is_hard_capped_by_elapsed_time():
    session = make_session(started_at=datetime.now(UTC) - timedelta(minutes=settings.interview_hard_cap_minutes + 1))
    assert sm.is_hard_capped(session, []) is True


def test_not_hard_capped_under_both_limits():
    session = make_session()
    turns = [make_turn(1, "main")]
    assert sm.is_hard_capped(session, turns) is False


def test_decide_next_step_advances_through_full_plan_without_followups():
    session = make_session()
    turns = [make_turn(1, "main", targets_gap="gap-1")]

    step = sm.decide_next_step(session, turns, QUESTION_PLAN, turns[0], "next_question", None)

    assert step["action"] == "next_question"
    assert step["question_text"] == "Question 2"


def test_decide_next_step_returns_follow_up_when_llm_requests_it():
    session = make_session()
    turns = [make_turn(1, "main", targets_gap="gap-1")]

    step = sm.decide_next_step(
        session, turns, QUESTION_PLAN, turns[0], "follow_up", "Can you elaborate on that?"
    )

    assert step["action"] == "follow_up"
    assert step["question_text"] == "Can you elaborate on that?"
    assert step["targets_gap"] == "gap-1"


def test_decide_next_step_caps_at_max_followups_per_question():
    session = make_session()
    main_turn = make_turn(1, "main", targets_gap="gap-1")
    turns = [main_turn]

    # simulate settings.interview_max_followups_per_question follow-ups already answered
    for i in range(settings.interview_max_followups_per_question):
        turns.append(make_turn(2 + i, "follow_up", targets_gap="gap-1"))

    step = sm.decide_next_step(
        session, turns, QUESTION_PLAN, turns[-1], "follow_up", "One more follow-up?"
    )

    # cap already reached -> forced to advance instead of granting another follow-up
    assert step["action"] == "next_question"
    assert step["question_text"] == "Question 2"


def test_decide_next_step_wraps_up_when_question_plan_exhausted():
    session = make_session()
    turns = [make_turn(i, "main") for i in range(1, len(QUESTION_PLAN) + 1)]

    step = sm.decide_next_step(session, turns, QUESTION_PLAN, turns[-1], "next_question", None)

    assert step["action"] == "wrap_up"


def test_decide_next_step_forces_wrap_up_on_hard_cap_even_if_llm_says_continue():
    # elapsed time exceeds the hard cap; LLM says "next_question" (i.e. keep going)
    # but the state machine must override it per §7.2.
    session = make_session(
        started_at=datetime.now(UTC) - timedelta(minutes=settings.interview_hard_cap_minutes + 5)
    )
    turns = [make_turn(1, "main", targets_gap="gap-1")]

    step = sm.decide_next_step(session, turns, QUESTION_PLAN, turns[0], "next_question", None)
    assert step["action"] == "wrap_up"

    # also true even when the LLM explicitly asks for a follow-up
    step2 = sm.decide_next_step(session, turns, QUESTION_PLAN, turns[0], "follow_up", "Tell me more")
    assert step2["action"] == "wrap_up"


def test_session_progress_counts_answered_mains_and_pending_followups():
    session = make_session()
    turns = [
        make_turn(1, "main"),
        make_turn(2, "follow_up"),
        make_turn(3, "main", answered=False),
    ]

    progress = sm.session_progress(session, turns, QUESTION_PLAN)

    assert progress["main_questions_answered"] == 1
    assert progress["main_questions_planned"] == len(QUESTION_PLAN)
    assert progress["follow_ups_used"] == 1
    assert progress["max_follow_ups_per_question"] == settings.interview_max_followups_per_question
    assert progress["hard_capped"] is False


def test_session_progress_caps_planned_questions_at_the_hard_cap():
    # A plan longer than the hard cap can't all be asked, so the UI must not
    # advertise more questions than the candidate will actually get.
    session = make_session()
    long_plan = [{"question_text": f"Q{i}"} for i in range(settings.interview_hard_cap_questions + 4)]

    progress = sm.session_progress(session, [], long_plan)

    assert progress["main_questions_planned"] == settings.interview_hard_cap_questions


def test_seconds_remaining_counts_down_from_the_same_clock_as_the_hard_cap():
    fresh = make_session()
    full_window = settings.interview_hard_cap_minutes * 60
    assert full_window - 5 < sm.seconds_remaining(fresh) <= full_window

    half_spent = make_session(
        started_at=datetime.now(UTC) - timedelta(minutes=settings.interview_hard_cap_minutes / 2)
    )
    assert abs(sm.seconds_remaining(half_spent) - full_window / 2) < 5


def test_seconds_remaining_floors_at_zero_when_the_cap_has_passed():
    expired = make_session(
        started_at=datetime.now(UTC) - timedelta(minutes=settings.interview_hard_cap_minutes + 10)
    )
    assert sm.seconds_remaining(expired) == 0.0
    assert sm.session_progress(expired, [], QUESTION_PLAN)["hard_capped"] is True

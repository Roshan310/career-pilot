from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict

from app.core.config import get_settings
from app.models.interview import InterviewSession, InterviewTurn

settings = get_settings()

Action = Literal["follow_up", "next_question", "wrap_up"]


class NextStep(TypedDict, total=False):
    action: Action
    question_text: str
    question_type: str
    targets_gap: str | None
    based_on: str | None


def _answered(turns: list[InterviewTurn]) -> list[InterviewTurn]:
    return [t for t in turns if t.answer_transcript is not None]


def main_question_count(turns: list[InterviewTurn]) -> int:
    return sum(1 for t in _answered(turns) if t.question_type == "main")


def followups_since_last_main(turns: list[InterviewTurn]) -> int:
    """Follow-ups answered since the most recently answered main question —
    resets to 0 every time a main question is answered."""
    count = 0
    for t in reversed(_answered(turns)):
        if t.question_type == "main":
            break
        if t.question_type == "follow_up":
            count += 1
    return count


def is_hard_capped(session: InterviewSession, turns: list[InterviewTurn]) -> bool:
    """SPECS.md §7.2 hard session cap: 20 minutes or 8 main questions,
    whichever comes first — enforced here in code, not left to the LLM."""
    elapsed = datetime.now(UTC) - session.started_at
    if elapsed >= timedelta(minutes=settings.interview_hard_cap_minutes):
        return True
    return main_question_count(turns) >= settings.interview_hard_cap_questions


def decide_next_step(
    session: InterviewSession,
    turns: list[InterviewTurn],
    question_plan: list[dict],
    just_answered: InterviewTurn,
    llm_next_action: str,
    llm_follow_up_question: str | None,
) -> NextStep:
    """Given the turn that was just answered and the LLM's evaluation verdict,
    decide what happens next. The hard cap and the max-follow-ups-per-question
    cap are both enforced here regardless of what the LLM says (§7.2)."""
    if is_hard_capped(session, turns):
        return {"action": "wrap_up"}

    if llm_next_action == "follow_up" and llm_follow_up_question:
        if followups_since_last_main(turns) < settings.interview_max_followups_per_question:
            return {
                "action": "follow_up",
                "question_text": llm_follow_up_question,
                "question_type": "follow_up",
                "targets_gap": just_answered.targets_gap,
                "based_on": just_answered.targets_gap or just_answered.question_text,
            }
        # max follow-ups for this main question already used — fall through to advance.

    next_index = main_question_count(turns)
    if next_index >= len(question_plan):
        return {"action": "wrap_up"}

    next_item = question_plan[next_index]
    return {
        "action": "next_question",
        "question_text": next_item["question_text"],
        "question_type": "main",
        "targets_gap": next_item.get("targets_gap"),
        "based_on": next_item.get("based_on"),
    }

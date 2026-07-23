from pydantic import BaseModel, ValidationError

from app.core.exceptions import LLMServiceError
from app.services.llm.client import call_json
from app.services.llm.prompts import answer_evaluation_prompt


class AnswerEvaluation(BaseModel):
    structure: int
    specificity: int
    relevance: int
    next_action: str  # "follow_up" | "next_question"
    follow_up_question: str | None = None


def evaluate_answer(question_text: str, based_on: str, answer_transcript: str) -> AnswerEvaluation:
    """SPECS.md §7.1 evaluation prompt. `based_on` here is the turn's stored
    targets_gap/question context — §4's interview_turns table has no separate
    based_on column, so we reuse what was persisted at question-generation time."""
    result = call_json(answer_evaluation_prompt(question_text, based_on, answer_transcript))
    if not isinstance(result, dict):
        raise LLMServiceError("Answer evaluation LLM call did not return a JSON object")

    try:
        return AnswerEvaluation.model_validate(result)
    except ValidationError as exc:
        raise LLMServiceError(f"Answer evaluation failed schema validation: {exc}") from exc

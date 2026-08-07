import logging

from pydantic import BaseModel

from app.core.exceptions import LLMConfigurationError, LLMServiceError
from app.services.llm.client import call_structured
from app.services.llm.prompts import answer_evaluation_prompt

logger = logging.getLogger(__name__)


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
    try:
        # Validation happens inside the retry (see `call_structured`): an
        # off-schema field is a resampling problem, not a fatal one.
        return call_structured(answer_evaluation_prompt(question_text, based_on, answer_transcript), AnswerEvaluation)
    except LLMConfigurationError:
        # Says exactly what is wrong already; relabelling it as a parsing
        # problem would send the user to re-upload a file that is fine.
        raise
    except LLMServiceError:
        logger.warning("Answer evaluation failed after every attempt", exc_info=True)
        raise LLMServiceError("We couldn't score that answer.") from None

import logging

from app.core.exceptions import LLMServiceError
from app.schemas.interview import QuestionPlan
from app.services.llm.client import call_structured
from app.services.llm.prompts import question_generation_prompt

logger = logging.getLogger(__name__)


def generate_question_plan(
    resume_parsed_data: dict, job_parsed_requirements: dict, missing_skills: list
) -> QuestionPlan:
    """SPECS.md §7.1 question-generation prompt — 6-8 questions, each tied to a
    specific resume detail or JD gap via `based_on`."""
    try:
        # Validation happens inside the retry (see `call_structured`): an
        # off-schema field is a resampling problem, not a fatal one.
        return call_structured(question_generation_prompt(resume_parsed_data, job_parsed_requirements, missing_skills), QuestionPlan)
    except LLMServiceError:
        logger.warning("Question plan failed schema validation after every attempt", exc_info=True)
        raise LLMServiceError("We couldn't prepare your interview questions. Please try again.") from None

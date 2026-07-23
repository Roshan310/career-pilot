from pydantic import ValidationError

from app.core.exceptions import LLMServiceError
from app.schemas.interview import QuestionPlan
from app.services.llm.client import call_json
from app.services.llm.prompts import question_generation_prompt


def generate_question_plan(
    resume_parsed_data: dict, job_parsed_requirements: dict, missing_skills: list
) -> QuestionPlan:
    """SPECS.md §7.1 question-generation prompt — 6-8 questions, each tied to a
    specific resume detail or JD gap via `based_on`."""
    result = call_json(question_generation_prompt(resume_parsed_data, job_parsed_requirements, missing_skills))
    if not isinstance(result, dict):
        raise LLMServiceError("Question generation LLM call did not return a JSON object")

    try:
        return QuestionPlan.model_validate(result)
    except ValidationError as exc:
        raise LLMServiceError(f"Question plan failed schema validation: {exc}") from exc

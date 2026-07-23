from pydantic import ValidationError

from app.core.exceptions import LLMServiceError
from app.schemas.job import ParsedJobRequirements
from app.services.llm.client import call_json
from app.services.llm.prompts import job_parsing_prompt


def parse_job(raw_text: str) -> ParsedJobRequirements:
    """Extract structured JD requirements — prompt is analogous to §6.3's resume
    prompt (not spec-verbatim, since §6.3 doesn't give one for jobs)."""
    result = call_json(job_parsing_prompt(raw_text))
    if not isinstance(result, dict):
        raise LLMServiceError("Job parsing LLM call did not return a JSON object")

    try:
        return ParsedJobRequirements.model_validate(result)
    except ValidationError as exc:
        raise LLMServiceError(f"Job parsing LLM response failed schema validation: {exc}") from exc

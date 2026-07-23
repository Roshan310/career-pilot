from pydantic import ValidationError

from app.core.exceptions import LLMServiceError
from app.schemas.resume import ParsedResumeData
from app.services.llm.client import call_json
from app.services.llm.prompts import resume_parsing_prompt


def parse_resume(raw_text: str) -> ParsedResumeData:
    """Extract structured resume data via the SPECS.md §6.3 prompt.

    Validates the LLM's JSON against ParsedResumeData rather than trusting it
    blindly — missing fields coerce to null/[] per the pydantic model's defaults.
    """
    result = call_json(resume_parsing_prompt(raw_text))
    if not isinstance(result, dict):
        raise LLMServiceError("Resume parsing LLM call did not return a JSON object")

    try:
        return ParsedResumeData.model_validate(result)
    except ValidationError as exc:
        raise LLMServiceError(f"Resume parsing LLM response failed schema validation: {exc}") from exc

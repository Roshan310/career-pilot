import logging

from app.core.config import get_settings
from app.core.exceptions import LLMServiceError
from app.schemas.resume import ParsedResumeData
from app.services.llm.client import call_structured
from app.services.llm.prompts import resume_parsing_prompt

logger = logging.getLogger(__name__)
settings = get_settings()


def parse_resume(raw_text: str) -> ParsedResumeData:
    """Extract structured resume data via the SPECS.md §6.3 prompt.

    Validates the LLM's JSON against ParsedResumeData rather than trusting it
    blindly — missing fields coerce to null/[] per the pydantic model's defaults.
    """
    try:
        # Validation happens inside the retry (see `call_structured`): an
        # off-schema field is a resampling problem, not a fatal one.
        return call_structured(resume_parsing_prompt(raw_text), ParsedResumeData,
            # Extraction, not reasoning: every field is already in the document.
            thinking_budget=settings.gemini_extractive_thinking_budget,
        )
    except LLMServiceError:
        logger.warning("Resume parsing response failed schema validation after every attempt", exc_info=True)
        raise LLMServiceError("We couldn't read this resume. Please try uploading it again.") from None

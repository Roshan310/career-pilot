import logging

from app.core.config import get_settings
from app.core.exceptions import LLMConfigurationError, LLMServiceError
from app.schemas.job import ParsedJobRequirements
from app.services.llm.client import call_structured
from app.services.llm.prompts import job_parsing_prompt

logger = logging.getLogger(__name__)
settings = get_settings()


def parse_job(raw_text: str) -> ParsedJobRequirements:
    """Extract structured JD requirements — prompt is analogous to §6.3's resume
    prompt (not spec-verbatim, since §6.3 doesn't give one for jobs)."""
    try:
        # Validation happens inside the retry (see `call_structured`): an
        # off-schema field is a resampling problem, not a fatal one.
        return call_structured(job_parsing_prompt(raw_text), ParsedJobRequirements,
            # Extraction, not reasoning: every field is already in the posting.
            thinking_budget=settings.gemini_extractive_thinking_budget,
        )
    except LLMConfigurationError:
        # Says exactly what is wrong already; relabelling it as a parsing
        # problem would send the user to re-upload a file that is fine.
        raise
    except LLMServiceError:
        logger.warning("Job parsing failed after every attempt", exc_info=True)
        raise LLMServiceError("We couldn't read this job description. Please try again.") from None

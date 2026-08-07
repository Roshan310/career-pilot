import logging

from app.core.exceptions import LLMServiceError
from app.schemas.job import ParsedJobRequirements
from app.services.llm.client import call_structured
from app.services.llm.prompts import job_parsing_prompt

logger = logging.getLogger(__name__)


def parse_job(raw_text: str) -> ParsedJobRequirements:
    """Extract structured JD requirements — prompt is analogous to §6.3's resume
    prompt (not spec-verbatim, since §6.3 doesn't give one for jobs)."""
    try:
        # Validation happens inside the retry (see `call_structured`): an
        # off-schema field is a resampling problem, not a fatal one.
        return call_structured(job_parsing_prompt(raw_text), ParsedJobRequirements)
    except LLMServiceError:
        logger.warning("Job parsing response failed schema validation after every attempt", exc_info=True)
        raise LLMServiceError("We couldn't read this job description. Please try again.") from None

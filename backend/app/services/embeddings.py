import logging

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.exceptions import LLMServiceError
from app.models.resume import EMBEDDING_DIM
from app.services.llm.providers.base import PermanentProviderError
from app.services.llm.providers.gemini import classify

settings = get_settings()
logger = logging.getLogger(__name__)

# Cached per API key, built lazily so this module imports without a key set.
_clients: dict[str, genai.Client] = {}

# Matches ATTEMPTS_PER_PROVIDER in llm/client.py — SPECS.md §9's "1 retry".
ATTEMPTS_PER_KEY = 2


def _get_client(api_key: str) -> genai.Client:
    if api_key not in _clients:
        _clients[api_key] = genai.Client(api_key=api_key)
    return _clients[api_key]


def _embed_once(api_key: str, text: str) -> list[float]:
    response = _get_client(api_key).models.embed_content(
        model=settings.gemini_embedding_model,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return list(response.embeddings[0].values)


def embed_text(text: str) -> list[float]:
    """Embed text with Gemini, at SPECS.md §4's 1536-d column width.

    Tries each configured API key in turn, exactly as `llm/client.py::call_json`
    does — an account that has burnt its quota hands off to the other rather
    than failing the upload. Unlike text generation there is no cross-vendor
    story here and there never will be: `resumes.embedding` and
    `job_descriptions.embedding` are `Vector(1536)` with ivfflat cosine indexes,
    and vectors from two different *models* don't share a space, so mixing them
    would silently corrupt `semantic_score` in matching. Two keys against the
    same model are fine — same model, same space.

    Raises LLMServiceError once every key is exhausted; callers decide whether
    that's fatal (resume/JD creation can't proceed without an embedding).
    """
    keys = settings.gemini_api_keys
    if not keys:
        raise LLMServiceError("Embedding call failed: no Gemini API key configured (set GEMINI_API_KEY).")

    failures: list[str] = []
    for index, api_key in enumerate(keys):
        label = "gemini" if index == 0 else f"gemini-{index + 1}"
        for attempt in range(1, ATTEMPTS_PER_KEY + 1):
            try:
                return _embed_once(api_key, text)
            except Exception as exc:
                error = classify(exc, label)
                failures.append(f"{label}: {error}")
                if isinstance(error, PermanentProviderError):
                    logger.warning("%s embedding failed permanently, not retrying: %s", label, error)
                    break
                logger.info("%s embedding failed, attempt %d/%d: %s",
                            label, attempt, ATTEMPTS_PER_KEY, error)

        if index + 1 < len(keys):
            logger.info("%s exhausted, falling back to the next Gemini key", label)

    raise LLMServiceError("Embedding call failed. " + "; ".join(failures))

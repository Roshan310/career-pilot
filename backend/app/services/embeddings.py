from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.core.exceptions import LLMServiceError
from app.models.resume import EMBEDDING_DIM

settings = get_settings()

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


@retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=True)
def _embed(text: str) -> list[float]:
    response = _get_client().models.embed_content(
        model=settings.gemini_embedding_model,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return list(response.embeddings[0].values)


def embed_text(text: str) -> list[float]:
    """Embed text with Gemini, at SPECS.md §4's 1536-d column width.

    Raises LLMServiceError after 1 retry — callers decide whether that's fatal
    (resume/JD creation can't proceed without an embedding) or degradable.
    """
    try:
        return _embed(text)
    except Exception as exc:
        raise LLMServiceError(f"Embedding call failed: {exc}") from exc

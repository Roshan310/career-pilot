import json

from google import genai
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.core.exceptions import LLMServiceError

settings = get_settings()

# Constructed lazily (not at import time) so the module can be imported — and
# mocked in tests — before GEMINI_API_KEY is configured.
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


# "1 retry" per SPECS.md §9 => 2 total attempts.
_llm_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(1),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)


@_llm_retry
def _generate(prompt: str) -> str:
    response = _get_client().models.generate_content(
        model=settings.gemini_llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    if not response.text:
        raise LLMServiceError("Gemini returned an empty response")
    return response.text


def call_json(prompt: str) -> dict | list:
    """Call Gemini with a prompt that instructs it to return JSON, and parse the result.

    Retries once (SPECS.md §9), then raises LLMServiceError — callers are
    responsible for graceful degradation (e.g. skip suggestions, don't fail
    the whole request) rather than this function silently returning a default.
    """
    try:
        raw_text = _generate(prompt)
    except Exception as exc:
        raise LLMServiceError(f"LLM call failed: {exc}") from exc

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LLMServiceError(f"LLM returned invalid JSON: {exc}") from exc

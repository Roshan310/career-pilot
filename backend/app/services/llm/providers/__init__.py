"""Builds the chain of LLM endpoints `call_json()` tries, in order.

Today every entry is Gemini — one per configured API key, because the free tier
meters `generate_content` per project and a second account is a second quota
pool. The `LLMProvider` protocol in `base.py` is deliberately vendor-neutral, so
adding a different vendor later is one module implementing it plus one line here.
"""

from app.core.config import get_settings
from app.services.llm.providers.base import (
    LLMProvider,
    PermanentProviderError,
    ProviderError,
    TransientProviderError,
)
from app.services.llm.providers.gemini import GeminiProvider

__all__ = [
    "LLMProvider",
    "ProviderError",
    "TransientProviderError",
    "PermanentProviderError",
    "GeminiProvider",
    "build_provider_chain",
]


def build_provider_chain() -> list[LLMProvider]:
    """One provider per configured Gemini key, primary first.

    Returns an empty list when no key is set; `call_json()` turns that into a
    clear LLMServiceError rather than hanging or silently returning nothing.
    """
    keys = get_settings().gemini_api_keys
    return [
        GeminiProvider(key, name="gemini" if index == 0 else f"gemini-{index + 1}")
        for index, key in enumerate(keys)
    ]

"""The single choke point for LLM calls.

Every structured-JSON call in the app goes through `call_json()` — resume
parsing, JD parsing, match suggestions, interview question generation, answer
evaluation — and every spoken answer goes through `call_transcription()`. That's
what makes failover a change to one file rather than seven, and it's why nothing
else may talk to an LLM SDK directly.

Failover: `build_provider_chain()` yields one Gemini endpoint per configured API
key (`GEMINI_API_KEY`, then `GEMINI_API_KEY_2`). Each gets up to
ATTEMPTS_PER_PROVIDER tries before the next is used, so a project that has burnt
its per-minute allowance (5 as of August 2026) hands off to the other account
instead of 502-ing. Embeddings run the same key sequence separately — see
services/embeddings.py.
"""

import json
import logging
from collections.abc import Callable
from typing import TypeVar

from app.core.exceptions import LLMServiceError
from app.services.llm.providers import (
    LLMProvider,
    PermanentProviderError,
    ProviderError,
    TransientProviderError,
    build_provider_chain,
)

logger = logging.getLogger(__name__)

# SPECS.md §9 asks for "1 retry" — 2 attempts, now per provider.
ATTEMPTS_PER_PROVIDER = 2

T = TypeVar("T")


class EmptyTranscriptionError(Exception):
    """The model returned nothing for audio that should contain speech. Retryable:
    it's a sampling outcome, not a broken key. Distinct from a genuinely silent
    recording, which never reaches here — a turn with no detected speech is
    submitted as `skipped` without spending a transcription call."""


def _with_failover(
    operation: Callable[[LLMProvider], T],
    retry_on: tuple[type[Exception], ...] = (),
) -> T:
    """Run `operation` against each configured key in turn, retrying transient
    failures within a key before moving to the next.

    `retry_on` names extra exception types that should be treated as transient —
    used for response-shape problems, which are a property of the call rather
    than of the provider.

    Raises LLMServiceError only once every key is exhausted. Callers are
    responsible for graceful degradation (skip suggestions, leave a turn
    unscored) rather than this function silently returning a default.
    """
    failures: list[str] = []
    chain = build_provider_chain()

    if not chain:
        raise LLMServiceError("LLM call failed: no Gemini API key configured (set GEMINI_API_KEY).")

    for index, provider in enumerate(chain):
        if not provider.configured:
            failures.append(f"{provider.name}: no API key configured")
            continue

        for attempt in range(1, ATTEMPTS_PER_PROVIDER + 1):
            try:
                return operation(provider)
            except retry_on as exc:
                failures.append(f"{provider.name}: bad response ({exc})")
                logger.info("%s returned an unusable response (attempt %d/%d): %s",
                            provider.name, attempt, ATTEMPTS_PER_PROVIDER, exc)
            except TransientProviderError as exc:
                failures.append(f"{provider.name}: {exc}")
                logger.info("%s failed, attempt %d/%d: %s",
                            provider.name, attempt, ATTEMPTS_PER_PROVIDER, exc)
            except PermanentProviderError as exc:
                # Retrying can't help (bad key, no credit, rejected request).
                # Don't add latency to every call — move on immediately.
                failures.append(f"{provider.name}: {exc}")
                logger.warning("%s failed permanently, not retrying: %s", provider.name, exc)
                break
            except ProviderError as exc:  # a provider raised the base type
                failures.append(f"{provider.name}: {exc}")
                break

        # Only a real fallback if something is left to fall back to.
        if index + 1 < len(chain):
            logger.info("%s exhausted, falling back to %s", provider.name, chain[index + 1].name)

    logger.warning("all LLM providers failed: %s", "; ".join(failures))
    raise LLMServiceError("LLM call failed. " + "; ".join(failures))


def call_json(prompt: str) -> dict | list:
    """Call the LLM with a prompt that instructs it to return JSON, and parse it."""
    # The parse lives INSIDE the retried unit on purpose. It used to sit outside,
    # so a truncated or malformed response got zero retries despite §9's policy
    # and went straight to a 502 — which happened in roughly 1 of 3 real runs.
    # Sampling again usually produces valid JSON; if it doesn't, the next key
    # gets a go.
    return _with_failover(
        lambda provider: json.loads(provider.generate(prompt)),
        retry_on=(json.JSONDecodeError,),
    )


def call_transcription(audio: bytes, mime_type: str) -> str:
    """Transcribe a spoken answer. Same keys, same failover, same retry policy as
    every other LLM call — an account that is out of quota for text is out of
    quota for audio too, and the second account covers both."""
    return _with_failover(
        lambda provider: provider.transcribe(audio, mime_type),
        retry_on=(EmptyTranscriptionError,),
    )

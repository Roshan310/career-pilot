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
import random
import time
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import LLMServiceError
from app.services.llm.providers import (
    LLMProvider,
    PermanentProviderError,
    ProviderError,
    RateLimitedError,
    TransientProviderError,
    build_provider_chain,
)

logger = logging.getLogger(__name__)

# SPECS.md §9 asks for "1 retry" — 2 attempts, now per provider.
ATTEMPTS_PER_PROVIDER = 2

# Backoff between attempts on the same key. Short, because a user is waiting on
# the other end of every one of these calls; jittered so concurrent requests
# don't retry in lockstep and recreate the burst that caused the failure.
RETRY_BASE_DELAY_SECONDS = 0.5
RETRY_MAX_DELAY_SECONDS = 4.0

T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=BaseModel)


def _sleep_before_retry(attempt: int) -> None:
    """Exponential backoff with full jitter.

    `time.sleep`, not `asyncio.sleep`: every caller reaches this through
    `asyncio.to_thread`, so this blocks a worker thread and never the event loop.
    """
    ceiling = min(RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)), RETRY_MAX_DELAY_SECONDS)
    time.sleep(random.uniform(0, ceiling))


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

        has_fallback = index + 1 < len(chain)

        for attempt in range(1, ATTEMPTS_PER_PROVIDER + 1):
            try:
                return operation(provider)
            except retry_on as exc:
                failures.append(f"{provider.name}: bad response ({exc})")
                logger.info("%s returned an unusable response (attempt %d/%d): %s",
                            provider.name, attempt, ATTEMPTS_PER_PROVIDER, exc)
            except RateLimitedError as exc:
                failures.append(f"{provider.name}: {exc}")
                # Another key is a separate project with its own per-minute
                # allowance, so switching beats waiting. Only back off when this
                # is the last key and waiting is the only option left.
                if has_fallback:
                    logger.info("%s is rate limited, switching keys: %s", provider.name, exc)
                    break
                logger.info("%s rate limited, attempt %d/%d: %s",
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

            # Space out the retry. Retrying instantly was close to guaranteed to
            # hit the same condition — especially a per-minute quota — so the
            # second attempt was spent for nothing. Never sleeps after the final
            # attempt: that delay would buy nothing at all.
            if attempt < ATTEMPTS_PER_PROVIDER:
                _sleep_before_retry(attempt)

        # Only a real fallback if something is left to fall back to.
        if has_fallback:
            logger.info("%s exhausted, falling back to %s", provider.name, chain[index + 1].name)

    # `failures` carries raw vendor text — quota metric names, project ids, the
    # number of keys configured. Useful in a log, not something to hand to an
    # API client, so the detail goes to the logger and the caller gets a summary.
    logger.warning("all LLM providers failed: %s", "; ".join(failures))
    raise LLMServiceError(
        "The AI service is temporarily unavailable. Please try again in a moment."
    )


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


def call_structured(prompt: str, model: type[ModelT]) -> ModelT:
    """Call the LLM and validate the response against a Pydantic model.

    Validation runs INSIDE the retried unit, for exactly the reason `json.loads`
    does. Schema validation used to happen in the caller, after `call_json`
    returned — so a response that parsed as JSON but missed the schema by one
    field got *zero* retries and became a hard 502, despite §9's retry policy.

    That is not a hypothetical: `years_experience_required` was declared `int`,
    a job description asking for three months of experience made the model emit
    `0.25`, and every attempt to save that job failed identically. The model is
    non-deterministic — resampling is the cheapest fix for an off-schema field,
    and it is what this policy was always meant to provide.
    """
    return _with_failover(
        lambda provider: model.model_validate(json.loads(provider.generate(prompt))),
        retry_on=(json.JSONDecodeError, ValidationError),
    )


def call_embedding(text: str, dimensions: int) -> list[float]:
    """Embed text. Same keys, same failover, same retry policy as every other
    call — see `services/embeddings.py` for why the chain must stay single-model."""
    return _with_failover(lambda provider: provider.embed(text, dimensions))


def call_transcription(audio: bytes, mime_type: str) -> str:
    """Transcribe a spoken answer. Same keys, same failover, same retry policy as
    every other LLM call — an account that is out of quota for text is out of
    quota for audio too, and the second account covers both."""
    return _with_failover(
        lambda provider: provider.transcribe(audio, mime_type),
        retry_on=(EmptyTranscriptionError,),
    )

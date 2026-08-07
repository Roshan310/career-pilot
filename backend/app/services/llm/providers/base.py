"""What every model endpoint has to offer, and nothing more.

A provider turns a prompt into raw text, and audio into a transcript. It does not
parse JSON, does not retry, and does not know that other providers exist — all of
that lives in `services/llm/client.py`, so failover logic exists in exactly one
place and adding a provider stays a one-file job.

Today the chain is Gemini under one API key per entry, but nothing here is
Gemini-specific: a second vendor would implement this same protocol.

The two exception types below are the contract that makes failover work: the
client needs to know whether retrying the *same* provider could plausibly help.
"""

from typing import Protocol, runtime_checkable


class ProviderError(Exception):
    """Base for provider failures. Carries the provider name for the error
    message the user eventually sees."""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(message)


class TransientProviderError(ProviderError):
    """Worth another attempt on the same provider: 5xx, timeouts, empty
    responses. Malformed JSON is folded in here too (the client raises it),
    since the model is non-deterministic and a second sample often parses."""


class RateLimitedError(TransientProviderError):
    """Out of quota on this key, specifically.

    Still transient — the quota refills — but it wants different handling from a
    generic blip. Each API key is a separate project with a separate per-minute
    allowance, so when another key is available the fastest path is to switch to
    it *now*; sleeping first would delay a call that was always going to succeed
    elsewhere. Backing off only makes sense once there is nothing left to fail
    over to.
    """


class PermanentProviderError(ProviderError):
    """Retrying the same provider cannot help: bad API key, no credit, a request
    this provider will always reject. Skip straight to the next provider —
    burning a retry here just adds latency to every single call."""


@runtime_checkable
class LLMProvider(Protocol):
    """Implemented by `GeminiProvider`."""

    name: str

    @property
    def configured(self) -> bool:
        """False when there's no API key. The client skips unconfigured
        providers silently rather than counting them as failures, so a .env with
        only one key set still works."""
        ...

    def generate(self, prompt: str) -> str:
        """Raw model output, expected (but not guaranteed) to be JSON.

        Raises TransientProviderError / PermanentProviderError. Must not raise
        bare exceptions — the client relies on the distinction.
        """
        ...

    def transcribe(self, audio: bytes, mime_type: str) -> str:
        """Spoken audio as plain text, with no commentary or formatting.

        Same error contract as `generate`. Kept on this protocol rather than in a
        separate one because it shares the thing that matters — the API key, and
        therefore the quota the failover is routing around.
        """
        ...

    def embed(self, text: str, dimensions: int) -> list[float]:
        """A vector of exactly `dimensions` floats.

        Same error contract again. Unlike the other two, this one carries a
        constraint the protocol cannot express: only providers sharing an
        embedding model may appear in the same chain, because vectors from
        different models are not comparable and mixing them silently corrupts
        similarity search.
        """
        ...

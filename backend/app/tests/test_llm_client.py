"""Failover behaviour of the LLM choke point.

The chain is one Gemini endpoint per configured API key ("gemini", then
"gemini-2"), so "primary" and "fallback" below mean first and second key. Mocked
at the provider boundary, so these run with no network and no API keys.
"""

from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.exceptions import LLMServiceError
from app.services.llm import client
from app.services.llm.providers import build_provider_chain
from app.services.llm.providers.base import (
    PermanentProviderError,
    TransientProviderError,
)


class FakeProvider:
    """Stands in for GeminiProvider. `script` is replayed one entry per call:
    a str is returned as raw model output, an Exception is raised."""

    def __init__(self, name: str, script: list, configured: bool = True):
        self.name = name
        self._script = list(script)
        self._configured = configured
        self.calls = 0

    @property
    def configured(self) -> bool:
        return self._configured

    def generate(self, prompt: str) -> str:
        return self._next()

    def transcribe(self, audio: bytes, mime_type: str) -> str:
        return self._next()

    def _next(self) -> str:
        self.calls += 1
        outcome = self._script.pop(0) if self._script else self._script_exhausted()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def _script_exhausted(self):
        raise AssertionError(f"{self.name} called more times than the test scripted")


def run_with(chain: list[FakeProvider]):
    with patch.object(client, "build_provider_chain", return_value=chain):
        return client.call_json("some prompt")


def transcribe_with(chain: list[FakeProvider]):
    with patch.object(client, "build_provider_chain", return_value=chain):
        return client.call_transcription(b"fake-audio-bytes", "audio/webm")


def test_primary_success_never_touches_the_fallback():
    primary = FakeProvider("gemini", ['{"ok": true}'])
    fallback = FakeProvider("gemini-2", [])

    assert run_with([primary, fallback]) == {"ok": True}
    assert primary.calls == 1
    assert fallback.calls == 0  # second account untouched on the happy path


def test_rate_limited_key_falls_back_to_the_second_account():
    """The whole point of two keys: 20 requests/minute is metered per project."""
    primary = FakeProvider(
        "gemini",
        [TransientProviderError("gemini", "429 RESOURCE_EXHAUSTED")] * 2,
    )
    fallback = FakeProvider("gemini-2", ['{"from": "second-key"}'])

    assert run_with([primary, fallback]) == {"from": "second-key"}
    assert primary.calls == client.ATTEMPTS_PER_PROVIDER  # retried before moving on
    assert fallback.calls == 1


def test_malformed_json_is_retried_on_the_same_key():
    """The folded-in bug fix: json.loads used to sit outside the retry, so one
    truncated response became a 502 with no second attempt."""
    primary = FakeProvider("gemini", ['{"truncated": ', '{"ok": true}'])
    fallback = FakeProvider("gemini-2", [])

    assert run_with([primary, fallback]) == {"ok": True}
    assert primary.calls == 2
    assert fallback.calls == 0  # recovered without spending the other account


def test_persistently_malformed_json_falls_back():
    primary = FakeProvider("gemini", ["not json at all", "still not json"])
    fallback = FakeProvider("gemini-2", ['{"from": "second-key"}'])

    assert run_with([primary, fallback]) == {"from": "second-key"}
    assert primary.calls == client.ATTEMPTS_PER_PROVIDER


def test_permanent_failure_skips_the_retry():
    """A revoked key fails identically every time — retrying only adds latency
    to every call in the app."""
    primary = FakeProvider("gemini", [PermanentProviderError("gemini", "401 invalid key")])
    fallback = FakeProvider("gemini-2", ['{"from": "second-key"}'])

    assert run_with([primary, fallback]) == {"from": "second-key"}
    assert primary.calls == 1


def test_unconfigured_provider_is_skipped_not_failed():
    primary = FakeProvider("gemini", [], configured=False)
    fallback = FakeProvider("gemini-2", ['{"from": "second-key"}'])

    assert run_with([primary, fallback]) == {"from": "second-key"}
    assert primary.calls == 0


def test_all_keys_failing_raises_naming_each_one():
    primary = FakeProvider("gemini", [TransientProviderError("gemini", "429")] * 2)
    fallback = FakeProvider("gemini-2", [TransientProviderError("gemini-2", "503")] * 2)

    with pytest.raises(LLMServiceError) as exc:
        run_with([primary, fallback])

    message = str(exc.value)
    assert "gemini" in message and "gemini-2" in message
    assert "429" in message and "503" in message


def test_empty_chain_raises_a_clear_error():
    """No key configured at all — say so, rather than emitting a bare
    'LLM call failed.' with no explanation."""
    with pytest.raises(LLMServiceError, match="no Gemini API key configured"):
        run_with([])


def test_key_order_is_respected():
    first = FakeProvider("gemini", ['{"from": "first-key"}'])
    second = FakeProvider("gemini-2", [])

    assert run_with([first, second]) == {"from": "first-key"}
    assert second.calls == 0


def test_json_arrays_still_parse():
    """call_json's contract is dict | list — resume parsing relies on the dict
    case, but nothing may assume a JSON object."""
    assert run_with([FakeProvider("gemini", ["[1, 2, 3]"])]) == [1, 2, 3]


# ---- transcription rides the same chain ----

def test_transcription_falls_back_to_the_second_key():
    """Audio and text share a key, so they share a quota. An account that is out
    for one is out for the other, and the second account has to cover both."""
    primary = FakeProvider("gemini", [TransientProviderError("gemini", "429 RESOURCE_EXHAUSTED")] * 2)
    fallback = FakeProvider("gemini-2", ["I rewrote the retry loop and shipped it."])

    assert transcribe_with([primary, fallback]) == "I rewrote the retry loop and shipped it."
    assert primary.calls == client.ATTEMPTS_PER_PROVIDER
    assert fallback.calls == 1


def test_transcription_of_silence_returns_empty_without_failing_over():
    """A clip with no speech is a real answer to "what did they say?" — nothing.
    Burning the second key retrying it would be wrong."""
    primary = FakeProvider("gemini", [""])
    fallback = FakeProvider("gemini-2", [])

    assert transcribe_with([primary, fallback]) == ""
    assert primary.calls == 1
    assert fallback.calls == 0


def test_transcription_with_no_key_raises_the_same_clear_error():
    with pytest.raises(LLMServiceError, match="no Gemini API key configured"):
        transcribe_with([])


# ---- chain construction from settings ----

def _settings(**overrides) -> Settings:
    # Both keys are pinned to "" here on purpose: Settings reads backend/.env,
    # so a field left unset would silently inherit the developer's real key and
    # make these assertions depend on whose machine they run on. Explicit init
    # kwargs outrank the env file.
    base = {
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/db",
        "database_url_sync": "postgresql+psycopg://u:p@localhost:5432/db",
        "redis_url": "redis://localhost:6379/0",
        "s3_endpoint_url": "http://localhost:9000",
        "s3_access_key": "a",
        "s3_secret_key": "b",
        "s3_bucket_name": "c",
        "jwt_secret_key": "d",
        "gemini_api_key": "",
        "gemini_api_key_2": "",
    }
    return Settings(**{**base, **overrides})


def _chain_names(**overrides) -> list[str]:
    with patch("app.services.llm.providers.get_settings", return_value=_settings(**overrides)):
        return [p.name for p in build_provider_chain()]


def test_one_key_builds_a_single_endpoint():
    """A .env with only GEMINI_API_KEY — i.e. every install before the second
    key existed — must behave exactly as it always did."""
    assert _chain_names(gemini_api_key="key-one") == ["gemini"]


def test_two_keys_build_two_endpoints_in_order():
    assert _chain_names(gemini_api_key="key-one", gemini_api_key_2="key-two") == [
        "gemini",
        "gemini-2",
    ]


def test_blank_and_whitespace_keys_are_ignored():
    """A .env line like `GEMINI_API_KEY_2=` must not create a broken endpoint
    that fails every call before the real key gets a turn."""
    assert _chain_names(gemini_api_key="key-one", gemini_api_key_2="   ") == ["gemini"]


def test_no_keys_builds_an_empty_chain():
    assert _chain_names() == []

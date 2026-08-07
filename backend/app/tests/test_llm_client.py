"""Failover behaviour of the LLM choke point.

The chain is one Gemini endpoint per configured API key ("gemini", then
"gemini-2"), so "primary" and "fallback" below mean first and second key. Mocked
at the provider boundary, so these run with no network and no API keys.
"""

import logging
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.core.exceptions import LLMConfigurationError, LLMServiceError
from app.services.llm import client
from app.services.llm.providers import build_provider_chain
from app.services.llm.providers.base import (
    PermanentProviderError,
    ProviderConfigurationError,
    RateLimitedError,
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
        self.thinking_budgets: list = []

    @property
    def configured(self) -> bool:
        return self._configured

    def generate(self, prompt: str, *, thinking_budget: int | None = None) -> str:
        self.thinking_budgets.append(thinking_budget)
        return self._next()

    def transcribe(self, audio: bytes, mime_type: str) -> str:
        return self._next()

    def embed(self, text: str, dimensions: int):
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


def embed_with(chain: list[FakeProvider]):
    with patch.object(client, "build_provider_chain", return_value=chain):
        return client.call_embedding("some text", 1536)


def test_primary_success_never_touches_the_fallback():
    primary = FakeProvider("gemini", ['{"ok": true}'])
    fallback = FakeProvider("gemini-2", [])

    assert run_with([primary, fallback]) == {"ok": True}
    assert primary.calls == 1
    assert fallback.calls == 0  # second account untouched on the happy path


def test_rate_limited_key_falls_back_to_the_second_account():
    """The whole point of two keys: requests/minute is metered per project.

    No retry on the exhausted key first — its quota window has not moved, so the
    second key is strictly faster and strictly more likely to work.
    """
    primary = FakeProvider("gemini", [RateLimitedError("gemini", "429 RESOURCE_EXHAUSTED")])
    fallback = FakeProvider("gemini-2", ['{"from": "second-key"}'])

    assert run_with([primary, fallback]) == {"from": "second-key"}
    assert primary.calls == 1
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


def test_all_keys_failing_logs_every_provider_but_does_not_leak_them(caplog):
    """Diagnosis in the log, not in the response body.

    The message used to be `"LLM call failed. " + "; ".join(failures)`, where each
    failure carried 200 characters of raw Google exception text — quota metric
    names, the project id, and by implication how many keys are configured. That
    reached any authenticated caller as a 502 body.
    """
    primary = FakeProvider("gemini", [TransientProviderError("gemini", "429 quota project=abc")] * 2)
    fallback = FakeProvider("gemini-2", [TransientProviderError("gemini-2", "503")] * 2)

    with caplog.at_level(logging.WARNING, logger="app.services.llm.client"):
        with pytest.raises(LLMServiceError) as exc:
            run_with([primary, fallback])

    message = str(exc.value)
    for secret in ("gemini", "gemini-2", "429", "503", "project=abc"):
        assert secret not in message, f"{secret!r} leaked into the client-facing error"
    assert "temporarily unavailable" in message

    logged = caplog.text
    assert "gemini" in logged and "gemini-2" in logged
    assert "429" in logged and "503" in logged


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
    primary = FakeProvider("gemini", [RateLimitedError("gemini", "429 RESOURCE_EXHAUSTED")])
    fallback = FakeProvider("gemini-2", ["I rewrote the retry loop and shipped it."])

    assert transcribe_with([primary, fallback]) == "I rewrote the retry loop and shipped it."
    assert primary.calls == 1
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


# --------------------------------------------------------------------------
# Backoff between attempts
#
# Retrying instantly was close to guaranteed to hit the same condition — a
# per-minute quota does not clear in zero seconds — so the retry SPECS.md §9 asks
# for was being spent for nothing.
# --------------------------------------------------------------------------


def test_a_retry_on_the_same_key_backs_off_first():
    provider = FakeProvider("gemini", [TransientProviderError("gemini", "503"), '{"ok": true}'])

    with patch.object(client.time, "sleep") as sleep:
        assert run_with([provider]) == {"ok": True}

    assert sleep.call_count == 1
    assert sleep.call_args.args[0] >= 0


def test_no_sleep_after_the_final_attempt():
    """Delay before giving up buys nothing — it only makes the failure slower."""
    provider = FakeProvider("gemini", [TransientProviderError("gemini", "503")] * 2)

    with patch.object(client.time, "sleep") as sleep:
        with pytest.raises(LLMServiceError):
            run_with([provider])

    # Two attempts means exactly one gap between them.
    assert sleep.call_count == 1


def test_a_successful_first_attempt_never_sleeps():
    with patch.object(client.time, "sleep") as sleep:
        assert run_with([FakeProvider("gemini", ['{"ok": true}'])]) == {"ok": True}

    sleep.assert_not_called()


def test_backoff_never_exceeds_the_ceiling():
    """Unbounded exponential growth would eventually out-wait the request itself."""
    with patch.object(client.time, "sleep") as sleep:
        for attempt in range(1, 6):
            client._sleep_before_retry(attempt)

    observed = [c.args[0] for c in sleep.call_args_list]
    assert all(0 <= d <= client.RETRY_MAX_DELAY_SECONDS for d in observed)


# --------------------------------------------------------------------------
# Rate limits switch keys instead of waiting
#
# Each key is a separate Google project with its own per-minute allowance, so
# when one is exhausted the fastest correct move is the other key — not a sleep
# followed by a retry that is still over quota.
# --------------------------------------------------------------------------


def test_switching_keys_on_a_rate_limit_does_not_sleep_first():
    primary = FakeProvider("gemini", [RateLimitedError("gemini", "429")])
    fallback = FakeProvider("gemini-2", ['{"from": "second-key"}'])

    with patch.object(client.time, "sleep") as sleep:
        assert run_with([primary, fallback]) == {"from": "second-key"}

    sleep.assert_not_called()


def test_the_last_key_does_back_off_when_rate_limited():
    """With nothing to fall back to, waiting is the only remaining option."""
    only_key = FakeProvider("gemini", [RateLimitedError("gemini", "429"), '{"ok": true}'])

    with patch.object(client.time, "sleep") as sleep:
        assert run_with([only_key]) == {"ok": True}

    assert only_key.calls == 2
    assert sleep.call_count == 1


# --------------------------------------------------------------------------
# Embeddings ride the same chain
#
# embed_text used to hand-roll a second copy of this whole loop, which never
# received the timeout, the backoff or the leak fix. These tests exist because
# that copy had none of its own.
# --------------------------------------------------------------------------


def test_embedding_falls_back_to_the_second_key():
    primary = FakeProvider("gemini", [RateLimitedError("gemini", "429")])
    fallback = FakeProvider("gemini-2", [[0.1, 0.2, 0.3]])

    assert embed_with([primary, fallback]) == [0.1, 0.2, 0.3]
    assert primary.calls == 1
    assert fallback.calls == 1


def test_embedding_retries_a_transient_failure_on_the_same_key():
    provider = FakeProvider("gemini", [TransientProviderError("gemini", "503"), [0.4]])

    with patch.object(client.time, "sleep"):
        assert embed_with([provider]) == [0.4]
    assert provider.calls == 2


def test_embedding_skips_the_retry_on_a_permanent_failure():
    primary = FakeProvider("gemini", [PermanentProviderError("gemini", "401 invalid key")])
    fallback = FakeProvider("gemini-2", [[0.5]])

    assert embed_with([primary, fallback]) == [0.5]
    assert primary.calls == 1


def test_embedding_with_no_key_raises_a_clear_error():
    """resumes.embedding is NOT NULL — the caller has to know this failed."""
    with pytest.raises(LLMServiceError, match="no Gemini API key configured"):
        embed_with([])


def test_embedding_exhaustion_does_not_leak_vendor_text():
    primary = FakeProvider("gemini", [TransientProviderError("gemini", "429 project=abc")] * 2)

    with patch.object(client.time, "sleep"):
        with pytest.raises(LLMServiceError) as exc:
            embed_with([primary])

    assert "project=abc" not in str(exc.value)


# --------------------------------------------------------------------------
# Schema validation is retried, not fatal
#
# model_validate used to run in the caller, after call_json had already
# returned — so a response that was valid JSON but missed the schema by one
# field got zero retries and became a hard 502. A real job description asking
# for "3 months of experience" made the model emit years_experience_required =
# 0.25 against an `int` field, and every single attempt to save it failed
# identically.
# --------------------------------------------------------------------------


class _Shape(BaseModel):
    years: int


def structured_with(chain: list[FakeProvider]):
    with patch.object(client, "build_provider_chain", return_value=chain):
        return client.call_structured("some prompt", _Shape)


def test_an_off_schema_response_is_resampled_on_the_same_key():
    provider = FakeProvider("gemini", ['{"years": 0.25}', '{"years": 1}'])

    with patch.object(client.time, "sleep"):
        assert structured_with([provider]) == _Shape(years=1)
    assert provider.calls == 2, "an off-schema field should be resampled, not fatal"


def test_a_persistently_off_schema_response_falls_back_to_the_other_key():
    primary = FakeProvider("gemini", ['{"years": 0.25}'] * 2)
    fallback = FakeProvider("gemini-2", ['{"years": 3}'])

    with patch.object(client.time, "sleep"):
        assert structured_with([primary, fallback]) == _Shape(years=3)
    assert primary.calls == client.ATTEMPTS_PER_PROVIDER


def test_structured_calls_still_retry_malformed_json():
    provider = FakeProvider("gemini", ['{"years": ', '{"years": 2}'])

    with patch.object(client.time, "sleep"):
        assert structured_with([provider]) == _Shape(years=2)


def test_a_json_array_where_an_object_was_expected_is_retried_not_crashed():
    """The old code checked isinstance(result, dict) and raised outright."""
    provider = FakeProvider("gemini", ["[1, 2, 3]", '{"years": 4}'])

    with patch.object(client.time, "sleep"):
        assert structured_with([provider]) == _Shape(years=4)


def test_exhausting_every_key_on_schema_failures_does_not_leak_the_payload():
    provider = FakeProvider("gemini", ['{"years": 0.25}'] * 2)

    with patch.object(client.time, "sleep"):
        with pytest.raises(LLMServiceError) as exc:
            structured_with([provider])

    assert "0.25" not in str(exc.value)


# --------------------------------------------------------------------------
# Misconfiguration is not "try again"
#
# A wrong GEMINI_LLM_MODEL produced a 404, which classify() called transient. It
# was retried twice per key, reported as "temporarily unavailable", and the
# resume parser relabelled it "We couldn't read this resume. Please try
# uploading it again." — advice that could never work, for a file that was fine.
# --------------------------------------------------------------------------


def test_an_unknown_model_is_reported_as_misconfiguration(caplog):
    missing = ProviderConfigurationError("gemini", "model not found — check GEMINI_LLM_MODEL")
    provider = FakeProvider("gemini", [missing])

    with caplog.at_level(logging.ERROR, logger="app.services.llm.client"):
        with pytest.raises(LLMConfigurationError) as exc:
            run_with([provider])

    assert "administrator" in str(exc.value)
    assert "retrying will not help" in str(exc.value)
    # Never retried: every key reads the same model name.
    assert provider.calls == 1
    # The operator gets the actionable detail; the API caller does not.
    assert "GEMINI_LLM_MODEL" in caplog.text
    assert "GEMINI_LLM_MODEL" not in str(exc.value)


def test_misconfiguration_does_not_waste_the_second_key():
    """Failing over cannot help — the model name is the same for both."""
    primary = FakeProvider("gemini", [ProviderConfigurationError("gemini", "model not found")])
    fallback = FakeProvider("gemini-2", [ProviderConfigurationError("gemini-2", "model not found")])

    with pytest.raises(LLMConfigurationError):
        run_with([primary, fallback])

    assert primary.calls == 1 and fallback.calls == 1


def test_a_genuine_outage_is_still_reported_as_temporary():
    """The distinction must not swallow real transient failures."""
    provider = FakeProvider("gemini", [TransientProviderError("gemini", "503")] * 2)

    with patch.object(client.time, "sleep"):
        with pytest.raises(LLMServiceError) as exc:
            run_with([provider])

    assert not isinstance(exc.value, LLMConfigurationError)
    assert "temporarily unavailable" in str(exc.value)


def test_a_mixed_failure_is_not_called_a_misconfiguration():
    """One key misconfigured and another merely down is not a config problem —
    telling the user to call an administrator would be wrong."""
    misconfigured = FakeProvider("gemini", [ProviderConfigurationError("gemini", "model not found")])
    flaky = FakeProvider("gemini-2", [TransientProviderError("gemini-2", "503")] * 2)

    with patch.object(client.time, "sleep"):
        with pytest.raises(LLMServiceError) as exc:
            run_with([misconfigured, flaky])

    assert not isinstance(exc.value, LLMConfigurationError)

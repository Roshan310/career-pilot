"""GeminiProvider's own response handling.

These exist because `test_llm_client.py`'s FakeProvider returns whatever the test
scripts it — so a test asserting "silence transcribes to empty" passed while the
real provider raised on exactly that input, and a live session 502'd. Anything
that interprets an SDK response has to be tested against a shape the SDK actually
produces, not against a stand-in that skips the interpreting.
"""

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.llm.providers.base import PermanentProviderError, TransientProviderError
from app.services.llm.providers.gemini import GeminiProvider


def response(text=None, finish_reason="STOP", thoughts=0):
    """The shape google-genai hands back. `finish_reason` is an enum whose `.name`
    is what the provider reads."""
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish_reason))],
        usage_metadata=SimpleNamespace(thoughts_token_count=thoughts, candidates_token_count=0),
    )


def transcribe(resp) -> str:
    provider = GeminiProvider("fake-key")
    with patch("app.services.llm.providers.gemini._get_client") as client:
        client.return_value.models.generate_content.return_value = resp
        return provider.transcribe(b"audio-bytes", "audio/webm")


def test_words_are_returned_trimmed():
    assert transcribe(response(text="  I rewrote the retry loop.\n")) == "I rewrote the retry loop."


def test_silence_transcribes_to_empty_rather_than_raising():
    """A clip with no speech in it is a real answer to "what did they say?" —
    nothing. The caller submits that turn as skipped. Raising here produced a 502
    on a turn the interview should simply have moved past."""
    assert transcribe(response(text="", finish_reason="STOP")) == ""
    assert transcribe(response(text=None, finish_reason="STOP")) == ""


def test_truncated_response_raises_with_the_reason_named():
    """The failure that actually happened: thinking tokens ate the output budget
    on a long answer, so the transcript came back empty with MAX_TOKENS. It was
    reported as "empty transcription", indistinguishable from silence, which sent
    the debugging in the wrong direction entirely."""
    with pytest.raises(TransientProviderError) as exc:
        transcribe(response(text="", finish_reason="MAX_TOKENS", thoughts=1500))

    message = str(exc.value)
    assert "MAX_TOKENS" in message
    assert "1500" in message  # the thinking-token count is the actual diagnosis


def test_blocked_response_raises_rather_than_reading_as_silence():
    with pytest.raises(TransientProviderError, match="SAFETY"):
        transcribe(response(text=None, finish_reason="SAFETY"))


def test_thinking_is_disabled_and_output_budget_is_explicit():
    """Both are load-bearing, and both are invisible in the response — the only
    place they can be checked is the request."""
    provider = GeminiProvider("fake-key")
    with patch("app.services.llm.providers.gemini._get_client") as client:
        generate = client.return_value.models.generate_content
        generate.return_value = response(text="words")
        provider.transcribe(b"audio", "audio/webm")

    config = generate.call_args.kwargs["config"]
    assert config.thinking_config.thinking_budget == 0
    assert config.max_output_tokens >= 4096


def test_audio_is_sent_with_the_mime_type_it_was_given():
    provider = GeminiProvider("fake-key")
    with patch("app.services.llm.providers.gemini._get_client") as client:
        generate = client.return_value.models.generate_content
        generate.return_value = response(text="words")
        provider.transcribe(b"audio-bytes", "audio/ogg")

    part = generate.call_args.kwargs["contents"][0]
    assert part.inline_data.mime_type == "audio/ogg"
    assert part.inline_data.data == b"audio-bytes"


# ==========================================================================
# Thinking budget
#
# Reasoning is the dominant latency cost on extractive parsing, but the allowed
# range is model-dependent (the SDK says so). A rejected value returns a 400,
# which classify() calls permanent — so a wrong guess would break resume upload
# outright rather than merely slowing it down.
# ==========================================================================


def _generate(provider, budget, side_effect=None, text='{"ok": true}'):
    captured = {}

    def fake_generate_content(**kwargs):
        captured["config"] = kwargs["config"]
        if side_effect is not None:
            outcome = side_effect.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
        return SimpleNamespace(text=text)

    client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content))
    with patch("app.services.llm.providers.gemini._get_client", return_value=client):
        result = provider.generate("prompt", thinking_budget=budget)
    return result, captured["config"]


def test_an_extractive_call_asks_for_no_thinking():
    _, config = _generate(GeminiProvider("k"), 0)
    assert config.thinking_config.thinking_budget == 0


def test_no_thinking_config_is_sent_when_none_is_requested():
    """Question generation and answer evaluation genuinely benefit from
    reasoning — they must keep the model default."""
    _, config = _generate(GeminiProvider("k"), None)
    assert config.thinking_config is None


def test_a_model_that_rejects_the_budget_falls_back_instead_of_failing(caplog):
    """The safety net. A 400 naming the thinking config is retried once without
    it — a slow parse is vastly better than a broken upload."""
    rejection = Exception("400 INVALID_ARGUMENT: thinking_budget is not supported for this model")

    with caplog.at_level(logging.WARNING):
        result, config = _generate(GeminiProvider("k"), 0, side_effect=[rejection, None])

    assert result == '{"ok": true}'
    assert config.thinking_config is None, "the retry must drop the rejected setting"
    assert "retrying with the model default" in caplog.text


def test_an_unrelated_rejection_is_not_retried():
    """A bad key must still fail fast — the fallback is narrow on purpose."""
    bad_key = Exception("401 PERMISSION_DENIED: API key not valid")

    with pytest.raises(PermanentProviderError):
        _generate(GeminiProvider("k"), 0, side_effect=[bad_key])

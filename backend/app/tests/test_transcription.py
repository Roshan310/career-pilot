"""Which recognizer runs, what counts as acceptable audio, and what empty means.

Mocked at the httpx boundary and at `call_transcription`, so these run with no
keys and no network.
"""

from unittest.mock import patch

import httpx
import pytest

from app.core.exceptions import UnprocessableError
from app.services import transcription


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"text": "words from scribe"}
        self.text = text or f"status {status_code}"

    def json(self):
        return self._payload


def _with_scribe(**kwargs):
    """Scribe configured, and its HTTP call stubbed."""
    return (
        patch.object(transcription.settings, "eleven_labs_api_key", "fake-key"),
        patch.object(transcription.httpx, "post", **kwargs),
    )


# ---- which recognizer runs ----

def test_scribe_is_preferred_and_gemini_is_left_alone():
    """A purpose-built recognizer can't answer a question it was asked to write
    down, and doesn't consume the Gemini quota the rest of the app shares."""
    configured, post = _with_scribe(return_value=FakeResponse())
    with configured, post as mock_post, patch.object(transcription, "call_transcription") as gemini:
        assert transcription.transcribe_answer(b"audio", "audio/webm") == "words from scribe"

    assert mock_post.call_count == 1
    assert gemini.call_count == 0


def test_gemini_is_used_when_no_eleven_labs_key_is_configured():
    with (
        patch.object(transcription.settings, "eleven_labs_api_key", ""),
        patch.object(transcription, "call_transcription", return_value="words from gemini") as gemini,
        patch.object(transcription.httpx, "post") as post,
    ):
        assert transcription.transcribe_answer(b"audio", "audio/webm") == "words from gemini"

    assert post.call_count == 0
    assert gemini.call_count == 1


def test_scribe_failure_falls_back_to_gemini_rather_than_ending_the_turn():
    """Transcription must not have a single point of failure — a vendor outage or
    an exhausted plan can't be allowed to end someone's interview."""
    configured, post = _with_scribe(return_value=FakeResponse(status_code=401, text="invalid key"))
    with configured, post, patch.object(
        transcription, "call_transcription", return_value="words from gemini"
    ) as gemini:
        assert transcription.transcribe_answer(b"audio", "audio/webm") == "words from gemini"

    assert gemini.call_count == 1


def test_scribe_network_error_also_falls_back():
    configured, post = _with_scribe(side_effect=httpx.ConnectError("no route to host"))
    with configured, post, patch.object(
        transcription, "call_transcription", return_value="words from gemini"
    ) as gemini:
        assert transcription.transcribe_answer(b"audio", "audio/webm") == "words from gemini"

    assert gemini.call_count == 1


def test_the_audio_is_posted_with_its_own_mime_type_and_the_configured_model():
    configured, post = _with_scribe(return_value=FakeResponse())
    with configured, post as mock_post, patch.object(transcription, "call_transcription"):
        transcription.transcribe_answer(b"opus-bytes", "audio/webm;codecs=opus")

    kwargs = mock_post.call_args.kwargs
    assert kwargs["files"]["file"][1] == b"opus-bytes"
    assert kwargs["files"]["file"][2] == "audio/webm"  # codecs parameter stripped
    assert kwargs["data"]["model_id"] == transcription.settings.eleven_labs_stt_model
    assert kwargs["headers"]["xi-api-key"] == "fake-key"


# ---- what the audio has to look like ----

def test_codec_parameter_is_stripped_before_the_recognizer_sees_it():
    """MediaRecorder reports `audio/webm;codecs=opus`. The parameter is a browser
    detail, not a media type, and forwarding it has 400'd a recognizer before."""
    assert transcription.normalize_mime_type("audio/webm;codecs=opus") == "audio/webm"
    assert transcription.normalize_mime_type("AUDIO/WEBM; codecs=opus") == "audio/webm"


def test_missing_content_type_assumes_the_common_case():
    assert transcription.normalize_mime_type(None) == "audio/webm"


def test_empty_upload_is_rejected_before_spending_a_call():
    with patch.object(transcription, "call_transcription") as gemini, patch.object(
        transcription.httpx, "post"
    ) as post:
        with pytest.raises(UnprocessableError, match="No audio"):
            transcription.transcribe_answer(b"", "audio/webm")
    assert gemini.call_count == 0 and post.call_count == 0


def test_oversized_upload_is_rejected_before_spending_a_call():
    with patch.object(transcription, "call_transcription") as gemini, patch.object(
        transcription.httpx, "post"
    ) as post:
        with pytest.raises(UnprocessableError, match="too large"):
            transcription.transcribe_answer(b"x" * (transcription.MAX_AUDIO_BYTES + 1), "audio/webm")
    assert gemini.call_count == 0 and post.call_count == 0


def test_unsupported_format_is_rejected_before_spending_a_call():
    with patch.object(transcription, "call_transcription") as gemini, patch.object(
        transcription.httpx, "post"
    ) as post:
        with pytest.raises(UnprocessableError, match="Unsupported audio format"):
            transcription.transcribe_answer(b"bytes", "video/mp4")
    assert gemini.call_count == 0 and post.call_count == 0


# ---- what empty means ----

def test_silence_transcribes_to_empty_rather_than_erroring():
    """A turn where nobody spoke is an ordinary outcome — the client submits it
    as skipped. Raising here would strand the interview on that question."""
    configured, post = _with_scribe(return_value=FakeResponse(payload={"text": ""}))
    with configured, post, patch.object(transcription, "call_transcription"):
        assert transcription.transcribe_answer(b"audio", "audio/webm") == ""


def test_a_missing_text_field_is_treated_as_silence_not_a_crash():
    configured, post = _with_scribe(return_value=FakeResponse(payload={}))
    with configured, post, patch.object(transcription, "call_transcription"):
        assert transcription.transcribe_answer(b"audio", "audio/webm") == ""


def test_surrounding_whitespace_is_trimmed():
    configured, post = _with_scribe(return_value=FakeResponse(payload={"text": "  I shipped it.\n"}))
    with configured, post, patch.object(transcription, "call_transcription"):
        assert transcription.transcribe_answer(b"audio", "audio/webm") == "I shipped it."

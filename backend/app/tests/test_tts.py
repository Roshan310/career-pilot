"""The interviewer's voice: caching, and never breaking the interview.

Mocked at the httpx boundary, so these run without an ElevenLabs key or network.
"""

import uuid
from unittest.mock import patch

import httpx
import pytest

from app.services import tts


class FakeResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"ID3-audio", text: str = ""):
        self.status_code = status_code
        self.content = content
        self.text = text or f"status {status_code}"


def _configured():
    """tts reads a module-level settings object, so patch the attribute it reads
    rather than the environment."""
    return patch.object(tts.settings, "eleven_labs_api_key", "fake-key")


def test_audio_is_generated_once_and_served_from_cache_after():
    """The cost control, not a nicety: TTS bills per character, so a reconnect or
    a replay must not re-bill a question the candidate already heard."""
    store: dict[str, bytes] = {}
    session_id = uuid.uuid4()

    with (
        _configured(),
        patch.object(tts.httpx, "post", return_value=FakeResponse(content=b"audio-bytes")) as post,
        patch.object(tts.storage_service, "get_bytes", side_effect=store.get),
        patch.object(tts.storage_service, "upload_bytes", side_effect=lambda k, c, t: store.update({k: c})),
    ):
        first = tts.question_audio(session_id, 1, "Tell me about a hard bug.")
        second = tts.question_audio(session_id, 1, "Tell me about a hard bug.")

    assert first == second == b"audio-bytes"
    assert post.call_count == 1  # the second call never left the process
    assert tts.cache_key(session_id, 1) in store


def test_each_turn_is_cached_separately():
    session_id = uuid.uuid4()
    assert tts.cache_key(session_id, 1) != tts.cache_key(session_id, 2)


def test_no_key_configured_raises_the_recoverable_error():
    """Must be TTSUnavailableError, not an AppError: the router turns this into a
    503 the client answers by falling back to browser speech. If it were an
    AppError it would surface as a failed interview instead of a quiet one."""
    with patch.object(tts.settings, "eleven_labs_api_key", ""):
        with pytest.raises(tts.TTSUnavailableError, match="no ELEVEN_LABS_API_KEY"):
            tts.question_audio(uuid.uuid4(), 1, "Anything.")


def test_vendor_error_body_survives_into_the_message():
    """The 402 that actually happened said `paid_plan_required` for a library
    voice — indistinguishable from a bad key unless the body is kept."""
    body = '{"detail":{"status":"paid_plan_required","message":"Free users cannot use library voices"}}'

    with (
        _configured(),
        patch.object(tts.storage_service, "get_bytes", return_value=None),
        patch.object(tts.httpx, "post", return_value=FakeResponse(status_code=402, text=body)),
    ):
        with pytest.raises(tts.TTSUnavailableError, match="paid_plan_required"):
            tts.question_audio(uuid.uuid4(), 1, "Anything.")


def test_network_failure_is_not_left_as_a_raw_httpx_error():
    with (
        _configured(),
        patch.object(tts.storage_service, "get_bytes", return_value=None),
        patch.object(tts.httpx, "post", side_effect=httpx.ConnectError("no route to host")),
    ):
        with pytest.raises(tts.TTSUnavailableError, match="no route to host"):
            tts.question_audio(uuid.uuid4(), 1, "Anything.")


def test_a_cache_write_failure_still_returns_the_audio():
    """Audio that was generated but couldn't be stored is still good audio.
    Raising here would turn a storage problem into a silent interview — and we'd
    have paid for the bytes anyway."""
    with (
        _configured(),
        patch.object(tts.storage_service, "get_bytes", return_value=None),
        patch.object(tts.storage_service, "upload_bytes", side_effect=OSError("minio is down")),
        patch.object(tts.httpx, "post", return_value=FakeResponse(content=b"audio-bytes")),
    ):
        assert tts.question_audio(uuid.uuid4(), 1, "Anything.") == b"audio-bytes"

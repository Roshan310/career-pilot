"""The interviewer's voice: caching, and never breaking the interview.

Mocked at the httpx boundary, so these run without an ElevenLabs key or network.
"""

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

    with (
        _configured(),
        patch.object(tts.httpx, "post", return_value=FakeResponse(content=b"audio-bytes")) as post,
        patch.object(tts.storage_service, "get_bytes", side_effect=store.get),
        patch.object(tts.storage_service, "upload_bytes", side_effect=lambda k, c, t: store.update({k: c})),
    ):
        first = tts.question_audio("Tell me about a hard bug.")
        second = tts.question_audio("Tell me about a hard bug.")

    assert first == second == b"audio-bytes"
    assert post.call_count == 1  # the second call never left the process
    assert tts.cache_key("Tell me about a hard bug.") in store


def test_the_same_question_in_a_different_session_is_a_cache_hit():
    """What makes replaying an interview free. The key used to contain the
    session id, so a replay — identical questions, identical voice — missed
    every object and re-billed audio already paid for."""
    store: dict[str, bytes] = {}

    with (
        _configured(),
        patch.object(tts.httpx, "post", return_value=FakeResponse(content=b"audio-bytes")) as post,
        patch.object(tts.storage_service, "get_bytes", side_effect=store.get),
        patch.object(tts.storage_service, "upload_bytes", side_effect=lambda k, c, t: store.update({k: c})),
    ):
        # Two entirely unrelated sessions; nothing about them is passed in.
        tts.question_audio("Walk me through your RAG project.")
        tts.question_audio("Walk me through your RAG project.")

    assert post.call_count == 1
    assert len(store) == 1


def test_different_questions_are_cached_separately():
    assert tts.cache_key("Tell me about a hard bug.") != tts.cache_key("Why this role?")


def test_the_key_changes_when_the_voice_does():
    """Otherwise switching voice, model, format or the hand-tuned voice_settings
    would keep serving audio in the old delivery from cache, forever."""
    text = "Tell me about a hard bug."
    baseline = tts.cache_key(text)

    with patch.object(tts.settings, "eleven_labs_voice_id", "some-other-voice"):
        assert tts.cache_key(text) != baseline
    with patch.object(tts.settings, "eleven_labs_model_id", "eleven_multilingual_v2"):
        assert tts.cache_key(text) != baseline
    with patch.object(tts.settings, "eleven_labs_output_format", "mp3_22050_32"):
        assert tts.cache_key(text) != baseline
    with patch.object(tts, "VOICE_SETTINGS_VERSION", "v2"):
        assert tts.cache_key(text) != baseline

    # ...and is stable when nothing changed.
    assert tts.cache_key(text) == baseline


def test_no_key_configured_raises_the_recoverable_error():
    """Must be TTSUnavailableError, not an AppError: the router turns this into a
    503 the client answers by falling back to browser speech. If it were an
    AppError it would surface as a failed interview instead of a quiet one."""
    with patch.object(tts.settings, "eleven_labs_api_key", ""):
        with pytest.raises(tts.TTSUnavailableError, match="no ELEVEN_LABS_API_KEY"):
            tts.question_audio("Anything.")


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
            tts.question_audio("Anything.")


def test_network_failure_is_not_left_as_a_raw_httpx_error():
    with (
        _configured(),
        patch.object(tts.storage_service, "get_bytes", return_value=None),
        patch.object(tts.httpx, "post", side_effect=httpx.ConnectError("no route to host")),
    ):
        with pytest.raises(tts.TTSUnavailableError, match="no route to host"):
            tts.question_audio("Anything.")


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
        assert tts.question_audio("Anything.") == b"audio-bytes"

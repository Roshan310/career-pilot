"""The interviewer's voice — ElevenLabs, cached in object storage.

Why this is server-side at all: the browser's `speechSynthesis` is not a
dependable transport. Brave restricts it, Linux Chromium ships with no local
voices unless speech-dispatcher is installed, and the API's own events are
famously unreliable. It also sounds like a screen reader. Generating the audio
here means every browser gets the same voice, and it's a voice a person would
actually want to be interviewed by.

Caching is not an optimization detail — it's what makes the cost bounded. TTS
bills per character, so without it a reconnect, a replay, or a page refresh
would re-bill every question the candidate has already heard.

The cache is keyed by *content*, not by session. Keying it by session and turn
meant a replay of a past interview — the same questions, in the same voice —
missed every object and re-billed audio already paid for, which made practising
an interview twice cost twice. Content addressing also deduplicates a follow-up
question that recurs across sessions.
"""

import hashlib
import logging

import httpx

from app.core.config import get_settings
from app.services import storage_service

logger = logging.getLogger(__name__)
settings = get_settings()

_API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"
CONTENT_TYPE = "audio/mpeg"
# Generous: turbo is sub-second in practice, but a cold connection on a slow link
# shouldn't surface as a failed question when waiting another beat would do.
_TIMEOUT_SECONDS = 30.0


class TTSUnavailableError(Exception):
    """No audio could be produced. Always recoverable from the caller's side —
    the client falls back to browser speech — so it is deliberately NOT an
    AppError subclass: this must never look like a failed interview."""


def is_configured() -> bool:
    return bool(settings.eleven_labs_api_key)


# Bumped by hand whenever the `voice_settings` block in `_synthesize` changes.
# Those numbers are part of what the bytes sound like, but unlike the voice and
# model ids they are literals rather than settings, so nothing else in the key
# would notice them changing — and the cache would happily serve audio in the
# old delivery forever.
VOICE_SETTINGS_VERSION = "v1"


def cache_key(text: str) -> str:
    """The object key for one question's audio.

    Derived from everything that determines the bytes: the question text and
    the full voice configuration. Two sessions asking the same question in the
    same voice therefore share one object, which is what makes replaying an
    interview cost nothing in TTS.
    """
    fingerprint = "|".join(
        (
            settings.eleven_labs_voice_id,
            settings.eleven_labs_model_id,
            settings.eleven_labs_output_format,
            VOICE_SETTINGS_VERSION,
            text,
        )
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return f"interview-audio/questions/{digest}.mp3"


def _synthesize(text: str) -> bytes:
    """One POST to ElevenLabs. Raises TTSUnavailableError for every failure mode,
    because the caller's response to all of them is identical."""
    try:
        response = httpx.post(
            f"{_API_BASE}/{settings.eleven_labs_voice_id}",
            headers={
                "xi-api-key": settings.eleven_labs_api_key,
                "Content-Type": "application/json",
            },
            params={"output_format": settings.eleven_labs_output_format},
            json={
                "text": text,
                "model_id": settings.eleven_labs_model_id,
                # Tuned for an interviewer rather than an audiobook narrator:
                # stability low enough to carry natural intonation, style at 0 so
                # it stays neutral and doesn't editorialize the question.
                "voice_settings": {
                    "stability": 0.45,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
            },
            timeout=_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise TTSUnavailableError(f"elevenlabs request failed: {exc}") from exc

    if response.status_code != 200:
        # The body carries ElevenLabs' own reason (quota exhausted, bad voice ID,
        # invalid key). Keep a slice of it — "TTS failed" alone is undebuggable.
        raise TTSUnavailableError(
            f"elevenlabs returned {response.status_code}: {response.text[:200]}"
        )
    if not response.content:
        raise TTSUnavailableError("elevenlabs returned an empty body")
    return response.content


def question_audio(text: str) -> bytes:
    """Audio for one question, from cache when possible.

    Takes only the text: which session or turn is asking is irrelevant to what
    the bytes are, and making it part of the identity is precisely what used to
    re-bill replays.

    A storage failure is logged and swallowed rather than raised: audio that was
    generated but not cached is still perfectly good audio, and refusing to serve
    it would turn a cache problem into a silent interview.
    """
    if not is_configured():
        raise TTSUnavailableError("no ELEVEN_LABS_API_KEY configured")

    key = cache_key(text)
    cached = storage_service.get_bytes(key)
    if cached:
        return cached

    audio = _synthesize(text)
    try:
        storage_service.upload_bytes(key, audio, CONTENT_TYPE)
    except Exception:  # noqa: BLE001 — see docstring
        logger.warning("could not cache question audio at %s", key, exc_info=True)
    return audio

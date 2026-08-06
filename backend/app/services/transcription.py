"""Spoken answers → text, server-side.

SPECS.md §7.3 assumed the browser would do this with the Web Speech API. It
can't: Brave ships `webkitSpeechRecognition` as a stub that returns a `network`
error instead of results, and feature-detecting the constructor says nothing
about whether it works. Doing it here means the interview behaves identically in
every browser, which is the whole point of the answer envelope being
provider-agnostic (`TurnSubmitRequest.source`, already able to say `server_stt`).

Two implementations, tried in order:

1. **ElevenLabs Scribe** — a real speech recognizer. Preferred, and not just for
   accuracy: an ASR model has no way to *respond* to what it hears. Gemini, being
   a general-purpose model, would answer a question it was asked to transcribe,
   and would spend thinking tokens on a task that needs no thought. Scribe also
   accepts WebM directly and is metered separately from the Gemini quota — which
   matters, because the whole app shares that quota.
2. **Gemini** — the fallback, on the same keys and failover as every other LLM
   call. Kept so transcription has no single point of failure: one vendor being
   down or out of credit must not end an interview.
"""

import logging

import httpx

from app.core.config import get_settings
from app.core.exceptions import UnprocessableError
from app.services.llm.client import call_transcription

logger = logging.getLogger(__name__)
settings = get_settings()

_SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
# Generous: a long answer is a large upload and the model reads the whole clip
# before returning anything.
_TIMEOUT_SECONDS = 120.0

# Opus in a WebM container is what MediaRecorder produces in every browser that
# has it. The rest are here because Safari and some Android builds disagree, and
# an answer rejected on a container technicality is an answer lost.
SUPPORTED_MIME_TYPES = (
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
)

# A 20-minute session cap (interview_hard_cap_minutes) bounds a single answer well
# below this; the limit exists to stop a malformed or hostile upload reaching the
# recognizer at all, not to constrain real answers.
MAX_AUDIO_BYTES = 25 * 1024 * 1024


class STTUnavailableError(Exception):
    """Scribe couldn't produce a transcript. Always recoverable — the caller falls
    back to Gemini — so this never reaches the client."""


def scribe_configured() -> bool:
    return bool(settings.eleven_labs_api_key)


def normalize_mime_type(raw: str | None) -> str:
    """MediaRecorder reports codecs inline — `audio/webm;codecs=opus`. The
    parameter is a browser detail, not a media type either recognizer accepts."""
    if not raw:
        return "audio/webm"
    return raw.split(";")[0].strip().lower()


def _transcribe_with_scribe(audio: bytes, mime_type: str) -> str:
    try:
        response = httpx.post(
            _SCRIBE_URL,
            headers={"xi-api-key": settings.eleven_labs_api_key},
            files={"file": ("answer", audio, mime_type)},
            data={"model_id": settings.eleven_labs_stt_model},
            timeout=_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise STTUnavailableError(f"scribe request failed: {exc}") from exc

    if response.status_code != 200:
        # Keep the body: it distinguishes "out of credit" from "bad key" from
        # "unsupported file", which the status code alone does not.
        raise STTUnavailableError(f"scribe returned {response.status_code}: {response.text[:200]}")

    # Scribe also returns word-level timings. Unused for now — the pause metric
    # already comes from the browser's own voice-activity detection, measured on
    # the raw audio. They'd be the better source if that ever stops being true.
    return (response.json().get("text") or "").strip()


def transcribe_answer(audio: bytes, content_type: str | None) -> str:
    """The candidate's words. Empty string when the clip holds no speech — that's
    an ordinary outcome (a turn where nobody said anything), not an error, and
    the caller submits it as a skipped turn."""
    if not audio:
        raise UnprocessableError("No audio was uploaded.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise UnprocessableError("That recording is too large to transcribe.")

    mime_type = normalize_mime_type(content_type)
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise UnprocessableError(f"Unsupported audio format: {mime_type}")

    # Logged before the call, not just after. When transcription came back empty
    # in the field there was no record of what had been sent, so "is the audio
    # wrong or is the recognizer wrong?" couldn't be answered from the logs at
    # all. The leading bytes identify the real container regardless of what the
    # browser labelled it (`\x1aE\xdf\xa3` = EBML/WebM, `OggS` = Ogg, `RIFF` = WAV).
    logger.info(
        "transcribing %d bytes, declared=%r normalized=%s magic=%r",
        len(audio), content_type, mime_type, audio[:4],
    )

    transcript = ""
    if scribe_configured():
        try:
            transcript = _transcribe_with_scribe(audio, mime_type)
        except STTUnavailableError as exc:
            logger.warning("scribe unavailable, falling back to Gemini: %s", exc)
            transcript = call_transcription(audio, mime_type).strip()
    else:
        transcript = call_transcription(audio, mime_type).strip()

    if not transcript:
        logger.warning(
            "no speech transcribed from %d bytes of %s — the turn will be treated as skipped",
            len(audio), mime_type,
        )
    else:
        logger.info("transcribed into %d characters", len(transcript))
    return transcript

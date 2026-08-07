"""Google Gemini text generation and audio transcription.

One instance per configured API key. Gemini's free tier caps `generate_content`
at 20 requests/minute *per project*, so a key from a second account is a second
quota pool — `build_provider_chain()` turns each key into its own provider and
`call_json()` fails over between them exactly as it would between vendors.
"""

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.services.llm.prompts import TRANSCRIPTION_PROMPT
from app.services.llm.providers.base import (
    PermanentProviderError,
    RateLimitedError,
    TransientProviderError,
)

settings = get_settings()

# Clients are cached per API key and built lazily (not at import time) so these
# modules can be imported — and mocked in tests — with no key configured.
_clients: dict[str, genai.Client] = {}


def _get_client(api_key: str) -> genai.Client:
    if api_key not in _clients:
        # Without an explicit timeout google-genai waits indefinitely. Combined
        # with ATTEMPTS_PER_PROVIDER x number of keys, a single hung connection
        # could pin a request — and, before these calls moved off the event loop,
        # the entire worker — with no upper bound at all. ElevenLabs has had
        # timeouts since it was added; this closes the same gap for Gemini.
        # google-genai takes milliseconds here.
        _clients[api_key] = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
        )
    return _clients[api_key]


class GeminiProvider:
    def __init__(self, api_key: str, name: str = "gemini"):
        self.api_key = api_key
        self.name = name

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str) -> str:
        try:
            response = _get_client(self.api_key).models.generate_content(
                model=settings.gemini_llm_model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
        except Exception as exc:  # google-genai raises its own hierarchy
            raise classify(exc, self.name) from exc

        if not response.text:
            raise TransientProviderError(self.name, "empty response")
        return response.text

    def embed(self, text: str, dimensions: int) -> list[float]:
        """Embed text at the column's exact width.

        Note this is the one operation that is *not* vendor-neutral in practice.
        Failing over between two keys is safe because both address the same
        model, and therefore the same vector space; a genuinely different vendor
        could not be added to this chain without corrupting `semantic_score`,
        because vectors from two models are not comparable. See `embed_text`.
        """
        try:
            response = _get_client(self.api_key).models.embed_content(
                model=settings.gemini_embedding_model,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=dimensions),
            )
        except Exception as exc:
            raise classify(exc, self.name) from exc

        if not response.embeddings:
            raise TransientProviderError(self.name, "no embedding returned")
        return list(response.embeddings[0].values)

    def transcribe(self, audio: bytes, mime_type: str) -> str:
        """Gemini takes audio as an ordinary input part, so transcription needs no
        separate vendor, no separate key, and no separate quota to reason about.

        Note the absence of `response_mime_type="application/json"` here: we want
        the bare words the candidate said. Asking for JSON would invite the model
        to summarise or restructure the answer, and the evaluator downstream is
        scoring how they actually phrased it.
        """
        try:
            response = _get_client(self.api_key).models.generate_content(
                model=settings.gemini_stt_model,
                contents=[types.Part.from_bytes(data=audio, mime_type=mime_type)],
                # As a system instruction rather than another content part. A
                # general-purpose model handed speech will treat it as something
                # to respond to unless told otherwise at the strongest level
                # available: fed a clip that ended in a question, it answered the
                # question instead of writing it down. Candidates end answers
                # with "does that make sense?" all the time.
                config=types.GenerateContentConfig(
                    system_instruction=TRANSCRIPTION_PROMPT,
                    # Thinking off. Writing down words that were just said needs no
                    # reasoning, and gemini-2.5-flash budgets thinking tokens out of
                    # the *same* output allowance — on a long answer it can spend
                    # the whole budget deliberating and return an empty transcript
                    # with finish_reason MAX_TOKENS. Costs latency and tokens for
                    # nothing even when it doesn't break.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    # A 20-minute session cap bounds one answer well under this;
                    # it exists so a long answer can't be silently truncated.
                    max_output_tokens=8192,
                    temperature=0.0,
                ),
            )
        except Exception as exc:
            raise classify(exc, self.name) from exc

        return self._transcript_from(response)

    def _transcript_from(self, response) -> str:
        """Pull the words out, and be specific about why there aren't any.

        Empty text is not automatically a failure — a clip with no speech in it
        genuinely transcribes to nothing, and the caller submits that turn as
        skipped. But empty text because the model was cut off or blocked *is* a
        failure, and reporting both as "empty transcription" made a real bug
        (thinking tokens exhausting the output budget) unreadable in the logs.
        """
        candidate = response.candidates[0] if response.candidates else None
        finish = getattr(candidate, "finish_reason", None)
        finish_name = getattr(finish, "name", str(finish)) if finish else "NONE"

        text = (response.text or "").strip()
        if text:
            return text

        # STOP with no text means the model listened and heard no words.
        if finish_name in ("STOP", "NONE"):
            return ""

        usage = getattr(response, "usage_metadata", None)
        thoughts = getattr(usage, "thoughts_token_count", None)
        raise TransientProviderError(
            self.name,
            f"no transcript (finish_reason={finish_name}, thinking_tokens={thoughts})",
        )


def classify(exc: Exception, provider: str = "gemini") -> Exception:
    """google-genai surfaces the HTTP status inside the message rather than as a
    typed hierarchy we can rely on, so match on it. Anything unrecognised is
    treated as transient — one wasted retry is cheaper than a hard failure on an
    error shape we haven't seen yet.

    Shared with services/embeddings.py so both paths agree on what "this key is
    out of quota, try the other one" looks like.
    """
    text = str(exc)
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        return RateLimitedError(provider, f"rate limited: {text[:200]}")
    if "401" in text or "403" in text or "PERMISSION_DENIED" in text or "API key" in text:
        return PermanentProviderError(provider, f"auth failed: {text[:200]}")
    if "400" in text or "INVALID_ARGUMENT" in text:
        return PermanentProviderError(provider, f"rejected request: {text[:200]}")
    return TransientProviderError(provider, text[:200])

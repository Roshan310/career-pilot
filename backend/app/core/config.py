from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    # Application log level. Below WARNING nothing is emitted at all unless
    # main.py configures the root logger — see the comment there.
    log_level: str = "INFO"

    database_url: str
    database_url_sync: str
    # Separate DB so pytest's create_all/drop_all never touches dev data.
    # Defaults to database_url's db name + '_test' unless set explicitly.
    test_database_url: str = ""

    @model_validator(mode="after")
    def _default_test_database_url(self) -> "Settings":
        if not self.test_database_url:
            base, _, db_name = self.database_url.rpartition("/")
            self.test_database_url = f"{base}/{db_name}_test"
        return self

    redis_url: str

    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_name: str
    s3_region: str = "us-east-1"

    # --- Gemini (LLM + embeddings) ---
    # Two keys are supported because the free tier caps generate_content per
    # project — 5 requests/minute as of August 2026, down from 20 — so a key from
    # a second account roughly doubles that. The second is optional — with only the first set, everything behaves
    # exactly as it did when only one key existed.
    gemini_api_key: str = ""
    gemini_api_key_2: str = ""
    gemini_llm_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    # Answer transcription. Gemini takes audio as an ordinary input part, so this
    # rides the same keys and the same failover as every other LLM call.
    gemini_stt_model: str = "gemini-2.5-flash"
    # Per-attempt ceiling on any Gemini call. Generous because question-plan
    # generation legitimately runs 5-15s, but bounded: an unbounded call could be
    # retried twice per key across two keys, so the worst case had no limit at
    # all. Transcription of a long answer is the slowest case, hence not 30s.
    gemini_timeout_seconds: int = 60

    @property
    def gemini_api_keys(self) -> list[str]:
        """Configured keys in priority order. Used for both call_json() failover
        and embeddings — one exhausted account shouldn't stop the other."""
        return [key.strip() for key in (self.gemini_api_key, self.gemini_api_key_2) if key.strip()]

    # --- ElevenLabs (interviewer voice) ---
    # Optional. Without a key the interview still runs: the audio endpoint returns
    # 503 and the browser falls back to its own speech synthesis, which is worse
    # but never silent-and-stuck. See docs/decisions.md.
    eleven_labs_api_key: str = ""
    # "Sarah" — mature, reassuring, confident, which is the register an interviewer
    # wants. A setting so the voice can change without a deploy.
    #
    # Must be a *premade* voice: free accounts get 402 `paid_plan_required` for
    # library voices via the API, and the message names the plan rather than the
    # voice, so it reads like a broken key. `GET /v2/voices` lists what a given
    # key may actually use.
    eleven_labs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    # Turbo trades a little fidelity for ~300ms time-to-first-byte. An interviewer
    # that pauses a beat before every question feels broken, so latency wins here.
    eleven_labs_model_id: str = "eleven_turbo_v2_5"
    eleven_labs_output_format: str = "mp3_44100_64"
    # Purpose-built ASR, used in preference to the LLM for transcription. Free
    # tier bills it separately from TTS characters — measured at 0 credits for a
    # 65-second answer.
    eleven_labs_stt_model: str = "scribe_v1"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 14

    free_tier_monthly_match_limit: int = 5
    free_tier_monthly_interview_limit: int = 10

    interview_max_followups_per_question: int = 2
    interview_hard_cap_minutes: int = 20
    interview_hard_cap_questions: int = 8

    max_resume_file_size_mb: int = 10
    # A job description goes straight into an LLM prompt and an embedding call.
    # Resumes were capped at 10MB; this side had no bound at all.
    max_job_description_chars: int = 50_000

    # --- Stale match sweep (services/match_reaper.py) ---
    # Scoring takes seconds. Ten minutes is an enormous margin over that, chosen
    # so a false positive is not realistically reachable.
    stale_match_after_seconds: int = 600
    stale_match_sweep_interval_seconds: int = 300

    # Origins allowed to call this API from a browser. Comma-separated in the
    # environment. Defaults cover local development; set explicitly in deployment.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_allow_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _reject_placeholder_secret(self) -> "Settings":
        """A default JWT signing key outside development is a silent, total
        auth bypass for anyone who has read the example env file."""
        placeholder = "change-me-to-a-long-random-string"
        if self.env != "development" and self.jwt_secret_key.strip() in {placeholder, ""}:
            raise ValueError(
                "JWT_SECRET_KEY is still the placeholder from .env.example. "
                "Set a long random value before running outside development."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

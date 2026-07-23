from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"

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

    gemini_api_key: str = ""
    gemini_llm_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 14

    free_tier_monthly_match_limit: int = 5
    free_tier_monthly_interview_limit: int = 3

    interview_max_followups_per_question: int = 2
    interview_hard_cap_minutes: int = 20
    interview_hard_cap_questions: int = 8

    max_resume_file_size_mb: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()

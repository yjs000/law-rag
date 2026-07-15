from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Process environment still has the highest priority. The second file
        # overrides the first one, matching Vercel/Next.js local conventions.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "에너지 법령 RAG"
    environment: Literal["development", "test", "production"] = "development"
    collector_state_dir: Path = Path(".collector-state")
    database_url: str | None = None
    direct_url: str | None = None
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_raw_bucket: str = "law-raw"
    openai_api_key: str | None = None
    ai_mode: Literal["auto", "off"] = "auto"
    openai_answer_model: Literal["gpt-5.6-terra"] = "gpt-5.6-terra"
    openai_embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 512
    rate_limit_secret: str = Field(default="development-only-secret", min_length=16)
    ai_daily_limit: int = Field(default=3, ge=1)
    search_daily_limit: int = Field(default=30, ge=1)
    authenticated_ai_daily_limit: int = Field(default=10, ge=1)
    authenticated_search_daily_limit: int = Field(default=100, ge=1)
    terms_version: str = "beta-2026-07-15"
    privacy_version: str = "beta-2026-07-15"
    web_origin: str = "http://localhost:3000"
    request_timeout_seconds: float = 30

    @field_validator("supabase_secret_key", mode="before")
    @classmethod
    def validate_supabase_secret_key(cls, value: object) -> object:
        if value in {None, ""}:
            return None
        if not isinstance(value, str) or not value.startswith("sb_secret_"):
            raise ValueError("SUPABASE_SECRET_KEY must start with sb_secret_")
        return value

    @property
    def ai_enabled(self) -> bool:
        return self.ai_mode == "auto" and bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "분산에너지 법령 RAG"
    environment: Literal["development", "test", "production"] = "development"
    law_open_api_oc: str | None = None
    law_open_api_base_url: str = "https://www.law.go.kr/DRF"
    collector_state_dir: Path = Path(".collector-state")
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_raw_bucket: str = "law-raw"
    openai_api_key: str | None = None
    ai_mode: Literal["auto", "off"] = "auto"
    openai_answer_model: Literal["gpt-5.6-terra"] = "gpt-5.6-terra"
    openai_embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 512
    rate_limit_secret: str = Field(default="development-only-secret", min_length=16)
    ai_daily_limit: int = 3
    search_daily_limit: int = 30
    web_origin: str = "http://localhost:3000"
    request_timeout_seconds: float = 30

    @property
    def ai_enabled(self) -> bool:
        return self.ai_mode == "auto" and bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

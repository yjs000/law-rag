from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CollectorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    law_open_api_oc: str | None = None
    law_open_api_base_url: str = "https://www.law.go.kr/DRF"
    collector_state_dir: Path = Path(".collector-state")
    collector_request_timeout_seconds: float = 30
    database_url: str | None = None
    direct_url: str | None = None
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_raw_bucket: str = "law-raw"

    @model_validator(mode="after")
    def validate_supabase_configuration(self):
        values = (
            self.direct_url or self.database_url,
            self.supabase_url,
            self.supabase_secret_key,
        )
        if any(values) and not all(values):
            raise ValueError(
                "Supabase collector에는 DB URL, SUPABASE_URL, SUPABASE_SECRET_KEY가 모두 필요합니다"
            )
        if self.supabase_secret_key and not self.supabase_secret_key.startswith("sb_secret_"):
            raise ValueError("SUPABASE_SECRET_KEY must start with sb_secret_")
        return self

    @property
    def supabase_enabled(self) -> bool:
        return bool(
            (self.direct_url or self.database_url)
            and self.supabase_url
            and self.supabase_secret_key
        )


@lru_cache
def get_settings() -> CollectorSettings:
    return CollectorSettings()

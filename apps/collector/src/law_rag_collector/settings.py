from functools import lru_cache
from pathlib import Path

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


@lru_cache
def get_settings() -> CollectorSettings:
    return CollectorSettings()

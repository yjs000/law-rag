from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str | None = None
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_route_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nvidia_generate_model: str = "nvidia/nemotron-3-ultra-550b-a55b"


@lru_cache
def get_settings() -> Settings:
    return Settings()

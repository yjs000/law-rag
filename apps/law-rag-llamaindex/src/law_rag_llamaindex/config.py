"""v2 LlamaIndex 검색 구성 값을 제공한다."""

from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수에서 읽는 v2 색인 및 임베딩 구성이다."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str | None = None
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_embedding_model: str = "nvidia/nemotron-3-embed-1b"
    embed_dim: int = 2048
    vector_table_name: str = "law_rag_llamaindex"
    hnsw_kwargs: dict[str, Any] | None = None


@lru_cache
def get_settings() -> Settings:
    """프로세스 동안 재사용할 v2 구성 값을 반환한다."""
    return Settings()

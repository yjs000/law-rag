import law_rag_llamaindex.config as config
from law_rag_llamaindex.config import Settings, get_settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url is None
    assert settings.nvidia_api_key is None
    assert settings.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.nvidia_embedding_model == "nvidia/nemotron-3-embed-1b"
    assert settings.embed_dim == 2048
    assert settings.vector_table_name == "law_rag_llamaindex"
    assert settings.hnsw_kwargs is None


def test_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/d"
    assert settings.nvidia_api_key == "test-key"


def test_direct_url_is_database_url_fallback(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DIRECT_URL", "postgresql://u:p@h:5432/d")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://u:p@h:5432/d"


def test_get_settings_loads_repository_env_file_outside_repository_cwd(monkeypatch, tmp_path):
    repository_root = tmp_path / "repository"
    unrelated_cwd = tmp_path / "elsewhere"
    repository_root.mkdir()
    unrelated_cwd.mkdir()
    (repository_root / ".env.local").write_text(
        "DIRECT_URL=postgresql://u:p@h:5432/from-file\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DIRECT_URL", raising=False)
    monkeypatch.setattr(config, "_REPOSITORY_ROOT", repository_root, raising=False)
    monkeypatch.chdir(unrelated_cwd)
    get_settings.cache_clear()

    try:
        settings = get_settings()
        assert settings.database_url == "postgresql://u:p@h:5432/from-file"
    finally:
        get_settings.cache_clear()


def test_get_settings_is_cached():
    assert get_settings() is get_settings()

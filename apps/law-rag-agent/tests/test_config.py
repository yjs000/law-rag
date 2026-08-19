from law_rag_agent.config import Settings, get_settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url is None
    assert settings.nvidia_api_key is None
    assert settings.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.nvidia_route_model == "nvidia/nemotron-3-ultra-550b-a55b"
    assert settings.nvidia_generate_model == "nvidia/nemotron-3-ultra-550b-a55b"


def test_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/d"
    assert settings.nvidia_api_key == "test-key"


def test_get_settings_is_cached():
    assert get_settings() is get_settings()

import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_env_local_is_loaded_and_overrides_env(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("AI_MODE=off\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text(
        "AI_MODE=auto\nOPENAI_API_KEY=local-key\n"
        "SUPABASE_SECRET_KEY=sb_secret_local\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)

    settings = Settings()

    assert settings.ai_mode == "auto"
    assert settings.openai_api_key == "local-key"
    assert settings.supabase_secret_key == "sb_secret_local"


def test_process_environment_overrides_env_local(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env.local").write_text("AI_MODE=auto\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_MODE", "off")

    settings = Settings()

    assert settings.ai_mode == "off"


def test_legacy_supabase_service_role_key_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "legacy-jwt-value")

    with pytest.raises(ValidationError, match="must start with sb_secret_"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({}, "DATABASE_URL, SUPABASE_URL, SUPABASE_SECRET_KEY"),
        (
            {
                "database_url": "postgresql://example",
                "supabase_url": "https://project.supabase.co",
                "supabase_secret_key": "sb_secret_example",
            },
            "non-default RATE_LIMIT_SECRET",
        ),
    ],
)
def test_production_rejects_missing_or_development_only_settings(
    overrides: dict[str, str], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(environment="production", _env_file=None, **overrides)


def test_production_accepts_explicit_dependencies_and_rate_limit_secret() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql://example",
        supabase_url="https://project.supabase.co",
        supabase_secret_key="sb_secret_example",
        rate_limit_secret="replace-with-managed-secret",
        _env_file=None,
    )

    assert settings.environment == "production"

import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_env_local_is_loaded_and_overrides_env(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("AI_MODE=off\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text(
        "AI_MODE=auto\nNVIDIA_API_KEY=local-key\n"
        "SUPABASE_SECRET_KEY=sb_secret_local\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)

    settings = Settings()

    assert settings.ai_mode == "auto"
    assert settings.nvidia_api_key == "local-key"
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


def test_nvidia_key_enables_generation_and_embedding() -> None:
    settings = Settings(
        nvidia_api_key="nvapi-test",
        _env_file=None,
    )

    assert settings.ai_enabled
    assert settings.embedding_enabled
    assert settings.nvidia_embedding_model == "nvidia/nemotron-3-embed-1b"
    assert settings.embedding_dimensions == 512
    assert settings.answer_max_output_tokens == 4096


def test_missing_nvidia_key_keeps_ai_disabled() -> None:
    settings = Settings(
        nvidia_api_key=None,
        _env_file=None,
    )

    assert not settings.ai_enabled
    assert not settings.embedding_enabled


def test_web_origins_splits_comma_separated_list() -> None:
    settings = Settings(
        web_origin="https://prod.example.com, https://preview-abc123.vercel.app",
        _env_file=None,
    )

    assert settings.web_origins == [
        "https://prod.example.com",
        "https://preview-abc123.vercel.app",
    ]


def test_web_origins_single_value_is_still_a_list() -> None:
    settings = Settings(web_origin="https://prod.example.com", _env_file=None)

    assert settings.web_origins == ["https://prod.example.com"]


def test_request_budget_timeout_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.question_request_timeout_seconds == 52
    assert settings.response_reserve_seconds == 3
    assert settings.route_classifier_timeout_seconds == 8
    assert settings.embedding_timeout_seconds == 5
    assert settings.retrieval_timeout_seconds == 8
    assert settings.answer_timeout_seconds == 40


def test_request_timeout_seconds_separate_from_question_request_timeout() -> None:
    settings = Settings(_env_file=None)

    assert settings.request_timeout_seconds == 30
    assert settings.question_request_timeout_seconds == 52


def test_response_reserve_must_be_smaller_than_question_timeout() -> None:
    with pytest.raises(ValidationError, match="response reserve must be smaller"):
        Settings(
            question_request_timeout_seconds=1,
            response_reserve_seconds=1,
            _env_file=None,
        )


def test_answer_timeout_must_fit_before_response_reserve() -> None:
    with pytest.raises(ValidationError, match="answer timeout must fit before"):
        Settings(
            question_request_timeout_seconds=52,
            response_reserve_seconds=3,
            answer_timeout_seconds=50,
            _env_file=None,
        )

from app import main
from app.settings import Settings


def test_runtime_account_quota_gate_is_toggleable_and_off_by_default() -> None:
    settings = Settings(_env_file=None)

    assert hasattr(main, "_check_quota")
    assert settings.account_quota_enabled is False
    assert settings.authenticated_ai_daily_limit == 10
    assert settings.authenticated_search_daily_limit == 100


def test_runtime_generation_is_nvidia_only() -> None:
    settings = Settings(_env_file=None)

    assert not hasattr(main, "OpenAIAnswerer")
    assert not hasattr(settings, "answer_provider")
    assert not hasattr(settings, "openai_api_key")
    assert not hasattr(settings, "openai_answer_model")

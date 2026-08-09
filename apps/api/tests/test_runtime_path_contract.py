from app import main
from app.settings import Settings


def test_runtime_has_no_account_quota_gate() -> None:
    settings = Settings(_env_file=None)

    assert not hasattr(main, "_check_quota")
    assert not hasattr(settings, "account_quota_enabled")
    assert not hasattr(settings, "authenticated_ai_daily_limit")
    assert not hasattr(settings, "authenticated_search_daily_limit")


def test_runtime_generation_is_nvidia_only() -> None:
    settings = Settings(_env_file=None)

    assert not hasattr(main, "OpenAIAnswerer")
    assert not hasattr(settings, "answer_provider")
    assert not hasattr(settings, "openai_api_key")
    assert not hasattr(settings, "openai_answer_model")

import pytest
from pydantic import ValidationError

from law_rag_collector.settings import CollectorSettings


def test_env_local_is_loaded_and_overrides_env(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("LAW_OPEN_API_OC", raising=False)
    (tmp_path / ".env").write_text("LAW_OPEN_API_OC=from-env\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("LAW_OPEN_API_OC=from-env-local\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    settings = CollectorSettings()

    assert settings.law_open_api_oc == "from-env-local"


def test_process_environment_overrides_env_local(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env.local").write_text("LAW_OPEN_API_OC=from-env-local\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LAW_OPEN_API_OC", "from-process")

    settings = CollectorSettings()

    assert settings.law_open_api_oc == "from-process"


def test_partial_supabase_configuration_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.test/postgres")
    monkeypatch.delenv("DIRECT_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match="모두 필요"):
        CollectorSettings(_env_file=None)


def test_complete_supabase_configuration_enables_repository(monkeypatch) -> None:
    monkeypatch.setenv("DIRECT_URL", "postgresql://example.test/postgres")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")

    settings = CollectorSettings(_env_file=None)

    assert settings.supabase_enabled is True

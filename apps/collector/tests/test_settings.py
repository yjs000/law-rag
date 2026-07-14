from law_rag_collector.settings import CollectorSettings


def test_env_local_is_loaded_and_overrides_env(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("LAW_OPEN_API_OC", raising=False)
    (tmp_path / ".env").write_text("LAW_OPEN_API_OC=from-env\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text(
        "LAW_OPEN_API_OC=from-env-local\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    settings = CollectorSettings()

    assert settings.law_open_api_oc == "from-env-local"


def test_process_environment_overrides_env_local(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env.local").write_text(
        "LAW_OPEN_API_OC=from-env-local\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LAW_OPEN_API_OC", "from-process")

    settings = CollectorSettings()

    assert settings.law_open_api_oc == "from-process"

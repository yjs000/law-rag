from unittest.mock import MagicMock

import pytest


def test_v2_resources_factory_uses_active_generation_provider_not_legacy_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from law_rag_llamaindex.active_index import ActiveGenerationIndexProvider

    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "database_url", "postgresql://factory.example/law")
    monkeypatch.setattr(main_module, "llamaindex_vector_store", None)
    monkeypatch.setattr(main_module, "llamaindex_embedder", None)
    monkeypatch.setattr(main_module, "llamaindex_repository", None)
    monkeypatch.setattr(
        main_module, "llamaindex_settings", type("Settings", (), {"nvidia_api_key": "key"})()
    )
    monkeypatch.setattr(main_module, "build_llamaindex_embedder", lambda settings: object())
    monkeypatch.setattr(
        main_module,
        "LlamaIndexLegalRepository",
        lambda delegate, vector_store, repository_embedder: object(),
    )
    main_module._build_llamaindex_resources.cache_clear()

    resources = main_module._build_llamaindex_resources("postgresql://factory.example/law", "key")

    assert resources is not None
    assert isinstance(resources[0], ActiveGenerationIndexProvider)
    main_module._build_llamaindex_resources.cache_clear()


def test_v2_catalog_engine_disables_asyncpg_statement_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.bootstrap as bootstrap

    captured: dict[str, object] = {}

    class AsyncEngine:
        async def dispose(self) -> None:
            return None

    class SyncEngine:
        def dispose(self) -> None:
            return None

    def create_async_engine(url: str, **kwargs: object) -> AsyncEngine:
        captured["url"] = url
        captured.update(kwargs)
        return AsyncEngine()

    monkeypatch.setattr(bootstrap, "create_async_engine", create_async_engine)
    monkeypatch.setattr(bootstrap, "create_engine", lambda *args, **kwargs: SyncEngine())

    resources = bootstrap.build_llamaindex_resources(
        "postgresql://pooler.example/law",
        "key",
        llamaindex_settings=object(),
        delegate=object(),
        embedder_factory=lambda settings: object(),
        repository_factory=lambda delegate, provider, embedder: object(),
    )

    assert resources is not None
    assert captured["connect_args"] == {"statement_cache_size": 0}


def test_v2_repository_does_not_request_legacy_query_embedding() -> None:
    import app.main as main_module
    from app.adapters.llamaindex_repository import LlamaIndexLegalRepository

    assert main_module._requires_legacy_query_embedding(
        LlamaIndexLegalRepository(MagicMock(), object(), object())
    ) is False


def test_v1_retrieval_uses_the_injected_query_embedding_capability() -> None:
    """Prevent a v1 retrieval path from recognizing framework adapter classes."""

    from app.application.v1.retrieval import requires_legacy_query_embedding

    class ActiveIndexCapability:
        def requires_application_query_embedding(self) -> bool:
            return False

    assert requires_legacy_query_embedding(ActiveIndexCapability()) is False

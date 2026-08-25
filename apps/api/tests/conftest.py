import os
from datetime import date

import pytest

# Local .env.local may contain real service credentials. Tests must never inherit
# them merely because pytest was started from a developer checkout.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = ""
os.environ["DIRECT_URL"] = ""
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SECRET_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["NVIDIA_API_KEY"] = ""
os.environ["AI_MODE"] = "auto"
os.environ["ANSWER_PROVIDER"] = "openai"
os.environ["COLLECTOR_STATE_DIR"] = ".data/nonexistent-api-test-state"


@pytest.fixture
def ready_corpus_temporal_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let non-temporal API tests exercise their own downstream concern."""

    import app.main as main_module
    from app.domain.schemas import CorpusTemporalState

    async def ready_state(repository) -> CorpusTemporalState:
        return CorpusTemporalState(
            ready=True,
            supported_as_of_from=date(1900, 1, 1),
            supported_as_of_through=date(2099, 12, 31),
            corpus_snapshot_id=f"corpus-sha256:{'a' * 64}",
            eligible_provision_count=1,
        )

    monkeypatch.setattr(main_module, "_load_corpus_temporal_state", ready_state)

@pytest.fixture
def search_only_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise legacy search-only contracts only when the feature is explicitly enabled."""
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "search_only_enabled", True)


@pytest.fixture
def legal_search_router(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep normal AI-flow tests on the post-routing legal-search path."""
    import app.main as main_module
    from app.domain.routing import RouteJudgment

    class LegalSearchRouter:
        async def route(self, question: str) -> RouteJudgment:
            return RouteJudgment(
                route="legal_search",
                confidence=1.0,
                reason="test legal-search judgment",
                missing_fields=(),
            )

    monkeypatch.setattr(main_module, "_question_router", lambda: LegalSearchRouter())

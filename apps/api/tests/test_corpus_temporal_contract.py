from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.corpus_temporal_contract import (
    UnsupportedCorpusDateError,
    canonical_corpus_snapshot_id,
    require_supported_corpus_date,
)
from app.domain.schemas import CorpusTemporalState

SUPPORTED_FROM = date(2007, 1, 1)
KOREA_TODAY = date(2026, 8, 4)
SNAPSHOT_ID = canonical_corpus_snapshot_id(
    parser_contract_version="3",
    retrieval_unit="provision",
    content_populations=[
        {
            "eligible_provision_count": 3066,
            "fingerprint_sha256": "a" * 64,
        }
    ],
)


def _ready_state() -> CorpusTemporalState:
    return CorpusTemporalState(
        ready=True,
        supported_as_of_from=SUPPORTED_FROM,
        supported_as_of_through=KOREA_TODAY,
        corpus_snapshot_id=SNAPSHOT_ID,
        eligible_provision_count=3066,
    )


class _BoundaryOnlyRepository:
    def __init__(self, state: CorpusTemporalState | None = None) -> None:
        self.state = state or _ready_state()
        self.temporal_calls: list[date] = []

    async def corpus_temporal_state(self, supported_through: date) -> CorpusTemporalState:
        self.temporal_calls.append(supported_through)
        return self.state

    def __getattr__(self, name: str):
        raise AssertionError(f"boundary validation must run before dependency access: {name}")


@pytest.mark.parametrize("supported_date", [SUPPORTED_FROM, KOREA_TODAY])
def test_dynamic_corpus_temporal_boundaries_are_inclusive(supported_date: date) -> None:
    assert require_supported_corpus_date(supported_date, _ready_state()) == supported_date


@pytest.mark.parametrize("unsupported_date", [date(2006, 12, 31), date(2026, 8, 5)])
def test_dynamic_corpus_rejects_dates_outside_the_current_window(
    unsupported_date: date,
) -> None:
    with pytest.raises(UnsupportedCorpusDateError) as exc_info:
        require_supported_corpus_date(unsupported_date, _ready_state())

    error = exc_info.value
    assert error.requested_date == unsupported_date
    assert error.supported_from == SUPPORTED_FROM
    assert error.supported_through == KOREA_TODAY
    assert error.snapshot_id == SNAPSHOT_ID


def test_content_snapshot_identity_does_not_include_the_calendar_date() -> None:
    first = canonical_corpus_snapshot_id(
        parser_contract_version="3",
        retrieval_unit="provision",
        content_populations=[
            {
                "as_of_date": "2026-08-03",
                "eligible_provision_count": 3066,
                "fingerprint_sha256": "a" * 64,
            }
        ],
    )
    second = canonical_corpus_snapshot_id(
        parser_contract_version="3",
        retrieval_unit="provision",
        content_populations=[
            {
                "as_of_date": "2026-08-04",
                "eligible_provision_count": 3066,
                "fingerprint_sha256": "a" * 64,
            }
        ],
    )

    assert first == second


@pytest.mark.parametrize(
    "population",
    [
        {"eligible_provision_count": 0, "fingerprint_sha256": "a" * 64},
        {"eligible_provision_count": 1, "fingerprint_sha256": "A" * 64},
    ],
)
def test_content_snapshot_identity_rejects_invalid_population_contracts(
    population: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        canonical_corpus_snapshot_id(
            parser_contract_version="3",
            retrieval_unit="provision",
            content_populations=[population],
        )


@pytest.mark.parametrize("unsupported_date", ["2006-12-31", "2026-08-05"])
@pytest.mark.parametrize("route", ["search", "question", "provision"])
def test_public_retrieval_routes_reject_dynamic_out_of_range_dates_before_work(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    unsupported_date: str,
) -> None:
    repository = _BoundaryOnlyRepository()
    monkeypatch.setattr(main_module, "repository", repository)
    monkeypatch.setattr(main_module, "_current_korea_date", lambda: KOREA_TODAY)
    monkeypatch.setattr(
        main_module,
        "_embedder",
        lambda: (_ for _ in ()).throw(
            AssertionError("date validation must run before embedding provider creation")
        ),
    )
    client = TestClient(main_module.app, raise_server_exceptions=False)

    if route == "search":
        response = client.post(
            "/v1/search",
            json={"query": "태양광 사업 준비", "as_of_date": unsupported_date},
        )
    elif route == "question":
        response = client.post(
            "/v1/questions",
            json={
                "question": "태양광 사업을 하려면 뭘 준비해야 하나요?",
                "as_of_date": unsupported_date,
                "answer_mode": "terra",
            },
        )
    else:
        response = client.get(
            f"/v1/provisions/{uuid4()}",
            params={"as_of_date": unsupported_date},
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "unsupported_corpus_date",
            "message": "현재 corpus는 검증된 기준일 범위 안에서만 검색할 수 있습니다.",
            "requested_as_of_date": unsupported_date,
            "supported_from": SUPPORTED_FROM.isoformat(),
            "supported_through": KOREA_TODAY.isoformat(),
            "corpus_snapshot_id": SNAPSHOT_ID,
        }
    }
    assert repository.temporal_calls == [KOREA_TODAY]


@pytest.mark.parametrize("route", ["search", "question", "provision"])
def test_public_retrieval_routes_fail_closed_when_temporal_corpus_is_unready(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    search_only_enabled: None,
) -> None:
    repository = _BoundaryOnlyRepository(
        CorpusTemporalState(
            ready=False,
            reason="no_currently_effective_corpus",
            supported_as_of_through=KOREA_TODAY,
        )
    )
    monkeypatch.setattr(main_module, "repository", repository)
    monkeypatch.setattr(main_module, "_current_korea_date", lambda: KOREA_TODAY)
    monkeypatch.setattr(
        main_module,
        "_embedder",
        lambda: (_ for _ in ()).throw(
            AssertionError("corpus readiness must be checked before embedding provider creation")
        ),
    )
    client = TestClient(main_module.app, raise_server_exceptions=False)

    if route == "search":
        response = client.post(
            "/v1/search",
            json={"query": "태양광 사업 준비", "as_of_date": KOREA_TODAY.isoformat()},
        )
    elif route == "question":
        response = client.post(
            "/v1/questions",
            json={
                "question": "태양광 사업을 하려면 뭘 준비해야 하나요?",
                "as_of_date": KOREA_TODAY.isoformat(),
                "answer_mode": "search_only",
            },
        )
    else:
        response = client.get(
            f"/v1/provisions/{uuid4()}",
            params={"as_of_date": KOREA_TODAY.isoformat()},
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "corpus_unready"


@pytest.mark.parametrize("supported_date", [SUPPORTED_FROM, KOREA_TODAY])
def test_search_accepts_both_dynamic_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    supported_date: date,
) -> None:
    class RecordingRepository(_BoundaryOnlyRepository):
        def __init__(self) -> None:
            super().__init__()
            self.requested_dates: list[date] = []

        async def consume_quota(self, *args, **kwargs) -> bool:
            return True

        async def search(self, query, as_of_date, limit, query_embedding):
            self.requested_dates.append(as_of_date)
            return []

    repository = RecordingRepository()
    monkeypatch.setattr(main_module, "repository", repository)
    monkeypatch.setattr(main_module, "_current_korea_date", lambda: KOREA_TODAY)

    response = TestClient(main_module.app).post(
        "/v1/search",
        json={"query": "태양광 사업 준비", "as_of_date": supported_date.isoformat()},
    )

    assert response.status_code == 200
    assert response.json() == []
    assert repository.requested_dates == [supported_date]


def test_corpus_status_exposes_dynamic_supported_date_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StatusRepository:
        async def corpus_items(self):
            return []

        async def corpus_temporal_state(self, supported_through: date):
            assert supported_through == KOREA_TODAY
            return _ready_state()

        async def last_sync(self):
            return None

    monkeypatch.setattr(main_module, "repository", StatusRepository())
    monkeypatch.setattr(main_module, "_current_korea_date", lambda: KOREA_TODAY)

    response = TestClient(main_module.app).get("/v1/corpus/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["corpus_snapshot_id"] == SNAPSHOT_ID
    assert payload["supported_as_of_from"] == SUPPORTED_FROM.isoformat()
    assert payload["supported_as_of_through"] == KOREA_TODAY.isoformat()
    assert payload["corpus_search_ready"] is True


def test_corpus_status_uses_one_overview_call_for_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OverviewRepository(PostgresLegalRepository):
        def __init__(self) -> None:
            self.overview_calls = 0

        async def corpus_overview(self, supported_through: date):
            self.overview_calls += 1
            assert supported_through == KOREA_TODAY
            return [], _ready_state(), None

        async def corpus_items(self):
            raise AssertionError("status must not open a separate corpus-items connection")

        async def corpus_temporal_state(self, supported_through: date):
            raise AssertionError("status must not open a separate temporal-state connection")

        async def last_sync(self):
            raise AssertionError("status must not open a separate last-sync connection")

    repository = OverviewRepository()
    monkeypatch.setattr(main_module, "repository", repository)
    monkeypatch.setattr(main_module, "_current_korea_date", lambda: KOREA_TODAY)

    response = TestClient(main_module.app).get("/v1/corpus/status")

    assert response.status_code == 200
    assert repository.overview_calls == 1


def test_corpus_status_exposes_null_identity_when_current_population_is_unready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StatusRepository:
        async def corpus_items(self):
            return []

        async def corpus_temporal_state(self, supported_through: date):
            return CorpusTemporalState(
                ready=False,
                reason="no_currently_effective_corpus",
                supported_as_of_through=supported_through,
            )

        async def last_sync(self):
            return None

    monkeypatch.setattr(main_module, "repository", StatusRepository())
    monkeypatch.setattr(main_module, "_current_korea_date", lambda: KOREA_TODAY)

    response = TestClient(main_module.app).get("/v1/corpus/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["corpus_search_ready"] is False
    assert payload["corpus_search_unavailable_reason"] == "no_currently_effective_corpus"
    assert payload["supported_as_of_from"] is None
    assert payload["supported_as_of_through"] == KOREA_TODAY.isoformat()
    assert payload["corpus_snapshot_id"] is None

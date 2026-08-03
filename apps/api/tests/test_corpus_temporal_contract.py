from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.corpus_temporal_contract import (
    CURRENT_CORPUS_SNAPSHOT_ID,
    CURRENT_CORPUS_SUPPORTED_FROM,
    CURRENT_CORPUS_SUPPORTED_THROUGH,
    UnsupportedCorpusDateError,
    require_supported_corpus_date,
)
from app.domain.schemas import CorpusSearchStatus


class _ForbiddenBoundaryDependency:
    def __getattr__(self, name: str):
        raise AssertionError(f"boundary validation must run before dependency access: {name}")


@pytest.mark.parametrize(
    "supported_date",
    [CURRENT_CORPUS_SUPPORTED_FROM, CURRENT_CORPUS_SUPPORTED_THROUGH],
)
def test_current_corpus_temporal_boundaries_are_inclusive(supported_date: date) -> None:
    assert require_supported_corpus_date(supported_date) == supported_date


@pytest.mark.parametrize("unsupported_date", [date(2026, 6, 2), date(2026, 8, 4)])
def test_current_corpus_rejects_dates_outside_the_fixed_snapshot(
    unsupported_date: date,
) -> None:
    with pytest.raises(UnsupportedCorpusDateError) as exc_info:
        require_supported_corpus_date(unsupported_date)

    error = exc_info.value
    assert error.requested_date == unsupported_date
    assert error.supported_from == date(2026, 6, 3)
    assert error.supported_through == date(2026, 8, 3)
    assert error.snapshot_id == "mvp-current-corpus-2026-08-03"


@pytest.mark.parametrize("unsupported_date", ["2026-06-02", "2026-08-04"])
@pytest.mark.parametrize("route", ["search", "question", "provision"])
def test_public_retrieval_routes_reject_unsupported_date_before_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    unsupported_date: str,
) -> None:
    forbidden = _ForbiddenBoundaryDependency()
    monkeypatch.setattr(main_module, "repository", forbidden)
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
            "supported_from": CURRENT_CORPUS_SUPPORTED_FROM.isoformat(),
            "supported_through": CURRENT_CORPUS_SUPPORTED_THROUGH.isoformat(),
            "corpus_snapshot_id": CURRENT_CORPUS_SNAPSHOT_ID,
        }
    }


@pytest.mark.parametrize(
    "supported_date",
    [CURRENT_CORPUS_SUPPORTED_FROM, CURRENT_CORPUS_SUPPORTED_THROUGH],
)
def test_search_accepts_both_fixed_snapshot_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    supported_date: date,
) -> None:
    class RecordingRepository:
        requested_dates: list[date] = []

        async def consume_quota(self, *args, **kwargs) -> bool:
            return True

        async def search(self, query, as_of_date, limit, query_embedding):
            self.requested_dates.append(as_of_date)
            return []

    repository = RecordingRepository()
    monkeypatch.setattr(main_module, "repository", repository)

    response = TestClient(main_module.app).post(
        "/v1/search",
        json={"query": "태양광 사업 준비", "as_of_date": supported_date.isoformat()},
    )

    assert response.status_code == 200
    assert response.json() == []
    assert repository.requested_dates == [supported_date]


def test_corpus_status_exposes_the_fixed_supported_date_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StatusRepository:
        async def corpus_items(self):
            return []

        async def corpus_search_status(self):
            return CorpusSearchStatus(ready=True)

        async def last_sync(self):
            return None

    monkeypatch.setattr(main_module, "repository", StatusRepository())

    response = TestClient(main_module.app).get("/v1/corpus/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["corpus_snapshot_id"] == CURRENT_CORPUS_SNAPSHOT_ID
    assert payload["supported_as_of_from"] == CURRENT_CORPUS_SUPPORTED_FROM.isoformat()
    assert payload["supported_as_of_through"] == CURRENT_CORPUS_SUPPORTED_THROUGH.isoformat()

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.adapters.postgres_identity import ConsentRequiredError, PostgresIdentityRepository
from app.adapters.supabase_auth import SupabaseIdentity
from app.domain.schemas import ProjectStage, QuestionRequest, QuestionResponse

AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


class FakeResult:
    def __init__(self, row=None) -> None:
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class FakeConnection:
    def __init__(self, existing: dict) -> None:
        self.existing = existing
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, statement, params):
        sql = str(statement)
        self.calls.append((sql, params))
        return FakeResult(self.existing if "SELECT id,email" in sql else None)


class TransactionContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_):
        return None


class FakeEngine:
    def __init__(self, existing: dict) -> None:
        self.connection = FakeConnection(existing)

    def begin(self):
        return TransactionContext(self.connection)


def _existing(*, consented: bool) -> dict:
    return {
        "id": USER_ID,
        "email": "old@example.com",
        "display_name": "old",
        "created_at": datetime(2026, 7, 15, tzinfo=UTC),
        "consented": consented,
    }


def _identity() -> SupabaseIdentity:
    return SupabaseIdentity(
        auth_user_id=AUTH_ID,
        email="new@example.com",
        display_name="new",
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_existing_profile_without_consent_is_rejected() -> None:
    engine = FakeEngine(_existing(consented=False))
    repository = PostgresIdentityRepository(engine)

    with pytest.raises(ConsentRequiredError):
        await repository.ensure_profile(_identity())

    assert not any("INSERT INTO user_consents" in sql for sql, _ in engine.connection.calls)


@pytest.mark.asyncio
async def test_existing_profile_can_record_missing_current_consent_once() -> None:
    engine = FakeEngine(_existing(consented=False))
    repository = PostgresIdentityRepository(engine)

    user = await repository.ensure_profile(_identity(), "beta-2026-07-15", "beta-2026-07-15")

    assert user.id == USER_ID
    consent_calls = [
        params for sql, params in engine.connection.calls if "INSERT INTO user_consents" in sql
    ]
    assert consent_calls == [
        {
            "id": USER_ID,
            "terms": "beta-2026-07-15",
            "privacy": "beta-2026-07-15",
        }
    ]


@pytest.mark.asyncio
async def test_existing_consented_profile_does_not_require_headers_again() -> None:
    engine = FakeEngine(_existing(consented=True))
    repository = PostgresIdentityRepository(engine)

    user = await repository.ensure_profile(_identity())

    assert user.email == "new@example.com"
    assert not any("INSERT INTO user_consents" in sql for sql, _ in engine.connection.calls)


@pytest.mark.asyncio
async def test_question_diagnostics_are_persisted_as_json() -> None:
    engine = FakeEngine({})
    repository = PostgresIdentityRepository(engine)
    request = QuestionRequest(
        question="전기사업 허가 기준은?",
        as_of_date="2026-07-18",
        project_stage=ProjectStage.PLANNING,
    )
    response = QuestionResponse(
        request_id="22222222-2222-4222-8222-222222222222",
        mode="search_only",
        summary="검색 결과가 없습니다.",
        scope="테스트",
        result_status="no_results",
        sections=[],
        checklist=[],
        citations=[],
        limitations=[],
    )

    await repository.save_question(
        USER_ID,
        request,
        response,
        diagnostics={"retrieval": {"candidate_count": 0}},
    )

    params = next(
        params for sql, params in engine.connection.calls if "INSERT INTO question_history" in sql
    )
    assert json.loads(params["diagnostics"])["retrieval"]["candidate_count"] == 0

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.memory_clarification_case import MemoryClarificationCaseRepository
from app.adapters.postgres_clarification_case import PostgresClarificationCaseRepository
from app.domain.clarification import ClarificationCase, RequiredFact
from app.ports.clarification_case import ClarificationCaseConflict, ClarificationCaseNotFound


def _case():
    return ClarificationCase(
        required_facts=(RequiredFact("capacity", "용량", "기준", True, "사업", 1),)
    )


@pytest.mark.asyncio
async def test_memory_case_requires_owner_and_expected_version():
    now = datetime(2026, 9, 3, tzinfo=UTC)
    repo = MemoryClarificationCaseRepository(now=lambda: now)
    stored = await repo.create(
        owner_scope="owner", case=_case(), expires_at=now + timedelta(days=1)
    )
    with pytest.raises(ClarificationCaseNotFound):
        await repo.get_owned(stored.case_id, "other")
    updated = await repo.merge(stored.case_id, "owner", expected_version=0, case=_case())
    assert updated.version == 1
    with pytest.raises(ClarificationCaseConflict):
        await repo.merge(stored.case_id, "owner", expected_version=0, case=_case())


@pytest.mark.asyncio
async def test_memory_case_requires_capability_for_anonymous_owner_and_expires_private_state():
    now = datetime(2026, 9, 3, tzinfo=UTC)
    repo = MemoryClarificationCaseRepository(now=lambda: now)
    stored = await repo.create(
        owner_scope="anonymous:session",
        capability_hash="secret-hash",
        case=_case(),
        expires_at=now,
    )

    with pytest.raises(ClarificationCaseNotFound):
        await repo.get_owned(stored.case_id, "anonymous:session", capability_hash="wrong")

    assert await repo.expire(now) == (stored.case_id,)
    with pytest.raises(ClarificationCaseNotFound):
        await repo.get_owned(stored.case_id, "anonymous:session", capability_hash="secret-hash")


@pytest.mark.asyncio
async def test_postgres_merge_uses_owner_capability_and_expected_version_predicate():
    case_id = __import__("uuid").uuid4()

    class Result:
        def mappings(self):
            return self

        def one_or_none(self):
            return None

    class Connection:
        def __init__(self):
            self.calls = []

        async def execute(self, statement, parameters):
            self.calls.append((str(statement), parameters))
            return Result()

    class Transaction:
        def __init__(self, connection):
            self.connection = connection

        async def __aenter__(self):
            return self.connection

        async def __aexit__(self, *_):
            return False

    class Engine:
        def __init__(self):
            self.connection = Connection()

        def begin(self):
            return Transaction(self.connection)

    engine = Engine()
    repository = PostgresClarificationCaseRepository(engine)  # type: ignore[arg-type]
    with pytest.raises(ClarificationCaseConflict):
        await repository.merge(
            case_id,
            "anonymous:session",
            expected_version=3,
            case=_case(),
            capability_hash="secret-hash",
        )

    update_sql, parameters = engine.connection.calls[-1]
    assert "owner_scope=:owner_scope" in update_sql
    assert "version=:expected_version" in update_sql
    assert "capability_hash=:capability_hash" in update_sql
    assert parameters["expected_version"] == 3

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.application.v2.phase_service as phase_service
from app.domain.question_execution import ExecutionStatus


class _Executions:
    async def expire(self, _now: datetime) -> None:
        return None

    async def get_owned(self, *_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(status=ExecutionStatus.PREPARED)


class _CompletedCoordinator:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    async def run(self, *_args: object, **_kwargs: object) -> tuple[object, ...]:
        return ()


@pytest.mark.asyncio
async def test_completed_phase_reports_timeout_releasing_capacity_lease_without_breaking_result(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    release_attempted = asyncio.Event()
    secret = "postgresql+asyncpg://secret-user:secret-password@database.example/law_rag"

    class _TimeoutLease:
        async def release(self) -> None:
            release_attempted.set()
            raise TimeoutError(secret)

    async def admit_phase(*_args: object) -> _TimeoutLease:
        return _TimeoutLease()

    now = datetime(2026, 9, 4, tzinfo=UTC)
    dependencies = SimpleNamespace(
        executions=_Executions(),
        now=lambda: now,
        phase_timeout=timedelta(seconds=10),
        admit_phase=admit_phase,
        run_core=lambda *_args: None,
        run_finalize=lambda *_args: None,
    )
    service = phase_service.V2QuestionExecutionService(lambda: dependencies)
    monkeypatch.setattr(phase_service, "QuestionPhaseCoordinator", _CompletedCoordinator)
    request = SimpleNamespace(
        execution_id=uuid4(), owner_scope="anonymous:test", capability_hash=None, user=None
    )

    with caplog.at_level(logging.ERROR, logger="law_rag.phase_lease_release"):
        phase_run = await service._begin_phase(request, "core")
        assert await phase_run.task == ()
        await release_attempted.wait()
        await asyncio.sleep(0)

    release_records = [
        record for record in caplog.records if record.name == "law_rag.phase_lease_release"
    ]
    assert len(release_records) == 1
    assert release_records[0].levelno == logging.ERROR
    assert release_records[0].message.startswith("{")
    assert json.loads(release_records[0].message) == {"error_type": "TimeoutError"}
    assert secret not in caplog.text

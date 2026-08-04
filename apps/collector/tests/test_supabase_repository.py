import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date
from uuid import UUID

import httpx
import pytest
import respx
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord
from law_rag_core.domain.identifiers import canonical_provision_id
from law_rag_core.persistence import (
    CORPUS_SEARCH_READY_FLAG_KEY,
    CORPUS_SYNC_RUN_LOCK_KEY,
    EMBEDDING_BACKFILL_LOCK_KEY,
)

from law_rag_collector.client import RawResponse
from law_rag_collector.deletions import DeletionRecord
from law_rag_collector.supabase_repository import (
    SupabaseCurrentCorpusRepository,
    SupabaseRawStorage,
    plan_provision_sync,
    raw_object_path,
    resolve_effective_to,
    version_record_changed,
)


def _document(body: str = "{}") -> LegalDocumentRecord:
    effective_from = date(2020, 2, 1)
    return LegalDocumentRecord(
        source_id="001",
        mst="1000",
        title="전기사업법",
        source_kind=SourceKind.LAW,
        promulgation_number="제1호",
        promulgated_on=date(2020, 1, 1),
        effective_from=effective_from,
        ministry="산업통상자원부",
        source_url="https://www.law.go.kr/법령/전기사업법",
        raw_format="JSON",
        raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
        provisions=[
            ProvisionRecord(
                id=canonical_provision_id(
                    source_kind=SourceKind.LAW,
                    source_id="001",
                    mst="1000",
                    effective_from=effective_from,
                    path="제1조",
                ),
                path="제1조",
                heading="목적",
                content="목적 조문",
            )
        ],
    )


def _provision_row(item: ProvisionRecord) -> dict[str, object]:
    return {
        "id": item.id,
        "path": item.path,
        "parent_path": item.parent_path,
        "heading": item.heading,
        "content": item.content,
        "ordinal": item.ordinal,
    }


def test_provision_sync_plan_separates_embedding_and_hierarchy_changes() -> None:
    original = _document().provisions[0]
    hierarchy_only = ProvisionRecord(
        id=original.id,
        path=original.path,
        heading=original.heading,
        content=original.content,
        parent_path="제0조",
        ordinal=9,
    )

    hierarchy_plan = plan_provision_sync([_provision_row(original)], [hierarchy_only])
    content_plan = plan_provision_sync(
        [_provision_row(original)],
        [
            ProvisionRecord(
                id=original.id,
                path=original.path,
                heading=original.heading,
                content="변경된 본문",
            )
        ],
    )

    assert hierarchy_plan.updated_ids == {original.id}
    assert hierarchy_plan.stale_embedding_ids == set()
    assert hierarchy_plan.stale_derived_ids == {original.id}
    assert content_plan.stale_embedding_ids == {original.id}


def test_provision_sync_plan_rejects_duplicate_incoming_ids() -> None:
    original = _document().provisions[0]

    with pytest.raises(ValueError, match="duplicate IDs"):
        plan_provision_sync(
            [],
            [
                original,
                ProvisionRecord(
                    id=original.id,
                    path="제2조",
                    heading=None,
                    content="다른 본문",
                ),
            ],
        )


def test_effective_boundary_uses_next_start_as_exclusive_end() -> None:
    versions = [
        {"mst": "old", "effective_from": date(2020, 1, 1)},
        {"mst": "future", "effective_from": date(2027, 1, 1)},
    ]

    assert resolve_effective_to(
        versions,
        incoming_mst="current",
        incoming_effective_from=date(2026, 1, 1),
        requested_effective_to=None,
    ) == date(2027, 1, 1)


def test_effective_boundary_rejects_ambiguous_same_day_mst() -> None:
    with pytest.raises(ValueError, match="동일 시행일"):
        resolve_effective_to(
            [{"mst": "other", "effective_from": date(2026, 1, 1)}],
            incoming_mst="incoming",
            incoming_effective_from=date(2026, 1, 1),
            requested_effective_to=None,
        )


def test_version_change_detects_metadata_without_raw_change() -> None:
    before = {field: None for field in (
        "promulgation_number",
        "promulgated_on",
        "effective_from",
        "effective_to",
        "ministry",
        "source_url",
        "raw_format",
        "raw_sha256",
        "raw_storage_path",
        "parser_schema_version",
        "fallback_reason",
        "lifecycle_state",
        "source_record_state",
        "source_deleted_on",
        "has_supplementary_provisions",
    )}
    after = dict(before)
    after["ministry"] = "산업통상자원부"

    assert version_record_changed(before, after)


def test_raw_object_path_is_content_addressed() -> None:
    raw = RawResponse("{}", "JSON", "https://example.test")
    document = _document()

    path = raw_object_path(document, raw)

    assert path.startswith("law/001/1000-2020-02-01-")
    assert document.raw_sha256 in path
    assert path.endswith(".json")


@pytest.mark.asyncio
@respx.mock
async def test_storage_creates_private_bucket_and_uploads_without_overwrite() -> None:
    get_bucket = respx.get("https://project.supabase.co/storage/v1/bucket/law-raw").mock(
        return_value=httpx.Response(
            400,
            json={
                "statusCode": "404",
                "error": "Bucket not found",
                "message": "Bucket not found",
            },
        )
    )
    create_bucket = respx.post("https://project.supabase.co/storage/v1/bucket").mock(
        return_value=httpx.Response(200, json={"name": "law-raw"})
    )
    upload = respx.post(
        "https://project.supabase.co/storage/v1/object/law-raw/law/001/raw.json"
    ).mock(return_value=httpx.Response(200, json={"Key": "law/001/raw.json"}))
    storage = SupabaseRawStorage(
        url="https://project.supabase.co",
        secret_key="sb_secret_test",
        bucket="law-raw",
    )
    raw = RawResponse("{}", "JSON", "https://example.test")

    try:
        stored = await storage.put_immutable("law/001/raw.json", raw)
    finally:
        await storage.close()

    assert stored == "law-raw/law/001/raw.json"
    assert get_bucket.called
    assert json.loads(create_bucket.calls.last.request.content) == {
        "id": "law-raw",
        "name": "law-raw",
        "public": False,
    }
    assert upload.calls.last.request.headers["x-upsert"] == "false"
    assert upload.calls.last.request.headers["apikey"] == "sb_secret_test"
    assert "authorization" not in upload.calls.last.request.headers


@pytest.mark.asyncio
@respx.mock
async def test_existing_immutable_object_is_idempotent() -> None:
    respx.get("https://project.supabase.co/storage/v1/bucket/law-raw").mock(
        return_value=httpx.Response(200, json={"name": "law-raw"})
    )
    respx.post("https://project.supabase.co/storage/v1/object/law-raw/law/001/raw.json").mock(
        return_value=httpx.Response(
            400,
            json={
                "statusCode": "409",
                "error": "Duplicate",
                "message": "The resource already exists",
            },
        )
    )
    storage = SupabaseRawStorage(
        url="https://project.supabase.co",
        secret_key="sb_secret_test",
        bucket="law-raw",
    )

    try:
        stored = await storage.put_immutable(
            "law/001/raw.json", RawResponse("{}", "JSON", "https://example.test")
        )
    finally:
        await storage.close()

    assert stored == "law-raw/law/001/raw.json"


_DOCUMENT_ID = UUID("11111111-1111-4111-8111-111111111111")
_VERSION_ID = UUID("22222222-2222-4222-8222-222222222222")


class _FakeResult:
    def __init__(self, *, scalar: object = None, rows: Sequence[object] = ()) -> None:
        self.scalar = scalar
        self.rows = list(rows)

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows

    def scalar_one(self):
        return self.scalar

    def scalar_one_or_none(self):
        return self.scalar


class _FakeConnection:
    def __init__(
        self,
        *,
        existing_document: Mapping[str, object],
        title_owners: Sequence[Mapping[str, object]],
        existing_versions: Sequence[Mapping[str, object]],
        existing_provisions: Sequence[Mapping[str, object]],
        persisted_provisions: Sequence[Mapping[str, object]],
        collisions: Sequence[Mapping[str, object]] = (),
        closed_versions: Sequence[object] = (),
    ) -> None:
        self.existing_document = existing_document
        self.title_owners = title_owners
        self.existing_versions = existing_versions
        self.existing_provisions = existing_provisions
        self.persisted_provisions = persisted_provisions
        self.collisions = collisions
        self.closed_versions = closed_versions
        self.calls: list[tuple[str, object]] = []
        self._provision_selects = 0

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params))
        if "schema.corpus_search_ready_v1" in sql:
            return _FakeResult(scalar=True)
        if "pg_advisory_xact_lock" in sql:
            return _FakeResult(scalar=None)
        if "SELECT id,exact_title FROM legal_documents" in sql:
            return _FakeResult(rows=[self.existing_document])
        if "SELECT id,source_kind,source_id FROM legal_documents" in sql:
            return _FakeResult(rows=self.title_owners)
        if "INSERT INTO legal_documents" in sql:
            return _FakeResult(scalar=_DOCUMENT_ID)
        if "SELECT id,mst,promulgation_number" in sql:
            return _FakeResult(rows=self.existing_versions)
        if "SELECT id,mst,effective_from,effective_to" in sql:
            return _FakeResult(rows=self.existing_versions)
        if "UPDATE document_versions SET effective_to" in sql:
            return _FakeResult(rows=self.closed_versions)
        if "INSERT INTO document_versions" in sql:
            return _FakeResult(scalar=_VERSION_ID)
        if "SELECT id,version_id FROM provisions" in sql:
            return _FakeResult(rows=self.collisions)
        if "SELECT id,path,parent_path,heading,content,ordinal" in sql:
            self._provision_selects += 1
            rows = (
                self.existing_provisions
                if self._provision_selects == 1
                else self.persisted_provisions
            )
            return _FakeResult(rows=rows)
        return _FakeResult()


class _TransactionContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection
        self.exception: type[BaseException] | None = None

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exception_type, *_):
        self.exception = exception_type
        return False


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection
        self.transaction = _TransactionContext(connection)

    def begin(self):
        return self.transaction

    def connect(self):
        return _TransactionContext(self.connection)


class _FakeStorage:
    async def put_immutable(self, path: str, _raw: RawResponse) -> str:
        return f"law-raw/{path}"

    async def close(self) -> None:
        return None


def _version_row(document: LegalDocumentRecord, raw: RawResponse) -> dict[str, object]:
    return {
        "id": _VERSION_ID,
        "mst": document.mst,
        "promulgation_number": document.promulgation_number,
        "promulgated_on": document.promulgated_on,
        "effective_from": document.effective_from,
        "effective_to": None,
        "ministry": document.ministry,
        "source_url": document.source_url,
        "raw_format": document.raw_format,
        "raw_sha256": document.raw_sha256,
        "raw_storage_path": f"law-raw/{raw_object_path(document, raw)}",
        "parser_schema_version": document.parser_schema_version,
        "fallback_reason": document.fallback_reason,
        "lifecycle_state": "active",
        "source_record_state": "available",
        "source_deleted_on": None,
        "has_supplementary_provisions": False,
    }


def _repository(connection: _FakeConnection) -> SupabaseCurrentCorpusRepository:
    return SupabaseCurrentCorpusRepository(
        database_url="postgresql://unused",
        supabase_url="https://unused.test",
        supabase_secret_key="unused",
        bucket="law-raw",
        engine=_FakeEngine(connection),  # type: ignore[arg-type]
        storage=_FakeStorage(),  # type: ignore[arg-type]
    )


def _corpus_gate_call_indices(calls: Sequence[tuple[str, object]]) -> list[int]:
    return [
        index
        for index, (_, params) in enumerate(calls)
        if isinstance(params, dict)
        and params.get("key") == CORPUS_SEARCH_READY_FLAG_KEY
    ]


@pytest.mark.asyncio
async def test_unchanged_sync_preserves_provisions_and_embeddings() -> None:
    document = _document()
    raw = RawResponse("{}", "JSON", document.source_url)
    provision_rows = [_provision_row(item) for item in document.provisions]
    connection = _FakeConnection(
        existing_document={"id": _DOCUMENT_ID, "exact_title": document.title},
        title_owners=[
            {
                "id": _DOCUMENT_ID,
                "source_kind": document.source_kind.value,
                "source_id": document.source_id,
            }
        ],
        existing_versions=[_version_row(document, raw)],
        existing_provisions=provision_rows,
        persisted_provisions=provision_rows,
    )

    changed = await _repository(connection).upsert(document, raw, effective_to=None)

    statements = [sql for sql, _ in connection.calls]
    assert changed is False
    assert "pg_advisory_xact_lock" in statements[0]
    assert not any("UPDATE embedding_profiles" in sql for sql in statements)
    assert not any("DELETE FROM provision_embeddings" in sql for sql in statements)
    assert not any("INSERT INTO provisions" in sql for sql in statements)
    assert _corpus_gate_call_indices(connection.calls) == []


@pytest.mark.asyncio
async def test_prepared_upsert_batches_more_than_one_hundred_provisions() -> None:
    document = _document()
    document.provisions = [
        ProvisionRecord(
            id=canonical_provision_id(
                source_kind=document.source_kind,
                source_id=document.source_id,
                mst=document.mst,
                effective_from=document.effective_from,
                path=f"제{index + 1}조",
            ),
            path=f"제{index + 1}조",
            heading=None,
            content=f"본문 {index + 1}",
            ordinal=index + 1,
        )
        for index in range(101)
    ]
    raw = RawResponse("{}", "JSON", document.source_url)
    connection = _FakeConnection(
        existing_document={"id": _DOCUMENT_ID, "exact_title": document.title},
        title_owners=[],
        existing_versions=[_version_row(document, raw)],
        existing_provisions=[],
        persisted_provisions=[_provision_row(item) for item in document.provisions],
    )

    changed = await _repository(connection).upsert(
        document,
        raw,
        effective_to=None,
        batch_size=100,
    )

    collision_batches = [
        params["provision_ids"]
        for sql, params in connection.calls
        if "SELECT id,version_id FROM provisions" in sql
    ]
    write_batches = [
        params
        for sql, params in connection.calls
        if "INSERT INTO provisions(" in sql
    ]
    assert changed is True
    assert [len(batch) for batch in collision_batches] == [100, 1]
    assert [len(batch) for batch in write_batches] == [100, 1]


@pytest.mark.asyncio
async def test_preview_reports_the_diff_without_storage_or_database_writes() -> None:
    document = _document()
    raw = RawResponse("{}", "JSON", document.source_url)
    provision_rows = [_provision_row(item) for item in document.provisions]
    connection = _FakeConnection(
        existing_document={"id": _DOCUMENT_ID, "exact_title": document.title},
        title_owners=[
            {
                "id": _DOCUMENT_ID,
                "source_kind": document.source_kind.value,
                "source_id": document.source_id,
            }
        ],
        existing_versions=[_version_row(document, raw)],
        existing_provisions=provision_rows,
        persisted_provisions=provision_rows,
    )

    preview = await _repository(connection).preview(document, raw, effective_to=None)

    statements = [sql for sql, _ in connection.calls]
    assert preview["new_document"] is False
    assert preview["new_version"] is False
    assert preview["version_changed"] is False
    assert preview["changed_version_fields"] == []
    assert preview["new_provisions"] == 0
    assert preview["missing_embeddings"] == 0
    assert preview["updated_provisions"] == 0
    assert preview["removed_provisions"] == 0
    assert not any(sql.lstrip().startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements)


@pytest.mark.asyncio
async def test_preview_reports_metadata_only_version_changes() -> None:
    document = _document()
    raw = RawResponse("{}", "JSON", document.source_url)
    old_version = _version_row(document, raw)
    old_version["ministry"] = "이전 소관 부처"
    provisions = [_provision_row(item) for item in document.provisions]
    connection = _FakeConnection(
        existing_document={"id": _DOCUMENT_ID, "exact_title": document.title},
        title_owners=[],
        existing_versions=[old_version],
        existing_provisions=provisions,
        persisted_provisions=provisions,
    )

    preview = await _repository(connection).preview(document, raw, effective_to=None)

    assert preview["version_changed"] is True
    assert preview["changed_version_fields"] == ["ministry"]
    assert preview["embedding_revalidation_required"] is False


@pytest.mark.asyncio
async def test_changed_sync_invalidates_dependencies_before_replacing_provisions() -> None:
    document = _document()
    raw = RawResponse("{}", "JSON", document.source_url)
    first = document.provisions[0]
    removed = ProvisionRecord(
        id=canonical_provision_id(
            source_kind=document.source_kind,
            source_id=document.source_id,
            mst=document.mst,
            effective_from=document.effective_from,
            path="제2조",
        ),
        path="제2조",
        heading="삭제 대상",
        content="이전 본문",
        ordinal=1,
    )
    updated = ProvisionRecord(
        id=first.id,
        path=first.path,
        heading=first.heading,
        content="변경된 본문",
        ordinal=0,
    )
    added = ProvisionRecord(
        id=canonical_provision_id(
            source_kind=document.source_kind,
            source_id=document.source_id,
            mst=document.mst,
            effective_from=document.effective_from,
            path="제3조",
        ),
        path="제3조",
        heading="신설",
        content="새 본문",
        ordinal=1,
    )
    document.title = "전기사업법 새 명칭"
    document.provisions = [updated, added]
    persisted = [_provision_row(item) for item in document.provisions]
    connection = _FakeConnection(
        existing_document={"id": _DOCUMENT_ID, "exact_title": "전기사업법"},
        title_owners=[],
        existing_versions=[_version_row(document, raw)],
        existing_provisions=[_provision_row(first), _provision_row(removed)],
        persisted_provisions=persisted,
    )

    changed = await _repository(connection).upsert(document, raw, effective_to=None)

    statements = [sql for sql, _ in connection.calls]
    profile_index = next(
        i for i, sql in enumerate(statements) if "UPDATE embedding_profiles" in sql
    )
    [corpus_gate_index] = _corpus_gate_call_indices(connection.calls)
    embedding_index = next(
        i for i, sql in enumerate(statements) if "DELETE FROM provision_embeddings e" in sql
    )
    relationship_index = next(
        i for i, sql in enumerate(statements) if "DELETE FROM legal_relationships" in sql
    )
    provision_delete_index = next(
        i for i, sql in enumerate(statements) if "DELETE FROM provisions" in sql
    )
    provision_insert_index = next(
        i for i, sql in enumerate(statements) if "INSERT INTO provisions" in sql
    )
    insert_sql = statements[provision_insert_index]

    assert changed is True
    assert corpus_gate_index < profile_index < embedding_index
    assert embedding_index < relationship_index < provision_delete_index
    assert provision_delete_index < provision_insert_index
    assert "version_id=excluded.version_id,path" not in insert_sql
    changed_params = connection.calls[provision_insert_index][1]
    assert isinstance(changed_params, list)
    assert {item["id"] for item in changed_params} == {updated.id, added.id}


@pytest.mark.asyncio
async def test_cross_version_provision_collision_rolls_back_before_deletion() -> None:
    document = _document()
    raw = RawResponse("{}", "JSON", document.source_url)
    rows = [_provision_row(item) for item in document.provisions]
    connection = _FakeConnection(
        existing_document={"id": _DOCUMENT_ID, "exact_title": document.title},
        title_owners=[],
        existing_versions=[_version_row(document, raw)],
        existing_provisions=[],
        persisted_provisions=rows,
        collisions=[{"id": document.provisions[0].id, "version_id": UUID(int=9)}],
    )
    repository = _repository(connection)

    with pytest.raises(ValueError, match="다른 법령 버전"):
        await repository.upsert(document, raw, effective_to=None)

    statements = [sql for sql, _ in connection.calls]
    assert repository.engine.transaction.exception is ValueError  # type: ignore[attr-defined]
    assert not any("DELETE FROM provision_embeddings" in sql for sql in statements)
    assert not any("DELETE FROM provisions" in sql for sql in statements)


@pytest.mark.asyncio
async def test_new_mst_closes_previous_open_version_before_insert() -> None:
    document = _document()
    document.mst = "1001"
    document.effective_from = date(2021, 1, 1)
    document.provisions[0].id = canonical_provision_id(
        source_kind=document.source_kind,
        source_id=document.source_id,
        mst=document.mst,
        effective_from=document.effective_from,
        path=document.provisions[0].path,
    )
    raw = RawResponse("{}", "JSON", document.source_url)
    old_version = _version_row(document, raw)
    old_version.update(
        {
            "id": UUID("33333333-3333-4333-8333-333333333333"),
            "mst": "1000",
            "effective_from": date(2020, 2, 1),
            "effective_to": None,
        }
    )
    rows = [_provision_row(item) for item in document.provisions]
    connection = _FakeConnection(
        existing_document={"id": _DOCUMENT_ID, "exact_title": document.title},
        title_owners=[
            {
                "id": _DOCUMENT_ID,
                "source_kind": document.source_kind.value,
                "source_id": document.source_id,
            }
        ],
        existing_versions=[old_version],
        existing_provisions=[],
        persisted_provisions=rows,
        closed_versions=[(old_version["id"],)],
    )

    changed = await _repository(connection).upsert(document, raw, effective_to=None)

    statements = [sql for sql, _ in connection.calls]
    close_index = next(
        i for i, sql in enumerate(statements) if "UPDATE document_versions SET effective_to" in sql
    )
    version_insert_index = next(
        i for i, sql in enumerate(statements) if "INSERT INTO document_versions" in sql
    )
    close_params = connection.calls[close_index][1]
    assert changed is True
    assert close_index < version_insert_index
    assert close_params["effective_from"] == date(2021, 1, 1)
    assert len(_corpus_gate_call_indices(connection.calls)) == 1
    assert any("UPDATE embedding_profiles" in sql for sql in statements)


class _RunLockConnection:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.calls: list[str] = []
        self.commits = 0

    async def execute(self, statement, _params=None):
        sql = str(statement)
        self.calls.append(sql)
        return _FakeResult(scalar=self.acquired if "pg_try_advisory_lock" in sql else True)

    async def commit(self) -> None:
        self.commits += 1


class _RunLockEngine:
    def __init__(self, acquired: bool) -> None:
        self.connection = _RunLockConnection(acquired)
        self.context = _TransactionContext(self.connection)  # type: ignore[arg-type]

    def connect(self):
        return self.context


def _lock_repository(acquired: bool) -> SupabaseCurrentCorpusRepository:
    return SupabaseCurrentCorpusRepository(
        database_url="postgresql://unused",
        supabase_url="https://unused.test",
        supabase_secret_key="unused",
        bucket="law-raw",
        engine=_RunLockEngine(acquired),  # type: ignore[arg-type]
        storage=_FakeStorage(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_sync_run_lock_is_released_after_the_full_fetch_window() -> None:
    repository = _lock_repository(True)

    async with repository.sync_run_lock():
        assert len(repository.engine.connection.calls) == 1  # type: ignore[attr-defined]

    calls = repository.engine.connection.calls  # type: ignore[attr-defined]
    assert "pg_try_advisory_lock" in calls[0]
    assert "hashtextextended" not in calls[0]
    assert "pg_advisory_unlock" in calls[1]
    assert repository.engine.connection.commits == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_sync_run_lock_rejects_a_concurrent_collector() -> None:
    repository = _lock_repository(False)

    with pytest.raises(RuntimeError, match="진행 중"):
        async with repository.sync_run_lock():
            raise AssertionError("unreachable")

    calls = repository.engine.connection.calls  # type: ignore[attr-defined]
    assert len(calls) == 1
    assert repository.engine.connection.commits == 1  # type: ignore[attr-defined]


class _PreparedRunLockConnection:
    def __init__(self, *, rejected_key: int | None = None) -> None:
        self.rejected_key = rejected_key
        self.calls: list[tuple[str, object]] = []
        self.commits = 0

    async def execute(self, statement, params=None):
        sql = str(statement)
        lock_key = params["lock_key"]
        self.calls.append((sql, lock_key))
        acquired = not ("pg_try_advisory_lock" in sql and lock_key == self.rejected_key)
        return _FakeResult(scalar=acquired)

    async def commit(self) -> None:
        self.commits += 1


class _PreparedRunLockEngine:
    def __init__(self, connection: _PreparedRunLockConnection) -> None:
        self.connection = connection

    def connect(self):
        return _TransactionContext(self.connection)  # type: ignore[arg-type]


def _prepared_lock_repository(
    connection: _PreparedRunLockConnection,
) -> SupabaseCurrentCorpusRepository:
    return SupabaseCurrentCorpusRepository(
        database_url="postgresql://unused",
        supabase_url="https://unused.test",
        supabase_secret_key="unused",
        bucket="law-raw",
        engine=_PreparedRunLockEngine(connection),  # type: ignore[arg-type]
        storage=_FakeStorage(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_prepared_publish_session_locks_and_unlocks_in_fixed_order() -> None:
    connection = _PreparedRunLockConnection()
    repository = _prepared_lock_repository(connection)

    async with repository.prepared_publish_session() as leased:
        assert leased is connection
        assert connection.calls == [
            ("SELECT pg_try_advisory_lock(:lock_key)", EMBEDDING_BACKFILL_LOCK_KEY),
            ("SELECT pg_try_advisory_lock(:lock_key)", CORPUS_SYNC_RUN_LOCK_KEY),
        ]

    assert connection.calls[-2:] == [
        ("SELECT pg_advisory_unlock(:lock_key)", CORPUS_SYNC_RUN_LOCK_KEY),
        ("SELECT pg_advisory_unlock(:lock_key)", EMBEDDING_BACKFILL_LOCK_KEY),
    ]
    assert connection.commits == 4


@pytest.mark.asyncio
async def test_prepared_publish_session_releases_first_lock_when_second_is_busy() -> None:
    connection = _PreparedRunLockConnection(rejected_key=CORPUS_SYNC_RUN_LOCK_KEY)
    repository = _prepared_lock_repository(connection)

    with pytest.raises(RuntimeError, match="다른 corpus writer"):
        async with repository.prepared_publish_session():
            raise AssertionError("unreachable")

    assert connection.calls[-1] == (
        "SELECT pg_advisory_unlock(:lock_key)",
        EMBEDDING_BACKFILL_LOCK_KEY,
    )
    assert connection.commits == 3


@pytest.mark.asyncio
async def test_searchability_change_invalidates_active_embedding_profiles() -> None:
    document = _document()
    raw = RawResponse("{}", "JSON", document.source_url)
    old_version = _version_row(document, raw)
    old_version["source_record_state"] = "deleted"
    provisions = [_provision_row(item) for item in document.provisions]
    connection = _FakeConnection(
        existing_document={"id": _DOCUMENT_ID, "exact_title": document.title},
        title_owners=[],
        existing_versions=[old_version],
        existing_provisions=provisions,
        persisted_provisions=provisions,
    )

    changed = await _repository(connection).upsert(document, raw, effective_to=None)

    statements = [sql for sql, _ in connection.calls]
    assert changed is True
    assert len(_corpus_gate_call_indices(connection.calls)) == 1
    assert any("UPDATE embedding_profiles SET active=false" in sql for sql in statements)
    assert not any("DELETE FROM provision_embeddings" in sql for sql in statements)


class _DeletionConnection:
    def __init__(
        self,
        rows: Sequence[Mapping[str, object]] = (),
        *,
        checkpoint: Mapping[str, object] | None = None,
        fail_mst: str | None = None,
    ) -> None:
        self.rows = [dict(row) for row in rows]
        self.checkpoint = dict(checkpoint) if checkpoint is not None else None
        self.fail_mst = fail_mst
        self.calls: list[tuple[str, object]] = []
        self.profile_invalidations = 0
        self.search_ready = True

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params))
        if "schema.corpus_search_ready_v1" in sql:
            return _FakeResult(scalar=True)
        if "pg_advisory_xact_lock" in sql:
            return _FakeResult()
        if "SELECT value->>'completed_on'" in sql:
            completed = self.checkpoint.get("completed_on") if self.checkpoint else None
            return _FakeResult(scalar=completed)
        if "SELECT v.id,v.source_record_state,v.source_deleted_on" in sql:
            assert isinstance(params, dict)
            if params["mst"] == self.fail_mst:
                raise RuntimeError("simulated deletion sync failure")
            matches = [
                {
                    "id": row["id"],
                    "source_record_state": row["source_record_state"],
                    "source_deleted_on": row["source_deleted_on"],
                }
                for row in self.rows
                if row["source_kind"] == params["source_kind"] and row["mst"] == params["mst"]
            ]
            return _FakeResult(rows=matches)
        if "UPDATE document_versions" in sql and "source_record_state='deleted'" in sql:
            assert isinstance(params, dict)
            version_ids = set(params["version_ids"])
            deleted_on = params["deleted_on"]
            changed = []
            for row in self.rows:
                if row["id"] not in version_ids:
                    continue
                row["source_record_state"] = "deleted"
                previous = row["source_deleted_on"]
                row["source_deleted_on"] = (
                    deleted_on if previous is None else min(previous, deleted_on)
                )
                changed.append((row["id"],))
            return _FakeResult(rows=changed)
        if "UPDATE embedding_profiles SET active=false" in sql:
            self.profile_invalidations += 1
            return _FakeResult()
        if "INSERT INTO runtime_flags" in sql:
            assert isinstance(params, dict)
            incoming = json.loads(params["value"])
            if params["key"] == CORPUS_SEARCH_READY_FLAG_KEY:
                self.search_ready = bool(incoming["ready"])
                return _FakeResult()
            current_date = (
                date.fromisoformat(str(self.checkpoint["completed_on"]))
                if self.checkpoint
                else None
            )
            if current_date is None or current_date <= params["completed_on"]:
                self.checkpoint = incoming
            return _FakeResult()
        raise AssertionError(f"unexpected SQL: {sql}")


class _DeletionEngine:
    def __init__(self, connection: _DeletionConnection) -> None:
        self.connection = connection

    def begin(self):
        return _TransactionContext(self.connection)  # type: ignore[arg-type]

    def connect(self):
        return _TransactionContext(self.connection)  # type: ignore[arg-type]


def _deletion_repository(connection: _DeletionConnection) -> SupabaseCurrentCorpusRepository:
    return SupabaseCurrentCorpusRepository(
        database_url="postgresql://unused",
        supabase_url="https://unused.test",
        supabase_secret_key="unused",
        bucket="law-raw",
        engine=_DeletionEngine(connection),  # type: ignore[arg-type]
        storage=_FakeStorage(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_supabase_deletion_window_uses_checkpoint_with_one_day_overlap() -> None:
    connection = _DeletionConnection()
    repository = _deletion_repository(connection)

    assert await repository.deletion_window(today=date(2026, 7, 14)) == (
        date(2026, 7, 7),
        date(2026, 7, 14),
    )

    connection.checkpoint = {"completed_on": "2026-07-10"}
    assert await repository.deletion_window(today=date(2026, 7, 14)) == (
        date(2026, 7, 9),
        date(2026, 7, 14),
    )

    connection.checkpoint = {"completed_on": "2026-07-20"}
    assert await repository.deletion_window(today=date(2026, 7, 14)) == (
        date(2026, 7, 13),
        date(2026, 7, 14),
    )


@pytest.mark.asyncio
async def test_supabase_source_deletions_deduplicate_and_preserve_earliest_date() -> None:
    law_first = UUID("44444444-4444-4444-8444-444444444444")
    law_already_deleted = UUID("55555555-5555-4555-8555-555555555555")
    rule = UUID("66666666-6666-4666-8666-666666666666")
    connection = _DeletionConnection(
        [
            {
                "id": law_first,
                "source_kind": "law",
                "mst": "1001",
                "source_record_state": "available",
                "source_deleted_on": None,
            },
            {
                "id": law_already_deleted,
                "source_kind": "law",
                "mst": "1001",
                "source_record_state": "deleted",
                "source_deleted_on": date(2026, 7, 9),
            },
            {
                "id": rule,
                "source_kind": "administrative_rule",
                "mst": "2001",
                "source_record_state": "available",
                "source_deleted_on": None,
            },
        ]
    )
    repository = _deletion_repository(connection)
    records = [
        DeletionRecord("1001", SourceKind.LAW, "law", date(2026, 7, 12)),
        DeletionRecord("1001", SourceKind.LAW, "law", date(2026, 7, 10)),
        DeletionRecord(
            "2001", SourceKind.ADMIN_RULE, "rule", date(2026, 7, 11)
        ),
        DeletionRecord("9999", SourceKind.LAW, "law", date(2026, 7, 8)),
    ]

    first = await repository.apply_source_deletions(records, completed_on=date(2026, 7, 14))

    assert first == {
        "law": {"matched": 2, "changed": 1},
        "administrative_rule": {"matched": 1, "changed": 1},
    }
    by_id = {row["id"]: row for row in connection.rows}
    assert by_id[law_first]["source_deleted_on"] == date(2026, 7, 10)
    assert by_id[law_already_deleted]["source_deleted_on"] == date(2026, 7, 9)
    assert by_id[rule]["source_deleted_on"] == date(2026, 7, 11)
    assert all(row["source_record_state"] == "deleted" for row in connection.rows)
    assert connection.profile_invalidations == 2
    assert connection.search_ready is False
    assert connection.checkpoint == {
        "completed_on": "2026-07-14",
        "record_count": 4,
        "deduplicated_record_count": 3,
    }

    replay = await repository.apply_source_deletions(records, completed_on=date(2026, 7, 14))

    assert replay == {
        "law": {"matched": 2, "changed": 0},
        "administrative_rule": {"matched": 1, "changed": 0},
    }
    assert connection.profile_invalidations == 2
    lock_calls = [sql for sql, _ in connection.calls if "pg_advisory_xact_lock" in sql]
    assert len(lock_calls) == 8


@pytest.mark.asyncio
async def test_supabase_deletion_failure_does_not_advance_checkpoint() -> None:
    connection = _DeletionConnection(fail_mst="1001")
    repository = _deletion_repository(connection)

    with pytest.raises(RuntimeError, match="simulated deletion sync failure"):
        await repository.apply_source_deletions(
            [DeletionRecord("1001", SourceKind.LAW, "law", date(2026, 7, 10))],
            completed_on=date(2026, 7, 14),
        )

    assert connection.checkpoint is None
    assert not any("INSERT INTO runtime_flags" in sql for sql, _ in connection.calls)


@pytest.mark.asyncio
async def test_supabase_deletion_checkpoint_never_moves_backwards() -> None:
    connection = _DeletionConnection(checkpoint={"completed_on": "2026-07-15"})
    repository = _deletion_repository(connection)

    stats = await repository.apply_source_deletions([], completed_on=date(2026, 7, 14))

    assert stats == {
        "law": {"matched": 0, "changed": 0},
        "administrative_rule": {"matched": 0, "changed": 0},
    }
    assert connection.checkpoint == {"completed_on": "2026-07-15"}

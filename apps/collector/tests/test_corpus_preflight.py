from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from datetime import date

import pytest

from law_rag_collector.cli import _parser
from law_rag_collector.corpus_preflight import (
    EXPECTED_PROFILE,
    CorpusPreflightError,
    _validated_report,
    preflight_current_corpus,
)


def _publish_row() -> dict[str, object]:
    return {
        "document_id": "document",
        "source_id": "001",
        "exact_title": "전기사업법",
        "source_kind": "law",
        "version_id": "version",
        "mst": "1000",
        "promulgation_number": "1",
        "promulgated_on": "2020-01-01",
        "effective_from": "2020-02-01",
        "effective_to": None,
        "ministry": "산업통상자원부",
        "source_url": "https://example.test/law",
        "raw_format": "JSON",
        "raw_sha256": "a" * 64,
        "raw_storage_path": "law/1000.json",
        "parser_schema_version": "3",
        "fallback_reason": None,
        "lifecycle_state": "active",
        "source_record_state": "available",
        "source_deleted_on": None,
        "has_supplementary_provisions": False,
        "provision_id": "provision",
        "path": "제1조",
        "parent_path": None,
        "heading": "목적",
        "content_sha256": "b" * 64,
        "ordinal": 0,
    }


def _valid_state() -> dict[str, object]:
    return {
        "transaction": {
            "transaction_isolation": "repeatable read",
            "transaction_read_only": "on",
            "statement_timeout": "15s",
            "lock_timeout": "2s",
        },
        "migration": {"migration_head": "0011"},
        "gate": {
            "capability_enabled": True,
            "search_ready": True,
            "reason": "ready",
        },
        "profiles": [dict(EXPECTED_PROFILE)],
        "coverage": {
            "searchable_provision_count": 1,
            "valid_profile_vector_count": 1,
            "missing_vector_count": 0,
            "wrong_dimension_count": 0,
            "source_sha_mismatch_count": 0,
            "non_unit_vector_count": 0,
        },
        "publish_rows": [_publish_row()],
        "temporal": {
            "supported_as_of_from": "2020-02-01",
            "supported_as_of_through": "2026-08-04",
            "eligible_provision_count": 1,
            "fingerprint_sha256": "c" * 64,
        },
    }


class _Result:
    def __init__(self, payload):
        self.payload = payload

    def mappings(self):
        return self

    def one(self):
        assert isinstance(self.payload, Mapping)
        return self.payload

    def all(self):
        assert isinstance(self.payload, list)
        return self.payload


class _Context:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False


class _Connection:
    def __init__(self, results):
        self.results = list(results)
        self.statements: list[str] = []

    def begin(self):
        return _Context()

    async def execute(self, statement, _parameters=None):
        sql = str(statement).strip()
        self.statements.append(sql)
        if sql.casefold().startswith("set "):
            return _Result({})
        return _Result(self.results.pop(0))


class _Engine:
    def __init__(self, connection):
        self.connection = connection
        self.disposed = False

    def connect(self):
        return _Context(self.connection)

    async def dispose(self):
        self.disposed = True


def _query_results(state: Mapping[str, object]) -> list[object]:
    return [
        state["transaction"],
        state["migration"],
        state["gate"],
        state["profiles"],
        state["coverage"],
        state["publish_rows"],
        state["temporal"],
    ]


async def test_preflight_uses_one_read_only_transaction_and_selects_only() -> None:
    state = _valid_state()
    connection = _Connection(_query_results(state))
    engine = _Engine(connection)

    report = await preflight_current_corpus(
        "postgresql://unused",
        today=date(2026, 8, 4),
        engine=engine,  # type: ignore[arg-type]
    )

    assert report["state"] == "ready"
    assert report["coverage"] == state["coverage"]
    assert report["bundle"] == {"present": False}
    assert engine.disposed is False
    assert connection.statements[:3] == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    forbidden = re.compile(
        r"\b(insert|update|delete|merge|call|do|create|alter|drop|truncate|advisory)\b",
        re.IGNORECASE,
    )
    assert all(
        statement.casefold().startswith(("select", "with")) and forbidden.search(statement) is None
        for statement in connection.statements[3:]
    )


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("migration", "migration_head", "0010", "migration head"),
        ("gate", "search_ready", False, "search gate"),
        ("coverage", "missing_vector_count", 1, "missing_vector_count"),
        ("coverage", "source_sha_mismatch_count", 1, "source_sha_mismatch_count"),
        ("coverage", "non_unit_vector_count", 1, "non_unit_vector_count"),
    ],
)
def test_preflight_fails_closed_on_invalid_state(section, key, value, message) -> None:
    state = deepcopy(_valid_state())
    state[section][key] = value  # type: ignore[index]

    with pytest.raises(CorpusPreflightError, match=message):
        _validated_report(
            state,
            today=date(2026, 8, 4),
            bundle_path=None,
        )


def test_preflight_command_is_available_without_a_bundle() -> None:
    arguments = _parser().parse_args(["preflight-current"])

    assert arguments.command == "preflight-current"
    assert arguments.bundle is None


async def test_preflight_requires_direct_url() -> None:
    with pytest.raises(ValueError, match="DIRECT_URL"):
        await preflight_current_corpus("")

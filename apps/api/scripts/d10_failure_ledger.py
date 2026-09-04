"""Safe append-only attempt ledger for D-10 failure-driven evaluation."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar, Literal

D10_CASE_IDS = frozenset(
    {
        "lay-energy-0111",
        "lay-energy-0201",
        "lay-energy-0251",
        "lay-energy-0346",
        "lay-energy-0521",
        "lay-energy-0561",
        "lay-energy-0601",
        "lay-energy-0605",
        "lay-energy-0836",
        "lay-energy-0943",
    }
)
ATTEMPT_STATUSES = frozenset({"pass", "failure", "blocked"})
CITATION_REASON = "not_generated_by_retrieval_runner"
_SAFE_CODE = re.compile(r"[a-z0-9_]+")


class LedgerValidationError(ValueError):
    """Raised when an attempt would violate the safe D-10 ledger contract."""


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    attempt_number: int
    case_id: str
    status: Literal["pass", "failure", "blocked"]
    error_code: str | None
    retrieved_evidence_count: int
    citation_count: None
    citation_reason: str

    _FIELD_NAMES: ClassVar[tuple[str, ...]] = (
        "attempt_number",
        "case_id",
        "status",
        "error_code",
        "retrieved_evidence_count",
        "citation_count",
        "citation_reason",
    )

    @classmethod
    def allowed_field_names(cls) -> tuple[str, ...]:
        return cls._FIELD_NAMES

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> AttemptRecord:
        if set(value) != set(cls._FIELD_NAMES):
            raise LedgerValidationError("attempt_fields_invalid")
        record = cls(**{field: value[field] for field in cls._FIELD_NAMES})
        record.validate()
        return record

    def validate(self) -> None:
        if (
            isinstance(self.attempt_number, bool)
            or not isinstance(self.attempt_number, int)
            or self.attempt_number < 1
        ):
            raise LedgerValidationError("attempt_number_invalid")
        if self.case_id not in D10_CASE_IDS:
            raise LedgerValidationError("case_id_not_in_d10")
        if self.status not in ATTEMPT_STATUSES:
            raise LedgerValidationError("attempt_status_invalid")
        if (
            self.error_code is not None
            and (not isinstance(self.error_code, str) or not _SAFE_CODE.fullmatch(self.error_code))
        ):
            raise LedgerValidationError("error_code_invalid")
        if (
            isinstance(self.retrieved_evidence_count, bool)
            or not isinstance(self.retrieved_evidence_count, int)
            or self.retrieved_evidence_count < 0
        ):
            raise LedgerValidationError("retrieved_evidence_count_invalid")
        if self.retrieved_evidence_count == 0 and self.status != "failure":
            raise LedgerValidationError("zero_evidence_requires_failure")
        if self.citation_count is not None or self.citation_reason != CITATION_REASON:
            raise LedgerValidationError("retrieval_citation_contract_invalid")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return asdict(self)


def _coerce_attempt(value: AttemptRecord | Mapping[str, object]) -> AttemptRecord:
    if isinstance(value, AttemptRecord):
        value.validate()
        return value
    if isinstance(value, Mapping):
        return AttemptRecord.from_mapping(value)
    raise LedgerValidationError("attempt_record_invalid")


def _load_attempts(path: Path) -> list[AttemptRecord]:
    if not path.exists():
        return []
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise LedgerValidationError("attempt_ledger_unreadable") from error
    attempts: list[AttemptRecord] = []
    for line in rows:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as error:
            raise LedgerValidationError("attempt_ledger_json_invalid") from error
        if not isinstance(raw, Mapping):
            raise LedgerValidationError("attempt_ledger_row_invalid")
        attempts.append(AttemptRecord.from_mapping(raw))
    for expected_number, attempt in enumerate(attempts, start=1):
        if attempt.attempt_number != expected_number:
            raise LedgerValidationError("attempt_numbers_not_contiguous")
    return attempts


def append_attempt(path: Path, value: AttemptRecord | Mapping[str, object]) -> AttemptRecord:
    attempt = _coerce_attempt(value)
    existing = _load_attempts(path)
    if attempt.attempt_number != len(existing) + 1:
        raise LedgerValidationError("attempt_number_not_next")
    encoded = json.dumps(
        attempt.to_dict(),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded + "\n")
    except OSError as error:
        raise LedgerValidationError("attempt_ledger_unwritable") from error
    return attempt


def summarize_attempts(path: Path) -> dict[str, object]:
    attempts = _load_attempts(path)
    attempts_by_case = Counter(attempt.case_id for attempt in attempts)
    status_counts = Counter(attempt.status for attempt in attempts)
    failure_codes = Counter(
        attempt.error_code
        for attempt in attempts
        if attempt.status == "failure" and attempt.error_code is not None
    )
    return {
        "total_attempts": len(attempts),
        "attempts_by_case": dict(sorted(attempts_by_case.items())),
        "status_counts": {status: status_counts[status] for status in sorted(ATTEMPT_STATUSES)},
        "failure_code_histogram": dict(sorted(failure_codes.items())),
    }

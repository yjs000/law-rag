"""Dynamic temporal contract for the currently searchable legal corpus.

The supported start is derived from collected parser-current legal versions.
The supported end is the current date in Korea.  A content snapshot identifies
the provision population effective on that end date; the date itself is not
part of the content identity.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone

from app.domain.schemas import CorpusTemporalState

SEOUL_TIME_ZONE = timezone(timedelta(hours=9), name="Asia/Seoul")


def korea_today() -> date:
    """Return the product's legal-current date, independent of server timezone."""

    return datetime.now(SEOUL_TIME_ZONE).date()


def canonical_corpus_population_fingerprint(
    rows: Sequence[Sequence[object]],
) -> str:
    """Hash provision identity rows with the PostgreSQL JSONB array encoding."""

    if any(len(row) != 11 for row in rows):
        raise ValueError("corpus population rows must use the 11-field v1 contract")
    provision_ids = [str(row[3]) for row in rows]
    if len(set(provision_ids)) != len(provision_ids):
        raise ValueError("corpus population provision IDs must be unique")
    ordered = sorted(rows, key=lambda row: str(row[3]))
    serialized = json.dumps(
        ordered,
        ensure_ascii=False,
        separators=(", ", ": "),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def canonical_corpus_snapshot_id(
    *,
    parser_contract_version: str,
    retrieval_unit: str,
    content_populations: Sequence[Mapping[str, object]],
) -> str:
    """Hash unique content populations without treating dates as content."""

    if not content_populations:
        raise ValueError("at least one corpus content population is required")
    identities: set[tuple[int, str]] = set()
    for population in content_populations:
        raw_count = population["eligible_provision_count"]
        if isinstance(raw_count, bool):
            raise ValueError("eligible provision count must be a positive integer")
        count = int(raw_count)
        fingerprint = str(population["fingerprint_sha256"])
        if count <= 0:
            raise ValueError("eligible provision count must be positive")
        if len(fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in fingerprint
        ):
            raise ValueError("population fingerprint must be lowercase SHA-256")
        identities.add((count, fingerprint))

    rows = [
        {
            "eligible_provision_count": count,
            "fingerprint_sha256": fingerprint,
        }
        for count, fingerprint in sorted(identities)
    ]
    payload = {
        "contract": "corpus-population-content-v1",
        "parser_contract_version": parser_contract_version,
        "retrieval_unit": retrieval_unit,
        "content_populations": rows,
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return f"corpus-sha256:{digest}"


class UnsupportedCorpusDateError(ValueError):
    """Raised when a request falls outside the current dynamic corpus bounds."""

    def __init__(self, requested_date: date, state: CorpusTemporalState) -> None:
        if (
            not state.ready
            or state.supported_as_of_from is None
            or state.corpus_snapshot_id is None
        ):
            raise ValueError("unsupported-date validation requires a ready temporal state")
        self.requested_date = requested_date
        self.supported_from = state.supported_as_of_from
        self.supported_through = state.supported_as_of_through
        self.snapshot_id = state.corpus_snapshot_id
        super().__init__(
            f"current corpus supports {self.supported_from.isoformat()} through "
            f"{self.supported_through.isoformat()}, not {requested_date.isoformat()}"
        )


def require_supported_corpus_date(
    requested_date: date,
    state: CorpusTemporalState,
) -> date:
    """Return a supported date or fail before quota and provider work begins."""

    if not state.ready or state.supported_as_of_from is None or state.corpus_snapshot_id is None:
        raise ValueError("corpus temporal state is not ready")
    if not state.supported_as_of_from <= requested_date <= state.supported_as_of_through:
        raise UnsupportedCorpusDateError(requested_date, state)
    return requested_date


__all__ = [
    "SEOUL_TIME_ZONE",
    "UnsupportedCorpusDateError",
    "canonical_corpus_population_fingerprint",
    "canonical_corpus_snapshot_id",
    "korea_today",
    "require_supported_corpus_date",
]

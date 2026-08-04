"""Dynamic temporal contract for the currently searchable legal corpus.

The supported start is derived from collected parser-current legal versions.
The supported end is the current date in Korea.  A content snapshot identifies
the provision population effective on that end date; the date itself is not
part of the content identity.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from law_rag_core.corpus_update_bundle import (
    canonical_corpus_population_fingerprint,
    canonical_corpus_snapshot_id,
)

from app.domain.schemas import CorpusTemporalState

SEOUL_TIME_ZONE = timezone(timedelta(hours=9), name="Asia/Seoul")


def korea_today() -> date:
    """Return the product's legal-current date, independent of server timezone."""

    return datetime.now(SEOUL_TIME_ZONE).date()


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

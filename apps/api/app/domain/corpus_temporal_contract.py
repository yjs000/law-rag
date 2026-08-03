"""Fixed temporal boundary for the currently deployed legal corpus snapshot.

The runtime corpus contains only the nine current open document versions that
were verified for the 2026-08-03 snapshot.  It is not a complete historical
archive.  Keeping this contract in one domain module prevents API entry points
from silently treating a sparse historical result as "no evidence".
"""

from datetime import date
from typing import Final

# Read-only production audit on 2026-08-03: all nine catalog documents had one
# current open parser-v3 version; the latest of their effective_from values was
# 2026-06-03.  Both inclusive boundaries expose the same 3,066 provisions.
CURRENT_CORPUS_SNAPSHOT_ID: Final[str] = "mvp-current-corpus-2026-08-03"
CURRENT_CORPUS_SUPPORTED_FROM: Final[date] = date(2026, 6, 3)
CURRENT_CORPUS_SUPPORTED_THROUGH: Final[date] = date(2026, 8, 3)


class UnsupportedCorpusDateError(ValueError):
    """Raised when a request asks the current snapshot to serve another date."""

    def __init__(self, requested_date: date) -> None:
        self.requested_date = requested_date
        self.supported_from = CURRENT_CORPUS_SUPPORTED_FROM
        self.supported_through = CURRENT_CORPUS_SUPPORTED_THROUGH
        self.snapshot_id = CURRENT_CORPUS_SNAPSHOT_ID
        super().__init__(
            f"current corpus supports {self.supported_from.isoformat()} through "
            f"{self.supported_through.isoformat()}, not {requested_date.isoformat()}"
        )


def require_supported_corpus_date(requested_date: date) -> date:
    """Return a supported date or fail before retrieval/provider work begins."""

    if not CURRENT_CORPUS_SUPPORTED_FROM <= requested_date <= CURRENT_CORPUS_SUPPORTED_THROUGH:
        raise UnsupportedCorpusDateError(requested_date)
    return requested_date


__all__ = [
    "CURRENT_CORPUS_SNAPSHOT_ID",
    "CURRENT_CORPUS_SUPPORTED_FROM",
    "CURRENT_CORPUS_SUPPORTED_THROUGH",
    "UnsupportedCorpusDateError",
    "require_supported_corpus_date",
]

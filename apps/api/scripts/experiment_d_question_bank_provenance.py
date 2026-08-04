"""Frozen corpus context recorded with the approved Experiment D question bank.

These values are historical provenance for the question text-and-scope review.
They are not runtime corpus authority and must not be used to accept or reject
production ``as_of_date`` requests.
"""

from datetime import date
from typing import Final

# Historical provenance only: this was the corpus context recorded when the
# question text and scope were generated, reviewed, and approved. Runtime code
# must obtain its supported range and snapshot identity from the runtime corpus
# contract instead of importing these constants.
QUESTION_BANK_CONTEXT_AS_OF_DATE: Final[str] = "2026-08-03"
QUESTION_BANK_CONTEXT_CORPUS_SNAPSHOT_ID: Final[str] = "mvp-current-corpus-2026-08-03"
QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_FROM: Final[date] = date(2026, 6, 3)
QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_THROUGH: Final[date] = date(2026, 8, 3)

__all__ = [
    "QUESTION_BANK_CONTEXT_AS_OF_DATE",
    "QUESTION_BANK_CONTEXT_CORPUS_SNAPSHOT_ID",
    "QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_FROM",
    "QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_THROUGH",
]

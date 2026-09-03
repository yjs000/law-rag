from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class FrozenCitation:
    id: str
    quote: str
    document_title: str = ""
    path: str = ""


@dataclass(frozen=True)
class GroundedSentence:
    text: str
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class GroundedSection:
    claim: GroundedSentence
    explanations: tuple[GroundedSentence, ...]


class CitationRegistry:
    """The immutable evidence set a v2 execution may cite."""

    def __init__(self, citations: Iterable[FrozenCitation]) -> None:
        items = tuple(citations)
        identifiers = [citation.id for citation in items]
        if any(not identifier for identifier in identifiers) or (
            len(set(identifiers)) != len(identifiers)
        ):
            raise ValueError("citation registry requires unique non-empty identifiers")
        self._citations = items
        self._by_id = {citation.id: citation for citation in items}

    @property
    def citations(self) -> tuple[FrozenCitation, ...]:
        return self._citations

    def verify(self, sentence: GroundedSentence) -> bool:
        if not sentence.text.strip() or not sentence.citation_ids:
            return False
        cited = tuple(self._by_id.get(identifier) for identifier in sentence.citation_ids)
        if any(citation is None for citation in cited):
            return False
        source_text = " ".join(
            f"{citation.document_title} {citation.path} {citation.quote}"
            for citation in cited
            if citation is not None
        )
        return _has_supported_numbers(sentence.text, source_text) and _has_supported_strength(
            sentence.text, source_text
        )


_NUMBERS = re.compile(r"\d+(?:[.,]\d+)?")
_STRONG_TERMS = ("반드시", "하여야", "해야", "의무", "금지", "허용", "모든", "항상", "예외 없이")


def _has_supported_numbers(text: str, source_text: str) -> bool:
    normalized_text = unicodedata.normalize("NFKC", text)
    normalized_source = unicodedata.normalize("NFKC", source_text)
    return all(number in normalized_source for number in _NUMBERS.findall(normalized_text))


def _has_supported_strength(text: str, source_text: str) -> bool:
    return all(term not in text or term in source_text for term in _STRONG_TERMS)

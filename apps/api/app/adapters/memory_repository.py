import json
import re
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.catalog import MVP_CATALOG
from app.domain.entities import LegalDocumentRecord
from app.domain.provision_queries import parse_provision_reference
from app.domain.schemas import CorpusItemStatus, SearchHit
from app.parsers.law_json import parse_legal_document as parse_json_document
from app.parsers.law_xml import parse_legal_document as parse_xml_document


class MemoryLegalRepository:
    def __init__(self) -> None:
        self._documents: dict[tuple[str, str, str, str], LegalDocumentRecord] = {}
        self._document_ids: dict[tuple[str, str, str, str], UUID] = {}
        self._effective_to: dict[tuple[str, str, str, str], date | None] = {}
        self._last_sync: datetime | None = None
        self._usage: dict[tuple[str, date, str], int] = {}

    async def consume_quota(self, subject_hash: str, day: date, kind: str, limit: int) -> bool:
        key = (subject_hash, day, kind)
        used = self._usage.get(key, 0)
        if used >= limit:
            return False
        self._usage[key] = used + 1
        return True

    async def upsert_document(self, document: LegalDocumentRecord) -> UUID:
        effective_key = (
            document.effective_from.isoformat() if document.effective_from else "unknown"
        )
        key = (document.source_kind.value, document.source_id, document.mst, effective_key)
        document_id = uuid5(
            NAMESPACE_URL,
            f"law.go.kr:{document.source_kind.value}:{document.source_id}:"
            f"{document.mst}:{effective_key}",
        )
        self._documents[key] = document
        self._document_ids[key] = document_id
        self._effective_to[key] = None
        self._last_sync = datetime.now(UTC)
        return document_id

    def load_collector_state(self, root: Path) -> tuple[int, list[str]]:
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            return 0, []
        state = json.loads(manifest_path.read_text(encoding="utf-8"))
        loaded = 0
        errors: list[str] = []
        for metadata in state.get("documents", {}).values():
            try:
                if metadata.get("lifecycle_state") in {"abolished", "deleted"}:
                    continue
                if metadata.get("source_record_state") == "deleted":
                    continue
                source_kind = next(
                    entry.source_kind
                    for entry in MVP_CATALOG
                    if entry.title == metadata["title"]
                )
                raw_path = root / metadata["raw_path"]
                body = raw_path.read_text(encoding="utf-8")
                parser = (
                    parse_json_document
                    if metadata["raw_format"] == "JSON"
                    else parse_xml_document
                )
                document = parser(
                    body,
                    expected_title=metadata["title"],
                    source_kind=source_kind,
                    source_url=metadata["source_url"],
                    mst_override=metadata["mst"],
                )
                document.effective_from = _date_or_none(metadata.get("effective_from"))
                key = (
                    document.source_kind.value,
                    document.source_id,
                    document.mst,
                    metadata.get("effective_from") or "unknown",
                )
                self._documents[key] = document
                self._document_ids[key] = uuid5(
                    NAMESPACE_URL,
                    f"law.go.kr:{':'.join(key)}",
                )
                self._effective_to[key] = _date_or_none(metadata.get("effective_to"))
                loaded += 1
            except Exception as exc:
                errors.append(f"{metadata.get('title', 'unknown')}: {type(exc).__name__}")
        runs = state.get("runs", [])
        if runs and runs[-1].get("finished_at"):
            self._last_sync = datetime.fromisoformat(runs[-1]["finished_at"])
        return loaded, errors

    async def upsert_embeddings(
        self, values: list[tuple[UUID, list[float]]], model: str, dimensions: int
    ) -> None:
        return None

    async def search(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
    ) -> list[SearchHit]:
        terms = _query_terms(query)
        compact_query = _compact_text(query)
        reference = parse_provision_reference(query)
        hits: list[SearchHit] = []
        for key, document in self._documents.items():
            if document.effective_from and document.effective_from > as_of_date:
                continue
            if self._effective_to.get(key) and self._effective_to[key] <= as_of_date:
                continue
            if reference and reference.document_title not in {None, document.title}:
                continue
            for provision in document.provisions:
                title = _normalize_text(document.title)
                heading = _normalize_text(provision.heading or "")
                content = _normalize_text(provision.content)
                matched_score = _match_score(
                    terms,
                    title=title,
                    heading=heading,
                    content=content,
                )
                if _compact_text(document.title) in compact_query:
                    matched_score += 4.0
                path_matched = (
                    reference is not None and provision.path in reference.storage_paths
                )
                if reference is not None and not path_matched:
                    continue
                if reference is None and not matched_score:
                    continue
                effective_to = self._effective_to.get(key)
                hits.append(
                    SearchHit(
                        provision_id=provision.id,
                        document_id=self._document_ids[key],
                        document_title=document.title,
                        source_kind=document.source_kind,
                        version_label=f"MST {document.mst}",
                        effective_from=document.effective_from,
                        effective_to=effective_to,
                        path=provision.path,
                        heading=provision.heading,
                        content=provision.content,
                        source_url=document.source_url,
                        score=(10.0 if path_matched else 0.0) + matched_score,
                    )
                )
        return sorted(hits, key=lambda hit: (-hit.score, hit.document_title, hit.path))[:limit]

    async def provision(self, provision_id: UUID, as_of_date: date) -> SearchHit | None:
        for key, document in self._documents.items():
            if document.effective_from and document.effective_from > as_of_date:
                continue
            if self._effective_to.get(key) and self._effective_to[key] <= as_of_date:
                continue
            for provision in document.provisions:
                if provision.id == provision_id:
                    return SearchHit(
                        provision_id=provision.id,
                        document_id=self._document_ids[key],
                        document_title=document.title,
                        source_kind=document.source_kind,
                        version_label=f"MST {document.mst}",
                        effective_from=document.effective_from,
                        effective_to=self._effective_to.get(key),
                        path=provision.path,
                        heading=provision.heading,
                        content=provision.content,
                        source_url=document.source_url,
                        score=1,
                    )
        return None

    async def corpus_items(self) -> list[CorpusItemStatus]:
        latest_by_title: dict[str, date] = {}
        for document in self._documents.values():
            current = latest_by_title.get(document.title)
            if current is None or document.effective_from > current:
                latest_by_title[document.title] = document.effective_from
        return [
            CorpusItemStatus(
                title=entry.title,
                source_kind=entry.source_kind,
                state="ready" if entry.title in latest_by_title else "missing",
                latest_effective_date=latest_by_title.get(entry.title),
            )
            for entry in MVP_CATALOG
        ]

    async def last_sync(self) -> datetime | None:
        return self._last_sync


repository = MemoryLegalRepository()


def _date_or_none(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _query_terms(query: str) -> set[str]:
    terms = set()
    for raw_term in re.findall(r"[가-힣A-Za-z0-9]+", _normalize_text(query)):
        term = _normalize_query_term(raw_term)
        if len(term) > 1 and not _is_question_filler(term):
            terms.add(term)
    aliases = {
        "신재생": {"신에너지", "재생에너지"},
        "신재생에너지": {"신에너지", "재생에너지"},
        "ess": {"전기저장시설", "에너지저장장치"},
        "에너지저장장치": {"전기저장시설"},
        "인허가": {"인가", "허가"},
    }
    for term in tuple(terms):
        terms.update(aliases.get(term, set()))
    return terms


_KOREAN_PARTICLES = (
    "으로부터",
    "에게서",
    "에서는",
    "으로는",
    "에서",
    "에게",
    "께서",
    "까지",
    "부터",
    "처럼",
    "보다",
    "으로",
    "와",
    "과",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "로",
    "도",
    "만",
)

_QUESTION_FILLER_PREFIXES = (
    "알려",
    "무엇",
    "어떤",
    "어떻게",
    "필요",
    "궁금",
    "보여",
    "설명",
)


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _compact_text(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", _normalize_text(value))


def _normalize_query_term(term: str) -> str:
    for particle in _KOREAN_PARTICLES:
        if term.endswith(particle) and len(term) - len(particle) >= 2:
            return term[: -len(particle)]
    return term


def _is_question_filler(term: str) -> bool:
    return any(term.startswith(prefix) for prefix in _QUESTION_FILLER_PREFIXES)


def _match_score(terms: set[str], *, title: str, heading: str, content: str) -> float:
    score = 0.0
    for term in terms:
        if term in title:
            score += 3.0
        if term in heading:
            score += 2.0
        if term in content:
            score += 1.0
    return score

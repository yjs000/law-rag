import json
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.catalog import MVP_CATALOG
from app.domain.entities import LegalDocumentRecord
from app.domain.provision_queries import parse_provision_reference
from app.domain.schemas import CorpusItemStatus, SearchHit
from app.domain.search_queries import (
    PreparedSearchQuery,
    SearchStageTrace,
    SearchTrace,
    compact_text,
    matching_terms,
    normalize_text,
    prepare_search_query,
)
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
                    entry.source_kind for entry in MVP_CATALOG if entry.title == metadata["title"]
                )
                raw_path = root / metadata["raw_path"]
                body = raw_path.read_text(encoding="utf-8")
                parser = (
                    parse_json_document if metadata["raw_format"] == "JSON" else parse_xml_document
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
        hits, _ = await self.search_with_trace(query, as_of_date, limit, query_embedding)
        return hits

    async def search_with_trace(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
    ) -> tuple[list[SearchHit], SearchTrace]:
        started = perf_counter()
        prepared = prepare_search_query(query)
        terms = set(prepared.expanded_terms)
        compact_query = compact_text(query)
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
                title = normalize_text(document.title)
                heading = normalize_text(provision.heading or "")
                content = normalize_text(provision.content)
                matched_score = _match_score(
                    terms,
                    title=title,
                    heading=heading,
                    content=content,
                )
                if compact_text(document.title) in compact_query:
                    matched_score += 4.0
                path_matched = reference is not None and provision.path in reference.storage_paths
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
        ranked = sorted(hits, key=lambda hit: (-hit.score, hit.document_title, hit.path))
        if reference is not None:
            selected = ranked[:limit]
            duration_ms = _elapsed_ms(started)
            return selected, SearchTrace(
                strategy="direct_path",
                normalized_query=prepared.normalized_text,
                terms=prepared.terms,
                executed_query=None,
                relaxed=False,
                reference_title=reference.document_title,
                reference_path=reference.path,
                candidate_count=len(selected),
                anchor_term=prepared.anchor_term,
                stages=(
                    SearchStageTrace(
                        stage="direct_path",
                        query=reference.path,
                        raw_candidate_count=len(ranked),
                        accepted_candidate_count=len(selected),
                        duration_ms=duration_ms,
                        status="matched" if selected else "insufficient_evidence",
                    ),
                ),
                total_duration_ms=duration_ms,
            )

        match_cache: dict[UUID, set[str]] = {}

        def matched(hit: SearchHit) -> set[str]:
            if hit.provision_id not in match_cache:
                match_cache[hit.provision_id] = matching_terms(
                    " ".join((hit.document_title, hit.heading or "", hit.content)), prepared
                )
            return match_cache[hit.provision_id]

        stages: list[SearchStageTrace] = []
        stage_started = perf_counter()
        all_terms = [hit for hit in ranked if len(matched(hit)) == len(prepared.terms)]
        stages.append(
            _stage_trace(
                "all_terms",
                prepared.strict_query,
                len(ranked),
                len(all_terms),
                stage_started,
                "matched" if all_terms else "no_match",
            )
        )
        if all_terms and prepared.terms:
            selected = all_terms[:limit]
            return selected, _natural_trace(
                prepared, selected, stages, started, prepared.strict_query, False
            )

        stage_started = perf_counter()
        minimum = min(2, len(prepared.terms))
        minimum_two = [hit for hit in ranked if minimum and len(matched(hit)) >= minimum]
        stages.append(
            _stage_trace(
                "minimum_two",
                prepared.minimum_match_query,
                len(ranked),
                len(minimum_two),
                stage_started,
                "candidate_pool" if minimum_two else "no_match",
            )
        )

        stage_started = perf_counter()
        anchored = (
            [hit for hit in minimum_two if prepared.anchor_term in matched(hit)]
            if prepared.anchor_term
            else []
        )
        stages.append(
            _stage_trace(
                "anchor_required",
                prepared.anchored_query or None,
                len(minimum_two),
                len(anchored),
                stage_started,
                (
                    "matched"
                    if anchored
                    else "skipped_no_anchor"
                    if prepared.anchor_term is None
                    else "no_match"
                ),
            )
        )
        if anchored:
            selected = anchored[:limit]
            return selected, _natural_trace(
                prepared, selected, stages, started, prepared.anchored_query, True
            )

        stage_started = perf_counter()
        stages.append(
            _stage_trace(
                "insufficient_evidence",
                None,
                0,
                0,
                stage_started,
                "insufficient_evidence",
            )
        )
        return [], SearchTrace(
            strategy="four_stage_keyword_memory",
            normalized_query=prepared.normalized_text,
            terms=prepared.terms,
            executed_query=prepared.minimum_match_query or prepared.strict_query or None,
            relaxed=True,
            reference_title=None,
            reference_path=None,
            candidate_count=0,
            anchor_term=prepared.anchor_term,
            stages=tuple(stages),
            total_duration_ms=_elapsed_ms(started),
        )

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


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000


def _stage_trace(
    stage: str,
    query: str | None,
    raw_count: int,
    accepted_count: int,
    started: float,
    status: str,
) -> SearchStageTrace:
    return SearchStageTrace(
        stage=stage,
        query=query or None,
        raw_candidate_count=raw_count,
        accepted_candidate_count=accepted_count,
        duration_ms=_elapsed_ms(started),
        status=status,
    )


def _natural_trace(
    prepared: PreparedSearchQuery,
    selected: list[SearchHit],
    stages: list[SearchStageTrace],
    started: float,
    executed_query: str,
    relaxed: bool,
) -> SearchTrace:
    return SearchTrace(
        strategy="four_stage_keyword_memory",
        normalized_query=prepared.normalized_text,
        terms=prepared.terms,
        executed_query=executed_query,
        relaxed=relaxed,
        reference_title=None,
        reference_path=None,
        candidate_count=len(selected),
        anchor_term=prepared.anchor_term,
        stages=tuple(stages),
        total_duration_ms=_elapsed_ms(started),
    )

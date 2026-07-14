import asyncio
import json
from datetime import date
from pathlib import Path

from app.adapters.memory_repository import MemoryLegalRepository
from app.adapters.openai_embedder import OpenAIEmbedder
from app.adapters.postgres_repository import PostgresLegalRepository
from app.application.answering import search_only_answer
from app.domain.schemas import ProjectStage, QuestionRequest
from app.settings import get_settings


def citation_quality(answer, hits) -> tuple[float, float]:
    citation_ids = {citation.id for citation in answer.citations}
    references = [
        citation_id
        for item in [*answer.sections, *answer.checklist]
        for citation_id in item.citation_ids
    ]
    existence_rate = (
        sum(citation_id in citation_ids for citation_id in references) / len(references)
        if references
        else 0.0
    )
    hit_content = {hit.provision_id: hit.content for hit in hits}
    original_match_rate = (
        sum(
            hit_content.get(citation.provision_id) == citation.quote
            for citation in answer.citations
        )
        / len(answer.citations)
        if answer.citations
        else 0.0
    )
    return existence_rate, original_match_rate


def enforce_quality(
    recall_at_10: float, citation_existence_rate: float, citation_original_match_rate: float
) -> None:
    if recall_at_10 < 0.9:
        raise SystemExit("Recall@10 < 0.90")
    if citation_existence_rate != 1.0:
        raise SystemExit("citation existence rate < 1.00")
    if citation_original_match_rate != 1.0:
        raise SystemExit("citation original match rate < 1.00")


async def main() -> None:
    settings = get_settings()
    dataset = json.loads(
        (Path(__file__).parents[1] / "evaluation" / "retrieval-v1.json").read_text(encoding="utf-8")
    )
    if settings.database_url:
        repository = PostgresLegalRepository(settings.database_url)
    else:
        repository = MemoryLegalRepository()
        loaded, errors = repository.load_collector_state(settings.collector_state_dir)
        if not loaded:
            raise SystemExit("평가할 collector 목업 코퍼스가 없습니다")
        if errors:
            raise SystemExit(f"collector 목업 코퍼스 {len(errors)}건을 읽지 못했습니다")
    embedder = (
        OpenAIEmbedder(
            api_key=settings.openai_api_key or "",
            model=settings.openai_embedding_model,
            dimensions=settings.embedding_dimensions,
        )
        if settings.ai_enabled and settings.database_url
        else None
    )
    passed = 0
    citation_references = 0
    existing_citation_references = 0
    returned_citations = 0
    exact_original_citations = 0
    details = []
    for case in dataset:
        vector = (await embedder.embed([case["question"]]))[0] if embedder else None
        hits = await repository.search(
            case["question"], date.fromisoformat(case["as_of_date"]), 10, vector
        )
        actual = {hit.document_title for hit in hits}
        success = bool(actual.intersection(case["expected_documents"]))
        request = QuestionRequest(
            question=case["question"],
            as_of_date=date.fromisoformat(case["as_of_date"]),
            project_stage=ProjectStage.PLANNING,
        )
        answer = search_only_answer(request, hits)
        existence_rate, original_match_rate = citation_quality(answer, hits)
        references = sum(len(item.citation_ids) for item in [*answer.sections, *answer.checklist])
        citation_references += references
        existing_citation_references += round(existence_rate * references)
        returned_citations += len(answer.citations)
        exact_original_citations += round(original_match_rate * len(answer.citations))
        passed += int(success)
        details.append({"question": case["question"], "passed": success})
    recall_at_10 = passed / len(dataset)
    citation_existence_rate = (
        existing_citation_references / citation_references if citation_references else 0.0
    )
    citation_original_match_rate = (
        exact_original_citations / returned_citations if returned_citations else 0.0
    )
    print(
        json.dumps(
            {
                "recall_at_10": recall_at_10,
                "citation_existence_rate": citation_existence_rate,
                "citation_original_match_rate": citation_original_match_rate,
                "cases": details,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    enforce_quality(recall_at_10, citation_existence_rate, citation_original_match_rate)


if __name__ == "__main__":
    asyncio.run(main())

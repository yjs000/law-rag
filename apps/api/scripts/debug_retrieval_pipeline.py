"""고정 질문셋의 원문·청크·질의·검색 단계와 시간을 JSON으로 기록한다."""

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import text

from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.search_queries import prepare_search_query
from app.settings import get_settings


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parents[1] / "evaluation" / "retrieval-debug-v1.json",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


async def _source_snapshot(repository, expected_documents: list[str]) -> list[dict]:
    async with repository.engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        """SELECT d.exact_title,COUNT(DISTINCT v.id) version_count,
                        COUNT(DISTINCT p.id) provision_count,
                        COUNT(DISTINCT e.provision_id) embedding_count,
                        MAX(v.parser_schema_version) parser_schema_version,
                        MAX(v.collected_at) last_collected_at
                        FROM legal_documents d
                        LEFT JOIN document_versions v ON v.document_id=d.id
                        LEFT JOIN provisions p ON p.version_id=v.id
                        LEFT JOIN provision_embeddings e ON e.provision_id=p.id
                        WHERE d.exact_title IN (
                          SELECT jsonb_array_elements_text(CAST(:titles AS jsonb))
                        ) GROUP BY d.exact_title ORDER BY d.exact_title"""
                    ),
                    {"titles": json.dumps(expected_documents, ensure_ascii=False)},
                )
            )
            .mappings()
            .all()
        )
    by_title = {row["exact_title"]: row for row in rows}
    return [
        {
            "document_title": title,
            "exists": title in by_title,
            "version_count": by_title[title]["version_count"] if title in by_title else 0,
            "provision_count": (
                by_title[title]["provision_count"] if title in by_title else 0
            ),
            "embedding_count": (
                by_title[title]["embedding_count"] if title in by_title else 0
            ),
            "parser_schema_version": (
                by_title[title]["parser_schema_version"] if title in by_title else None
            ),
            "last_collected_at": (
                by_title[title]["last_collected_at"].isoformat()
                if title in by_title and by_title[title]["last_collected_at"]
                else None
            ),
        }
        for title in expected_documents
    ]


async def _environment_snapshot(repository) -> dict:
    async with repository.engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        """SELECT
                        (SELECT version_num FROM alembic_version LIMIT 1) db_revision,
                        (SELECT COUNT(*) FROM legal_documents) document_count,
                        (SELECT COUNT(*) FROM document_versions) version_count,
                        (SELECT COUNT(*) FROM provisions) provision_count,
                        (SELECT COUNT(*) FROM provision_embeddings) embedding_count,
                        (SELECT COUNT(*) FROM evaluation_runs) evaluation_run_count"""
                    )
                )
            )
            .mappings()
            .one()
        )
    return dict(row)


def _load_dataset(dataset_path: Path) -> list[dict]:
    return json.loads(dataset_path.read_text(encoding="utf-8"))


def _top_chunk_metadata(hit, rank: int) -> dict[str, object]:
    return {
        "rank": rank,
        "provision_id": str(hit.provision_id),
        "document_id": str(hit.document_id),
        "document_title": hit.document_title,
        "version_label": hit.version_label,
        "path": hit.path,
        "heading": hit.heading,
        "score": hit.score,
    }


async def _run(cases: list[dict], dataset_path: Path) -> dict:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL이 필요합니다.")
    repository = PostgresLegalRepository(settings.database_url)
    environment = await _environment_snapshot(repository)
    results = []
    for case in cases:
        prepared = prepare_search_query(case["question"])
        hits, trace = await repository.search_with_trace(
            case["question"], date.fromisoformat(case["as_of_date"]), 10, None
        )
        expected = set(case["expected_documents"])
        results.append(
            {
                "id": case.get("id"),
                "question": case["question"],
                "as_of_date": case["as_of_date"],
                "expected_documents": case["expected_documents"],
                "expected_outcome": case.get("expected_outcome", "evidence_expected"),
                "pipeline_version": {
                    "embedding_model": settings.openai_embedding_model,
                    "embedding_dimensions": settings.embedding_dimensions,
                    "ai_enabled": settings.ai_enabled,
                    "query_plan_schema": "four-stage-v1",
                    "parser_schema": "2",
                },
                "source_documents": await _source_snapshot(
                    repository, case["expected_documents"]
                ),
                "query_transform": {
                    "normalized_text": prepared.normalized_text,
                    "terms": list(prepared.terms),
                    "anchor_term": prepared.anchor_term,
                    "strict_query": prepared.strict_query,
                    "minimum_match_query": prepared.minimum_match_query,
                    "anchored_query": prepared.anchored_query,
                },
                "retrieval_trace": trace.as_dict(),
                "generation": {
                    "status": "not_run_retrieval_debug",
                    "llm_response": None,
                },
                "expected_document_retrieved": any(
                    hit.document_title in expected for hit in hits
                ),
                "outcome_passed": (
                    not hits
                    if case.get("expected_outcome") == "no_evidence"
                    else any(hit.document_title in expected for hit in hits)
                ),
                "top_chunks": [
                    _top_chunk_metadata(hit, index)
                    for index, hit in enumerate(hits[:5], 1)
                ],
            }
        )
    durations = sorted(case["retrieval_trace"]["total_duration_ms"] for case in results)
    p50 = durations[(len(durations) - 1) // 2] if durations else 0.0
    p95 = durations[min(len(durations) - 1, round(len(durations) * 0.95))] if durations else 0.0
    await repository.engine.dispose()
    return {
        "schema_version": "1",
        "dataset": str(dataset_path),
        "environment": environment,
        "case_count": len(results),
        "retrieved_expected_count": sum(
            case["expected_document_retrieved"] for case in results
        ),
        "passed_count": sum(case["outcome_passed"] for case in results),
        "under_one_second_count": sum(
            case["retrieval_trace"]["total_duration_ms"] < 1000 for case in results
        ),
        "latency_ms": {
            "minimum": durations[0] if durations else 0.0,
            "p50": p50,
            "p95": p95,
            "maximum": durations[-1] if durations else 0.0,
        },
        "cases": results,
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = _arguments()
    report = asyncio.run(_run(_load_dataset(arguments.dataset), arguments.dataset))
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

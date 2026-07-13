import asyncio
import json
from datetime import date
from pathlib import Path

from app.adapters.openai_embedder import OpenAIEmbedder
from app.adapters.postgres_repository import PostgresLegalRepository
from app.settings import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL이 필요합니다")
    dataset = json.loads(
        (Path(__file__).parents[1] / "evaluation" / "retrieval-v1.json").read_text(encoding="utf-8")
    )
    repository = PostgresLegalRepository(settings.database_url)
    embedder = (
        OpenAIEmbedder(
            api_key=settings.openai_api_key or "",
            model=settings.openai_embedding_model,
            dimensions=settings.embedding_dimensions,
        )
        if settings.ai_enabled
        else None
    )
    passed = 0
    details = []
    for case in dataset:
        vector = (await embedder.embed([case["question"]]))[0] if embedder else None
        hits = await repository.search(
            case["question"], date.fromisoformat(case["as_of_date"]), 10, vector
        )
        actual = {hit.document_title for hit in hits}
        success = bool(actual.intersection(case["expected_documents"]))
        passed += int(success)
        details.append({"question": case["question"], "passed": success})
    recall_at_10 = passed / len(dataset)
    print(
        json.dumps({"recall_at_10": recall_at_10, "cases": details}, ensure_ascii=False, indent=2)
    )
    if recall_at_10 < 0.9:
        raise SystemExit("Recall@10 < 0.90")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
from dataclasses import asdict

from app.adapters.memory_repository import repository
from app.adapters.openai_embedder import OpenAIEmbedder
from app.adapters.postgres_repository import PostgresLegalRepository
from app.adapters.supabase_storage import SupabaseRawStorage
from app.application.ingestion import IngestionService
from app.clients.law_open_api import LawOpenApiClient
from app.settings import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.law_open_api_oc:
        raise SystemExit("LAW_OPEN_API_OC가 필요합니다")
    target_repository = (
        PostgresLegalRepository(settings.database_url) if settings.database_url else repository
    )
    embedder = (
        OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            dimensions=settings.embedding_dimensions,
        )
        if settings.ai_enabled and settings.openai_api_key
        else None
    )
    raw_storage = (
        SupabaseRawStorage(
            url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=settings.supabase_raw_bucket,
        )
        if settings.supabase_url and settings.supabase_service_role_key
        else None
    )
    async with LawOpenApiClient(
        oc=settings.law_open_api_oc,
        base_url=settings.law_open_api_base_url,
        timeout=settings.request_timeout_seconds,
    ) as client:
        results = await IngestionService(
            client, target_repository, embedder, raw_storage
        ).ingest_mvp()
    print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

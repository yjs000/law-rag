import argparse
import asyncio
import json
from collections.abc import Sequence

from law_rag_core.domain.catalog import MVP_CATALOG

from law_rag_collector.client import LawOpenApiClient
from law_rag_collector.ports import resolve
from law_rag_collector.repository import MockCorpusRepository
from law_rag_collector.service import CollectorService
from law_rag_collector.settings import get_settings
from law_rag_collector.supabase_repository import SupabaseCurrentCorpusRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="국가법령정보 Open API 독립 수집기")
    parser.add_argument("command", choices=("sync-current", "sync-history", "status"))
    parser.add_argument(
        "--title",
        help="본문은 허용 목록의 한 문서만 수집한다. 삭제 목록은 전체 manifest에 적용한다.",
    )
    return parser


async def _run(command: str, title: str | None = None) -> int:
    settings = get_settings()
    repository = (
        SupabaseCurrentCorpusRepository(
            database_url=settings.direct_url or settings.database_url or "",
            supabase_url=settings.supabase_url or "",
            supabase_secret_key=settings.supabase_secret_key or "",
            bucket=settings.supabase_raw_bucket,
        )
        if settings.supabase_enabled
        else MockCorpusRepository(settings.collector_state_dir)
    )
    if command == "status":
        print(
            json.dumps(
                await resolve(repository.status()),
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        if isinstance(repository, SupabaseCurrentCorpusRepository):
            await repository.close()
        return 0
    if command == "sync-history" and isinstance(repository, SupabaseCurrentCorpusRepository):
        print(
            json.dumps(
                {"error": "Supabase 연혁·삭제 동기화는 아직 활성화되지 않았습니다"},
                ensure_ascii=False,
            )
        )
        await repository.close()
        return 2
    if not settings.law_open_api_oc:
        print(
            json.dumps(
                {"error": "LAW_OPEN_API_OC가 필요합니다", "command": command},
                ensure_ascii=False,
            )
        )
        return 2
    try:
        async with LawOpenApiClient(
            oc=settings.law_open_api_oc,
            base_url=settings.law_open_api_base_url,
            timeout=settings.collector_request_timeout_seconds,
        ) as client:
            service = CollectorService(client, repository)
            entries = [entry for entry in MVP_CATALOG if title is None or entry.title == title]
            if not entries:
                print(
                    json.dumps(
                        {"error": "허용 목록에 없는 정확 명칭입니다"},
                        ensure_ascii=False,
                    )
                )
                return 2
            results = (
                await service.sync_current(entries)
                if command == "sync-current"
                else await service.sync_history(entries)
            )
    finally:
        if isinstance(repository, SupabaseCurrentCorpusRepository):
            await repository.close()
    failed = [item for item in results if item.state == "failed"]
    reported = (
        results
        if len(results) <= 20
        else [
            item
            for item in results
            if item.state == "failed" or item.title.startswith("삭제 데이터")
        ]
    )
    payload = {
        "command": command,
        "ready": sum(item.state == "ready" for item in results),
        "unchanged": sum(item.state == "unchanged" for item in results),
        "failed": len(failed),
        "results": [item.model_dump(mode="json") for item in reported],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    raise SystemExit(asyncio.run(_run(args.command, args.title)))

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from law_rag_core.domain.catalog import MVP_CATALOG

from law_rag_collector.client import LawOpenApiClient
from law_rag_collector.corpus_preflight import (
    CorpusPreflightSettings,
    preflight_current_corpus,
)
from law_rag_collector.ports import resolve
from law_rag_collector.prepared_publisher import publish_prepared_bundle
from law_rag_collector.repository import MockCorpusRepository
from law_rag_collector.service import CollectorService
from law_rag_collector.settings import get_settings
from law_rag_collector.supabase_repository import SupabaseCurrentCorpusRepository

_CURRENT_EMBEDDING_PROFILE_KEY = "nvidia-nemotron-3-embed-1b-512-v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="국가법령정보 Open API 독립 수집기")
    parser.add_argument(
        "command",
        choices=(
            "apply-prepared",
            "preflight-current",
            "prepare-current",
            "preview-current",
            "sync-current",
            "sync-history",
            "status",
        ),
    )
    parser.add_argument(
        "--title",
        help="본문은 허용 목록의 한 문서만 수집한다. 삭제 목록은 전체 manifest에 적용한다.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="prepare-current 번들을 기록할 비어 있는 디렉터리",
    )
    parser.add_argument(
        "--embedding-profile-key",
        default=_CURRENT_EMBEDDING_PROFILE_KEY,
        help="prepare-current가 후속 임베딩 단계에 고정할 profile key",
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        help=(
            "apply-prepared가 반영하거나 preflight-current가 선택적으로 검증할 "
            "ready bundle 디렉터리"
        ),
    )
    return parser


async def _run(
    command: str,
    title: str | None = None,
    *,
    output: Path | None = None,
    embedding_profile_key: str | None = None,
    bundle: Path | None = None,
) -> int:
    if command == "preflight-current":
        direct_url = CorpusPreflightSettings().direct_url
        if not direct_url:
            print(
                json.dumps(
                    {"error": "preflight-current에는 DIRECT_URL이 필요합니다"},
                    ensure_ascii=False,
                )
            )
            return 2
        try:
            result = await preflight_current_corpus(
                direct_url,
                bundle_path=bundle,
            )
        except Exception as exc:
            detail = str(exc).replace("\r", " ").replace("\n", " ").strip()
            print(
                json.dumps(
                    {
                        "command": command,
                        "state": "failed",
                        "detail": f"{type(exc).__name__}: {detail}"[:300],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        print(
            json.dumps(
                {"command": command, **result},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return 0
    settings = get_settings()
    repository = (
        SupabaseCurrentCorpusRepository(
            database_url=settings.direct_url or "",
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
    if command == "apply-prepared":
        if not isinstance(repository, SupabaseCurrentCorpusRepository):
            print(
                json.dumps(
                    {"error": "apply-prepared는 Supabase corpus에서만 지원합니다"},
                    ensure_ascii=False,
                )
            )
            return 2
        if bundle is None:
            print(
                json.dumps(
                    {"error": "apply-prepared에는 --bundle이 필요합니다"},
                    ensure_ascii=False,
                )
            )
            await repository.close()
            return 2
        try:
            result = await publish_prepared_bundle(repository, bundle)
        except Exception as exc:
            detail = str(exc).replace("\r", " ").replace("\n", " ").strip()
            print(
                json.dumps(
                    {
                        "command": command,
                        "state": "failed",
                        "detail": f"{type(exc).__name__}: {detail}"[:300],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        finally:
            await repository.close()
        print(
            json.dumps(
                {"command": command, **result},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return 0
    if command == "sync-history" and isinstance(repository, SupabaseCurrentCorpusRepository):
        print(
            json.dumps(
                {
                    "error": (
                        "Supabase 과거 버전 전체 수집은 아직 활성화되지 않았습니다. "
                        "공식 삭제 이력은 sync-current에서 반영합니다."
                    )
                },
                ensure_ascii=False,
            )
        )
        await repository.close()
        return 2
    if command == "preview-current" and not isinstance(
        repository, SupabaseCurrentCorpusRepository
    ):
        print(
            json.dumps(
                {"error": "preview-current는 Supabase corpus에서만 지원합니다"},
                ensure_ascii=False,
            )
        )
        return 2
    if command == "prepare-current":
        if not isinstance(repository, SupabaseCurrentCorpusRepository):
            print(
                json.dumps(
                    {"error": "prepare-current는 Supabase corpus에서만 지원합니다"},
                    ensure_ascii=False,
                )
            )
            return 2
        if title is not None:
            print(
                json.dumps(
                    {"error": "prepare-current는 전체 고정 catalog만 준비합니다"},
                    ensure_ascii=False,
                )
            )
            await repository.close()
            return 2
        if output is None or not embedding_profile_key:
            print(
                json.dumps(
                    {
                        "error": (
                            "prepare-current에는 --output이 필요합니다"
                        )
                    },
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
        if isinstance(repository, SupabaseCurrentCorpusRepository):
            await repository.close()
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
            if command == "prepare-current":
                try:
                    bundle = await service.prepare_current(
                        output=output,
                        embedding_profile_key=embedding_profile_key,
                        entries=entries,
                    )
                except Exception as exc:
                    print(
                        json.dumps(
                            {
                                "command": command,
                                "state": "failed",
                                "detail": f"{type(exc).__name__}: {exc}"[:300],
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                    return 1
                print(
                    json.dumps(
                        {
                            "command": command,
                            "state": bundle.manifest.state,
                            "output": str(bundle.root),
                            "base_snapshot_id": bundle.manifest.base_snapshot_id,
                            "counts": bundle.manifest.counts.model_dump(),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            if command == "preview-current":
                async with repository.sync_run_lock():
                    previews = await service.preview_current(entries)
                failed_previews = [item for item in previews if item["state"] == "failed"]
                print(
                    json.dumps(
                        {
                            "command": command,
                            "ready": len(previews) - len(failed_previews),
                            "failed": len(failed_previews),
                            "results": previews,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 1 if failed_previews else 0
            if command == "sync-current" and isinstance(
                repository, SupabaseCurrentCorpusRepository
            ):
                async with repository.sync_run_lock():
                    results = await service.sync_current(entries)
            else:
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    raise SystemExit(
        asyncio.run(
            _run(
                args.command,
                args.title,
                output=args.output,
                embedding_profile_key=args.embedding_profile_key,
                bundle=args.bundle,
            )
        )
    )

import asyncio
import json

from app.clients.law_open_api import LawOpenApiClient
from app.domain.catalog import MVP_CATALOG, SourceKind
from app.settings import get_settings


def error_chain(exc: Exception) -> list[str]:
    errors: list[str] = []
    current: BaseException | None = exc
    while current and len(errors) < 4:
        errors.append(f"{type(current).__name__}: {current}")
        current = current.__cause__
    return errors


async def main() -> None:
    settings = get_settings()
    if not settings.law_open_api_oc:
        raise SystemExit("LAW_OPEN_API_OC가 필요합니다")
    results = []
    async with LawOpenApiClient(
        oc=settings.law_open_api_oc, base_url=settings.law_open_api_base_url
    ) as client:
        for entry in MVP_CATALOG:
            try:
                response = (
                    await client.search_current_law(entry.title)
                    if entry.source_kind is SourceKind.LAW
                    else await client.search_admin_rule(entry.title)
                )
                results.append(
                    {
                        "query": entry.title,
                        "format": response.raw.wire_format,
                        "titles": [item.title for item in response.value[:10]],
                    }
                )
            except Exception as exc:
                results.append({"query": entry.title, "errors": error_chain(exc)})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

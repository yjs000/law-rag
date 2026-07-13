import asyncio
import json

from app.clients.law_open_api import LawOpenApiClient
from app.domain.catalog import SourceKind
from app.settings import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.law_open_api_oc:
        raise SystemExit("LAW_OPEN_API_OC가 필요합니다")
    async with LawOpenApiClient(
        oc=settings.law_open_api_oc, base_url=settings.law_open_api_base_url
    ) as client:
        search = await client.search_current_law("전기사업법")
        exact = [item for item in search.value if item.title == "전기사업법"]
        if len(exact) != 1:
            raise SystemExit(f"정확 명칭 결과가 1건이 아닙니다: {len(exact)}")
        item = exact[0]
        document = await client.get_document(
            expected_title="전기사업법",
            source_kind=SourceKind.LAW,
            source_id=item.source_id,
            mst=item.mst,
        )
    paths = {provision.path for provision in document.value.provisions}
    if len(paths) != len(document.value.provisions):
        raise SystemExit("중복 조문 경로가 있습니다")
    print(
        json.dumps(
            {
                "search_format": search.raw.wire_format,
                "body_format": document.raw.wire_format,
                "fallback_reason": document.raw.fallback_reason,
                "source_id": document.value.source_id,
                "mst": document.value.mst,
                "effective_from": str(document.value.effective_from),
                "provision_count": len(document.value.provisions),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())

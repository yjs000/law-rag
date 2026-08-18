import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from law_rag_llamaindex.source import fetch_provisions

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="requires a live Postgres DATABASE_URL"
)


@pytest.mark.asyncio
async def test_fetch_provisions_returns_expected_fields():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        records = await fetch_provisions(engine)
    finally:
        await engine.dispose()
    assert isinstance(records, list)
    if records:
        record = records[0]
        for key in (
            "provision_id",
            "document_id",
            "document_title",
            "source_kind",
            "law_type_code",
            "version_label",
            "effective_from",
            "effective_to",
            "path",
            "heading",
            "content",
            "source_url",
        ):
            assert key in record

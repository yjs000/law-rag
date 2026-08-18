from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_llamaindex.passage import ProvisionRecord

_PROVISIONS_QUERY = text(
    """
    SELECT p.id AS provision_id, d.id AS document_id, d.exact_title AS document_title,
           d.source_kind, d.law_type_code,
           'MST ' || v.mst AS version_label,
           v.effective_from, v.effective_to,
           p.path, p.heading, p.content, v.source_url
    FROM provisions p
    JOIN document_versions v ON v.id = p.version_id
    JOIN legal_documents d ON d.id = v.document_id
    """
)


async def fetch_provisions(engine: AsyncEngine) -> list[ProvisionRecord]:
    async with engine.connect() as connection:
        result = await connection.execute(_PROVISIONS_QUERY)
        rows = result.mappings().all()
    return [
        {
            "provision_id": str(row["provision_id"]),
            "document_id": str(row["document_id"]),
            "document_title": row["document_title"],
            "source_kind": row["source_kind"],
            "law_type_code": row["law_type_code"],
            "version_label": row["version_label"],
            "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
            "effective_to": row["effective_to"].isoformat() if row["effective_to"] else None,
            "path": row["path"],
            "heading": row["heading"],
            "content": row["content"],
            "source_url": row["source_url"],
        }
        for row in rows
    ]

"""Persistence-level coordination contracts shared by API and collector writers."""

from typing import Final

from law_rag_core.domain.identifiers import PARSER_SCHEMA_VERSION

# All code that changes corpus rows or their derived embeddings must take this
# transaction-scoped PostgreSQL advisory lock.  The literal is a versioned,
# stable signed-bigint key; changing it would create two independent lock
# domains and re-introduce partial corpus/vector visibility.
CORPUS_MUTATION_LOCK_KEY: Final[int] = 5_737_565_776_311_091_201

# A collector CLI holds this session-scoped lock across the complete multi-law
# fetch/sync run. Embedding profile promotion takes the same key transactionally
# before the mutation lock, so it cannot expose a partially refreshed corpus.
CORPUS_SYNC_RUN_LOCK_KEY: Final[int] = 5_737_565_776_311_091_202

# Prevent two NIM/backfill processes from mixing independently generated
# vectors for the same profile while one of them is promoting the profile.
EMBEDDING_BACKFILL_LOCK_KEY: Final[int] = 5_737_565_776_311_091_203

# SQL fragments below intentionally use the canonical aliases ``p``
# (provisions), ``v`` (document_versions), and ``d`` (legal_documents).
# Keeping the legal-provision-v1 text/hash formula in one module prevents the
# writer's staleness check from drifting away from the runtime search gate.
SEARCHABLE_DOCUMENT_VERSION_SQL: Final[str] = f"""v.source_record_state='available'
AND (v.lifecycle_state IN ('active','scheduled')
     OR (v.lifecycle_state='abolished' AND v.effective_to IS NOT NULL))
AND v.parser_schema_version='{PARSER_SCHEMA_VERSION}'"""
LEGAL_PROVISION_V1_SOURCE_SHA_SQL: Final[str] = """encode(digest(concat_ws(E'\\n',
NULLIF(btrim(d.exact_title),''),NULLIF(btrim(p.path),''),
NULLIF(btrim(COALESCE(p.heading,'')),''),NULLIF(btrim(p.content),'')),
'sha256'),'hex')"""


__all__ = [
    "CORPUS_MUTATION_LOCK_KEY",
    "CORPUS_SYNC_RUN_LOCK_KEY",
    "EMBEDDING_BACKFILL_LOCK_KEY",
    "LEGAL_PROVISION_V1_SOURCE_SHA_SQL",
    "SEARCHABLE_DOCUMENT_VERSION_SQL",
]

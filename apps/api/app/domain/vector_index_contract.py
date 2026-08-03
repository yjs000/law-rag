"""Authoritative pgvector HNSW contract for the active NVIDIA profile."""

from __future__ import annotations

from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE

NEMOTRON_HNSW_INDEX_NAME = "provision_embeddings_nemotron_512_hnsw"
NEMOTRON_HNSW_EF_SEARCH = 40
NEMOTRON_HNSW_ITERATIVE_SCAN = "off"
NEMOTRON_HNSW_MAX_SCAN_TUPLES = 20_000
NEMOTRON_HNSW_SCAN_MEM_MULTIPLIER = 1

NEMOTRON_HNSW_READY_SQL = f"""EXISTS(
  SELECT 1
  FROM pg_class c
  JOIN pg_namespace n ON n.oid=c.relnamespace
  JOIN pg_index i ON i.indexrelid=c.oid
  JOIN pg_am am ON am.oid=c.relam
  JOIN pg_attribute index_column
    ON index_column.attrelid=c.oid AND index_column.attnum=1
  JOIN pg_opclass opclass ON opclass.oid=i.indclass[0]
  WHERE n.nspname='public' AND c.relname='{NEMOTRON_HNSW_INDEX_NAME}'
    AND i.indrelid=to_regclass('public.provision_embeddings')
    AND i.indisvalid AND i.indisready
    AND i.indnkeyatts=1
    AND am.amname='hnsw'
    AND opclass.opcname='vector_cosine_ops'
    AND format_type(index_column.atttypid,index_column.atttypmod)='vector(512)'
    AND i.indexprs IS NOT NULL
    AND regexp_replace(
      pg_get_expr(i.indexprs,i.indrelid),'[\\s()]','','g'
    )='embedding::vector512'
    AND i.indpred IS NOT NULL
    AND regexp_replace(
      pg_get_expr(i.indpred,i.indrelid),'[\\s()]','','g'
    ) IN (
      'profile_key=''{NVIDIA_NEMOTRON_512_PROFILE.key}''',
      'profile_key=''{NVIDIA_NEMOTRON_512_PROFILE.key}''::text'
    )
)"""

NEMOTRON_HNSW_STATE_SQL = f"""SELECT
  c.oid::text index_oid,
  pg_relation_filenode(c.oid)::text index_relfilenode,
  pg_relation_size(c.oid) index_size_bytes,
  c.relname index_name,
  i.indrelid::regclass::text indexed_relation,
  i.indnkeyatts key_attribute_count,
  am.amname access_method,
  opclass.opcname operator_class,
  format_type(index_column.atttypid,index_column.atttypmod) indexed_type,
  pg_get_expr(i.indexprs,i.indrelid) index_expression,
  pg_get_expr(i.indpred,i.indrelid) index_predicate,
  i.indisvalid index_valid,
  i.indisready index_ready,
  pg_get_indexdef(c.oid) index_definition,
  {NEMOTRON_HNSW_READY_SQL} contract_ready
FROM pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
JOIN pg_index i ON i.indexrelid=c.oid
JOIN pg_am am ON am.oid=c.relam
JOIN pg_attribute index_column
  ON index_column.attrelid=c.oid AND index_column.attnum=1
JOIN pg_opclass opclass ON opclass.oid=i.indclass[0]
WHERE n.nspname='public' AND c.relname='{NEMOTRON_HNSW_INDEX_NAME}'"""


__all__ = [
    "NEMOTRON_HNSW_EF_SEARCH",
    "NEMOTRON_HNSW_INDEX_NAME",
    "NEMOTRON_HNSW_ITERATIVE_SCAN",
    "NEMOTRON_HNSW_MAX_SCAN_TUPLES",
    "NEMOTRON_HNSW_READY_SQL",
    "NEMOTRON_HNSW_SCAN_MEM_MULTIPLIER",
    "NEMOTRON_HNSW_STATE_SQL",
]

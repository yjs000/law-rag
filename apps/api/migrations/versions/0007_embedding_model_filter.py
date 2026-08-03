"""임베딩 provider별 벡터 공간 격리.

Revision ID: 0007
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


HYBRID_SEARCH_WITH_MODEL = """
CREATE OR REPLACE FUNCTION hybrid_search(
  search_query text, as_of_date date, query_embedding text,
  embedding_model text, result_limit integer
) RETURNS TABLE(
  provision_id uuid, document_id uuid, document_title text, source_kind text,
  version_label text, effective_from date, effective_to date, path text,
  heading text, content text, source_url text, score double precision
) LANGUAGE sql STABLE AS $$
WITH valid AS (
  SELECT p.*,v.document_id,v.mst,v.effective_from,v.effective_to,v.source_url,
         d.exact_title,d.source_kind,p.tableoid provision_tableoid,p.ctid provision_ctid
  FROM provisions p JOIN document_versions v ON v.id=p.version_id
  JOIN legal_documents d ON d.id=v.document_id
  WHERE (v.effective_from IS NULL OR v.effective_from<=as_of_date)
    AND (v.effective_to IS NULL OR v.effective_to>as_of_date)
), keyword AS (
  SELECT v.id,row_number() OVER(ORDER BY
    (CASE WHEN v.exact_title &@~ search_query THEN 3.0 ELSE 0.0 END) +
    (CASE WHEN ARRAY[COALESCE(v.heading,''),v.content] &@~
      (search_query,ARRAY[2,1],'provisions_search_pgroonga')::pgroonga_full_text_search_condition
      THEN GREATEST(pgroonga_score(v.provision_tableoid,v.provision_ctid),1.0)
      ELSE 0.0 END) DESC,
    v.ordinal) rank
  FROM valid v
  WHERE v.exact_title &@~ search_query
     OR ARRAY[COALESCE(v.heading,''),v.content] &@~
       (search_query,ARRAY[2,1],'provisions_search_pgroonga')::pgroonga_full_text_search_condition
  LIMIT 50
), semantic AS (
  SELECT v.id,row_number() OVER(ORDER BY e.embedding <=> query_embedding::vector) rank
  FROM valid v JOIN provision_embeddings e ON e.provision_id=v.id
  WHERE query_embedding IS NOT NULL
    AND embedding_model IS NOT NULL
    AND e.model=embedding_model
    AND e.dimensions=512
    AND e.embedding_version='1'
  LIMIT 50
), fused AS (
  SELECT COALESCE(k.id,s.id) id,
         COALESCE(1.0/(60+k.rank),0)+COALESCE(1.0/(60+s.rank),0) score
  FROM keyword k FULL JOIN semantic s ON s.id=k.id
)
SELECT v.id,v.document_id,v.exact_title,v.source_kind,'MST '||v.mst,
       v.effective_from,v.effective_to,v.path,v.heading,v.content,v.source_url,f.score
FROM fused f JOIN valid v ON v.id=f.id ORDER BY f.score DESC LIMIT result_limit
$$
"""


def upgrade() -> None:
    op.execute(HYBRID_SEARCH_WITH_MODEL)


def downgrade() -> None:
    op.execute("DROP FUNCTION hybrid_search(text,date,text,text,integer)")

"""법령 코퍼스와 하이브리드 검색 기반 스키마.

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgroonga")
    op.execute(
        """
        CREATE TABLE legal_documents (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id text NOT NULL,
          exact_title text NOT NULL, source_kind text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(source_kind,source_id)
        );
        CREATE TABLE document_versions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), document_id uuid NOT NULL REFERENCES legal_documents(id),
          mst text NOT NULL, promulgation_number text, promulgated_on date,
          effective_from date, effective_to date, ministry text, source_url text NOT NULL,
          raw_format text NOT NULL CHECK (raw_format IN ('JSON','XML')), raw_sha256 text NOT NULL,
          raw_storage_path text, parser_schema_version text NOT NULL, fallback_reason text,
          collected_at timestamptz NOT NULL DEFAULT now(), UNIQUE(document_id,mst)
        );
        CREATE TABLE provisions (
          id uuid PRIMARY KEY, version_id uuid NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
          path text NOT NULL, parent_path text, heading text, content text NOT NULL, ordinal integer NOT NULL,
          UNIQUE(version_id,path)
        );
        CREATE TABLE provision_embeddings (
          provision_id uuid NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
          model text NOT NULL, dimensions integer NOT NULL, embedding_version text NOT NULL,
          embedding vector(512) NOT NULL, PRIMARY KEY(provision_id,model,embedding_version)
        );
        CREATE TABLE legal_relationships (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), from_provision_id uuid REFERENCES provisions(id),
          to_provision_id uuid REFERENCES provisions(id), relationship_type text NOT NULL, metadata jsonb NOT NULL DEFAULT '{}'
        );
        CREATE TABLE derived_obligations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provision_id uuid NOT NULL REFERENCES provisions(id),
          actor text, conditions text, obligation_type text NOT NULL, action text NOT NULL, exception_text text,
          extraction_version text NOT NULL, verified boolean NOT NULL DEFAULT false
        );
        CREATE TABLE ingestion_runs (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), started_at timestamptz NOT NULL DEFAULT now(),
          completed_at timestamptz, state text NOT NULL, stats jsonb NOT NULL DEFAULT '{}', error_code text
        );
        CREATE TABLE evaluation_runs (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), created_at timestamptz NOT NULL DEFAULT now(),
          dataset_version text NOT NULL, model text, index_version text NOT NULL, prompt_version text,
          metrics jsonb NOT NULL
        );
        CREATE TABLE runtime_flags (
          key text PRIMARY KEY, value jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE anonymous_usage (
          subject_hash text NOT NULL, usage_date date NOT NULL, kind text NOT NULL,
          count integer NOT NULL CHECK(count>0), PRIMARY KEY(subject_hash,usage_date,kind)
        );
        CREATE INDEX provisions_content_pgroonga ON provisions USING pgroonga (content);
        CREATE INDEX provision_embeddings_hnsw ON provision_embeddings USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX versions_effective_range ON document_versions (effective_from,effective_to);
        CREATE OR REPLACE FUNCTION hybrid_search(
          search_query text, as_of_date date, query_embedding text, result_limit integer
        ) RETURNS TABLE(
          provision_id uuid, document_id uuid, document_title text, source_kind text,
          version_label text, effective_from date, effective_to date, path text,
          heading text, content text, source_url text, score double precision
        ) LANGUAGE sql STABLE AS $$
        WITH valid AS (
          SELECT p.*,v.document_id,v.mst,v.effective_from,v.effective_to,v.source_url,
                 d.exact_title,d.source_kind
          FROM provisions p JOIN document_versions v ON v.id=p.version_id
          JOIN legal_documents d ON d.id=v.document_id
          WHERE (v.effective_from IS NULL OR v.effective_from<=as_of_date)
            AND (v.effective_to IS NULL OR v.effective_to>as_of_date)
        ), keyword AS (
          SELECT v.id,row_number() OVER(ORDER BY pgroonga_score(p.tableoid,p.ctid) DESC) rank
          FROM provisions p JOIN valid v ON v.id=p.id
          WHERE p.content &@~ search_query LIMIT 50
        ), semantic AS (
          SELECT v.id,row_number() OVER(ORDER BY e.embedding <=> query_embedding::vector) rank
          FROM valid v JOIN provision_embeddings e ON e.provision_id=v.id
          WHERE query_embedding IS NOT NULL LIMIT 50
        ), fused AS (
          SELECT COALESCE(k.id,s.id) id,
                 COALESCE(1.0/(60+k.rank),0)+COALESCE(1.0/(60+s.rank),0) score
          FROM keyword k FULL JOIN semantic s ON s.id=k.id
        )
        SELECT v.id,v.document_id,v.exact_title,v.source_kind,'MST '||v.mst,
               v.effective_from,v.effective_to,v.path,v.heading,v.content,v.source_url,f.score
        FROM fused f JOIN valid v ON v.id=f.id ORDER BY f.score DESC LIMIT result_limit;
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS anonymous_usage,runtime_flags,evaluation_runs,ingestion_runs,derived_obligations,"
        "legal_relationships,provision_embeddings,provisions,document_versions,legal_documents CASCADE"
    )

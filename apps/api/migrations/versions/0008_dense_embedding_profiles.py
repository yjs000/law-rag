"""dense-only 검색을 위한 임베딩 프로필과 벡터 저장 계약.

Revision ID: 0008
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

NVIDIA_PROFILE_KEY = "nvidia-nemotron-3-embed-1b-512-v1"


def upgrade() -> None:
    statements = [
        "DROP FUNCTION IF EXISTS hybrid_search(text,date,text,integer)",
        "DROP FUNCTION IF EXISTS hybrid_search(text,date,text,text,integer)",
        "ALTER TABLE provision_embeddings RENAME TO provision_embeddings_legacy",
        """
        CREATE TABLE embedding_profiles (
          profile_key text PRIMARY KEY,
          provider text NOT NULL,
          model text NOT NULL,
          native_dimensions integer NOT NULL CHECK(native_dimensions>0),
          stored_dimensions integer NOT NULL CHECK(stored_dimensions>0),
          document_input_type text NOT NULL,
          query_input_type text NOT NULL,
          truncation text NOT NULL,
          normalization text NOT NULL,
          text_template_version text NOT NULL,
          profile_version text NOT NULL,
          active boolean NOT NULL DEFAULT false,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(profile_key,stored_dimensions),
          UNIQUE(provider,model,stored_dimensions,text_template_version,profile_version)
        )
        """,
        """
        CREATE TABLE provision_embeddings (
          provision_id uuid NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
          profile_key text NOT NULL,
          dimensions integer NOT NULL CHECK(dimensions>0),
          source_text_sha256 text NOT NULL CHECK(source_text_sha256 ~ '^[0-9a-f]{64}$'),
          embedding vector NOT NULL,
          embedded_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(provision_id,profile_key),
          FOREIGN KEY(profile_key,dimensions)
            REFERENCES embedding_profiles(profile_key,stored_dimensions),
          CHECK(vector_dims(embedding)=dimensions),
          CHECK(vector_norm(embedding)>0)
        )
        """,
        f"""
        INSERT INTO embedding_profiles(
          profile_key,provider,model,native_dimensions,stored_dimensions,
          document_input_type,query_input_type,truncation,normalization,
          text_template_version,profile_version,active
        ) VALUES(
          '{NVIDIA_PROFILE_KEY}','nvidia','nvidia/nemotron-3-embed-1b',2048,512,
          'passage','query','first_512','l2','legal-provision-v1','1',true
        )
        """,
        """
        INSERT INTO embedding_profiles(
          profile_key,provider,model,native_dimensions,stored_dimensions,
          document_input_type,query_input_type,truncation,normalization,
          text_template_version,profile_version,active
        )
        SELECT DISTINCT
          'legacy:'||encode(digest(model||E'\\x1f'||dimensions::text||E'\\x1f'||embedding_version,'sha256'),'hex'),
          'legacy',model,dimensions,dimensions,'unknown','unknown','unknown','unknown',
          'legacy-unknown',embedding_version,false
        FROM provision_embeddings_legacy
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO provision_embeddings(
          provision_id,profile_key,dimensions,source_text_sha256,embedding
        )
        SELECT legacy.provision_id,
          'legacy:'||encode(digest(legacy.model||E'\\x1f'||legacy.dimensions::text||E'\\x1f'||legacy.embedding_version,'sha256'),'hex'),
          legacy.dimensions,encode(digest(p.content,'sha256'),'hex'),legacy.embedding
        FROM provision_embeddings_legacy legacy
        JOIN provisions p ON p.id=legacy.provision_id
        """,
        "DROP TABLE provision_embeddings_legacy",
        """
        CREATE INDEX provision_embeddings_profile_source_sha
        ON provision_embeddings(profile_key,source_text_sha256)
        """,
        f"""
        CREATE INDEX provision_embeddings_nemotron_512_hnsw
        ON provision_embeddings
        USING hnsw ((embedding::vector(512)) vector_cosine_ops)
        WHERE profile_key='{NVIDIA_PROFILE_KEY}'
        """,
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError(
        "0008 removes ambiguous hybrid functions and records vector provenance; "
        "automatic downgrade would discard that provenance"
    )

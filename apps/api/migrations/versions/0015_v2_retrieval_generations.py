"""Catalog immutable LlamaIndex vector generations and their active pointer.

Revision ID: 0015
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE llamaindex_retrieval_generations (
          generation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          physical_table_name text NOT NULL UNIQUE
            CHECK(physical_table_name ~ '^law_rag_li_[a-f0-9]{32}$'),
          source_fingerprint text NOT NULL
            CHECK(source_fingerprint ~ '^[a-f0-9]{64}$'),
          transform_fingerprint text NOT NULL
            CHECK(transform_fingerprint ~ '^[a-f0-9]{64}$'),
          status text NOT NULL
            CHECK(status IN ('building','verified','active','rollback','failed')),
          source_count integer NOT NULL DEFAULT 0 CHECK(source_count >= 0),
          node_count integer NOT NULL DEFAULT 0 CHECK(node_count >= 0),
          failure_code text,
          created_at timestamptz NOT NULL DEFAULT now(),
          verified_at timestamptz,
          published_at timestamptz,
          CHECK((status = 'failed') = (failure_code IS NOT NULL)),
          CHECK(status NOT IN ('verified','active','rollback') OR verified_at IS NOT NULL),
          CHECK(status NOT IN ('active','rollback') OR published_at IS NOT NULL)
        )
        """,
        """
        CREATE TABLE llamaindex_generation_sources (
          generation_id uuid NOT NULL
            REFERENCES llamaindex_retrieval_generations(generation_id) ON DELETE CASCADE,
          provision_id uuid NOT NULL,
          source_fingerprint text NOT NULL
            CHECK(source_fingerprint ~ '^[a-f0-9]{64}$'),
          node_count integer NOT NULL CHECK(node_count >= 0),
          copied_from_generation_id uuid
            REFERENCES llamaindex_retrieval_generations(generation_id),
          PRIMARY KEY(generation_id,provision_id)
        )
        """,
        """
        CREATE TABLE llamaindex_active_generation (
          singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
          generation_id uuid NOT NULL UNIQUE
            REFERENCES llamaindex_retrieval_generations(generation_id),
          updated_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE INDEX llamaindex_retrieval_generations_status_created
        ON llamaindex_retrieval_generations(status,created_at DESC)
        """,
        """
        CREATE UNIQUE INDEX llamaindex_retrieval_generations_one_active
        ON llamaindex_retrieval_generations(status)
        WHERE status = 'active'
        """,
        """
        CREATE INDEX llamaindex_generation_sources_source_fingerprint
        ON llamaindex_generation_sources(source_fingerprint)
        """,
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS llamaindex_active_generation")
    op.execute("DROP TABLE IF EXISTS llamaindex_generation_sources")
    op.execute("DROP TABLE IF EXISTS llamaindex_retrieval_generations")

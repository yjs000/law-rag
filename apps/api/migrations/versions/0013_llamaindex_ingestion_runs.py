"""v2 LlamaIndex 파이프라인의 ingestion 완료 마커 테이블.

Revision ID: 0013
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE law_rag_llamaindex_ingestion_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            node_count integer NOT NULL DEFAULT 0,
            status text NOT NULL CHECK (status IN ('running', 'completed', 'failed'))
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS law_rag_llamaindex_ingestion_runs")

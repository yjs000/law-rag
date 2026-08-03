"""Add a model-independent fail-closed corpus search readiness gate.

Revision ID: 0010
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_FLAG_KEY = "corpus.search_ready"
_CAPABILITY_KEY = "schema.corpus_search_ready_v1"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO runtime_flags(key,value,updated_at)
        VALUES(
          '{_CAPABILITY_KEY}',
          jsonb_build_object('enabled',false,'migration','0010'),
          now()
        )
        ON CONFLICT(key) DO UPDATE
        SET value=excluded.value,updated_at=now()
        """
    )
    op.execute(
        f"""
        INSERT INTO runtime_flags(key,value,updated_at)
        VALUES(
          '{_FLAG_KEY}',
          jsonb_build_object('ready',false,'reason','migration_0010'),
          now()
        )
        ON CONFLICT(key) DO UPDATE
        SET value=excluded.value,updated_at=now()
        """
    )
    op.execute(
        f"""
        UPDATE runtime_flags
        SET value=jsonb_build_object('enabled',true,'migration','0010'),updated_at=now()
        WHERE key='{_CAPABILITY_KEY}'
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "runtime retrieval depends on the corpus.search_ready fail-closed gate"
    )

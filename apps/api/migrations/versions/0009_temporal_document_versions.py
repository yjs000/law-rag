"""법령 버전의 시간 효력과 출처 레코드 상태를 분리한다.

Revision ID: 0009
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM document_versions WHERE effective_from IS NULL
          ) THEN
            RAISE EXCEPTION
              'document_versions.effective_from must be populated before migration 0009';
          END IF;
          IF EXISTS (
            SELECT 1
            FROM document_versions
            WHERE effective_to IS NOT NULL AND effective_to <= effective_from
          ) THEN
            RAISE EXCEPTION
              'document_versions contains a non-positive effective period';
          END IF;
          IF EXISTS (
            SELECT document_id
            FROM document_versions
            WHERE effective_to IS NULL
            GROUP BY document_id
            HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION
              'document_versions contains more than one open version for a document';
          END IF;
        END
        $$
        """,
        """
        ALTER TABLE document_versions
          ADD COLUMN lifecycle_state text,
          ADD COLUMN source_record_state text,
          ADD COLUMN source_deleted_on date,
          ADD COLUMN has_supplementary_provisions boolean
        """,
        """
        UPDATE document_versions
        SET lifecycle_state='active',
            source_record_state='available',
            has_supplementary_provisions=false
        """,
        """
        UPDATE embedding_profiles SET active=false
        """,
        """
        ALTER TABLE document_versions
          ALTER COLUMN lifecycle_state SET NOT NULL,
          ALTER COLUMN source_record_state SET NOT NULL,
          ALTER COLUMN has_supplementary_provisions SET NOT NULL,
          ADD CONSTRAINT document_versions_lifecycle_state_check
            CHECK (lifecycle_state IN ('active','scheduled','abolished')),
          ADD CONSTRAINT document_versions_source_record_state_check
            CHECK (source_record_state IN ('available','deleted')),
          ADD CONSTRAINT document_versions_effective_period_check
            CHECK (effective_to IS NULL OR effective_to > effective_from)
        """,
        """
        ALTER TABLE document_versions
          ALTER COLUMN effective_from SET NOT NULL
        """,
        """
        ALTER TABLE document_versions
          DROP CONSTRAINT document_versions_document_id_mst_key,
          ADD CONSTRAINT document_versions_document_mst_effective_from_key
            UNIQUE (document_id,mst,effective_from)
        """,
        """
        CREATE UNIQUE INDEX document_versions_one_open_per_document
        ON document_versions(document_id)
        WHERE effective_to IS NULL
        """,
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError(
        "0009 permits one MST to have multiple effective dates; reverting to the old "
        "document_id/MST key could discard version identity"
    )

"""법제처 API의 법종구분(코드)을 legal_documents에 저장한다.

Revision ID: 0012
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE legal_documents "
        "ADD COLUMN law_type_name text, ADD COLUMN law_type_code text"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE legal_documents DROP COLUMN law_type_name, DROP COLUMN law_type_code"
    )

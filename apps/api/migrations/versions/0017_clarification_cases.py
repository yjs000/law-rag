"""Persist private clarification conversation state.

Revision ID: 0017
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE clarification_cases (
          case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          owner_scope text NOT NULL,
          capability_hash text,
          original_question text NOT NULL,
          as_of_date date NOT NULL,
          project_stage text NOT NULL,
          conversation_id uuid,
          facts jsonb NOT NULL DEFAULT '[]'::jsonb,
          status text NOT NULL CHECK(status IN ('waiting_for_user','completed','cancelled','expired')),
          version integer NOT NULL DEFAULT 0 CHECK(version >= 0),
          expires_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX clarification_cases_status_expires_at ON clarification_cases(status,expires_at)"
    )
    # Optimistic writes use: WHERE case_id=:case_id AND version=:expected_version.


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS clarification_cases")

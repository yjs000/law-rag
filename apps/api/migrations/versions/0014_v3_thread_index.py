"""v3 LangGraph 에이전트의 (user_id, thread_id) 최소 인덱스.

Revision ID: 0014
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE v3_agent_threads (
          thread_id uuid PRIMARY KEY,
          user_id uuid REFERENCES user_profiles(id) ON DELETE CASCADE,
          created_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    op.execute("CREATE INDEX v3_agent_threads_user_id_idx ON v3_agent_threads (user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS v3_agent_threads_user_id_idx")
    op.execute("DROP TABLE IF EXISTS v3_agent_threads")

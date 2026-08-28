"""Persist idempotent v2 question executions and provider capacity leases.

Revision ID: 0016
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE question_executions (
          execution_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          owner_scope text NOT NULL,
          prepare_idempotency_key text NOT NULL,
          capability_hash text,
          generation_id uuid NOT NULL
            REFERENCES llamaindex_retrieval_generations(generation_id),
          status text NOT NULL CHECK(status IN (
            'prepared','core_running','core_answered','core_repair_required',
            'finalize_running','phase_recovery_required','completed','failed','cancelled','expired'
          )),
          version integer NOT NULL DEFAULT 0 CHECK(version >= 0),
          private_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
          frozen_citations jsonb NOT NULL DEFAULT '[]'::jsonb,
          verified_response jsonb,
          phase_deadline_at timestamptz,
          outcome text,
          expires_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(owner_scope,prepare_idempotency_key)
        )
        """,
        """
        CREATE TABLE question_execution_events (
          execution_id uuid NOT NULL REFERENCES question_executions(execution_id) ON DELETE CASCADE,
          phase text NOT NULL CHECK(phase IN ('prepare','core','finalize')),
          sequence integer NOT NULL CHECK(sequence >= 0),
          event_type text NOT NULL,
          public_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(execution_id,phase,sequence)
        )
        """,
        """
        CREATE TABLE question_execution_issues (
          issue_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          execution_id uuid NOT NULL REFERENCES question_executions(execution_id) ON DELETE CASCADE,
          phase text NOT NULL CHECK(phase IN ('prepare','core','finalize')),
          stage text NOT NULL,
          public_reason_code text NOT NULL,
          recoverable boolean NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE provider_capacity_leases (
          lease_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          provider text NOT NULL,
          slot integer NOT NULL CHECK(slot >= 0),
          execution_id uuid REFERENCES question_executions(execution_id) ON DELETE CASCADE,
          phase text NOT NULL CHECK(phase IN ('core','finalize')),
          expires_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(provider,slot),
          UNIQUE(execution_id,phase)
        )
        """,
        """
        CREATE INDEX question_executions_status_expires_at
        ON question_executions(status,expires_at)
        """,
        """
        CREATE INDEX question_execution_events_execution_phase
        ON question_execution_events(execution_id,phase,sequence)
        """,
        """
        CREATE INDEX provider_capacity_leases_expires_at
        ON provider_capacity_leases(expires_at)
        """,
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS provider_capacity_leases")
    op.execute("DROP TABLE IF EXISTS question_execution_issues")
    op.execute("DROP TABLE IF EXISTS question_execution_events")
    op.execute("DROP TABLE IF EXISTS question_executions")

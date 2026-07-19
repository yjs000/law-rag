import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "0006_history_retention_job.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location("history_retention_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_retention_migration_records_auditable_cleanup(monkeypatch) -> None:
    migration = load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = "\n".join(statements)
    assert migration.revision == "0006"
    assert migration.down_revision == "0005"
    assert "CREATE TABLE public.history_retention_runs" in sql
    assert "cutoff_at timestamptz NOT NULL" in sql
    assert "status text NOT NULL" in sql
    assert "expired_history_deleted integer NOT NULL" in sql
    assert "checklist_exports_deleted integer NOT NULL" in sql
    assert "conversations_updated integer NOT NULL" in sql
    assert "conversations_deleted integer NOT NULL" in sql
    assert "error_code text" in sql
    assert "CREATE OR REPLACE FUNCTION public.purge_expired_question_history" in sql
    assert "expires_at <= p_cutoff_at" in sql
    assert "FROM public.conversations c" in sql
    assert "ORDER BY c.id" in sql
    assert "FOR UPDATE" in sql
    assert sql.index("FROM public.conversations c") < sql.index(
        "DELETE FROM public.question_history"
    )
    assert "DELETE FROM public.checklist_exports e" in sql
    assert "RETURNING e.id" in sql
    assert "INTO v_exports_deleted FROM deleted_exports" in sql
    assert "JOIN public.question_history q ON q.id=e.history_id" not in sql
    assert "DELETE FROM public.question_history" in sql
    assert "DELETE FROM public.conversations" in sql
    assert "turn_count=(SELECT count(*) FROM public.question_history" in sql
    assert "last_turn_id=(SELECT id FROM public.question_history" in sql
    assert "status='succeeded'" in sql
    assert "status='failed'" in sql
    assert "p_cutoff_at > pg_catalog.clock_timestamp()" in sql
    assert "ERRCODE = '22023'" in sql
    assert "GET STACKED DIAGNOSTICS" not in sql
    assert "SQLERRM" not in sql


def test_retention_migration_is_serialized_idempotent_and_scheduler_neutral(
    monkeypatch,
) -> None:
    migration = load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = "\n".join(statements)
    assert "pg_advisory_xact_lock" in sql
    assert "ON DELETE CASCADE" in migration.CASCADE_CONTRACT
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "SECURITY DEFINER" in sql
    assert "SET search_path = pg_catalog, public, pg_temp" in sql
    assert "REVOKE ALL ON TABLE public.history_retention_runs" in sql
    assert "REVOKE ALL ON SEQUENCE public.history_retention_runs_id_seq" in sql
    assert "REVOKE ALL ON FUNCTION public.purge_expired_question_history" in sql
    assert "FROM PUBLIC, anon, authenticated" in sql
    assert "GRANT EXECUTE ON FUNCTION public.purge_expired_question_history" in sql
    assert "GRANT SELECT ON TABLE public.history_retention_runs TO service_role" in sql
    assert "DELETE FROM public.checklist_exports e" in sql
    assert "USING public.question_history q" in sql
    assert "TO anon, authenticated" not in sql
    assert "CREATE EXTENSION" not in sql.upper()
    assert "cron.schedule" not in sql
    assert "pg_cron" not in sql

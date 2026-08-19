import importlib.util
from pathlib import Path

MIGRATION_PATH = Path(__file__).parents[1] / "migrations" / "versions" / "0014_v3_thread_index.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("v3_thread_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_v3_thread_migration_has_expected_revision_and_schema(monkeypatch) -> None:
    migration = load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    assert migration.revision == "0014"
    assert migration.down_revision == "0013"
    assert statements == [
        """CREATE TABLE v3_agent_threads (
          thread_id uuid PRIMARY KEY,
          user_id uuid REFERENCES user_profiles(id) ON DELETE CASCADE,
          created_at timestamptz NOT NULL DEFAULT now()
        )""",
        "CREATE INDEX v3_agent_threads_user_id_idx ON v3_agent_threads (user_id)",
    ]


def test_v3_thread_migration_downgrade_drops_index_before_table(monkeypatch) -> None:
    migration = load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.downgrade()

    assert statements == [
        "DROP INDEX IF EXISTS v3_agent_threads_user_id_idx",
        "DROP TABLE IF EXISTS v3_agent_threads",
    ]

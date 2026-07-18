import importlib.util
from pathlib import Path


def test_initial_migration_executes_one_ddl_command_at_a_time(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[1] / "migrations" / "versions" / "0001_legal_corpus.py"
    )
    spec = importlib.util.spec_from_file_location("initial_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    assert len(statements) == 17
    assert all(statement.upper().count("CREATE TABLE") <= 1 for statement in statements)
    assert sum("CREATE TABLE" in statement.upper() for statement in statements) == 10


def test_retrieval_migration_indexes_title_heading_and_content(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0004_retrieval_diagnostics.py"
    )
    spec = importlib.util.spec_from_file_location("retrieval_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = "\n".join(statements)
    assert "question_history ADD COLUMN diagnostics jsonb" in sql
    assert "legal_documents USING pgroonga(exact_title)" in sql
    assert "provisions USING pgroonga(heading,content)" in sql
    assert "ARRAY[COALESCE(v.heading,''),v.content]" in sql

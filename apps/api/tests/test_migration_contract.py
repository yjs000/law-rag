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

import importlib.util
from pathlib import Path

from sqlalchemy import text


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


def test_conversation_migration_backfills_ownership_and_cursor_indexes(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0005_conversation_history.py"
    )
    spec = importlib.util.spec_from_file_location("conversation_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = "\n".join(statements)
    assert "CREATE TABLE conversations" in sql
    assert "SELECT id,user_id" in sql
    assert "FOREIGN KEY(conversation_id,user_id)" in sql
    assert "conversations_user_updated_id" in sql
    assert "question_history_conversation_turn_id" in sql
    assert "CREATE POLICY own_conversations" in sql


def test_dense_profile_migration_removes_hybrid_and_tracks_vector_provenance(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0008_dense_embedding_profiles.py"
    )
    spec = importlib.util.spec_from_file_location("dense_profile_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = "\n".join(statements)
    assert "DROP FUNCTION IF EXISTS hybrid_search(text,date,text,integer)" in sql
    assert "DROP FUNCTION IF EXISTS hybrid_search(text,date,text,text,integer)" in sql
    assert "CREATE TABLE embedding_profiles" in sql
    assert "source_text_sha256" in sql
    assert "CHECK(vector_dims(embedding)=dimensions)" in sql
    assert "embedding::vector(512)" in sql
    assert "WHERE profile_key='nvidia-nemotron-3-embed-1b-512-v1'" in sql
    assert "CREATE OR REPLACE FUNCTION hybrid_search" not in sql


def test_temporal_version_migration_enforces_version_identity_and_state(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0009_temporal_document_versions.py"
    )
    spec = importlib.util.spec_from_file_location("temporal_version_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = "\n".join(statements)
    assert migration.revision == "0009"
    assert migration.down_revision == "0008"
    assert "effective_from IS NULL" in statements[0]
    assert "effective_to <= effective_from" in statements[0]
    assert "HAVING count(*) > 1" in statements[0]
    assert "ADD COLUMN lifecycle_state text" in sql
    assert "ADD COLUMN source_record_state text" in sql
    assert "source_deleted_on date" in sql
    assert "ADD COLUMN has_supplementary_provisions boolean" in sql
    assert "SET lifecycle_state='active'" in sql
    assert "source_record_state='available'" in sql
    assert "has_supplementary_provisions=false" in sql
    assert "UPDATE embedding_profiles SET active=false" in sql
    assert "ALTER COLUMN lifecycle_state SET NOT NULL" in sql
    assert "ALTER COLUMN source_record_state SET NOT NULL" in sql
    assert "ALTER COLUMN has_supplementary_provisions SET NOT NULL" in sql
    assert "DEFAULT 'active'" not in sql
    assert "DEFAULT 'available'" not in sql
    assert "lifecycle_state IN ('active','scheduled','abolished')" in sql
    assert "source_record_state IN ('available','deleted')" in sql
    assert "effective_to IS NULL OR effective_to > effective_from" in sql
    assert "ALTER COLUMN effective_from SET NOT NULL" in sql
    assert "DROP CONSTRAINT document_versions_document_id_mst_key" in sql
    assert "UNIQUE (document_id,mst,effective_from)" in sql
    assert "CREATE UNIQUE INDEX document_versions_one_open_per_document" in sql
    assert "WHERE effective_to IS NULL" in sql
    assert "EXCLUDE" not in sql.upper()


def test_corpus_search_readiness_migration_starts_fail_closed(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0010_corpus_search_readiness.py"
    )
    spec = importlib.util.spec_from_file_location("corpus_readiness_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = "\n".join(statements)
    assert migration.revision == "0010"
    assert migration.down_revision == "0009"
    assert "INSERT INTO runtime_flags" in sql
    assert "schema.corpus_search_ready_v1" in sql
    assert "corpus.search_ready" in sql
    assert "jsonb_build_object('ready',false" in sql
    assert "jsonb_build_object('enabled',true" in sql
    assert "ON CONFLICT(key) DO UPDATE" in sql
    assert all("false" not in text(statement)._bindparams for statement in statements)


def test_retrieval_catalog_migration_tracks_independent_generations(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0011_retrieval_catalog.py"
    )
    spec = importlib.util.spec_from_file_location("retrieval_catalog_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = "\n".join(statements)
    assert migration.revision == "0011"
    assert migration.down_revision == "0010"
    assert "CREATE TABLE corpus_snapshots" in sql
    assert "CREATE TABLE retrieval_profiles" in sql
    assert "CREATE TABLE retrieval_index_builds" in sql
    assert "CREATE TABLE retrieval_configurations" in sql
    assert "CREATE TABLE retrieval_configuration_members" in sql
    assert "CREATE TABLE retrieval_releases" in sql
    assert "CREATE TABLE retrieval_release_builds" in sql
    assert "CREATE TABLE active_retrieval_release" in sql
    assert "embedding_profile_key text REFERENCES embedding_profiles(profile_key)" in sql
    assert "FOREIGN KEY(build_id,profile_key,snapshot_id)" in sql
    assert "FOREIGN KEY(release_key,configuration_key,snapshot_id)" in sql
    assert "FOREIGN KEY(configuration_key,profile_key)" in sql
    assert "FOREIGN KEY(release_key,release_state)" in sql
    assert "FOREIGN KEY(retrieval_release_key,corpus_snapshot_id)" in sql
    assert "retrieval_release_key IS NULL OR corpus_snapshot_id IS NOT NULL" in sql
    assert "CHECK(release_state='ready')" in sql
    assert "UNIQUE(configuration_key,ordinal)" in sql
    assert "ADD COLUMN dataset_sha256 text" in sql
    assert "ADD COLUMN code_sha256 text" in sql
    assert "ADD COLUMN corpus_snapshot_id text" in sql
    assert "ADD COLUMN retrieval_release_key text" in sql
    assert "schema.retrieval_catalog_v1" in sql
    assert "retrieval_index_builds_profile_snapshot_state" in sql
    assert "retrieval_releases_snapshot_state" in sql
    assert "evaluation_runs_retrieval_provenance" in sql
    assert "USING hnsw" not in sql
    assert "bm25" not in sql.lower()
    assert "rrf" not in sql.lower()


def test_law_type_classification_migration_adds_legal_documents_columns(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0012_law_type_classification.py"
    )
    spec = importlib.util.spec_from_file_location("law_type_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = "\n".join(statements)
    assert migration.revision == "0012"
    assert migration.down_revision == "0011"
    assert "ALTER TABLE legal_documents" in sql
    assert "ADD COLUMN law_type_name text" in sql
    assert "ADD COLUMN law_type_code text" in sql

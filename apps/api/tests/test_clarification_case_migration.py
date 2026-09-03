from pathlib import Path


def test_clarification_case_migration_has_private_state_and_expiry_contract() -> None:
    migration = (
        Path(__file__).parents[1] / "migrations" / "versions" / "0017_clarification_cases.py"
    )
    source = migration.read_text(encoding="utf-8")
    assert "CREATE TABLE clarification_cases" in source
    assert "capability_hash" in source
    assert "as_of_date" in source
    assert "project_stage" in source
    assert "conversation_id" in source
    assert "facts jsonb" in source
    assert "version integer" in source
    assert "expires_at timestamptz" in source
    assert "clarification_cases_status_expires_at" in source
    assert "AND version=:expected_version" in source

import json
import logging

from app.observability import emit_execution_phase


def test_v2_execution_observability_hashes_identifiers_and_excludes_private_content(
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="law_rag.execution_phase")
    emit_execution_phase("execution-with-private-question-never-here", "core", "completed")

    payload = json.loads(caplog.records[-1].message)

    assert payload["phase"] == "core"
    assert payload["outcome"] == "completed"
    assert len(payload["execution_correlation"]) == 16
    assert "execution-with-private-question-never-here" not in caplog.records[-1].message

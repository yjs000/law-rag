from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.experiment_d_10_frozen_contract import (
    DEFAULT_CONTRACT,
    FrozenCase,
    FrozenD10ContractError,
    load_frozen_contract,
    preflight_frozen_d10,
)


def test_tracked_frozen_contract_seals_ten_user_confirmed_cases() -> None:
    contract = load_frozen_contract()

    assert contract.artifact_class == "frozen_small_sample_evaluation_not_full_gold"
    assert len(contract.cases) == 10
    assert contract.cases[0].case_id == "lay-energy-0201"
    assert contract.cases[-1].case_id == "lay-energy-0943"
    assert "full_gold" in contract.prohibited_claims
    assert contract.run_binding.eligible_provision_count == 3066


def test_frozen_case_rejects_direct_evidence_for_unanswerable_case() -> None:
    with pytest.raises(ValidationError, match="cannot freeze direct evidence"):
        FrozenCase(
            case_id="case-1",
            question_sha256="a" * 64,
            question_scope_sha256="b" * 64,
            final_verdict="not_answerable_from_current_corpus",
            context_verdict="blocked",
            direct_evidence_provision_ids=["provision-1"],
            known_irrelevant_top5_provision_ids=[],
        )


def test_frozen_contract_rejects_payload_drift(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    payload["allowed_metrics"].append("unfrozen_metric")
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(FrozenD10ContractError, match="payload SHA-256 mismatch"):
        load_frozen_contract(contract_path)


@pytest.mark.skipif(
    not (DEFAULT_CONTRACT.parents[2] / ".data" / "experiments" / "d-manual").exists(),
    reason="local confirmed D-10 artifacts are intentionally not tracked",
)
def test_local_frozen_artifacts_pass_full_preflight() -> None:
    result = preflight_frozen_d10()

    assert result["status"] == "valid"
    assert result["question_count"] == 10
    assert result["external_calls"] == 0
    assert result["m3_calibration_ready"] is True

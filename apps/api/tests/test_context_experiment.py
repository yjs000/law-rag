import hashlib
import json
from pathlib import Path

import pytest

import scripts.experiment_context as context_module
from scripts.experiment_context import (
    ContextRecordingError,
    build_context_package,
    record_context_result,
)


def _chunk(path: str, content: str, parent_path: str | None, ordinal: int) -> dict[str, object]:
    return {
        "chunk_id": f"source:mst:{path}",
        "ordinal": ordinal,
        "title": "시험법",
        "source_id": "source",
        "mst": "mst",
        "effective_from": "2026-01-01",
        "source_url": "https://example.test/source",
        "path": path,
        "parent_path": parent_path,
        "heading": "시험",
        "content": content,
    }


def _search(question: str, *, include_expected: bool = True) -> dict[str, object]:
    candidates = []
    if include_expected:
        candidates.append(
            {
                "rank": 1,
                "title": "시험법",
                "article_path": "제1조",
            }
        )
    return {
        "question": question,
        "article_candidates": candidates,
    }


def _case(scope: str = "in_scope") -> dict[str, object]:
    return {
        "id": "purpose",
        "question": "시험법의 목적은?",
        "scope": scope,
        "expected_title": "시험법",
        "expected_article_path": "제1조",
        "required_evidence_terms": ["국민의 권리", "공공복리"],
    }


def _corpus() -> dict[str, object]:
    return {
        "chunks": [
            _chunk("제1조", "제1조(목적)", None, 1),
            _chunk("제1조/항①", "① 국민의 권리와 공공복리를 보호한다.", "제1조", 2),
        ]
    }


def test_builds_full_article_hierarchy_when_required_evidence_is_present() -> None:
    result = build_context_package(
        _search("시험법의 목적은?"),
        _corpus(),
        _case(),
        search_run=3,
        corpus_sha256="sha",
        generated_at="2026-08-03T04:00:00Z",
    )

    assert result["status"] == "ready"
    assert result["reason"] is None
    assert result["expected_article_rank"] == 1
    assert result["safety"]["cosine_threshold_used"] is False
    bundle = result["evidence_bundles"][0]
    assert [chunk["path"] for chunk in bundle["chunks"]] == ["제1조", "제1조/항①"]
    assert bundle["chunks"][1]["parent_path"] == "제1조"


def test_missing_required_text_is_insufficient_even_when_article_was_retrieved() -> None:
    corpus = _corpus()
    corpus["chunks"][1]["content"] = "① 관련된 일반 문장"

    result = build_context_package(
        _search("시험법의 목적은?"),
        corpus,
        _case(),
        search_run=1,
        corpus_sha256="sha",
    )

    assert result["status"] == "insufficient_evidence"
    assert result["reason"] == "source_content_invalid"
    assert result["missing_evidence_terms"] == ["국민의 권리", "공공복리"]
    assert result["evidence_bundles"] == []
    assert result["safety"]["answer_generation_allowed"] is False


def test_out_of_scope_contract_is_insufficient_without_guessing_from_similar_articles() -> None:
    result = build_context_package(
        _search("시험법의 목적은?", include_expected=False),
        {"chunks": []},
        _case("out_of_scope"),
        search_run=2,
        corpus_sha256="sha",
    )

    assert result["status"] == "insufficient_evidence"
    assert result["reason"] == "governing_provision_outside_corpus"
    assert result["expected_article_rank"] is None


def test_context_recording_appends_exact_stdout_and_hash(tmp_path: Path) -> None:
    data = tmp_path / "runs.json"
    report = tmp_path / "runs.md"
    result = build_context_package(
        _search("시험법의 목적은?"),
        _corpus(),
        _case(),
        search_run=1,
        corpus_sha256="sha",
    )

    first = record_context_result(result, data_path=data, report_path=report)
    second = record_context_result(result, data_path=data, report_path=report)

    history = json.loads(data.read_text(encoding="utf-8"))
    assert [run["run"] for run in history["runs"]] == [1, 2]
    assert history["runs"][0]["stdout"] == first
    assert history["runs"][1]["stdout"] == second
    assert history["runs"][0]["stdout_sha256"] == hashlib.sha256(first.encode("utf-8")).hexdigest()
    markdown = report.read_text(encoding="utf-8")
    assert first.rstrip("\n") in markdown
    assert second.rstrip("\n") in markdown


def test_recording_failure_preserves_previous_outputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data = tmp_path / "runs.json"
    report = tmp_path / "runs.md"
    data.write_text("previous data", encoding="utf-8")
    report.write_text("previous report", encoding="utf-8")

    monkeypatch.setattr(context_module, "_load_context_runs", lambda _path: [])
    monkeypatch.setattr(
        context_module,
        "_stage",
        lambda _path, _content: (_ for _ in ()).throw(OSError("disk full")),
    )
    result = build_context_package(
        _search("시험법의 목적은?"),
        _corpus(),
        _case(),
        search_run=1,
        corpus_sha256="sha",
    )

    with pytest.raises(ContextRecordingError, match="could not be saved"):
        record_context_result(result, data_path=data, report_path=report)

    assert data.read_text(encoding="utf-8") == "previous data"
    assert report.read_text(encoding="utf-8") == "previous report"

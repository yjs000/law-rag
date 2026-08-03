from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from scripts.experiment_search import (
    DEFAULT_CORPUS_PATH,
    DEFAULT_EVALUATION_QUESTIONS,
    DEFAULT_SEARCH_RUNS_DATA,
    REPOSITORY_ROOT,
    _article_root,
    _load_evaluation_cases,
    _normalize_evidence_text,
    load_corpus,
)

DEFAULT_CONTEXT_RUNS_DATA = (
    REPOSITORY_ROOT / ".data" / "experiments" / "context" / "context-runs.json"
)
DEFAULT_CONTEXT_RUNS_REPORT = (
    REPOSITORY_ROOT / ".data" / "experiments" / "context" / "context-results.md"
)
BUILD_COMMAND = "uv run --directory apps/api python -m scripts.experiment_context build"


class ContextRecordingError(RuntimeError):
    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="실험 C 후보를 법률 계층으로 복원하고 근거 충분성을 검사하는 실험 D"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="기록된 실험 C 질문의 근거 문맥 구성")
    build.add_argument("--search-runs", type=Path, default=DEFAULT_SEARCH_RUNS_DATA)
    build.add_argument("--run", type=int, required=True)
    build.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    build.add_argument("--questions", type=Path, default=DEFAULT_EVALUATION_QUESTIONS)
    build.add_argument("--results-data", type=Path, default=DEFAULT_CONTEXT_RUNS_DATA)
    build.add_argument("--results-report", type=Path, default=DEFAULT_CONTEXT_RUNS_REPORT)
    build.add_argument("--no-record", action="store_true")
    return parser


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"input file could not be hashed: {path.name}") from exc


def _load_search_run(path: Path, run_number: int) -> tuple[dict[str, object], str]:
    if run_number <= 0:
        raise ValueError("search run number must be positive")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid experiment C search history") from exc
    runs = payload.get("runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list) or run_number > len(runs):
        raise ValueError("experiment C search run does not exist")
    run = runs[run_number - 1]
    if not isinstance(run, dict) or run.get("run") != run_number:
        raise ValueError("invalid experiment C search history")
    stdout = run.get("stdout")
    expected_stdout_sha = run.get("stdout_sha256")
    corpus_sha = run.get("corpus_sha256")
    if (
        not isinstance(stdout, str)
        or not isinstance(expected_stdout_sha, str)
        or hashlib.sha256(stdout.encode("utf-8")).hexdigest() != expected_stdout_sha
        or not isinstance(corpus_sha, str)
    ):
        raise ValueError("invalid experiment C search history")
    result = json.loads(stdout)
    if not isinstance(result, dict):
        raise ValueError("invalid experiment C recorded result")
    return result, corpus_sha


def _evidence_case(question: str, cases: list[dict[str, object]]) -> dict[str, object]:
    matches = [case for case in cases if case.get("question") == question]
    if len(matches) != 1:
        raise ValueError("question has no unique evidence contract")
    return matches[0]


def _article_chunks(
    corpus: dict[str, object], *, title: str, article_path: str
) -> list[dict[str, object]]:
    chunks = corpus["chunks"]
    assert isinstance(chunks, list)
    selected = [
        chunk
        for chunk in chunks
        if isinstance(chunk, dict)
        and chunk.get("title") == title
        and (article := _article_root(str(chunk.get("path", "")))) is not None
        and article[0] == article_path
    ]
    selected.sort(key=lambda chunk: (int(chunk["ordinal"]), str(chunk["path"])))
    return selected


def _candidate_rank(search: dict[str, object], *, title: str, article_path: str) -> int | None:
    candidates = search.get("article_candidates")
    if not isinstance(candidates, list):
        raise ValueError("recorded search has no article candidates")
    for candidate in candidates:
        if (
            isinstance(candidate, dict)
            and candidate.get("title") == title
            and candidate.get("article_path") == article_path
            and isinstance(candidate.get("rank"), int)
        ):
            return int(candidate["rank"])
    return None


def build_context_package(
    search: dict[str, object],
    corpus: dict[str, object],
    case: dict[str, object],
    *,
    search_run: int,
    corpus_sha256: str,
    generated_at: str | None = None,
) -> dict[str, object]:
    question = str(search.get("question", ""))
    if not question or question != case.get("question"):
        raise ValueError("search question and evidence contract do not match")
    title = str(case["expected_title"])
    article_path = str(case["expected_article_path"])
    required_terms = case["required_evidence_terms"]
    if not isinstance(required_terms, list):
        raise ValueError("invalid evidence contract")
    chunks = _article_chunks(corpus, title=title, article_path=article_path)
    article_rank = _candidate_rank(search, title=title, article_path=article_path)
    combined = _normalize_evidence_text(" ".join(str(chunk["content"]) for chunk in chunks))
    missing_terms = [
        str(term) for term in required_terms if _normalize_evidence_text(term) not in combined
    ]

    reason = None
    if case.get("scope") == "out_of_scope":
        reason = "governing_provision_outside_corpus" if not chunks else "declared_out_of_scope"
    elif not chunks:
        reason = "governing_provision_outside_corpus"
    elif missing_terms:
        reason = "source_content_invalid"
    elif article_rank is None:
        reason = "retrieval_miss"

    evidence_bundles: list[dict[str, object]] = []
    if reason is None:
        first = chunks[0]
        evidence_bundles.append(
            {
                "title": title,
                "source_id": first["source_id"],
                "mst": first["mst"],
                "effective_from": first["effective_from"],
                "source_url": first["source_url"],
                "article_path": article_path,
                "retrieval_rank": article_rank,
                "required_evidence_terms": required_terms,
                "chunks": [
                    {
                        "chunk_id": chunk["chunk_id"],
                        "path": chunk["path"],
                        "parent_path": chunk["parent_path"],
                        "heading": chunk["heading"],
                        "content": chunk["content"],
                    }
                    for chunk in chunks
                ],
            }
        )

    candidates = search.get("article_candidates")
    assert isinstance(candidates, list)
    return {
        "schema_version": 1,
        "experiment": "D",
        "generated_by": BUILD_COMMAND,
        "generated_at": generated_at
        or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "search_run": search_run,
        "corpus_sha256": corpus_sha256,
        "question": question,
        "evidence_contract_id": case["id"],
        "candidate_observation_count": len(candidates),
        "status": "ready" if reason is None else "insufficient_evidence",
        "reason": reason,
        "expected_article_rank": article_rank,
        "missing_evidence_terms": missing_terms,
        "evidence_bundles": evidence_bundles,
        "safety": {
            "cosine_threshold_used": False,
            "semantic_claim": "fixed_evidence_contract_only",
            "answer_generation_allowed": reason is None,
        },
    }


def _stage(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return temporary
    except Exception:
        with suppress(OSError):
            temporary.unlink()
        raise


def _atomic_write_many(outputs: list[tuple[Path, str]]) -> None:
    if len({path.resolve() for path, _ in outputs}) != len(outputs):
        raise ContextRecordingError("context result output paths must be different")
    previous = {path: path.read_bytes() if path.exists() else None for path, _ in outputs}
    staged: list[tuple[Path, Path]] = []
    replaced: list[Path] = []
    try:
        staged = [(path, _stage(path, content)) for path, content in outputs]
        for target, temporary in staged:
            temporary.replace(target)
            replaced.append(target)
    except (OSError, UnicodeError) as exc:
        for _, temporary in staged:
            with suppress(OSError):
                temporary.unlink()
        for target in reversed(replaced):
            old = previous[target]
            if old is None:
                with suppress(OSError):
                    target.unlink()
            else:
                restore = _stage(target, old.decode("utf-8"))
                restore.replace(target)
        raise ContextRecordingError("context result outputs could not be saved") from exc


def _load_context_runs(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContextRecordingError("invalid experiment D history") from exc
    runs = payload.get("runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        raise ContextRecordingError("invalid experiment D history")
    return runs


def _render_report(runs: list[dict[str, object]]) -> str:
    lines = [
        "# 실험 D — 실제 검색 문맥 실행 기록",
        "",
        f"> 생성 명령: `{BUILD_COMMAND}`",
        f"> 마지막 기록: `{runs[-1]['recorded_at']}`",
        "",
        "| 실행 | 검색 실행 | 질문 | 상태 | 이유 | 기대 조 rank |",
        "| ---: | ---: | --- | --- | --- | ---: |",
    ]
    for run in runs:
        result = json.loads(str(run["stdout"]))
        question = str(result["question"]).replace("|", "\\|")
        lines.append(
            f"| {run['run']} | {result['search_run']} | {question} | {result['status']} | "
            f"{result['reason'] or '-'} | {result['expected_article_rank'] or '-'} |"
        )
    lines.extend(["", "## 실제 stdout", ""])
    for run in runs:
        lines.extend(
            [
                f"### 실행 {run['run']}",
                "",
                f"- 기록 시각: `{run['recorded_at']}`",
                f"- stdout SHA-256: `{run['stdout_sha256']}`",
                "",
                "```json",
                str(run["stdout"]).rstrip("\n"),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def record_context_result(result: dict[str, object], *, data_path: Path, report_path: Path) -> str:
    runs = _load_context_runs(data_path)
    recorded_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    recorded = dict(result)
    recorded["recording"] = {
        "run": len(runs) + 1,
        "recorded_at": recorded_at,
        "data_path": str(data_path),
        "report_path": str(report_path),
    }
    stdout = json.dumps(recorded, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    runs.append(
        {
            "run": len(runs) + 1,
            "recorded_at": recorded_at,
            "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            "stdout": stdout,
        }
    )
    history = {
        "schema_version": 1,
        "experiment": "D",
        "generated_by": BUILD_COMMAND,
        "updated_at": recorded_at,
        "runs": runs,
    }
    _atomic_write_many(
        [
            (data_path, json.dumps(history, ensure_ascii=False, indent=2) + "\n"),
            (report_path, _render_report(runs)),
        ]
    )
    return stdout


def _build(args: argparse.Namespace) -> str:
    corpus = load_corpus(args.corpus)
    search, recorded_corpus_sha = _load_search_run(args.search_runs, args.run)
    actual_corpus_sha = _sha256(args.corpus)
    if recorded_corpus_sha != actual_corpus_sha:
        raise ValueError("search run corpus SHA-256 does not match current corpus")
    cases = _load_evaluation_cases(args.questions)
    case = _evidence_case(str(search.get("question", "")), cases)
    result = build_context_package(
        search,
        corpus,
        case,
        search_run=args.run,
        corpus_sha256=actual_corpus_sha,
    )
    if args.no_record:
        return json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    return record_context_result(
        result, data_path=args.results_data, report_path=args.results_report
    )


def run_cli(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            sys.stdout.write(_build(args))
        return 0
    except ContextRecordingError:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": "result_recording_failed",
                    "message": "실험 D 결과를 기록하지 못했습니다",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    except OSError, ValueError, KeyError, json.JSONDecodeError:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": "experiment_d_failed",
                    "message": "실험 D를 실행하지 못했습니다",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(run_cli())

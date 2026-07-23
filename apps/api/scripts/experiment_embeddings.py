from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from math import fsum, isfinite, sqrt
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.settings import get_settings

DEFAULT_SENTENCE_A = "전기사업을 하려는 자는 산업통상자원부장관의 허가를 받아야 한다."
DEFAULT_SENTENCE_B = "산업통상자원부장관의 허가를 받지 않으면 전기사업을 시작할 수 없다."
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DATA = REPOSITORY_ROOT / "docs" / "generated" / "experiment-b-embedding-runs.json"
DEFAULT_RESULTS_DOCUMENT = (
    REPOSITORY_ROOT / "docs" / "generated" / "experiment-b-embedding-results.md"
)
GENERATION_COMMAND = "uv run --directory apps/api python -m scripts.experiment_embeddings"


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NVIDIA NIM으로 두 문장을 임베딩하고 코사인 유사도를 출력한다"
    )
    parser.add_argument("--sentence-a", default=DEFAULT_SENTENCE_A)
    parser.add_argument("--sentence-b", default=DEFAULT_SENTENCE_B)
    parser.add_argument(
        "--results-data",
        type=Path,
        default=DEFAULT_RESULTS_DATA,
        help="반복 비교용 실제 stdout 이력을 저장할 JSON 경로",
    )
    parser.add_argument(
        "--results-document",
        type=Path,
        default=DEFAULT_RESULTS_DOCUMENT,
        help="예상 조건과 실제 실행값을 생성할 Markdown 경로",
    )
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="실제 결과 파일을 갱신하지 않고 터미널에만 출력",
    )
    return parser


def _norm(vector: list[float]) -> float:
    return sqrt(fsum(value * value for value in vector))


async def run_experiment(
    sentence_a: str,
    sentence_b: str,
    *,
    embedder: Embedder,
    model: str,
) -> dict[str, object]:
    if not sentence_a.strip() or not sentence_b.strip():
        raise ValueError("sentences must not be empty")
    vectors = await embedder.embed([sentence_a, sentence_b])
    if len(vectors) != 2 or any(len(vector) != 512 for vector in vectors):
        raise ValueError("embedder returned an invalid result shape")
    vector_a, vector_b = vectors
    norm_a = _norm(vector_a)
    norm_b = _norm(vector_b)
    if not isfinite(norm_a) or not isfinite(norm_b) or norm_a == 0 or norm_b == 0:
        raise ValueError("embedder returned an invalid vector norm")
    similarity = fsum(a * b for a, b in zip(vector_a, vector_b, strict=True)) / (
        norm_a * norm_b
    )
    if not isfinite(similarity):
        raise ValueError("cosine similarity is not finite")
    similarity = min(1.0, max(-1.0, similarity))
    return {
        "provider": "nvidia_nim",
        "model": model,
        "native_dimensions": 2048,
        "output_dimensions": 512,
        "sentence_a": sentence_a,
        "embedding_a": vector_a,
        "sentence_b": sentence_b,
        "embedding_b": vector_b,
        "norm_a": norm_a,
        "norm_b": norm_b,
        "cosine_similarity": similarity,
    }


async def _run_cli(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    if not settings.nvidia_api_key:
        raise RuntimeError("nvidia_api_key_missing")
    embedder = NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    return await run_experiment(
        args.sentence_a,
        args.sentence_b,
        embedder=embedder,
        model=settings.nvidia_embedding_model,
    )


def _load_runs(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("experiment") != "B"
        or not isinstance(payload.get("runs"), list)
    ):
        raise ValueError("invalid experiment B result history")
    runs = payload["runs"]
    for expected_run_number, run in enumerate(runs, start=1):
        if (
            not isinstance(run, dict)
            or not isinstance(run.get("run"), int)
            or not isinstance(run.get("recorded_at"), str)
            or not isinstance(run.get("stdout_sha256"), str)
            or not isinstance(run.get("stdout"), str)
        ):
            raise ValueError("invalid experiment B result record")
        stdout = run["stdout"]
        if run["run"] != expected_run_number or run["stdout_sha256"] != sha256(
            stdout.encode("utf-8")
        ).hexdigest():
            raise ValueError("invalid experiment B result record integrity")
        _parse_stdout(stdout)
    return runs


def _parse_stdout(stdout: str) -> dict[str, object]:
    result = json.loads(stdout)
    if not isinstance(result, dict):
        raise ValueError("experiment B stdout must contain a JSON object")
    for key in ("embedding_a", "embedding_b"):
        vector = result.get(key)
        if (
            not isinstance(vector, list)
            or len(vector) != 512
            or any(not isinstance(value, int | float) or not isfinite(value) for value in vector)
        ):
            raise ValueError("experiment B stdout contains an invalid embedding")
    similarity = result.get("cosine_similarity")
    if not isinstance(similarity, int | float) or not isfinite(similarity):
        raise ValueError("experiment B stdout contains an invalid cosine similarity")
    return result


def _embedding_digest(vector: list[object]) -> str:
    canonical = json.dumps(vector, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _max_absolute_difference(left: list[object], right: list[object]) -> float:
    return max(abs(float(a) - float(b)) for a, b in zip(left, right, strict=True))


def _display_float(value: object) -> str:
    return format(float(value), ".17g")


def _code_fence(stdout: str) -> str:
    longest = 0
    current = 0
    for character in stdout:
        if character == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return "`" * max(3, longest + 1)


def _render_results_document(runs: list[dict[str, object]]) -> str:
    parsed = [_parse_stdout(str(run["stdout"])) for run in runs]
    baseline = parsed[0]
    baseline_a = baseline["embedding_a"]
    baseline_b = baseline["embedding_b"]
    assert isinstance(baseline_a, list)
    assert isinstance(baseline_b, list)

    lines = [
        "# 실험 B — 실제 임베딩 출력과 반복 실행 비교",
        "",
        f"> 생성 명령: `{GENERATION_COMMAND}`",
        f"> 마지막 기록: {runs[-1]['recorded_at']}",
        (
            "> 원시 이력: "
            "[experiment-b-embedding-runs.json](experiment-b-embedding-runs.json)"
        ),
        "",
        "## 비교 목적",
        "",
        "예상값을 실제값처럼 쓰지 않는다. 아래 예상은 모델·adapter 계약에서 확인할 조건이다.",
        "512차원 벡터는 각 live 실행의 표준출력 문자열을 그대로 옮긴 실제 결과다.",
        "",
        "| 항목 | 실행 전 예상 | 실제 확인 방법 |",
        "| --- | --- | --- |",
        "| provider/model | NVIDIA NIM / `nvidia/nemotron-3-embed-1b` | 각 실행 JSON의 필드 확인 |",
        "| 차원 | native 2048, 최종 512 | `native_dimensions`, `output_dimensions` 확인 |",
        "| norm | 재정규화 후 1에 가까움 | `norm_a`, `norm_b` 확인 |",
        "| cosine 범위 | `[-1, 1]` | `cosine_similarity` 확인 |",
        (
            "| 의미 가설 | 관련 문장 쌍이므로 양의 높은 값 예상, "
            "정확한 값은 미리 정하지 않음 | 실제값 관찰 |"
        ),
        "| 반복 안정성 | 미결정 | 실행 1과 전체 벡터·cosine을 정확 비교 |",
        "",
        "## 반복 실행 비교",
        "",
        "`같음`은 표시 자릿수만 비교한 것이 아니라 JSON에 기록된 512개 float 전체의 정확 일치다.",
        "`최대 좌표 차이`는 실행 1의 같은 위치 값과 비교한 절댓값 차이 중 최댓값이다.",
        "",
        (
            "| 실행 | 기록 시각 | cosine | 실행 1 대비 Δcosine | A 전체 | B 전체 | "
            "A 최대 좌표 차이 | B 최대 좌표 차이 |"
        ),
        "| ---: | --- | ---: | ---: | --- | --- | ---: | ---: |",
    ]
    baseline_similarity = float(baseline["cosine_similarity"])
    for run, result in zip(runs, parsed, strict=True):
        vector_a = result["embedding_a"]
        vector_b = result["embedding_b"]
        assert isinstance(vector_a, list)
        assert isinstance(vector_b, list)
        difference_a = _max_absolute_difference(baseline_a, vector_a)
        difference_b = _max_absolute_difference(baseline_b, vector_b)
        similarity_difference = float(result["cosine_similarity"]) - baseline_similarity
        run_number = int(run["run"])
        lines.append(
            "| "
            f"{run_number} | {run['recorded_at']} | "
            f"{_display_float(result['cosine_similarity'])} | "
            f"{_display_float(similarity_difference)} | "
            f"{'기준' if run_number == 1 else ('같음' if vector_a == baseline_a else '다름')} | "
            f"{'기준' if run_number == 1 else ('같음' if vector_b == baseline_b else '다름')} | "
            f"{_display_float(difference_a)} | {_display_float(difference_b)} |"
        )

    lines.extend(["", "## 벡터 지문", ""])
    for run, result in zip(runs, parsed, strict=True):
        vector_a = result["embedding_a"]
        vector_b = result["embedding_b"]
        assert isinstance(vector_a, list)
        assert isinstance(vector_b, list)
        lines.extend(
            [
                f"- 실행 {run['run']} stdout SHA-256: `{run['stdout_sha256']}`",
                f"  - embedding A SHA-256: `{_embedding_digest(vector_a)}`",
                f"  - embedding B SHA-256: `{_embedding_digest(vector_b)}`",
            ]
        )

    lines.extend(["", "## 실제 터미널 출력", ""])
    for run in runs:
        stdout = str(run["stdout"])
        fence = _code_fence(stdout)
        lines.extend(
            [
                f"### 실행 {run['run']}",
                "",
                f"기록 시각: `{run['recorded_at']}`",
                "",
                f"{fence}json",
                stdout.rstrip("\n"),
                fence,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def record_experiment_result(
    result: dict[str, object],
    *,
    stdout: str,
    data_path: Path = DEFAULT_RESULTS_DATA,
    document_path: Path = DEFAULT_RESULTS_DOCUMENT,
    recorded_at: str | None = None,
) -> None:
    if _parse_stdout(stdout) != result:
        raise ValueError("recorded stdout does not match the experiment result")
    runs = _load_runs(data_path)
    runs.append(
        {
            "run": len(runs) + 1,
            "recorded_at": recorded_at
            or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "stdout_sha256": sha256(stdout.encode("utf-8")).hexdigest(),
            "stdout": stdout,
        }
    )
    history = {
        "schema_version": 1,
        "experiment": "B",
        "generated_by": GENERATION_COMMAND,
        "updated_at": runs[-1]["recorded_at"],
        "data_kind": "actual_live_stdout_history",
        "runs": runs,
    }
    history_json = json.dumps(history, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    document = _render_results_document(runs)
    previous = {
        path: path.read_text(encoding="utf-8") if path.exists() else None
        for path in (data_path, document_path)
    }
    try:
        _atomic_write(data_path, history_json)
        _atomic_write(document_path, document)
    except Exception:
        for path, old_content in previous.items():
            if old_content is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, old_content)
        raise


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = asyncio.run(_run_cli(args))
    except RuntimeError as exc:
        code = (
            "nvidia_api_key_missing"
            if str(exc) == "nvidia_api_key_missing"
            else "embedding_failed"
        )
        print(
            json.dumps(
                {"status": "error", "code": code, "message": "NVIDIA 임베딩을 실행하지 못했습니다"},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    except Exception:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": "embedding_failed",
                    "message": "NVIDIA 임베딩을 실행하지 못했습니다",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    stdout = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if not args.no_record:
        try:
            record_experiment_result(
                result,
                stdout=stdout,
                data_path=args.results_data,
                document_path=args.results_document,
            )
        except Exception:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": "result_recording_failed",
                        "message": "실험 결과 문서를 기록하지 못했습니다",
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                file=sys.stderr,
            )
            return 2
    print(stdout, end="")
    return 0


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()

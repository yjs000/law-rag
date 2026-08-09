"""0025 M5 item 6: bounded hosted smoke test for real NVIDIA answer generation.

"동결 10문항 중 최소 표본의 bounded hosted smoke로 schema, timeout, provider error와
검색 전용 fallback만 먼저 확인한다" (0025 M5 item 6). This is NOT experiment E-10 (M6) -
it is a minimal, cheap check that the real pipeline works end to end, not a quality
evaluation. Uses the real Postgres repository and real NVIDIA NIM answerer (both picked
up automatically by app.main via .env.local - no test conftest overrides apply outside
pytest).

Sample (minimal, per the roadmap's "최소 표본"):
  - Two D-10 legal_search questions (0201, 0521) to exercise the real happy path:
    routing -> embedding -> search -> generation -> grounding gate -> schema.
  - One deliberately unanswerable question to exercise the search-only fallback path
    without needing to force a real provider error.

Provider-error/timeout handling itself is already covered by mocked unit tests
(tests/test_ai_fallback.py) - forcing a real NVIDIA outage isn't practical or reliable,
so this script doesn't attempt to.

Usage: uv run python scripts/hosted_answer_smoke_test.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import uuid4

_API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_API_ROOT))

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main_module  # noqa: E402

CASES = [
    (
        "lay-energy-0201 (legal_search happy path)",
        "태양광 발전소 허가를 준비하고 있는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요?",
    ),
    (
        "lay-energy-0521 (legal_search happy path)",
        "발전량은 기록되지만 신재생에너지 공급인증서(REC)가 발급되지 않고 있는데, "
        "발급 대상과 신청 조건을 어떻게 확인하나요?",
    ),
    (
        "unanswerable (search-only fallback path)",
        "제 냉장고에서 이상한 소리가 나는데 왜 그런가요?",
    ),
]


def main() -> None:
    print("provider: nvidia_nim")
    print("model:", main_module.settings.nvidia_answer_model)
    print("repository:", type(main_module.repository).__name__)
    client = TestClient(main_module.app)

    for label, question in CASES:
        start = time.monotonic()
        response = client.post(
            "/v1/questions",
            json={
                "client_request_id": str(uuid4()),
                "question": question,
                "answer_mode": "terra",
            },
        )
        elapsed = time.monotonic() - start
        print(f"\n=== {label}")
        print("status:", response.status_code, f"({elapsed:.1f}s)")
        if response.status_code != 200:
            print("body:", response.text[:500])
            continue
        body = response.json()
        print(
            "mode:",
            body.get("mode"),
            "| route:",
            body.get("route"),
            "| action:",
            body.get("action"),
            "| fallback_reason:",
            body.get("fallback_reason"),
        )
        print(
            "sections:",
            len(body.get("sections", [])),
            "| checklist:",
            len(body.get("checklist", [])),
            "| citations:",
            len(body.get("citations", [])),
        )
        print("summary:", (body.get("summary") or "")[:200])


if __name__ == "__main__":
    main()

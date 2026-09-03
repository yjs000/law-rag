# Task 4 fix-round 재리뷰 — scoped roadmap pre-commit hook

## 범위와 검증

- 비교 범위: `c30a74a..9a7fee5` (`ci: enforce generated roadmap consistency` 후속 fix).
- 대상 파일: `scripts/install_git_hooks.py`, `scripts/tests/test_roadmap_registry.py`.
- 수정 diff는 위 두 파일에만 포함되며, hook installer의 기존 보존·idempotency 계약과 CI/verify 변경은
  건드리지 않는다.
- `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v` — 34개 실행,
  `OK` (권한 상승 filesystem 실행; sandbox에서는 `TemporaryDirectory(dir=Path.cwd())` fixture 생성이
  Windows ACL에 의해 거부됨).
- `uv run --project apps/api ruff check scripts/install_git_hooks.py scripts/tests/test_roadmap_registry.py`
  — 통과.
- `uv run --project apps/api python -m py_compile scripts/install_git_hooks.py scripts/tests/test_roadmap_registry.py`
  — 통과.
- `git diff --check c30a74a..9a7fee5` — 통과.
- `uv run --project apps/api python scripts/check_roadmap.py` 및 `--staged` — 모두 통과; 15 plans,
  `Picked Up: 1`, digest `7e5e2d0a6d431310cc11202cb13a6fe0da84010ff87570ab16a16c184a5c50d4`.

## Verdict

**PASS — 기존 P1 두 건이 모두 해결되었고, fix diff에서 새로운 P0–P2 회귀를 발견하지 못했다.**

## 이전 finding 확인

### P1 — staged-path discovery fail-open: 해결

- `scripts/install_git_hooks.py:24-28`은 staged-path 조회를 먼저 `staged_paths=$(...)`로 수행하고,
  Git 명령이 0이 아닌 경우 `||` 분기에서 오류를 stderr로 알린 뒤 원래 상태 코드로 즉시 종료한다.
  따라서 `git diff`가 index를 읽지 못할 때 no-match처럼 `exit 0`으로 진행하지 않는다.
- `scripts/tests/test_roadmap_registry.py:811-833`의
  `test_pre_commit_dispatcher_rejects_staged_path_discovery_failure`는 corrupt
  `GIT_INDEX_FILE`을 hook에 주입하고 commit이 거부되는지 검증한다. 전체 34개 suite에서 통과했다.

### P1 — Git-quoted non-ASCII staged path가 필터를 우회: 해결

- 같은 조회 명령에 `git -c core.quotePath=false`를 적용해 저장소의 `core.quotePath` 설정을 변경하지
  않고 해당 invocation의 비ASCII 경로를 그대로 출력한다. 이후 `printf`와 기존 scope 정규식이
  `docs/exec-plans/` 및 `docs/ROADMAP.md`를 정상적으로 선택한다(`scripts/install_git_hooks.py:24-31`).
- `scripts/tests/test_roadmap_registry.py:835-864`는 저장소 설정을 `core.quotePath=true`로 둔 채
  `docs/exec-plans/todo/0001-한글.md`를 stage하고 checker가 `--staged`로 호출되는지 검증한다.
  테스트는 통과했다.

## Regression sweep

- 기존 hook 동작(비관련 staged path에서는 checker 미호출, roadmap/plan path에서는 호출), installer의
  user-owned hook 보존·재실행 idempotency·`core.hooksPath` 및 `post-commit` 보존이 기존 테스트와
  함께 통과했다.
- 일반 및 staged roadmap checker는 동일한 plan count와 digest를 반환했고, fix commit의 whitespace
  검증도 통과했다.
- `check_docs.py`는 `docs/QUALITY_SCORE.md`의 기존 평가일 `2026-07-18`이 현재 날짜 기준 47일
  경과했다는 사유로 여전히 실패한다. 해당 파일과 checker는 reviewed range에서 변경되지 않았으므로
  Task 4 fix의 회귀가 아니다.

## Finding count

| Severity | Count |
| --- | ---: |
| P0 | 0 |
| P1 | 0 |
| P2 | 0 |
| P3 | 0 |

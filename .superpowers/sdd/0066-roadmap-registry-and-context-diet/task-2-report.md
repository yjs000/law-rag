# Task 2 구현·self-review 보고서

## 범위

Task 2의 생성 roadmap writer와 읽기 전용 checker를 구현했다. 변경과 커밋에는
`scripts/render_roadmap.py`, `scripts/check_roadmap.py`,
`scripts/tests/test_roadmap_registry.py`만 포함했다. Task 2 controller ruling에 따라
`docs/ROADMAP.md`는 생성하지도 수정하지도 않았고 커밋에도 넣지 않았다.

## TDD 증거

### Red — entry point 부재

테스트를 먼저 추가한 뒤 필수 focused 명령을 실행했다.

```text
uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
```

결과: 테스트 모듈 import 단계에서 `ImportError: cannot import name 'check_roadmap' from
'scripts'`로 실패했다. 이는 renderer/checker production entry point를 추가하기 전의 의도한
실패다. 첫 실행은 Windows sandbox ACL 때문에 fixture용 `TemporaryDirectory(dir=Path.cwd())`
생성도 거부했으므로, 같은 명령을 권한 상승 환경에서 재실행해 위의 올바른 red 원인을 확인했다.

### Red — Windows byte newline 회귀

원자적 writer가 text mode일 때 Windows가 LF를 CRLF로 변환하는 것을 발견해, 회귀 테스트를
추가하고 production 수정 전 단일 테스트를 실행했다.

```text
uv run --project apps/api python -m unittest \
  scripts.tests.test_roadmap_registry.RoadmapRegistryFixtures.\
  test_renderer_cli_writes_the_rendered_utf8_bytes_without_newline_translation -v
```

결과: CRLF writer bytes와 expected LF bytes가 달라지는 실패를 확인했다. writer를 binary
UTF-8로 바꾼 뒤 같은 테스트가 `OK`가 됐다.

## 구현 결과

- `render_roadmap(records)`는 registry의 deterministic sections를 `Todo`, `Blocked`, `Done`
  순서로 렌더한다. `Picked Up`은 `Todo`에 표시하고, `Done`은 최신 12개와 completed index
  link만 표시한다.
- 출력 상단에 시간에 의존하지 않는 생성 명령과 입력 digest comment를 기록한다. task ID,
  type, plan title link, `다음 행동` 또는 `재개 조건`만 task row에 포함한다.
- renderer CLI는 `validate_registry`를 먼저 실행하고, 성공할 때만 같은 디렉터리의 binary
  temporary file을 `os.replace`로 `docs/ROADMAP.md`에 원자적으로 교체한다. validation
  실패 시 기존 파일을 유지한다.
- checker CLI는 registry validation 후 expected output과 checked-in 또는 staged roadmap
  bytes를 비교한다. 불일치 시 첫 번째 차이 줄과 `python scripts/render_roadmap.py` 명령을
  보고하며 어떤 파일도 쓰지 않는다.
- `--staged` checker는 plan header를 registry의 staged reader에서 읽고 roadmap bytes는
  `git show :docs/ROADMAP.md`에서 읽으므로 작업 트리 변경을 사용하지 않는다.
- isolated fixtures는 deterministic rendering, output field 제한, Picked Up 배치, Done
  truncation, validation-before-write, manual one-character drift, staged plan/roadmap
  precedence를 검증한다.

## 저장소 roadmap 생성을 연기한 정확한 이유

`progress.md`의 controller ruling에 따라 현재 repository의 todo/active plan headers는
Task 3 metadata migration 전까지 의도적으로 invalid하다. 설계상 plan header가 유일한
source of truth이고 renderer는 validation을 우회할 수 없으므로, Task 2에서 invalid
metadata를 허용하거나 `docs/ROADMAP.md`를 부분 생성하는 것은 계약 위반이다. 따라서 Task 2는
valid isolated fixtures만으로 renderer/checker를 증명하고, Task 3이 required `다음 행동`
필드와 header/lifecycle/reference 범위를 이행한 뒤 첫 repository render와 checker를
수행한다.

현재 worktree에서 read-only registry validation은 20개 parsed records와 188개 errors를
보고했다(주요 범위: strict H1/header grammar, missing `다음 행동`, malformed/out-of-range
`참고 범위`, lifecycle/reference issues). 이 상태에서 실행한 renderer와 checker는 모두
non-zero로 종료했고 `docs/ROADMAP.md`는 존재와 bytes가 그대로 유지됐다.

## 변경 파일

- `scripts/render_roadmap.py`
- `scripts/check_roadmap.py`
- `scripts/tests/test_roadmap_registry.py`

`docs/ROADMAP.md`, `graphify-out/`, 기존 SDD artifacts는 staged/commit 대상에서 제외했다.

## 검증

```text
uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
```

결과: 25 tests, `OK`.

```text
uv run --project apps/api ruff check scripts/render_roadmap.py scripts/check_roadmap.py scripts/tests/test_roadmap_registry.py
```

결과: `All checks passed!`.

```text
uv run --project apps/api python -m py_compile scripts/render_roadmap.py scripts/check_roadmap.py scripts/tests/test_roadmap_registry.py
```

결과: exit code 0.

```text
git diff --cached --check
```

결과: 출력 없음, exit code 0.

```text
graphify update .
```

결과: AST graph update 성공. pyproject zero-node와 5,000-node aggregate warning이 있었고,
graphify output은 기존 dirty state로 유지했으며 커밋하지 않았다.

## 커밋

```text
7e2e5952bfb2b1d59d071d71de358db931601856 feat: generate and verify roadmap
```

커밋에는 위 scoped files 3개만 포함했다.

## Concerns

- repository-wide render/check는 Task 3 migration 전까지 의도적으로 실패한다. 이 실패를
  숨기거나 validation을 약화하지 않았다.
- Windows sandbox ACL 때문에 focused unittest와 temporary Git fixture는 권한 상승으로
  실행했다. 구현에는 영향을 주지 않았다.
- `harness` CLI는 현재 환경에 설치되어 있지 않아 execution-harness start command를
  실행할 수 없었다. 대신 bounded context와 focused evidence 계약을 유지했다.

# Task 1 fix-round 재리뷰 — roadmap registry parser

## 범위와 검증

- 비교 범위: `645c02a2e46654b4543e429c9428caab20429581..2980fdc7a3c655c67688ab0b5cdd9237113fcec4`
- 현재 HEAD: `2980fdc7a3c655c67688ab0b5cdd9237113fcec4`
- 대상 파일: `scripts/roadmap_registry.py`, `scripts/tests/test_roadmap_registry.py`
- `git diff --check 645c02a..2980fdc` 통과.
- `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`: 19개 실행, `OK` (elevated filesystem 실행; sandbox에서는 임시 fixture 디렉터리 생성 권한이 거부됨).
- `uv run --project apps/api --no-sync ruff check scripts/roadmap_registry.py scripts/tests/test_roadmap_registry.py`: 통과.
- `uv run --project apps/api --no-sync python -m py_compile scripts/roadmap_registry.py scripts/tests/test_roadmap_registry.py`: 통과.

## Verdict

**PASS — 이전 P1 5건과 P2 2건이 모두 해결되었고, fix diff에서 새로운 P0–P2 회귀를 발견하지 못했다.**

## 이전 finding 확인

### P1 — 전체 plan 본문 materialization: 해결

- `scripts/roadmap_registry.py:202-211`의 `_header_lines()`는 iterator를 소비하다 첫 exact `##`에서 즉시 중단한다.
- disk 경로는 `scripts/roadmap_registry.py:266-276`에서 `Path.open()`과 해당 iterator만 사용한다.
- staged 경로는 `scripts/roadmap_registry.py:214-263`에서 `git show :path` stdout을 line-streaming하고 첫 H2 뒤 process를 종료한다. 전체 blob을 `subprocess.run(...).stdout`로 materialize하는 경로가 제거되었다.
- `scripts/tests/test_roadmap_registry.py:111-145`는 큰 body 및 H2 뒤 metadata가 status/title/digest에 영향을 주지 않는지 확인한다.

### P1 — staged reference의 worktree fallback: 해결

- `scripts/roadmap_registry.py:500-556`의 `_staged_line_count()`는 index의 `git show :reference`만 사용한다.
- `scripts/roadmap_registry.py:559-572`의 staged 분기에는 disk fallback이 없다. index에 없는 reference는 `None`으로 귀결되어 `scripts/roadmap_registry.py:613-623`에서 missing-reference error가 된다.
- `scripts/tests/test_roadmap_registry.py:234-253`은 index에 없는 worktree-only 파일을 거부하고, index의 4줄 범위가 worktree 1줄 때문에 실패하지 않는지 확인한다.

### P1 — headerless todo/active 누락: 해결

- `scripts/roadmap_registry.py:438-447`은 header read 실패/빈 header를 `completed`만 skip하고 `todo`·`active`는 빈 header record로 parse한다.
- `scripts/roadmap_registry.py:381-400`의 parse errors 및 validator의 required-field checks가 ID, 파일, 필드, 기본 correction command를 포함한 오류를 만든다.
- `scripts/tests/test_roadmap_registry.py:255-285`은 headerless todo/active의 모든 required field와 correction command, headerless completed skip을 각각 확인한다.

### P1 — `다음 행동` 한 문장: 해결

- `scripts/roadmap_registry.py:57-61`에 종결 부호와 whitespace/end 경계를 문서화한 regex가 있고, `scripts/roadmap_registry.py:770-789`에서 120자 검증과 함께 두 개 이상의 문장 종결을 거부한다. 종결 부호 없는 단일 action은 명시적으로 허용한다.
- `scripts/tests/test_roadmap_registry.py:353-365`가 정상 단문, 두 문장, 정확히 120자의 경계를 검증한다.

### P1 — acceptance tests의 lifecycle/cardinality/actionability/body 경계 누락: 해결

- missing-field 오류와 correction command: `scripts/tests/test_roadmap_registry.py:147-185`.
- body boundary 및 staged streaming: `scripts/tests/test_roadmap_registry.py:111-145`.
- 독립 fixture의 global Picked Up cardinality와 단일 actionable error: `scripts/tests/test_roadmap_registry.py:306-328`; 구현은 `scripts/roadmap_registry.py:805-815`.
- 7개 forbidden directory/status 조합 전부: `scripts/tests/test_roadmap_registry.py:330-351`; lifecycle mapping은 `scripts/roadmap_registry.py:669-684`.

### P2 — loose header grammar: 해결

- `scripts/roadmap_registry.py:333-369`는 blank, 허용된 blockquote field, `참고 범위` 아래 reference bullet, H1 외의 nonblank preamble 입력을 actionable parse error로 만든다. duplicate field와 reference-outside-section도 거부한다.
- H1 개수와 metadata 뒤 배치 검사는 `scripts/roadmap_registry.py:380-393`에 있다.
- prose-before-header, code fence, malformed field, reference-outside-section, unknown field 회귀는 `scripts/tests/test_roadmap_registry.py:367-391`에서 확인한다.

### P2 — 불필요한 compatibility alias surface: 해결

- `ReferenceRange`, `RegistryError`, `PlanRecord`에는 canonical dataclass fields만 남아 있다(`scripts/roadmap_registry.py:67-121`). 이전 alias property들과 `ReferenceRange.raw`가 제거되었다.
- public export는 `scripts/roadmap_registry.py:889-901`의 canonical models/functions/constants로 제한된다.
- alias 부재는 `scripts/tests/test_roadmap_registry.py:393-412`에서 회귀 검증한다. 저장소 내 대상 모델의 제거된 alias를 사용하는 caller도 검색에서 발견되지 않았다.

## Regression sweep

- fix round는 위 두 파일만 변경했다.
- staged plan/source 모두 index-only read boundary를 유지하며, disk 모드만 worktree를 읽는다.
- first-H2 streaming, invalid lifecycle/status, missing references, digest ordering, immutable records의 기존 동작이 19개 focused tests에서 모두 통과했다.
- 새로운 P0: 0, P1: 0, P2: 0, P3: 0.

## Finding count

| Severity | Count |
| --- | ---: |
| P0 | 0 |
| P1 | 0 |
| P2 | 0 |
| P3 | 0 |

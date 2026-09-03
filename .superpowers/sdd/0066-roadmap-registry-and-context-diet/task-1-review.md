# Task 1 리뷰 — roadmap registry parser

리뷰 범위는 `645c02a2e46654b4543e429c9428caab20429581^..645c02a2e46654b4543e429c9428caab20429581`의 두 신규 파일뿐이다. 지정한 requirements brief, 구현 보고서, binding design 및 `docs/PLANS.md`와 대조했다. `git diff --check`은 통과했다. 요청 범위가 읽기 전용이므로 테스트를 재실행하지 않았으며, 아래의 테스트 평가는 커밋에 포함된 테스트 소스를 근거로 한다.

## Verdict

- **Spec compliance: FAIL — P1 수정 필요.** 핵심 컨텍스트 경계, staged-index 정합성, 헤더 누락 검출, `다음 행동` 문장 제약이 계약을 충족하지 않는다.
- **Code quality: NEEDS CHANGES — P1 수정 필요.** acceptance test가 여러 요구 사례를 실제로 증명하지 못하고, 새 모듈에 불필요한 public alias 표면이 크다.

## Findings

### P1 — 전체 plan 본문을 실제로 읽고 materialize 한다

- Evidence: `scripts/roadmap_registry.py:295-304`의 `_read_plan()`은 disk에서 `read_text()`로 전체 파일을 읽고, `:352-354`는 `text.splitlines()`로 본문까지 모두 list로 materialize한 뒤에야 첫 H2를 찾는다. staged 경로도 `:296-299`에서 `git show` 전체 blob을 받는다. 이후의 `preamble` slice만으로는 "파일 시작부터 첫 `##` 직전까지만 읽는다"는 Task 1/design의 context-diet 계약을 만족하지 않는다.
- Impact: 긴 완료/활성 계획의 구현 이력·테스트 출력·개인 데이터가 parser process에 불필요하게 들어온다. header-only registry의 핵심 비용·노출 경계가 무너진다.
- Fix: disk reader는 line streaming으로 첫 exact H2를 만나면 즉시 중단하고 preamble만 반환하라. staged reader도 stdout을 line-streaming하여 같은 지점에서 process를 종료/닫고, full blob fallback을 쓰지 말라. 첫 H2 뒤에 metadata처럼 보이는 invalid 값과 큰 body를 두고, reader가 H2 뒤 입력을 소비하지 않으며 결과/digest가 변하지 않는 테스트를 추가하라.

### P1 — staged 검증이 index에 없는 reference를 worktree에서 허용한다

- Evidence: `scripts/roadmap_registry.py:509-517`은 `record.staged`여도 `git show :reference`가 실패하면 `(root / reference_path).read_text()`로 fallback한다. 따라서 stage된 plan이 아직 stage하지 않은 worktree-only 파일을 참고하면 pre-commit 검사가 통과하지만 commit에는 그 파일이 없다.
- Impact: `--staged`가 commit 대상이 아닌 파일과 줄 수를 검증해 staged-index 계약 및 hook의 안전성을 위반한다.
- Fix: `staged=True`에서는 index read 실패를 즉시 missing-reference error로 처리하고 disk fallback을 금지하라 (`_read_plan()`도 같은 fail-closed 원칙 적용). stage된 plan이 untracked worktree-only reference를 가리키는 fixture와, index/worktree reference line count가 다른 fixture를 추가하여 index 값만 쓰는지 검증하라.

### P1 — metadata가 전혀 없는 todo/active 계획이 조용히 registry에서 사라진다

- Evidence: `_has_index_header()`는 known field 하나도 없으면 `False`를 반환한다 (`scripts/roadmap_registry.py:307-315`). `load_registry()`는 디렉터리 구분 없이 그런 모든 file을 `continue`한다 (`:452-455`). 구현 보고서는 **legacy completed** plan만 migration boundary로 skip한다고 했지만 코드의 skip은 `todo`와 `active`에도 적용된다. `docs/PLANS.md`의 initial migration 대상은 현행 `todo/`와 `active/`다.
- Impact: malformed/empty header 또는 아직 이행되지 않은 active/todo milestone은 renderer/checker 입력에서 누락되어 authoritative roadmap에서 보이지 않고 actionable error도 없다.
- Fix: header 없는 legacy `completed/`만 명시적으로 skip하고, `todo/`와 `active/`는 field 없는 경우에도 record/parse error를 만들어 모든 필수 필드 오류를 보고하라. 각각의 headerless todo·active가 record ID/relative file/field/correction을 포함한 실패를 내고, headerless completed만 skip되는 테스트를 추가하라.

### P1 — `다음 행동`의 “한 문장” 계약을 검증하지 않는다

- Evidence: `scripts/roadmap_registry.py:717-727`은 비어 있음과 120자 초과만 검사한다. 예를 들어 `첫 행동을 한다. 이어서 둘째 행동을 한다.`는 120자 이하여서 허용된다.
- Impact: roadmap 행에 단일 resume action만 넣는 design 제약이 기계적으로 보장되지 않는다.
- Fix: 문장 종결 부호와 공백에 대한 명확하고 문서화된 validation rule을 도입해 두 개 이상의 문장을 거부하라(한글 서술어처럼 종결 부호 없는 단일 action은 허용). 두-문장, 120자 경계, 정상 단문을 각각 단언하는 tests를 추가하라.

### P1 — tests가 요구한 lifecycle/cardinality/actionability/body-boundary 사례를 실제로 증명하지 않는다

- Evidence:
  - `scripts/tests/test_roadmap_registry.py:62-65`의 H2 뒤 body에는 parser가 인식할 metadata가 없어, `:86-104` test는 parser가 body를 읽거나 재해석해도 통과한다.
  - `:195-204`는 두 `Picked Up` record를 `todo/`에 만든다. 따라서 `:204`의 `"Picked Up"` assertion은 global 0–1 cardinality check가 없어도 todo lifecycle error만으로 통과한다. `:200`의 status assertion도 generic `"상태"`를 허용해 unknown-status check가 아니라 lifecycle error로 통과할 수 있다.
  - brief가 요구한 **each forbidden directory/state pair**와 달리 `:206-217`은 세 pair만 만든다. 허용 조합은 todo=Todo, active=Todo/Picked Up/Blocked, completed=Done이므로 나머지 네 forbidden pair도 검증되지 않는다.
  - missing-field test는 ID/file/field만 검사한다 (`:129-136`); brief가 요구한 concrete correction command는 검사하지 않는다.
- Impact: 보고된 9 passing tests는 핵심 acceptance conditions 회귀를 막지 못한다.
- Fix: unrelated lifecycle errors가 없는 active fixture로 two-Picked-Up case를 만들고 exact cardinality message를 assert하라. seven forbidden directory/status pairs를 subtest로 전부 열거하라. 모든 missing-field assertion에 correction command를 포함하고, H2 뒤에는 duplicate/invalid metadata를 배치해 header parsing 결과에 영향이 없음을 단언하라.

### P2 — header grammar가 strict하지 않고 header 외 preamble text를 무시한다

- Evidence: `scripts/roadmap_registry.py:361-378`은 recognized field/reference line 외 모든 preamble line을 조용히 무시한다. `:307-315`도 file 시작의 arbitrary prose 또는 malformed quoted field를 무시한 채 나중의 known field 하나만으로 header를 활성화한다. H1이 마지막 recognized field 뒤에 있다는 것만 검사한다 (`:389-407`).
- Impact: design이 금지한 code block, test output, 장문 배경, 잘못된 field spelling이 index header에 들어가도 validator가 발견하지 못할 수 있다. “blockquote header 뒤의 단일 H1” 구조가 강제되지 않는다.
- Fix: first nonblank line부터 H1까지를 finite-state grammar로 parse하라: 허용된 blockquote fields, `참고 범위` 아래의 reference bullets, blank lines, 정확히 하나의 후속 H1만 허용하고 그 외 nonblank input/duplicate field를 actionable error로 만들라. malformed field, prose-before-header, code fence, and reference bullet outside the reference section tests를 추가하라.

### P2 — 새 foundation에 불필요한 compatibility alias가 많아 module surface가 과도하다

- Evidence: `ReferenceRange` alias properties (`scripts/roadmap_registry.py:76-92`), `RegistryError` alias properties (`:105-127`), `PlanRecord` alias properties (`:161-201`)만 약 80 lines다. Task 1은 새 모듈이며 요구 public interface는 dataclass와 다섯 함수이지 이 호환 alias들이 아니다. 결과적으로 parser/validator 840 lines에 tests 259 lines가 되어 핵심 grammar보다 API 추측 비용이 크다.
- Impact: 후속 renderer/checker가 여러 동의어를 임의로 채택할 수 있어 API를 안정화하기 어려우며 유지보수·test surface만 늘어난다.
- Fix: 실제 caller가 없는 alias를 제거하고 요구된 canonical dataclass field만 export하라. 외부 호환이 필요한 alias가 확인되면 그 caller와 해당 alias만 별도 근거 및 test로 추가하라.

## Positive observations

- Immutable/slot dataclasses, canonical JSON SHA-256 serialization, record sorting, reference inclusive-bound validation, and lifecycle mapping 자체의 구현 방향은 적절하다.
- `git diff --check`은 clean하다.

## Finding count

| Severity | Count |
| --- | ---: |
| P0 | 0 |
| P1 | 5 |
| P2 | 2 |
| P3 | 0 |

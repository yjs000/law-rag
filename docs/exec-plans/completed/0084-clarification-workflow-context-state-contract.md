> 작업 ID: `B-013`
> 상태: `Done`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `Security`
> 선행 조건: 없음
> 다음 행동: 없음 — run별 Context 격리와 관련 회귀 검증 완료.
> 참고 범위:
> - `apps/api/app/adapters/llamaindex_clarification_workflow.py` L25-L203 — run별 `Context.store` 상태
> - `apps/api/tests/test_clarification_workflow.py` L102-L319 — workflow 이벤트·상태 전이 회귀 테스트
> - `docs/superpowers/specs/2026-09-23-clarification-context-state-contract-design.md` L1-L60 — 승인된 Context·case·phase 경계 설계

# LlamaIndex Clarification Context State Contract Implementation Plan

> **For agentic workers:** 구현 시 `superpowers:executing-plans`를 적용한다. 사용자가 별도로 subagent 방식을 선택하면 `superpowers:subagent-driven-development`를 적용한다.

**Goal:** 여러 HTTP 턴의 clarification 정본은 PostgreSQL case에 두고, 한 Workflow run의 임시 상태는 LlamaIndex `Context`에서만 공유한다.

**Architecture:** `run_turn()`마다 `Context(self)`를 새로 만들어 같은 Context를 `Workflow.run(ctx=...)`과 각 step에 전달한다. Workflow 이벤트는 현재의 `request_id`와 공개 정책만 담고, 다음 HTTP 턴은 repository에서 case를 다시 읽는다. `prepare`의 구조화 결과는 기존 question execution snapshot을 거쳐 `core`와 `finalize`로 전달된다.

**Tech Stack:** Python 3.14, LlamaIndex Workflow, pytest, PostgreSQL clarification case repository.

**Spec:** `docs/superpowers/specs/2026-09-23-clarification-context-state-contract-design.md`

## 전역 제약

- `ClarificationTurnOrchestrator.run_turn(request, owner)`의 application-facing 계약과 기존 case repository의 version·소유권·만료 규칙을 유지한다.
- 원 질문·사용자 fact 값·capability를 Workflow 이벤트나 로그에 싣지 않는다. Context는 한 run 뒤 보관·직렬화하지 않는다.
- extractor 의미, Web의 bounded `conversation_context`, answer prompt, execution 10분 수명, `prepare → core → finalize` phase 계약은 바꾸지 않는다.
- B-014의 stale conflict API 응답과 Web continuation, B-009의 브라우저 acceptance는 이 계획에 넣지 않는다.

## 리뷰 중점

1. 두 소유자의 run이 겹칠 때 각각 자기 case·판정만 사용한다 — Task 1의 동시 실행 테스트.
2. 한 run의 interpreter가 실패해도 다른 run과 다음 run의 사실·오류가 섞이지 않는다 — Task 1의 실패 병행 테스트.
3. 두 번째 HTTP 턴이 이전 Context 없이 저장된 case의 원 질문·facts를 읽는다 — Task 1의 후속 턴 테스트.
4. Workflow 이벤트에는 민감한 case/fact payload가 없다 — 기존 이벤트 필드 테스트와 Task 2 검토.
5. cancel·즉시 답변 요청·남은 사실 질문의 정책은 refactor 전후 같다 — 기존 workflow 상태 전이 테스트.

---

### Task 1: run 격리와 기존 후속 턴 동작 고정

- **결과:** 두 소유자의 병행 run, 한 run의 interpreter 실패, 저장된 case를 사용하는 다음 run을 재현하는 테스트가 생긴다. 인스턴스에 turn 상태 map을 두지 않는 구조 계약은 현재 코드에서 RED로 확인한다.
- **대상:** `apps/api/tests/test_clarification_workflow.py` L1-L101의 fake·요청 helper와 L102-L319의 회귀 테스트 수정 약 80줄; `apps/api/app/adapters/llamaindex_clarification_workflow.py` L25-L84 읽기 전용 확인 0줄. 예상 변경량 합계 약 80줄.
- **실행 절차:**
  1. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_clarification_workflow.py -q`로 기존 상태 전이·비공개 이벤트·provider 실패의 GREEN 기준선을 확인한다.
  2. 서로 다른 질문·owner와 서로 다른 판정을 barrier로 겹치게 하는 fake를 추가하고 `asyncio.gather`로 두 `run_turn()` 결과의 case ID·fact·owner scope가 입력별로 분리되는지 검증한다. 한 interpreter만 실패할 때 다른 결과와 다음 run이 정상이고 실패 결과에 사용자 사실이 없는지도 확인한다.
  3. 첫 run에서 생성한 case ID로 다음 run을 호출해 저장된 원 질문·남은 fact를 조회하는지 확인한다. 별도 구조 계약 테스트는 Workflow 인스턴스에 요청별 상태 map이 없음을 검사한다.
  4. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_clarification_workflow.py -q`를 실행해 구조 계약의 RED를 확인한다. 동시성 행동 테스트가 기존 코드에서 이미 통과하면 characterization으로 기록하고 실패를 억지로 만들지 않는다.
  5. `git diff --check`와 테스트 diff를 확인한다.
- **완료 증거:** 새 구조 계약 테스트가 현재 `_turns` 때문에 실패하고, 동시성·실패·다음 턴 테스트가 상태 혼합을 발견할 수 있는 서로 다른 입력·결과를 검사한다.
- **의존성:** 없음.

### Task 2: Workflow 임시 상태를 run별 Context로 이동

- **결과:** `run_turn()`가 새 `Context`를 만들고 모든 step이 해당 Context의 request·owner·record·judgment를 읽고 갱신한다. `_turns`, `_state()`, 읽히지 않는 `case_id` 기록이 사라진다.
- **대상:** `apps/api/app/adapters/llamaindex_clarification_workflow.py` L25-L210 수정 약 65줄; `apps/api/tests/test_clarification_workflow.py` L102-L319 필요한 assertion 보강 약 10줄. 예상 변경량 합계 약 75줄.
- **실행 절차:**
  1. Task 1의 RED와 GREEN 결과를 확인한다. 로컬 LlamaIndex 계약은 `Context(workflow)`와 `Workflow.run(ctx=Context, start_event=...)`다.
  2. `run_turn()`에서 매 호출 새 Context를 만들고 비공개 turn 상태를 `ctx.store`에 넣는다. `load_case`부터 `format_questions`까지 모든 step이 전달된 `ctx`에서 상태를 읽고 변경 뒤 저장하게 한다. 이벤트 필드와 `ClarificationTurnOrchestrator`의 공개 메서드 서명은 유지한다.
  3. 기존 repository `get_owned`·`create_or_get`·version 조건 `merge` 호출 위치와 interpreter 실패의 안전 결과를 유지한다. Workflow 객체의 `_turns`·`_state()` 및 소비하지 않는 `request_id`/`case_id` Context 기록을 제거한다.
  4. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_clarification_workflow.py -q`와 `.\scripts\run_python.ps1 -m ruff check apps/api/app/adapters/llamaindex_clarification_workflow.py apps/api/tests/test_clarification_workflow.py`를 실행한다.
  5. `git diff --check`와 adapter diff를 확인해 민감한 필드가 이벤트·로그·execution phase로 이동하지 않았는지 검토한다.
- **완료 증거:** Task 1의 구조 계약과 모든 workflow 회귀가 GREEN이고, 동일 Workflow 인스턴스의 병행 run·실패 후 run에서 교차 상태가 없다.
- **의존성:** Task 1의 동시성·실패·다음 턴 회귀와 구조 계약 RED.

### Task 3: 실행 경계 문서와 API 회귀 검증

- **결과:** 학습 흐름도가 실제 구현과 일치하고 clarification API 경계 및 저장된 execution snapshot의 기존 동작이 통과한다.
- **대상:** `docs/learning/01-system-map.md` L72-L92의 구현 전 표기 수정 약 2줄; `apps/api/tests/test_clarification_answering.py` L419-L625와 `apps/api/tests/test_v2_question_executions.py` L178-L505 검증 0줄; 이 계획의 결과·잔여 작업 기록 약 10줄; `docs/ROADMAP.md` renderer 산출물. 예상 변경량 합계 약 12줄과 생성된 roadmap 변경.
- **실행 절차:**
  1. Task 2 검증을 확인하고 학습 문서의 B-013 목표 흐름 표시를 현재 동작으로 바꾼다. 승인 설계의 `prepare` 안 Context, `core`/`finalize`의 execution snapshot, 다음 HTTP 턴의 case 재조회가 코드와 일치하는지 대조한다.
  2. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_clarification_workflow.py apps/api/tests/test_clarification_answering.py apps/api/tests/test_v2_question_executions.py -q`로 관련 API 회귀를 검증한다.
  3. `.\scripts\run_python.ps1 -m ruff check apps/api/app/adapters/llamaindex_clarification_workflow.py apps/api/tests/test_clarification_workflow.py`, `.\scripts\run_python.ps1 scripts/check_docs.py`, `.\scripts\run_python.ps1 scripts/check_roadmap.py`와 `git diff --check`를 실행한다. 병합 전 대표 검증은 `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`로 수행한다.
  4. 결과와 잔여 B-014/B-009 경계를 이 계획에 기록한다. 완료 조건이 모두 충족되면 상태를 `Done`으로 바꾸고 동일 파일명을 `completed/`로 이동한 뒤 `.\scripts\run_python.ps1 scripts/render_roadmap.py`, `.\scripts\run_python.ps1 scripts/check_roadmap.py`를 실행하고 staged diff를 확인한다.
- **완료 증거:** focused 테스트·ruff·문서 검사·대표 검증이 성공하고, 학습 그림과 구현된 phase/state 경계가 일치한다. B-014와 B-009는 각각의 계획에서 이어진다.
- **의존성:** Task 2의 per-run Context 구현과 focused 검증.

## 결과 및 잔여 작업

- run마다 새 `Context`를 생성하고 임시 상태를 해당 Context에만 보관한다. LlamaIndex 런타임의 내부 메모리 snapshot이 dataclass 상태를 직렬화하므로, 신뢰된 로컬 객체에 한해 `PickleSerializer`를 사용한다. Context를 후속 HTTP 요청이나 execution phase에 보관하지 않는다.
- 기존 repository의 case 소유권·version·만료 계약과 이벤트 필드를 유지했다. 병행 run, 한 run의 interpreter 실패, 새 Workflow 인스턴스의 저장 case 재조회 회귀를 추가했다.
- focused API 테스트 69개, 전체 API 테스트 1015개 통과(3개 skip), core 37개와 collector 97개 통과(5개 skip). Ruff, 문서·로드맵 검사와 worktree Web lint(기존 경고 2건)·테스트 147개도 통과했다. `verify.ps1`의 pnpm 단계는 worktree의 외부 의존성 junction을 재설치 대상으로 판단해 중단되었다. 같은 변경되지 않은 Web 소스의 main checkout에서 Turbopack build와 TypeScript 검사는 통과했다. Worktree의 webpack 대체 build와 그 생성 파일을 포함한 TypeScript 검사에서는 `oauthRedirectMessage` export 오류가 재현되므로, worktree의 Web build는 검증 제한으로 남긴다.
- 잔여 작업: B-015의 자유 문장 fact 추출과 B-016의 원 질문·누적 fact 답변 입력, 그 뒤 B-014의 API·Web 교차 계층 회귀와 B-009의 브라우저 acceptance.

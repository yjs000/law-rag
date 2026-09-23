> 작업 ID: `B-013`
> 상태: `Picked Up`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `Security`
> 선행 조건: 없음
> 다음 행동: 작성한 per-run Context와 PostgreSQL case 경계 설계 문서에 대한 사용자 검토를 받는다.
> 참고 범위:
> - `apps/api/app/adapters/llamaindex_clarification_workflow.py` L25-L210 — 현재 `_turns` 상태와 `Context.store` 기록
> - `apps/api/tests/test_clarification_workflow.py` L102-L319 — workflow 이벤트·상태 전이 회귀 테스트
> - `docs/superpowers/specs/2026-09-23-clarification-context-state-contract-design.md` L1-L39 — 승인 검토할 Context·case·phase 경계 설계

# LlamaIndex Clarification Context State Contract Implementation Plan

**Goal:** 여러 HTTP 턴의 clarification 정본은 PostgreSQL case에 유지하면서, 한 Workflow run 안에서 step들이 공유하는 요청 상태는 LlamaIndex가 지원하는 Context 계약으로 관리하고 write-only 상태 기록을 남기지 않는다.

**State boundary:** `ClarificationCaseRepository`는 사용자 추가정보와 case version·소유권·만료를 턴 간 보존한다. LlamaIndex `Context`는 한 run의 request·owner·record·judgment만 격리하며, 별도 승인 없이 HTTP 턴 간 Context를 재사용하거나 직렬화하지 않는다.

### Task 1: 현재 Context 우회와 동시 run 격리 실패 가능성 재현

- **결과:** 같은 Workflow 인스턴스에서 서로 다른 두 turn을 동시에 실행해 state 교차 오염·정리 누락·write-only Context 기록을 관찰하는 RED 또는 characterization 테스트가 생긴다.
- **대상:** `apps/api/tests/test_clarification_workflow.py` L102-L319 수정 약 55줄, `apps/api/app/adapters/llamaindex_clarification_workflow.py` L25-L84 검토, 합계 약 55줄.
- **실행 절차:** `asyncio.gather`로 서로 다른 case·owner·judgment를 동시에 실행하고 각 결과가 자기 입력만 반영하는지, 성공·예외 후 임시 상태가 남지 않는지 검증한다. `ctx.store`에 기록한 값이 어느 step에서도 소비되지 않는 현재 계약을 테스트 이름과 assertion으로 드러낸다. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_clarification_workflow.py -q`로 RED 또는 기존 동작의 characterization 결과를 확인한다.
- **완료 증거:** 재현 테스트가 인스턴스 공유 상태와 Context 상태의 책임 차이를 명시하며, 동시 요청의 결과가 서로 바뀌면 실패한다.
- **의존성:** 없음.

### Task 2: per-run 상태를 Context 계약으로 정규화

- **결과:** step 간 상태는 run별 Context에서 읽고 쓰며, `_turns` 같은 Workflow 인스턴스 공유 mutable map과 사용되지 않는 `ctx.store` 값이 제거된다. PostgreSQL case는 계속 턴 간 정본이다.
- **대상:** `apps/api/app/adapters/llamaindex_clarification_workflow.py` L25-L210 수정 약 50줄, `apps/api/app/application/clarification_workflow.py` L75-L103 필요 시 수정 약 8줄, 합계 최대 약 58줄.
- **실행 절차:** 민감한 사용자 사실을 이벤트 payload에 넣지 않는 기존 보안 경계를 유지하면서 request·owner·record·judgment를 run별 Context로 전달한다. HTTP 요청 사이에는 Context를 재사용하지 않고 case ID로 repository를 다시 조회한다. Task 1 테스트와 기존 workflow 테스트를 실행하고 `git diff --check`로 변경을 확인한다.
- **완료 증거:** 모든 step이 동일 run의 Context만 사용하고, 인스턴스 수준 임시 turn map과 읽히지 않는 Context write가 없으며, 기존 상태 전이 결과가 유지된다.
- **의존성:** Task 1의 재현 테스트.

### Task 3: 상태 책임 문서화와 전체 관련 검증

- **결과:** Context와 repository의 책임 경계가 운영·설계 문서에 명시되고 관련 API 회귀가 통과한다.
- **대상:** `docs/design-docs/`의 clarification 관련 설계 문서 수정 약 12줄, `apps/api/tests/test_clarification_answering.py` L419-L625 검증, 이 계획 결과 기록 약 10줄, `docs/ROADMAP.md` renderer 생성 변경.
- **실행 절차:** Context는 per-run, repository는 cross-turn이라는 계약과 Context 비직렬화 원칙을 기록한다. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_clarification_workflow.py apps/api/tests/test_clarification_answering.py apps/api/tests/test_v2_question_executions.py -q`, `git diff --check`, roadmap renderer와 checker를 실행한다.
- **완료 증거:** 상태 소유권 문서와 동시 run 회귀 테스트가 일치하고 관련 API 테스트가 모두 통과한다.
- **의존성:** Task 2 완료.

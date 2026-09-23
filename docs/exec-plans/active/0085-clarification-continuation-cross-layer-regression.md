> 작업 ID: `B-014`
> 상태: `Todo`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `UX`
> 선행 조건: `B-013` 완료 후
> 다음 행동: API stale case conflict, Web continuation payload, 최초 질문부터 완료까지의 교차 계층 회귀를 고정한다.
> 참고 범위:
> - `apps/api/tests/test_v2_question_executions.py` L178-L505 — capability 전달, continuation 호출, case 오류 API 경계
> - `apps/api/app/adapters/postgres_clarification_case.py` L146-L180 — version 기반 stale case 쓰기 거부
> - `apps/web/app/page.tsx` L568-L608 — 다음 요청에 case ID와 capability를 연결하는 제출 경로

# Clarification Continuation Cross-Layer Regression Implementation Plan

**Goal:** 최초 clarification 질문부터 부분 답변·남은 질문·완료까지의 사용자 흐름과 동시성 실패 경계를 API와 Web 회귀 테스트로 고정해, 단위 테스트가 통과해도 실제 대화가 끊기는 공백을 제거한다.

**Safety contract:** 동시 요청은 서로의 turn state를 읽지 않는다. 같은 case의 stale 답변은 데이터를 덮어쓰지 않고 열거 불가능한 안정적 오류로 끝난다. Web은 capability를 화면·대화 context에 노출하지 않고 continuation 요청에만 전달한다.

**착수 조건:** B-013의 run별 Context 격리와 focused 검증이 완료되어 API 경계 회귀의 기준이 마련되었다.

### Task 1: stale case conflict의 API 응답과 저장 상태 검증

- **결과:** 동일한 이전 case version의 후속 요청 중 하나만 반영되고 stale 요청은 case 존재 여부나 capability를 노출하지 않는 안정된 HTTP conflict로 끝나며 기존 fact를 덮어쓰지 않는다.
- **대상:** `apps/api/tests/test_v2_question_executions.py` L178-L505 수정 약 55줄, `apps/api/app/api/v2/executions.py` L169-L225 수정 약 15줄, 합계 약 70줄.
- **실행 절차:** 같은 case ID와 version으로 두 continuation 요청을 경쟁시킨다. repository version guard가 한 쓰기만 반영하는지 확인하고, 나머지 요청의 conflict 변환을 API 테스트에서 먼저 실패시킨다. 안정된 status/code/message가 case 소유권과 capability 존재를 드러내지 않는지 확인한 뒤 `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_v2_question_executions.py -q`를 실행한다. Workflow run 자체의 Context 격리는 선행 B-013 테스트에 맡긴다.
- **완료 증거:** stale continuation은 일관된 안전 응답을 반환하고 repository에는 유효한 한 번의 병합만 남는다.
- **의존성:** B-013 완료 및 per-run Context 격리의 focused 검증.

### Task 2: Web continuation 실제 요청 payload 회귀 검증

- **결과:** waiting 응답 뒤 다음 자유 문장 제출이 같은 case ID와 capability를 보내고, 완료·오류·중지·새 대화에서는 stale continuation을 재사용하지 않는 테스트가 생긴다.
- **대상:** `apps/web/lib/chat-state.test.ts` L242-L258 수정 약 45줄, `apps/web/lib/api-client-flow.test.ts` V2 요청 구간 수정 약 50줄, `apps/web/app/page.test.tsx` L1-L27 및 제출 흐름 수정 약 45줄, 필요 시 `apps/web/app/page.tsx` L568-L608 최소 추출 약 25줄, 합계 최대 약 165줄.
- **실행 절차:** 첫 waiting 응답의 opaque capability를 메시지와 conversation context에서 숨긴 채 다음 POST body에만 포함하는지 확인한다. terminal 응답, 요청 실패, 사용자 중지, 새 채팅에서 case ID와 capability가 제거되는 경계 테스트를 먼저 실패시킨 뒤 최소 상태 정리 변경만 적용한다. `pnpm test:web`과 `pnpm typecheck`를 실행한다.
- **완료 증거:** 실제 API 요청 캡처 assertion이 continuation 식별자 전달과 stale 상태 제거를 모두 검증하고 capability 문자열은 렌더링 결과에 없다.
- **의존성:** Task 1의 오류 계약.

### Task 3: 최초 질문부터 완료까지 교차 계층 시나리오 고정

- **결과:** 최초 `clarification_required`, 부분 답변, 남은 질문, 전체 답변 또는 현재 정보 답변을 하나의 재현 가능한 시나리오로 검증한다.
- **대상:** `apps/api/tests/test_clarification_answering.py` L419-L625 수정 약 65줄, `apps/web/lib/api-client-flow.test.ts` clarification 시나리오 수정 약 55줄, `apps/web/app/page.test.tsx` clarification 사용자 흐름 수정 약 55줄, 이 계획 결과 기록 약 10줄, `docs/ROADMAP.md` renderer 생성 변경, 합계 약 185줄.
- **실행 절차:** 동일 case ID를 사용해 remaining count가 감소하고 마지막 턴에서 clarification이 사라지는지 API 응답과 Web state를 대조한다. 익명 capability가 공개 응답·화면·conversation context에 없는지 확인한다. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_clarification_workflow.py apps/api/tests/test_clarification_answering.py apps/api/tests/test_v2_question_executions.py -q`, `pnpm test:web`, `pnpm lint:web`, `pnpm typecheck`, `git diff --check`를 실행한다.
- **완료 증거:** 첫 질문부터 terminal 응답까지 동일 case의 상태·payload·화면 동작이 자동 회귀 테스트로 재현되고 전체 관련 검증이 통과한다.
- **의존성:** Task 1과 Task 2 완료.

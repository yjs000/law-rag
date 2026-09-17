> 작업 ID: `B-009`
> 상태: `Todo`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `UX`
> 선행 조건: 없음
> 다음 행동: clarification 상태 전이표와 첫 질문부터 후속 답변까지의 회귀 시나리오를 고정한다.
> 참고 범위:
> - `apps/api/app/application/clarification_workflow.py` L1-L186 — clarification intent·fact 병합·상태 전이의 application 계약
> - `apps/api/app/api/v2/executions.py` L169-L225 — 최초 route와 후속 clarification case를 V2 실행에 연결하는 경계
> - `apps/web/lib/chat-state.ts` L226-L339 — clarification case·capability 보관과 후속 대화 상태 정리 경계

# clarification_required 상태·대화 연결 검증 Implementation Plan

**Goal:** `clarification_required`가 나온 뒤 서버 상태와 Web 대화가 같은 case를 안전하게 이어 가고, 사용자의 추가 답변을 반영해 다시 묻거나 최종 답변으로 끝나는지 처음부터 끝까지 확인한다.

**State contract:** 최초 추가 질문은 `waiting_for_user`가 되고, 일부만 답하면 답하지 않은 항목만 남는다. 필요한 답을 모두 주면 `completed/full`, 지금 정보로 답해 달라고 하면 `completed/conditional`로 끝난다. 취소·새 질문·만료·다른 사용자의 case에서는 이전 상태나 capability가 다음 대화에 남지 않는다.

### Task 1: 서버 clarification 상태 전이표 검증

- **결과:** 최초 질문, 일부 답변, 전체 답변, 답변 거절, 즉시 답변 요청, 취소, 만료·잘못된 소유권의 상태와 결과가 회귀 테스트로 고정된다.
- **대상:** `apps/api/tests/test_clarification_workflow.py` L1-L319 수정 약 70줄, `apps/api/tests/test_v2_question_executions.py` clarification 구간 수정 약 55줄, 합계 약 125줄.
- **실행 절차:** 상태 전이표를 테스트 이름과 assertion으로 옮긴다. 같은 case version에서 이미 답한 fact가 다시 열리지 않고 `remaining_count`가 줄어드는지, 저장은 grounded 응답 생성 뒤에만 일어나는지, stale·foreign·expired case가 안전하게 거부되는지 검증한다. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_clarification_workflow.py apps/api/tests/test_v2_question_executions.py`로 현재 결과를 확인하고 실패를 재현한다.
- **완료 증거:** 모든 상태 전이 행에 정상·실패·경계 테스트가 있으며, 발견된 불일치는 재현 가능한 RED 테스트로 남는다.
- **의존성:** 없음.

### Task 2: Web 후속 대화 연결 검증과 최소 수정

- **결과:** Web이 서버의 case ID와 익명 capability를 화면에 노출하지 않고 다음 사용자 메시지에만 붙이며, terminal 응답 뒤에는 상태를 지운다.
- **대상:** `apps/web/lib/chat-state.test.ts` L240-L258 수정 약 45줄, `apps/web/lib/api-client-flow.test.ts`의 V2 실행 구간 수정 약 35줄, `apps/web/app/page.test.tsx` L1-L27 수정 약 20줄, 필요 시 대응 구현 파일 합계 최대 약 35줄.
- **실행 절차:** 최초 `waiting_for_user` 응답, 사용자의 자유 문장 답변, 일부 fact 잔존, 전체 완료, “현재 정보로 답변”, 중지·오류·새 대화 시나리오를 한 흐름으로 검증한다. 다음 요청이 같은 `clarification_case_id`와 capability를 보내되 렌더링 메시지·대화 context·로그에는 capability가 없는지 확인한다. 실패가 있으면 상태 소유 경계를 유지하는 최소 수정만 하고 `pnpm test:web`, `pnpm lint:web`, `pnpm typecheck`를 실행한다.
- **완료 증거:** 사용자가 추가 질문에 자연어로 답했을 때 같은 대화가 이어지고, 완료 또는 이탈 시 stale clarification 상태가 다음 질문에 붙지 않는다.
- **의존성:** Task 1의 상태 전이표.

### Task 3: 실제 대화 시나리오와 전체 검증

- **결과:** 브라우저에서 추가 질문이 보이고, 사용자가 답한 뒤 남은 질문 또는 근거 있는 최종 답변으로 이어지는 사용자 여정 증거가 남는다.
- **대상:** API·Web 통합/E2E clarification 시나리오 추가 약 80줄, `docs/FRONTEND.md` clarification 상태 설명 추가 약 6줄, 이 계획 결과 기록 약 12줄, `docs/ROADMAP.md` renderer 생성 변경.
- **실행 절차:** 대표 질문 하나로 `clarification_required`를 만들고, 일부 답변 턴과 완료 턴을 같은 대화에서 실행한다. 각 턴의 공개 응답, private state, 화면 표시를 대조하고 새로고침·중지 후에도 권한 정보가 노출되거나 잘못 재사용되지 않는지 확인한다. API와 Web 전체 검증, `git diff --check`, 관련 문서 검사를 실행한다. 결함이 없으면 검증 증거만 기록하고, 결함을 수정했다면 회귀 테스트와 관측 가능성을 함께 남긴다. 계획을 `completed/`로 이동한 뒤 roadmap renderer와 checker를 실행한다.
- **완료 증거:** 최초 추가 질문부터 최종 답변까지 동일 case의 상태가 기대대로 전이하고, 화면에서도 대화가 끊기지 않는 재현 가능한 E2E 증거와 전체 검증 성공 결과가 있다.
- **의존성:** Task 1과 Task 2 완료.

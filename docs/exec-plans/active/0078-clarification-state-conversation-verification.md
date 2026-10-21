> 작업 ID: `B-009`
> 상태: `Blocked`
> 우선순위: `P1`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `UX`
> 선행 조건: `B-013`, `B-015`, `B-016`, `B-014` 완료
> 다음 행동: B-013·B-015·B-016·B-014 완료 후 최초 추가 질문부터 최종 답변까지 통합 acceptance를 실행한다.
> 참고 범위:
> - `apps/api/app/application/clarification_workflow.py` L1-L186 — clarification intent·fact 병합·상태 전이의 application 계약
> - `apps/api/app/api/v2/executions.py` L169-L225 — 최초 route와 후속 clarification case를 V2 실행에 연결하는 경계
> - `apps/web/lib/chat-state.ts` L226-L339 — clarification case·capability 보관과 후속 대화 상태 정리 경계

# clarification_required 상태·대화 연결 검증 Implementation Plan

**Goal:** `clarification_required`가 나온 뒤 서버 상태와 Web 대화가 같은 case를 안전하게 이어 가고, 사용자의 추가 답변을 반영해 다시 묻거나 최종 답변으로 끝나는지 처음부터 끝까지 확인한다.

**State contract:** 최초 추가 질문은 `waiting_for_user`가 되고, 일부만 답하면 답하지 않은 항목만 남는다. 필요한 답을 모두 주면 `completed/full`, 지금 정보로 답해 달라고 하면 `completed/conditional`로 끝난다. 취소·새 질문·만료·다른 사용자의 case에서는 이전 상태나 capability가 다음 대화에 남지 않는다.

**차단 사유:** B-013의 per-run state, B-015의 자유 문장 fact 추출, B-016의 원 질문·누적 fact 기반 답변 입력, B-014의 API·Web 회귀가 갖춰지기 전에는 B-009 완료조건을 신뢰성 있게 판정할 수 없다.

**재개 조건:** B-013·B-015·B-016·B-014가 모두 `Done`이고 각 계획의 focused 검증 증거가 기록되어야 한다.

### Task 1: 자식 계획 결과와 상태 전이표 대조

- **결과:** B-013의 Context/repository 책임, B-015의 자유 문장 fact 추출, B-016의 원 질문·누적 fact 답변 입력과 B-014의 회귀 시나리오가 B-009 상태 전이표의 모든 행을 충족한다.
- **대상:** `docs/exec-plans/completed/0084-clarification-workflow-context-state-contract.md`, `0086-clarification-free-text-fact-extraction.md`, `0087-clarification-case-grounded-answer-input.md`, `0085-clarification-continuation-cross-layer-regression.md` 완료 경로 검토, 이 계획 결과 기록 약 15줄.
- **실행 절차:** 최초 질문, 자유 문장 부분·전체 답변의 fact 병합, 원 질문·누적 fact 기반 최종 답변, 현재 정보 답변, 취소·새 질문, stale·foreign·expired case, capability 비노출 증거를 선행 계획 결과와 테스트 이름에 일대일로 대응시킨다. 빠진 행이 있으면 B-009를 완료하지 않고 해당 선행 계획을 보완한다.
- **완료 증거:** 모든 상태 전이 행이 자동 테스트 또는 명시적 E2E 증거에 연결된 대조표가 이 계획에 기록된다.
- **의존성:** B-013·B-015·B-016·B-014 완료.

### Task 2: 실제 대화 통합 acceptance와 완료 판정

- **결과:** 브라우저에서 추가 질문이 보이고, 사용자가 답한 뒤 남은 질문 또는 근거 있는 최종 답변으로 이어지는 사용자 여정 증거가 남는다.
- **대상:** B-014가 확정한 API·Web 통합/E2E clarification 시나리오 검증, `docs/FRONTEND.md` clarification 상태 설명 필요 시 약 6줄, 이 계획 결과 기록 약 12줄, `docs/ROADMAP.md` renderer 생성 변경.
- **실행 절차:** 대표 질문 하나로 `clarification_required`를 만들고 부분 답변 턴과 완료 턴을 같은 대화에서 실행한다. 각 턴의 공개 응답, private state, 화면 표시를 대조하고 새로고침·중지 후에도 권한 정보가 노출되거나 재사용되지 않는지 확인한다. API·Web 전체 검증과 `git diff --check`를 실행하고 실패하면 B-009를 완료하지 않는다. 성공 결과를 기록한 뒤 계획을 `completed/`로 이동하고 roadmap renderer와 checker를 실행한다.
- **완료 증거:** 최초 추가 질문부터 최종 답변까지 동일 case의 상태가 기대대로 전이하고, 화면에서도 대화가 끊기지 않는 재현 가능한 E2E 증거와 전체 검증 성공 결과가 있다.
- **의존성:** Task 1 완료.

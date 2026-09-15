> 작업 ID: F-009
> 상태: Todo
> 유형: Feature
> 보조 라벨: UX, Performance
> 선행 조건: 없음
> 다음 행동: NVIDIA 무료 티어 안내와 SSE 상세 생성 진행 표시의 프런트엔드 회귀 테스트부터 작성한다.
> 참고 범위:
> - `apps/web/app/page.tsx` L596-L603 — SSE 핵심 답변을 streaming 메시지로 반영하는 현재 흐름
> - `apps/web/app/page.tsx` L812-L833 — 메인 환영 화면, 답변 상태, 질문 입력 영역 렌더링
> - `apps/web/lib/chat-state.ts` L270-L285 — 핵심 답변 수신 뒤 streaming 상태를 만드는 상태 전이

# NVIDIA 무료 티어 지연 안내 및 SSE 상세 생성 진행 표시 Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 사용자가 NVIDIA Nemotron 무료 티어의 긴 응답 시간을 미리 예상할 수 있게 하고, SSE 핵심 답변이 먼저 표시된 뒤에도 상세 답변 생성이 계속되고 있음을 명확히 보여준다.

**User-visible copy:** 메인 화면에 `NVIDIA Nemotron 무료 티어 사용으로 답변 생성에 1분 이상 걸릴 수 있습니다.`를 표시한다.

**Architecture:** 기존 V2 SSE와 채팅 메시지 상태 계약을 유지한다. 환영 화면에 정적 안내를 추가하고, 핵심 답변이 도착한 `streaming` 상태에서만 답변 하단에 애니메이션 `...` 진행 표시를 렌더링한다. `complete`, `error`, `stopped` 상태에서는 진행 표시를 제거한다.

### Task 1: 사용자 안내와 진행 상태 회귀 테스트

- [ ] 메인 환영 화면의 승인 문구를 검증하는 프런트엔드 테스트를 작성하고 실패를 확인한다.
- [ ] SSE 핵심 답변 이후 `streaming` 상태에서는 `...`가 보이고 완료·오류·중지 상태에서는 보이지 않는 테스트를 작성하고 실패를 확인한다.
- [ ] 진행 표시가 스크린 리더에 중복 안내를 만들지 않도록 접근성 계약을 테스트한다.

### Task 2: 메인 화면 안내와 SSE 진행 표시 구현

- [ ] 환영 화면에 승인된 NVIDIA Nemotron 무료 티어 지연 안내를 추가한다.
- [ ] 기존 답변을 가리지 않는 답변 하단 진행 표시를 추가하고 현재 상태 스타일과 조화되는 애니메이션을 적용한다.
- [ ] SSE 완료·오류·중지 전이에서 진행 표시가 남지 않는지 확인한다.

### Task 3: 검증과 완료 기록

- [ ] focused 프런트엔드 테스트를 실행한다.
- [ ] `pnpm lint:web`, `pnpm typecheck`, `pnpm test:web`, `pnpm build:web`를 실행한다.
- [ ] 사용자 동작 변경을 `docs/FRONTEND.md`에 기록한다.
- [ ] 결과를 기록하고 계획을 `completed/`로 이동한 뒤 로드맵을 갱신한다.

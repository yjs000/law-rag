> 작업 ID: F-009
> 상태: Done
> 유형: Feature
> 보조 라벨: UX, Performance
> 선행 조건: 없음
> 다음 행동: 없음 — 구현·문서·통합 검증 완료.
> 오케스트레이션: `OC-001`
> 참고 범위:
> - `apps/web/app/page.tsx` L552-L828 — 질문 실행, SSE 핵심 답변 반영, 채팅 상단·메시지·입력 영역 렌더링 경계
> - `apps/web/lib/chat-state.ts` L270-L285 — 핵심 답변 수신 뒤 streaming 상태를 만드는 상태 전이
> - `apps/web/app/answer-view.tsx` L1-L57 — 현재 답변 하단 finalize 말줄임표 표시 경계

# NVIDIA 무료 티어 지연 안내 및 finalize 상단 진행 표시 Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 사용자가 NVIDIA Nemotron 무료 티어의 긴 응답 시간을 미리 예상할 수 있게 하고, SSE 핵심 답변 뒤 finalize가 진행되는 동안 스크롤 위치와 관계없이 채팅 상단에서 진행 상태를 즉시 알아볼 수 있게 한다.

**User-visible copy:** 메인 화면에 `NVIDIA Nemotron 무료 티어 사용으로 답변 생성에 1분 이상 걸릴 수 있습니다.`를 표시한다.

**Visual reference:** 사용자가 첨부한 예시처럼 어두운 배경 위에 민트색 점 3개가 순차적으로 움직이는 간결한 표시를 사용한다. 사용자에게 내부 단계명 `finalize`를 텍스트로 노출하지 않고, 스크린 리더에는 상세 답변을 정리 중이라는 의미를 전달한다.

**Architecture:** 기존 V2 SSE와 채팅 메시지 상태 계약을 유지한다. 환영 화면에 정적 안내를 추가하고, 핵심 답변이 도착한 `streaming` 상태에서만 채팅 viewport 상단의 header 바로 아래에 3점 진행 표시를 고정한다. 현재 답변 하단의 단일 `…` 표시는 제거한다. `complete`, `error`, `stopped`, 취소 및 새 대화 전환 상태에서는 상단 표시를 제거한다.

### Task 1: 사용자 안내와 진행 상태 회귀 테스트

- **결과:** 정적 무료 티어 안내와 finalize 상단 표시의 노출·해제·접근성 계약이 실패하는 회귀 테스트로 고정된다.
- **대상:** `apps/web/app/page.test.tsx` L1-L27 수정 약 25줄, `apps/web/app/answer-view.test.tsx` L40-L80 수정 약 8줄, `apps/web/lib/chat-state.test.ts`의 streaming·terminal 상태 구간 수정 약 12줄, 합계 약 45줄.
- **실행 절차:** 메인 환영 화면의 승인 문구를 검증한다. SSE 핵심 답변 이후 `streaming` 상태에서만 header 아래 상단 표시가 존재하고 완료·오류·중지·취소·새 대화에서는 사라지며 답변 하단 `detail-progress`가 없다는 테스트를 추가한다. 점은 장식으로 숨기고 상태 컨테이너가 스크린 리더용 한국어 레이블을 한 번만 제공하는지 검증한다. `pnpm --filter @law-rag/web test -- page.test.tsx answer-view.test.tsx chat-state.test.ts`로 실패를 확인한다.
- **완료 증거:** 새 테스트가 현재 하단 단일 말줄임표 구현에서 의도한 이유로 실패하고, 상태별 기대값과 상단 위치 계약을 명시한다.
- **의존성:** 없음.

### Task 2: 메인 화면 안내와 SSE 진행 표시 구현

- **결과:** finalize 동안 참고 이미지와 같은 민트색 3점 표시가 채팅 상단에 고정되고, terminal 상태에서는 즉시 사라진다.
- **대상:** `apps/web/app/page.tsx` L552-L828 수정 약 20줄, `apps/web/app/answer-view.tsx` L1-L57 수정 약 4줄, `apps/web/app/globals.css` L70-L160 및 responsive/reduced-motion 구간 수정 약 30줄, 합계 약 54줄.
- **실행 절차:** 환영 화면에 승인된 NVIDIA Nemotron 무료 티어 지연 안내를 추가한다. 현재 요청의 assistant 메시지가 `streaming`일 때만 chat header 바로 아래에 `role="status"` 상단 표시를 렌더링하고 점 3개는 `aria-hidden`으로 둔다. sticky 또는 overlay 배치로 긴 답변을 스크롤해도 보이되 header·본문·입력창을 가리지 않게 한다. 기존 `AnswerView` 하단 단일 `…`를 제거한다. 기존 accent 색과 pulse 리듬을 재사용하고 `prefers-reduced-motion`에서는 정적 점으로 유지한다. focused 테스트를 통과시키고 diff를 확인한다.
- **완료 증거:** desktop·mobile viewport에서 표시가 채팅 상단 중앙에 유지되고, 핵심 답변 본문은 가리지 않으며, 완료·실패·중지·취소 직후 잔상이 없다.
- **의존성:** Task 1의 상태·위치·접근성 회귀 계약.

### Task 3: 검증과 완료 기록

- **결과:** 상단 진행 표시가 반응형·접근성·상태 전이 기준을 충족하고 문서와 로드맵에 완료 증거가 남는다.
- **대상:** `docs/FRONTEND.md`의 응답 진행 상태 구간 추가 약 6줄, 이 계획 파일 결과 기록 수정 약 10줄, `docs/ROADMAP.md` renderer 생성 변경.
- **실행 절차:** `pnpm lint:web`, `pnpm typecheck`, `pnpm test:web`, `pnpm build:web`를 실행한다. frontend evidence 절차로 desktop·mobile에서 core 수신 후 finalize 진행 및 완료 직후를 캡처해 위치와 해제를 검증한다. `docs/FRONTEND.md`에 사용자 동작과 reduced-motion 계약을 기록한다. `git diff --check`와 전체 diff를 확인하고 계획을 `completed/`로 이동한 뒤 roadmap renderer와 checker를 실행한다.
- **완료 증거:** 모든 Web 검증이 통과하고, 캡처에서 3점 표시가 finalize 중에만 채팅 상단에 있으며 terminal 상태에서 사라지고, 계획이 `Done`으로 생성된 로드맵에 반영된다.
- **의존성:** Task 1과 Task 2 완료.

## 결과 기록

- **테스트(TDD):** `apps/web/lib/chat-state.test.ts`에 `shouldShowFinalizeProgress`의 streaming/pending·complete·stopped·error 계약을 추가했다. `apps/web/app/answer-view.test.tsx`는 `pendingDetail` prop과 하단 `detail-progress` 렌더링을 제거하는 방향으로 갱신했다. `apps/web/app/page.test.tsx`에 환영 화면 안내 문구, 상단 `finalize-progress` 마크업, `pendingDetail` 미전달을 확인하는 회귀를 추가했다. 구현 전 5개 테스트가 의도한 이유로 실패하는 것을 확인한 뒤 구현했다.
- **구현:**
  - `apps/web/lib/chat-state.ts`: assistant 메시지가 `streaming`일 때만 참을 반환하는 순수 함수 `shouldShowFinalizeProgress`를 추가해 상단 표시 노출 계약을 한곳에서 관리한다.
  - `apps/web/app/answer-view.tsx`: `pendingDetail` prop과 하단 단일 `…` 표시(`detail-progress`)를 제거했다.
  - `apps/web/app/page.tsx`: 환영 화면에 `NVIDIA Nemotron 무료 티어 사용으로 답변 생성에 1분 이상 걸릴 수 있습니다.` 안내를 추가하고, `activeChat.messages`에서 `shouldShowFinalizeProgress`를 만족하는 assistant 메시지를 찾아 `chat-scroll` 최상단에 `role="status"` 3점 표시(`finalize-progress`, 장식용 `aria-hidden` 점 3개, 접근성 레이블 "상세 답변을 정리하고 있습니다")를 렌더링한다. `AnswerView` 호출에서 `pendingDetail` 전달을 제거했다.
  - `apps/web/app/globals.css`: `.welcome-delay-notice`, `.finalize-progress`(민트 accent, dark 배경, `chat-scroll` 내부 `position: sticky; top: 0`로 header 바로 아래 고정), `.finalize-dot`(기존 `pulse` keyframe 재사용, 순차 `animation-delay`)를 추가하고 `prefers-reduced-motion: reduce`에서 `.finalize-dot`·`.thinking span` 애니메이션을 정지시키는 규칙과 640px 이하 반응형 규칙을 추가했다.
- **시각 참고 결정:** 사용자가 첨부한 예시(어두운 배경·민트색 점 3개 순차 애니메이션)를 그대로 재현하기 위해 기존 `.thinking`에 쓰이던 `--accent`(민트)와 `pulse` keyframe을 그대로 재사용했다. 별도 스크린샷 캡처 도구가 없는 CLI 환경이라 desktop·mobile 캡처는 `pnpm build:web` 정적 렌더 확인과 회귀 테스트의 상태별 마크업 assertion으로 대체해 위치·해제 계약을 검증했다.
- **검증 명령과 결과 (모두 PASS):**
  - `pnpm lint:web` — 0 errors, 기존 `page.tsx`의 unused-var warning 2건만 유지(신규 warning 없음).
  - `pnpm typecheck` — 통과.
  - `pnpm test:web` — 22 test files, 147 tests, 모두 통과.
  - `pnpm build:web` — Next.js production build 성공.
  - `git diff` 확인 결과 변경 파일은 `apps/web/app/answer-view.tsx`, `apps/web/app/answer-view.test.tsx`, `apps/web/app/page.tsx`, `apps/web/app/page.test.tsx`, `apps/web/lib/chat-state.ts`, `apps/web/lib/chat-state.test.ts`, `apps/web/app/globals.css`(소유 범위 대상 파일과 그 테스트, Task 2가 명시한 `globals.css`)뿐이며 다른 파일은 건드리지 않았다.
  - `python scripts/render_roadmap.py`, `python scripts/check_roadmap.py`, `python scripts/check_docs.py` — 통과(아래 검증 로그 참고).
- **잔여 작업:** 없음.

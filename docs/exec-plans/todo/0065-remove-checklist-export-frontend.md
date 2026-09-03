> 작업 ID: F-007
> 상태: Todo
> 유형: Feature
> 보조 라벨: UX
> 선행 조건: 없음
> 다음 행동: UI·클라이언트 제거의 테스트 우선 구현을 시작
> 참고 범위:
> - `docs/product-specs/grounded-legal-qa.md` L7-L13 — 제거 전 핵심 여정과 체크리스트 범위
> - `apps/web/app/page.tsx` L318-L323 — 체크리스트 UI와 내보내기 제어
> - `apps/web/lib/checklist-export.ts` L3-L25 — 프런트 내보내기 렌더링 함수

# 체크리스트 내보내기 프런트 제거 Implementation Plan

## 계획 본문

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 현재 제품 범위에서 체크리스트 내보내기 UI와 프런트 전용 코드를 제거한다.

**Removed product requirement:** 사업 단계 체크리스트를 Markdown을 기본으로, CSV 또는 PDF를 선택해 내보낸다. 동일한 체크리스트 데이터에서 Markdown·CSV·PDF를 생성하고 표지·브랜딩 없는 PDF를 제공한다.

**Architecture:** 프런트 내보내기 제어, Markdown·CSV 생성, PDF 요청 클라이언트만 제거한다. 고정 API, 서버 PDF renderer, export audit·저장 구조는 바꾸지 않는다.

### Task 1: 내보내기 UI와 클라이언트 코드 제거

- [ ] 제거 전 UI 회귀 테스트를 작성하고 실패를 확인한다.
- [ ] AnswerView 내보내기 제어와 PDF 다운로드 호출을 제거한다.
- [ ] 미사용 checklist-export 모듈·테스트를 제거하고 focused test를 통과시킨다.

### Task 2: 검증과 완료 기록

- [ ] pnpm lint:web, pnpm typecheck, pnpm test:web, pnpm build:web를 실행한다.
- [ ] API·서버 renderer·export audit 변경이 없음을 확인한다.
- [ ] 결과를 기록하고 계획을 completed/로 이동한 뒤 로드맵을 갱신한다.

> 작업 ID: F-007
> 상태: `Done`
> 유형: Feature
> 보조 라벨: UX
> 선행 조건: 없음
> 다음 행동: 없음 — 구현·문서·통합 검증 완료.
> 오케스트레이션: `OC-001`
> 참고 범위:
> - `docs/product-specs/grounded-legal-qa.md` L32-L40 — grounded 응답의 체크리스트 계약

# 체크리스트 내보내기 프런트 제거 Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 현재 제품 범위에서 체크리스트 내보내기 UI와 프런트 전용 코드를 제거한다.

**Removed product requirement:** 사업 단계 체크리스트를 Markdown을 기본으로, CSV 또는 PDF를 선택해 내보낸다. 동일한 체크리스트 데이터에서 Markdown·CSV·PDF를 생성하고 표지·브랜딩 없는 PDF를 제공한다.

**Architecture:** 프런트 내보내기 제어, Markdown·CSV 생성, PDF 요청 클라이언트만 제거한다. 고정 API, 서버 PDF renderer, export audit·저장 구조는 바꾸지 않는다.

### Task 1: 내보내기 UI와 클라이언트 코드 제거

- [x] 제거 전 UI 회귀 테스트를 작성하고 실패를 확인한다.
- [x] AnswerView 내보내기 제어와 PDF 다운로드 호출을 제거한다.
- [x] 미사용 checklist-export 모듈·테스트를 제거하고 focused test를 통과시킨다.

### Task 2: 검증과 완료 기록

- [x] pnpm lint:web, pnpm typecheck, pnpm test:web, pnpm build:web를 실행한다.
- [x] API·서버 renderer·export audit 변경이 없음을 확인한다.
- [x] 결과를 기록하고 계획을 completed/로 이동한 뒤 로드맵을 갱신한다.

## 완료 기록 (2026-09-18)

**제거한 항목:**
- `apps/web/app/answer-view.tsx`: 체크리스트 섹션의 `export-controls`(형식 선택 `<select>` + 내보내기
  버튼)와 관련 props(`exportFormat`, `exporting`, `onExport`, `onExportFormat`, 미사용이 된 `question`)를
  제거했다.
- `apps/web/app/page.tsx`: `checklist-export` import, `exportFormat`/`exporting` state,
  `exportChecklist` 핸들러, `api-client`의 `downloadPdf` import와 `AnswerView` 호출부의 관련 props를
  제거했다.
- `apps/web/lib/checklist-export.ts`, `apps/web/lib/checklist-export.test.ts`: 파일을 삭제했다
  (Markdown·CSV 생성, blob 다운로드 유틸리티).

**범위 안내:** 소유 범위 헤더는 `page.tsx`와 `checklist-export.*` 세 파일만 명시했지만, 실제 내보내기
UI는 `page.tsx`가 렌더링을 위임하는 `apps/web/app/answer-view.tsx`(및 그 테스트
`apps/web/app/answer-view.test.tsx`)에 있었다. 내보내기 컨트롤을 실제로 제거하려면 이 두 파일도
함께 고쳐야 했으므로, 프런트 전용 UI 파일로 한정해 최소 범위로 수정했다. API 라우트, 서버 PDF
renderer, export audit·저장 코드는 손대지 않았다 — `git diff --stat`으로 확인.

**변경하지 않은 항목:** `apps/web/lib/api-client.ts`의 `downloadPdf` 함수와
`apps/web/lib/api-client-flow.test.ts`의 관련 테스트는 소유 범위 밖이라 그대로 두었다(더 이상
호출되지 않지만 서버 PDF 엔드포인트 계약은 이 작업 범위가 아님).

**검증 결과 (모두 통과):**
- `pnpm lint:web` — 0 errors, 2 warnings(`page.tsx`의 기존 `currentHistoryId`/`submittedQuestion`
  state가 이번 제거로 read-path를 잃어 미사용 경고만 남음; 컴파일·타입에는 영향 없음)
- `pnpm typecheck` — 통과, 오류 없음
- `pnpm test:web` — 22개 테스트 파일, 142개 테스트 모두 통과 (제거된 `checklist-export.test.ts`의
  테스트 2건 제외하고 나머지 전부 통과, `answer-view.test.tsx`에 추가한 회귀 assertion 포함)
- `pnpm build:web` — Next.js production build 성공

**git diff 범위:** `apps/web/app/answer-view.test.tsx`, `apps/web/app/answer-view.tsx`,
`apps/web/app/page.tsx` 수정, `apps/web/lib/checklist-export.ts`,
`apps/web/lib/checklist-export.test.ts` 삭제. API·서버·감사(audit) 코드 변경 없음.

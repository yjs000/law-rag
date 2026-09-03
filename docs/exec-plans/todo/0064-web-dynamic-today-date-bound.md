> 작업 ID: F-006
> 상태: Todo
> 유형: Feature
> 보조 라벨: UX, Reliability
> 선행 조건: 없음
> 참고 범위:
> - apps/web/app/page.tsx L132-L140, L328-L347, L556-L633, L840-L850 — 날짜 UI·제출 흐름
> - apps/web/lib/api-client.ts L108-L136 — V2 질문 실행 API 경계
> - apps/web/lib/v2-execution.ts L32-L127 — prepare/core/finalize SSE 계약
> - docs/product-specs/grounded-legal-qa.md, docs/FRONTEND.md — 제품·UI 요구

# Web 기준일 선택 상한을 한국 오늘으로 동적 유지 Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 기준일 UI가 한국 날짜 today()를 상한으로 유지하고, 선택값을 V2 질문 실행 API에 그대로 전달한다.

**Architecture:** page.tsx가 date input의 max를 한국 오늘으로 전달하고 한국 날짜 경계에서 갱신한다. 기존 api-client.ts → V2 prepare/core/finalize SSE 흐름은 유지한다. 코퍼스 준비·snapshot·지원 범위의 판정과 갱신은 서버가 최종 권위이며, 프런트는 /v1/corpus/status를 날짜 제어 목적으로 호출·해석하지 않는다.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest.

**Spec:** docs/product-specs/grounded-legal-qa.md; docs/FRONTEND.md

## Global Constraints

- date input의 max 기본값은 한국 시간의 today()이고 다음 한국 날짜에 새 오늘을 사용한다.
- min/max는 date input API에 전달하는 UI 제약이며 선택은 UI가 한다.
- as_of_date에는 선택한 날짜를 그대로 전송한다.
- 프런트는 코퍼스 상태를 조회·추정·선제 차단·최신화하지 않는다.
- POST /v2/question-executions 및 /core·/finalize SSE를 유지하고 /v1/questions로 대체하지 않는다.

---

### Task 1: 날짜 입력 상한의 TDD 구현

**Files:**
- Modify: apps/web/app/page.tsx:132-140, 328-347, 840-850
- Test: apps/web/lib/auth-page-state.test.ts

**Interfaces:**
- Consumes: koreaTodayIsoDate(now?: Date): string
- Produces: 한국 오늘을 max로 사용하고 한국 자정 뒤 새 상한을 반영하는 date input

- [ ] 실패하는 자정 경계 테스트를 작성하고 focused test가 기대대로 실패함을 확인한다.
- [ ] date input의 max와 자정 갱신/정리 상태를 최소 구현한다.
- [ ] focused test를 통과시키고 이 작업만 검토해 로컬 커밋한다.

### Task 2: V2 기준일 전달 회귀 테스트

**Files:**
- Modify: apps/web/lib/api-client-flow.test.ts:49-109
- Verify: apps/web/lib/api-client.ts:108-136, apps/web/lib/v2-execution.ts:32-127

**Interfaces:**
- Consumes: QuestionInput.as_of_date
- Produces: POST /v2/question-executions body가 선택 날짜를 보존함을 검증하는 테스트

- [ ] V2 prepare 요청 body의 as_of_date 단언을 작성하고, 누락된 단언이 실패함을 확인한다.
- [ ] 프로덕션 변경이 필요할 때만 최소 수정하고 prepare/core/finalize 흐름을 회귀 검증한다.
- [ ] focused test를 통과시키고 이 작업만 검토해 로컬 커밋한다.

### Task 3: 전체 검증과 완료 기록

**Files:**
- Modify: 이 계획과 docs/ROADMAP.md
- Verify: 프런트 lint, typecheck, test, build

- [ ] pnpm lint:web, pnpm typecheck, pnpm test:web, pnpm build:web를 실행한다.
- [ ] diff에서 코퍼스 상태 선제 처리와 V1 질문 호출이 추가되지 않았음을 확인한다.
- [ ] 검증 결과를 기록하고 계획을 completed/로 이동, 로드맵을 Done으로 갱신한 뒤 별도 로컬 커밋한다.

## API Alignment Amendment

| 사용자 요구 | 현재 API 경계 | 계획 조치 |
| --- | --- | --- |
| AI 근거 답변·스트리밍·중지 | POST /v2/question-executions → core/finalize SSE → DELETE execution | request body·phase·취소 회귀 테스트 |
| 로그인 사용자 대화 이력 | GET /v1/conversations, GET/DELETE /v1/conversations/{id}/turns | cursor·상세 지연 로딩 회귀 테스트 |
| Google 인증·계정 삭제 | Supabase OAuth, GET /v1/auth/me, DELETE /v1/account | 인증 헤더·개인정보 초기화 회귀 테스트 |
| Markdown/CSV/PDF 체크리스트 | 클라이언트 생성, GET /v1/questions/history/{id}/checklist?format=pdf | PDF 인증 요청 회귀 테스트 |
| 인용 원문 | V2 QuestionResponse.citations | 별도 /v1/provisions 호출을 추가하지 않음 |
| 기준일 선택 | UI date input + QuestionInput.as_of_date | 한국 오늘 max 갱신과 요청 body 회귀 테스트 |
| 코퍼스 준비·지원 범위 | 서버 측 판정 | UI 범위에서 제외; 상태 API 선제 차단·재조회 미구현 |

### Task 0: 요구사항별 API 계약 회귀 검증

- [ ] V2 prepare/core/finalize/cancel, 대화 목록·상세·삭제, PDF 인증 요청을 요구사항 매핑으로 회귀 검증한다.
- [ ] 인용 표시에 별도 search/provision 호출을 추가하지 않는 경계를 확인한다.
- [ ] focused 테스트를 통과시키고 이 작업만 검토해 로컬 커밋한다.

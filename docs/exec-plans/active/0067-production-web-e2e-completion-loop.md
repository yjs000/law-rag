> 작업 ID: `B-004`
> 상태: `Picked Up`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `UX`, `Evaluation`
> 선행 조건: 없음
> 다음 행동: P0 첫 진입부터 AI 질문·근거 원문 정상 흐름을 배포 환경에서 검증
> 참고 범위:
> - `docs/product-specs/web-e2e-validation.md` L1-L120 — 승인된 전체 E2E 체크리스트와 우선순위
> - `apps/web/app/page.tsx` L332-L856 — 웹 사용자 흐름과 화면 상태
> - `apps/web/lib/v2-execution.ts` L1-L241 — 질문 실행 단계와 재연결·취소 계약

# Production Web E2E Completion Loop Implementation Plan

## 계획 본문

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 배포 웹의 정상 흐름을 먼저 보장하고 저장된 E2E 명세의 모든 기본·경계 흐름을 증거와 함께 완료한다.

**Architecture:** 실제 배포 환경의 정상 흐름은 브라우저로 검증하고, 장애 주입이 필요한 경계 흐름은 기존 Vitest 계약 테스트와 최소한의 결정적 브라우저 재현을 함께 사용한다. 발견된 결함은 실패 테스트를 먼저 추가한 뒤 최소 수정하고, 각 작업이 끝날 때 전체 완료 체크를 다시 실행한다.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, Supabase Auth, FastAPI V2 execution API, Codex Browser

**Spec:** `docs/product-specs/web-e2e-validation.md`

## Global Constraints

- P0 정상 흐름이 전부 통과하기 전에는 P1 개선을 우선하지 않는다.
- 법률 답변의 실질적 주장은 검색된 근거와 인용 위치를 가져야 한다.
- 개인정보, 인증정보, 법률 원문 전문을 테스트 증거나 로그에 남기지 않는다.
- 결함 수정은 재현 테스트의 RED를 확인한 뒤 최소 구현으로 GREEN을 만든다.
- 각 작업 후 `uv run --project apps/api python scripts/check_roadmap.py`로 전체 계획 완료 여부를 다시 확인한다.

---

### Task 1: 검증 명세·기준선 고정

**Files:**
- Create: `docs/product-specs/web-e2e-validation.md`
- Create: `docs/exec-plans/active/0067-production-web-e2e-completion-loop.md`
- Modify: `docs/product-specs/index.md`
- Generated: `docs/ROADMAP.md`

**Interfaces:**
- Consumes: 사용자가 승인한 기본 흐름·경계 흐름 목록
- Produces: `B-004`의 단일 authoritative 체크리스트와 Picked Up 실행계획

- [x] **Step 1: 제품 명세 색인에 E2E 검증 명세를 연결한다.**
- [x] **Step 2: roadmap renderer를 실행하고 B-004가 유일한 Picked Up인지 확인한다.**
- [x] **Step 3: 웹 unit test, lint, typecheck, build 기준선을 실행한다.**
- [x] **Step 4: 문서와 생성 로드맵을 기능 단위로 커밋한다.**

### Task 2: P0 익명 정상 질문·근거 흐름

**Files:**
- Modify if a defect is reproduced: `apps/web/app/page.tsx`, `apps/web/lib/*.ts`
- Test if a defect is reproduced: `apps/web/**/*.test.ts`, `apps/web/**/*.test.tsx`
- Evidence: repository-approved E2E evidence path selected during execution

**Interfaces:**
- Consumes: 배포 URL과 P0 첫 진입부터 익명 저장 경계까지의 체크 항목
- Produces: 정상 질문, V2 실행, 인용, 필터, 기준일, Markdown/CSV, 익명 안내의 브라우저 증거

- [ ] **Step 1: 1280px에서 첫 진입과 세 추천 질문을 실행해 Network·Console·화면 결과를 기록한다.**
- [ ] **Step 2: 직접 입력, Enter/Shift+Enter, 근거 이동, 문서 필터, 오늘·과거 기준일을 검증한다.**
- [ ] **Step 3: Markdown/CSV 내보내기와 익명 로그인 안내·비소급 저장 계약을 검증한다.**
- [ ] **Step 4: 실패가 있으면 재현 테스트 RED → 최소 수정 → focused GREEN → 배포 재검증을 반복한다.**
- [ ] **Step 5: P0 익명 항목을 증거와 함께 갱신하고 전체 완료 체크를 실행한다.**

**오류 증빙 (2026-09-04):** 운영 `finalize` 상세 생성에서 NVIDIA HTTP 503이 발생하면 검증된
core 요약으로 강등되어 checklist가 빈 응답이 됐다. 같은 로그에서 detached phase lease 반환의
DB `TimeoutError`가 미관측 background 예외로 남는 것도 재현했다. 후자는 `ef931da`,
`278bbb9`에서 예외를 관측하고 오류 유형만 JSON 로그로 남기도록 수정했으며, focused API
회귀 21건과 Ruff를 통과했다. provider 503으로 checklist UI가 열리지 않은 경우는 정상 통과로
기록하지 않는다. `graphify update .`는 Windows 접근 거부가 난 기존 `pytest-cache-files-*`
임시 디렉터리 때문에 실패했으므로 graph 산출물은 커밋하지 않았다.

**재검증 결과:** lease 관측 수정이 배포된 뒤에도 P0 추천 질문은 5건의 인용과 core 요약 뒤
`검증된 요약만 제공합니다.`로 강등되어 checklist를 반환하지 않았다. 따라서 Markdown/CSV
내보내기와 인증 전 저장 경계의 후속 검증은 아직 통과 처리하지 않는다.

### Task 2.1: P0 core repair 실패 진단·복구

**Files:**
- Modify if a defect is reproduced: `apps/api/app/application/v2/phase_service.py`,
  `apps/api/app/application/v2/grounding.py`, 또는 관련 V2 execution 경계
- Test if a defect is reproduced: `apps/api/tests/test_v2_question_executions.py`,
  `apps/api/tests/test_question_phase_coordinator.py`, 또는 새 focused 회귀 테스트
- Evidence: 실행 ID와 화면 결과를 포함한 Task 2 오류 증빙

**Interfaces:**
- Consumes: `core_repair_required`로 끝난 운영 V2 execution과 frozen evidence/core grounding 계약
- Produces: 원인 분류, 재현 자동화, 정상 core 또는 사용자에게 복구 가능한 안전 종료, 배포 재검증

- [x] **Step 1: execution `83bc14d8-5b26-48ee-84e2-9edcb3e253ff`의 core repair 원인을 로그·persisted 상태에서 분류한다.**
- [x] **Step 2: 같은 core repair 조건을 재현하는 focused regression을 RED로 추가한다.**
- [x] **Step 3: core repair 경로가 무한 대기·빈 결과를 만들지 않도록 최소 수정하고 focused GREEN을 확인한다.**
- [x] **Step 4: 배포 환경에서 같은 정상 질문의 prepare → core → finalize와 화면 답변·체크리스트를 재검증한다.**
- [x] **Step 5: Task 2 P0 항목을 다시 점검하고, 통과하지 않은 항목은 오류 증빙과 재개 조건을 유지한다.**

**오류 증빙 (2026-09-04):** 운영 execution
`83bc14d8-5b26-48ee-84e2-9edcb3e253ff`의 core 단계가
`core_repair_required`와 `next_action=repair_core`로 끝났다. 이후 finalize는 완료됐지만
화면에는 `검색 결과가 없습니다` 안전 응답만 표시됐다. P0 AI 실행과 추천 질문의 답변·체크리스트
조건은 미통과이며, Step 1–4 재검증 전에는 통과 처리하지 않는다.

Vercel의 동일 core 요청 로그는 `{"error_type": "TimeoutError"}`를 기록했다. 서버는 core 예외를
`core_repair_required`로 일반화하지만 상세 원인을 SSE에 보존하지 않는다. 이어 웹 클라이언트는
`repair_core`를 core 재시도가 아니라 finalize로 매핑한다. `verified_core`가 없는 finalize는
`grounding_fallback()`으로 강등되어 위의 빈 안전 응답을 반환한다. 따라서 timeout 자체와
`repair_core` phase 매핑 결함을 분리하여 회귀 테스트·수정·배포 검증한다.

### Task 3: P0 인증·대화·이력 정상 흐름

**Files:**
- Modify if a defect is reproduced: `apps/web/app/page.tsx`, `apps/web/lib/api-client.ts`, `apps/web/lib/chat-state.ts`
- Test if a defect is reproduced: `apps/web/lib/api-client-flow.test.ts`, `apps/web/lib/auth-page-state.test.ts`, `apps/web/lib/chat-state.test.ts`
- Evidence: same evidence path as Task 2

**Interfaces:**
- Consumes: 사용 가능한 안전한 Google 테스트 세션
- Produces: 로그인, 연속 질문, 기록 복원·페이지네이션·삭제, PDF, 로그아웃의 브라우저 증거

- [ ] **Step 1: 로그인·가입 모달과 Google 인증 완료를 검증한다.**
- [ ] **Step 2: 연속 질문, 새 질문, 새로고침 복원, 기록 열기와 페이지네이션을 검증한다.**
- [ ] **Step 3: 기록 삭제 취소·확인, PDF 내보내기, 로그아웃을 검증한다.**
- [ ] **Step 4: 실패가 있으면 TDD 수정 루프를 돌리고 인증 P0 전체를 다시 실행한다.**
- [ ] **Step 5: P0 전체 완료 체크를 실행하고 P0가 모두 통과한 경우에만 Task 4로 이동한다.**

### Task 4: P1 입력·검색·네트워크·인증 경계

**Files:**
- Modify if a defect is reproduced: affected `apps/web/app/` or `apps/web/lib/` source
- Test: affected focused Vitest file plus browser scenario
- Evidence: same evidence path as Task 2

**Interfaces:**
- Consumes: P1 입력·날짜·검색·네트워크·상태·인증·내보내기 체크 항목
- Produces: 각 오류의 사용자 복구 가능성, 재시도 상한, 중복 실행 방지 증거

- [ ] **Step 1: 입력, IME, 길이, XSS, 날짜와 필터 경계를 검증한다.**
- [ ] **Step 2: 빈 결과, 불완전 조문, 범위 밖 질문, 인용 무결성, AI 폴백을 검증한다.**
- [ ] **Step 3: 재시도 가능·불가능 HTTP 상태, 스트림 재연결, 중지, 화면 전환 경쟁 상태를 검증한다.**
- [ ] **Step 4: 인증 취소·세션 만료·다른 탭 로그아웃·이력 및 내보내기 실패를 검증한다.**
- [ ] **Step 5: 각 실패마다 TDD 수정 후 P1 관련 묶음과 P0 정상 흐름을 함께 재실행한다.**

### Task 5: 반응형·접근성·전체 회귀 및 완료

**Files:**
- Modify if a defect is reproduced: affected web source and focused tests
- Modify: `docs/product-specs/web-e2e-validation.md`
- Modify then move: `docs/exec-plans/active/0067-production-web-e2e-completion-loop.md`
- Generated: `docs/ROADMAP.md`, `graphify-out/`

**Interfaces:**
- Consumes: Task 1–4의 최신 통과 증거와 남은 체크 항목
- Produces: 375px, 430px, 1280px 시각 증거, 전체 회귀 결과, Done 실행계획

- [ ] **Step 1: 375px, 430px, 1280px에서 동일 핵심 시나리오를 캡처하고 overflow·가림을 확인한다.**
- [ ] **Step 2: 모달 포커스 순환, Escape 복귀, 키보드 조작, live region을 검증한다.**
- [ ] **Step 3: `pnpm test:web`, `pnpm lint:web`, `pnpm typecheck`, `pnpm build:web` 및 관련 API 회귀를 실행한다.**
- [ ] **Step 4: 코드 변경이 있으면 `graphify update .`를 실행하고 변경 산출물을 함께 검증한다.**
- [ ] **Step 5: 독립 리뷰를 반영하고 모든 명세 체크박스가 증거와 함께 완료됐는지 확인한다.**
- [ ] **Step 6: 계획을 Done으로 옮기고 roadmap renderer/checker를 실행한 뒤 기능 단위로 커밋한다.**

## 완료 체크 명령

```powershell
uv run --project apps/api python scripts/check_roadmap.py
pnpm test:web
pnpm lint:web
pnpm typecheck
pnpm build:web
```

완료 조건은 위 명령 성공만이 아니라 `docs/product-specs/web-e2e-validation.md`의 모든 체크박스에 최신
실행 증거가 연결되어 있는 것이다.

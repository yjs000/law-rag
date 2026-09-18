> 작업 ID: `B-010`
> 상태: `Todo`
> 유형: `Bug`
> 보조 라벨: `UX`
> 선행 조건: 없음
> 다음 행동: 한 글자 입력 허용과 공백 전용 입력 거부를 Web·API 회귀 테스트로 먼저 고정한다.
> 오케스트레이션: `OC-001`
> 우선순위: `P0`
> 관리 상태: `통합 대기`
> 선행 작업: `B-003`, `B-008`
> 소유 범위:
> - `apps/web/lib/composer-state.ts`
> - `apps/web/app/page.tsx`
> - `packages/law-rag-core/src/law_rag_core/domain/schemas.py`
> 참고 범위:
> - `apps/web/lib/composer-state.ts` L1-L11 — trim 이후 두 글자 미만 입력을 버리는 현재 제출 경계
> - `apps/web/app/page.tsx` L552-L848 — 제출 함수와 두 글자 미만일 때 비활성화되는 전송 버튼
> - `packages/law-rag-core/src/law_rag_core/domain/schemas.py` L89-L123 — 공용 `QuestionRequest.question`의 현재 최소 두 글자 API 계약

# 공백이 아닌 한 글자 질문도 전송 허용 Implementation Plan

**Goal:** 사용자가 공백이 아닌 내용을 하나라도 입력하면 길이가 한 글자여도 전송할 수 있게 하고, Web과 API의 입력 규칙을 일치시킨다.

**Input contract:** 앞뒤 공백을 제거한 뒤 내용이 하나 이상이면 허용한다. 한글 한 글자, 숫자 하나, 문장부호 하나, 이모지 하나도 유효하다. 공백·탭·줄바꿈만 있는 입력은 거부하고 기존 최대 2,000자 제한은 유지한다.

### Task 1: Web 한 글자 제출 회귀 고정

- **결과:** 입력 소비 함수와 전송 버튼이 한 글자부터 허용하고 빈 입력만 막는 계약이 실패 테스트로 고정된다.
- **대상:** `apps/web/lib/composer-state.test.ts` L1-L15 수정 약 18줄, `apps/web/app/page.test.tsx` L1-L27 수정 약 12줄, 합계 약 30줄.
- **실행 절차:** `가`, `1`, `?`, 단일 이모지와 앞뒤 공백이 있는 한 글자 입력은 정규화 후 제출되고, 빈 문자열·공백·탭·줄바꿈만 있는 입력은 제출되지 않는 테스트를 추가한다. 전송 버튼의 disabled 계약도 같은 기준인지 검증한다. `pnpm --filter @law-rag/web test -- composer-state.test.ts page.test.tsx`를 실행해 현재 두 글자 제한으로 RED가 나는지 확인한다.
- **완료 증거:** 한 글자 유효 입력 사례만 현재 구현에서 실패하고 공백 전용·2,000자 경계 테스트는 기대대로 유지된다.
- **의존성:** 없음.

### Task 2: Web과 공용 API 최소 길이 일치

- **결과:** Web이 허용한 한 글자 질문을 V1·V2 API도 받아들이며, 공백 전용 질문은 서버 경계에서 거부된다.
- **대상:** `apps/web/lib/composer-state.ts` L1-L11 수정 약 2줄, `apps/web/app/page.tsx` L552-L848 수정 약 2줄, `packages/law-rag-core/src/law_rag_core/domain/schemas.py` L89-L123 수정 약 3줄, `packages/law-rag-core/tests/test_contracts.py` 질문 계약 구간 수정 약 24줄, 합계 약 31줄.
- **실행 절차:** Web의 제출 함수와 버튼 조건을 trim 후 비어 있는지만 검사하도록 맞춘다. 공용 `QuestionRequest.question`은 공백을 정규화한 뒤 최소 길이 1을 요구하도록 바꾸고 최대 길이 2,000은 유지한다. 한 글자·공백 전용·2,000자·2,001자 API 계약 테스트를 추가한다. `pnpm --filter @law-rag/web test -- composer-state.test.ts page.test.tsx`와 `.\scripts\run_python.ps1 -m pytest packages/law-rag-core/tests/test_contracts.py`를 실행하고 diff를 확인한다.
- **완료 증거:** 같은 한 글자 입력이 Web과 `QuestionRequest`에서 모두 통과하고, whitespace-only와 2,001자 입력은 양쪽 경계에서 거부된다.
- **의존성:** Task 1의 입력 사례 표.

### Task 3: 통합 검증과 완료 기록

- **결과:** 실제 질문 전송 경로에서 한 글자 입력이 클라이언트 선제 차단이나 API 422 없이 처리되고 문서·로드맵에 결과가 남는다.
- **대상:** `apps/web/lib/api-client-flow.test.ts`의 V2 질문 전송 구간 수정 약 12줄, `docs/product-specs/grounded-legal-qa.md` 입력 계약 추가 약 3줄, 이 계획 결과 기록 약 10줄, `docs/ROADMAP.md` renderer 생성 변경.
- **실행 절차:** 한 글자 질문이 V2 prepare 요청 body까지 전달되는 통합 테스트를 추가하고 공백 전용 입력은 fetch가 시작되지 않는지 확인한다. `pnpm lint:web`, `pnpm typecheck`, `pnpm test:web`, `pnpm build:web`와 API 포맷·lint·타입·단위 테스트를 실행한다. `git diff --check`와 전체 diff를 확인하고 계획을 `completed/`로 이동한 뒤 roadmap renderer와 checker를 실행한다.
- **완료 증거:** 한 글자 질문의 Web→V2 요청 경로가 통과하고 빈 입력 방지·최대 길이 보호가 유지되며 계획이 `Done`으로 생성된 로드맵에 반영된다.
- **의존성:** Task 1과 Task 2 완료.

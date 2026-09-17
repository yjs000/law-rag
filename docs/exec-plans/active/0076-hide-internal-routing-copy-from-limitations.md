> 작업 ID: `B-008`
> 상태: `Todo`
> 유형: `Bug`
> 보조 라벨: `UX`
> 선행 조건: 없음
> 다음 행동: no-search 안내 응답의 사용자용 `scope` 계약을 회귀 테스트로 먼저 고정한다.
> 오케스트레이션: `OC-001`
> 우선순위: `P0`
> 관리 상태: `준비 중`
> 선행 작업: 없음
> 소유 범위:
> - `apps/api/app/application/v1/guidance.py`
> - `apps/api/tests/test_routing_pipeline.py`
> - `apps/web/app/answer-view.test.tsx`
> 참고 범위:
> - `apps/api/app/application/v1/guidance.py` L73-L116 — no-search 경로가 사용자용 `scope`와 내부 `route`를 함께 만드는 현재 경계
> - `apps/api/tests/test_routing_pipeline.py` L621-L733 — 검색 미실행 응답과 내부 route 보존을 검증하는 API 회귀 테스트
> - `apps/web/app/answer-view.test.tsx` L40-L59 — 내부 라우팅 문구를 현재 fixture로 렌더링하는 프런트 회귀 테스트

# 내부 라우팅 문구의 “범위와 한계” 노출 제거 Implementation Plan

**Goal:** `라우팅: clarification_required (검색 미실행)` 같은 내부 처리 상태를 사용자 화면의 “범위와 한계”에 노출하지 않고, 사용자가 이해할 수 있는 안내만 표시한다.

**Scope:** V1 no-search 안내 응답의 사용자용 `scope` 문구와 이를 표시하는 Web 회귀 계약을 수정한다. 구조화된 `route` 필드, 서버 관측 정보, 검색을 실제로 건너뛰는 동작은 유지한다.

### Task 1: 사용자용 no-search 응답 계약 고정

- **결과:** clarification 경로의 응답 본문에는 `clarification_required`, `라우팅:` 같은 내부 식별자가 없지만 구조화된 `route` 값과 no-search 동작은 그대로 유지된다.
- **대상:** `apps/api/tests/test_routing_pipeline.py` L621-L733 수정 약 12줄, `apps/api/app/application/v1/guidance.py` L73-L116 수정 약 4줄, 합계 약 16줄.
- **실행 절차:** 관련 API 테스트에 사용자용 `scope`와 내부 문자열 비노출 assertion을 추가해 실패를 확인한다. `generate_blocked_answer`가 내부 route 대신 자연어 범위 안내를 반환하도록 최소 수정한다. `apps/api`에서 `uv run pytest tests/test_routing_pipeline.py`를 실행하고 diff를 확인한다.
- **완료 증거:** focused API 테스트가 통과하고, JSON의 `route`는 `clarification_required`를 유지하면서 `scope`·`limitations`에는 내부 route 이름이나 `라우팅:` 접두사가 없다.
- **의존성:** 없음.

### Task 2: Web 표시와 제품 명세 회귀 고정

- **결과:** “범위와 한계”는 자연어 안내만 렌더링하며 내부 라우팅 식별자를 사용자에게 보여주지 않는 제품 계약이 문서와 테스트에 남는다.
- **대상:** `apps/web/app/answer-view.test.tsx` L40-L59 수정 약 6줄, `apps/web/app/answer-view.tsx` L48-L52 검증(필요 시 수정 최대 6줄), `docs/product-specs/grounded-legal-qa.md` L7-L14 및 L86-L95 추가 약 3줄, 합계 최대 약 15줄.
- **실행 절차:** API가 반환할 자연어 `scope` fixture로 테스트를 바꾸고 내부 route 문자열이 렌더링되지 않는 assertion을 추가한다. 컴포넌트 변경 없이 계약을 만족하면 그대로 두고, 필요할 때만 사용자 표시 경계에 최소 방어를 추가한다. `pnpm test:web`, `pnpm lint:web`, `pnpm typecheck`를 실행하고 제품 명세 결정 기록과 diff를 확인한다.
- **완료 증거:** Web 테스트·lint·typecheck가 통과하고 렌더링 결과에 `clarification_required`, `라우팅:` 또는 `(검색 미실행)`이 없으며 자연어 한계 안내는 남는다.
- **의존성:** Task 1의 사용자용 응답 문구 계약.

### Task 3: 전체 검증과 계획 종료

- **결과:** 변경이 no-search 라우팅·검색 차단·구조화된 진단 계약을 훼손하지 않았고 로드맵 상태가 완료로 전이된다.
- **대상:** 위 변경 파일 전체 diff 검증, 이 계획 파일 상태·결과 기록 수정 약 10줄, `docs/ROADMAP.md` renderer 생성 변경.
- **실행 절차:** `pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm build`와 `./scripts/run_python.ps1 scripts/check_docs.py`를 실행한다. `git diff --check`와 `git diff`로 내부 route 필드 및 검색 미실행 동작이 유지되는지 확인한다. 계획에 결과를 기록하고 `completed/`로 이동한 뒤 roadmap renderer와 checker를 실행한다.
- **완료 증거:** 저장소 대표 검증이 모두 통과하고 계획이 `Done`으로 생성된 로드맵에 반영된다.
- **의존성:** Task 1과 Task 2 완료.

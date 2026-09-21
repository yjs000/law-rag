> 작업 ID: `B-011`
> 상태: `Done`
> 유형: `Bug`
> 보조 라벨: `UX`, `Evaluation`
> 선행 조건: `docs/design-docs/clarification-missing-information-structural-validation.md` 승인 완료.
> 다음 행동: 없음 — 구조 검증, 프롬프트 계약, provenance와 전체 회귀 검증 완료.
> 참고 범위:
> - `apps/api/app/application/answering.py` L147-L207 — 고정 라벨 allowlist와 공용 요약 렌더러
> - `apps/api/app/adapters/openai_answerer.py` L13-L461 — missing_information 스키마와 네 생성 프롬프트
> - `docs/design-docs/clarification-missing-information-structural-validation.md` L1-L128 — 승인 설계와 권한 계약

# 0082: clarification 응답의 missing_information이 사용자에게 빈 값으로 전달되는 문제

상태: `완료 (2026-09-21)`

제안 출처: F-010 Task 3(대표 출력 평가)에서 실제 NVIDIA 개발 credential로 clarification
대표 질문("제 설비 용량에 맞는 절차는 무엇인가요?")을 2회 독립 실행해 재현했다.

## 재현 요약

- 질문: "제 설비 용량에 맞는 절차는 무엇인가요?" (fixture id: `clarification`,
  `apps/api/tests/fixtures/layperson_plain_language_questions.py`)
- 실제 응답: `action=clarification_required`, `route=clarification_required`,
  `summary`에 "추가 정보:" 뒤에 채울 항목이 전혀 없이 `- [ ]` 한 줄만 출력됨 — 사용자가
  다음에 무엇을 입력해야 하는지 전혀 알 수 없다.
- 2회 독립 실행 모두 같은 결과로 재현됨(우연한 provider flake 아님).

## 원인

`app/application/answering.py`의 `safe_clarification_missing_fields()`는 모델이 만든
`missing_information` 문자열을 신뢰하지 않는 외부 입력으로 취급해 6개 고정 라벨
(설비용량, 전압, 전기 사용 방식, 공사 종류, 토지 지목, 용도지역)과 **정확히 일치**할 때만
통과시키는 input allowlist다(AGENTS.md "외부 입력은 시스템 경계에서 검증한다" 불변조건에
따른 의도된 보안 경계).

반면 F-010이 도입한 `build_blocked_route_messages()`의 `clarification_required` 안내는
모델에게 "각 항목은 무엇을 알려줘야 하는지와 함께 간단한 예시 값을 붙여 쓴다(예:
'발전설비용량(예: 50kW)')"라고 구체적 예시 값을 포함한 자유 텍스트를 요구한다. 이 형식은
allowlist의 정확 일치 조건을 구조적으로 통과할 수 없어, 이 route에서는 missing_information이
사실상 항상 비게 된다.

## 왜 F-010 Task 3에서 고치지 않았는가

해결에는 다음 중 하나가 필요하며 둘 다 F-010의 소유 범위(`openai_answerer.py`,
`nvidia_nim_clarification.py`)를 벗어나거나 이미 승인된 계약과 충돌한다:

1. allowlist를 완화해 모델이 만든 자유 텍스트(예시 값 포함)를 사용자에게 그대로
   노출한다 — 신뢰하지 않는 LLM 출력을 검증 경계 밖으로 내보내는 변경이라 별도 보안
   검토가 필요하다.
2. `clarification_required` 안내에서 "간단한 예시 값" 요구를 제거한다 — F-010 Task 1이
   승인한 언어 계약("추가 질문은 '무엇을 알려 달라는지'와 간단한 입력 예시를 바로 이해할
   수 있게 쓴다")과 기존 통과 테스트를 정면으로 바꾸는 일이라 별도 설계 승인이 필요하다.

## 완료 조건

- 두 해법 중 하나(또는 제3안: 고정 라벨별로 서버가 예시 값을 미리 매핑해 붙이는 안 등)를
  design-doc으로 확정하고 사용자 승인을 받는다.
- 승인된 안대로 구현해 clarification 대표 질문 재실행 시 사용자에게 실제로 채울 필드가
  표시됨을 확인한다.
- 기존 `test_clarification_route_missing_information_requires_example_value`를 그대로
  유지하거나, 계약이 바뀌면 그 변경 이유를 테스트와 언어 계약 문서에 함께 남긴다.

## Task 1 — 설계·상태 계약 고정

- **결과:** 승인 방향, 권한 경계, 제품 명세 링크와 `Picked Up` 상태가 서로 일치한다.
- **대상:** `docs/design-docs/clarification-missing-information-structural-validation.md` L1-L112,
  `docs/design-docs/index.md` L1-L58, `docs/product-specs/grounded-legal-qa.md` L103-L109,
  `docs/CURRENT_STATE.md` L1-L15, 이 계획 파일 L1-L61, `docs/ROADMAP.md` 생성 파일.
- **예상 변경량:** 문서 합계 추가 45줄, 수정 25줄, 삭제 12줄.
- **실행 절차:** 승인 문구와 권한 표를 기록하고, plan을 `active/`로 이동해 `Picked Up`으로
  바꾼다. `\.\scripts\run_python.ps1 scripts/render_roadmap.py`와
  `\.\scripts\run_python.ps1 scripts/check_roadmap.py`를 실행하고 diff를 확인한다.
- **완료 증거:** roadmap checker 통과, ROADMAP의 유일한 `Picked Up` 행이 B-011이다.
- **의존성:** 사용자 2026-09-21 승인.

## Task 2 — 자유형 clarification 구조 검증 TDD

- **결과:** 고정 필드 사전 없이 짧은 명사형 라벨과 자연어 질문+예시가 통과하고, 빈 값·과다
  항목·URL·마크업·제어문자·서술형 법률 주장은 공개되지 않는다.
- **대상:** `apps/api/tests/test_clarification_missing_information.py` 새 파일,
  `apps/api/app/application/answering.py` L147-L207.
- **예상 변경량:** 테스트 추가 85줄, 구현 추가 35줄·수정 15줄·삭제 19줄; 합계 154줄.
- **실행 절차:** 새 라벨, 자연어 질문+예시, strip/dedupe/최대 5개, 위험 패턴, fallback을 각각
  실제 `safe_clarification_missing_fields()`와 `clarification_resubmission_summary()`로
  검증하는 테스트를 작성한다. `\.\scripts\run_python.ps1 -m pytest
  apps/api/tests/test_clarification_missing_information.py -q`가 기존 exact-match allowlist 때문에
  실패함을 확인한다. 최소 구조 검증을 구현하고 같은 명령과 기존 clarification 테스트를 실행한다.
- **완료 증거:** 신규 테스트가 RED에서 기대값 불일치로 실패한 기록과 GREEN 통과 결과,
  `test_clarification_answering.py` 기존 회귀 통과.
- **의존성:** Task 1 설계 규칙.

## Task 3 — 모든 생성 프롬프트의 질문+예시 계약 통일

- **결과:** 사전 route와 검색 후 clarification 생성 모두 필요한 사실을 자연어 질문으로 묻고
  사용자가 따라 쓸 예시를 포함하며 법률 판단·답변을 `missing_information`에 쓰지 않는다.
- **대상:** `apps/api/tests/test_layperson_prompt_v2.py` L1-L211,
  `apps/api/app/adapters/openai_answerer.py` L139-L153, L249-L267, L321-L338, L455-L461,
  `apps/api/app/domain/generation_profiles.py` L35-L75,
  `apps/api/tests/test_generation_profiles.py` L39-L50.
- **예상 변경량:** 테스트 추가 30줄·수정 2줄, 구현 수정 20줄; 합계 52줄.
- **실행 절차:** 각 prompt builder의 사용자 관찰 계약을 테스트하고 실패를 확인한다. 네 prompt
  문구를 같은 질문+예시·비답변 규칙으로 맞추고 V1·V2 prompt provenance를 올린 뒤 focused
  테스트와 Ruff를 실행한다.
- **완료 증거:** prompt 회귀 테스트와 `ruff check` 통과.
- **의존성:** Task 2 검증기가 허용하는 형식.

## Task 4 — 통합 회귀·문서 완료

- **결과:** V1·V2 공용 요약에서 대표 자연어 질문과 예시가 보이고 기존 clarification·grounding
  계약이 깨지지 않으며 계획이 `Done`으로 완료된다.
- **대상:** `apps/api/tests/test_clarification_answering.py` L290-L351, L900-L1004,
  `docs/product-specs/grounded-legal-qa.md` L103-L109, 이 계획과 생성 roadmap.
- **예상 변경량:** 테스트 수정 12줄, 문서 수정 20줄; 합계 32줄.
- **실행 절차:** 대표 fixture를 자연어 질문+예시로 바꾸고 관련 pytest, API 전체 pytest,
  repository 전체 verify를 실행한다. diff와 민감정보를 확인하고 계획 결과를 기록해
  `completed/`로 이동한 뒤 roadmap renderer/checker를 재실행한다.
- **완료 증거:** focused·전체 검증 최신 성공 출력, 깨끗한 diff 검토, 로컬 기능 커밋.
- **의존성:** Task 2~3 완료.

## 결과

- `_SAFE_CLARIFICATION_FIELD_ALIASES`를 제거하고 최대 5개, 항목당 160자, 표시 안전성,
  `질문? (예: 값)` 구조를 검증하는 공용 경계로 교체했다. pre-routing의 짧은 명사형 라벨은
  호환 유지하며 새 라벨도 코드 변경 없이 통과한다.
- V1·V2·core·사전 차단 생성 프롬프트가 사용자 질문과 예시 값을 요구하고 법률 판단·답변을
  `missing_information`에 넣지 않도록 통일했다.
- prompt provenance를 V1 `answer-system-prompt-v1.1`, V2 `answer-system-prompt-v2.2`로 갱신했다.
- RED→GREEN 회귀는 자유형 질문 보존, 신규 라벨, 위험 표시 패턴, 최대 5개, `(예시:)`,
  불완전 예시, 160자 상한, 명사형 라벨, 서술형 주장과 trailing 서술 차단을 포함한다.

## 최종 검증

- `\.\scripts\verify.ps1` — exit 0.
- Core: 37 passed.
- API: 1011 passed, 3 skipped. dependency deprecation warning 127건은 기존 upstream 경고다.
- Collector: 97 passed, 5 skipped.
- Docs: 188 files 검사 통과, roadmap checker 통과.
- Web: ESLint 0 errors(기존 unused 변수 warning 2건), TypeScript 통과, Vitest 147 passed,
  Next.js production build 통과.
- 외부 hosted 모델·credential·DB·배포는 사용하지 않았다. 잔여 작업 없음.

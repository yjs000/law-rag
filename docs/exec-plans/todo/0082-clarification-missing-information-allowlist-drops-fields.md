> 작업 ID: `B-011`
> 상태: `Todo`
> 유형: `Bug`
> 보조 라벨: `UX`, `Evaluation`
> 선행 조건: allowlist 완화 또는 언어 계약 재검토 중 어느 쪽으로 풀지 별도 design 승인이 필요하다.
> 다음 행동: allowlist 완화안과 언어 계약 재검토안을 비교해 design-doc으로 먼저 고정한다.
> 참고 범위:
> - `apps/api/app/application/answering.py` L179-L207 — 고정 라벨 6개만 통과시키는 input allowlist
> - `apps/api/app/adapters/openai_answerer.py` L455-L461 — 예시 값 포함 자유 텍스트를 요구하는 F-010 언어 계약
> - `apps/api/tests/test_layperson_prompt_v2.py` L206-L211 — 예시 값 요구를 고정한 현재 통과 회귀 테스트

# 0082: clarification 응답의 missing_information이 사용자에게 빈 값으로 전달되는 문제

상태: `제안됨 (2026-09-18)`

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

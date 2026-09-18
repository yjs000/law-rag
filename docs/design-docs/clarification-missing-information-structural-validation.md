# clarification missing_information 구조적 검증 (B-011)

## 상태

승인 — 2026-09-18. 사용자는 고정 라벨 allowlist를 완전히 없애고 구조적 검증으로 대체하는
안을 승인했다. 라벨은 어떤 값이든 확장 가능해야 하며, 사용자의 후속 자유 답변도 그대로
받아들여야 한다는 조건이 붙었다.

## 문제

[B-011 / exec-plan 0082](../exec-plans/todo/0082-clarification-missing-information-allowlist-drops-fields.md)
에서 등록됨. `clarification_required` route에서 사용자에게 "추가 정보: - [ ]"만 표시되고
실제로 무엇을 입력해야 하는지 전혀 안내되지 않는다. F-010 Task 3에서 대표 질문("제 설비
용량에 맞는 절차는 무엇인가요?")으로 2회 독립 실행해 재현했다(우연한 provider flake 아님).

## 원인

`apps/api/app/application/answering.py`의 `safe_clarification_missing_fields()`는
모델/router가 만든 `missing_information` 문자열을 신뢰하지 않는 외부 입력으로 취급해
`_SAFE_CLARIFICATION_FIELD_ALIASES` 사전에 등록된 6개 고정 라벨(설비용량, 전압, 전기 사용
방식, 공사 종류, 토지 지목, 용도지역)과 **정확히 일치**할 때만 통과시키는 input allowlist다.

반면 `apps/api/app/adapters/openai_answerer.py`(L455-461, F-010에서 승인된 언어 계약)는
모델에게 "각 항목은 무엇을 알려줘야 하는지와 함께 간단한 예시 값을 붙여 쓴다(예:
'발전설비용량(예: 50kW)')"라고 요구한다. 이 형식은 애초에 예시 값을 담을 자리가 없는
라벨 전용 allowlist를 구조적으로 통과할 수 없어, missing_information이 사실상 항상 빈다.

## 왜 고정 allowlist로 되돌아갈 수 없는가

라벨 매핑 테이블을 6개(또는 몇 개든) 고정 사전으로 유지하는 안(예시값 서버측 매핑)도
검토했으나, 사용자가 명시적으로 거부했다 — 라벨 집합이 앞으로 계속 늘어날 도메인
질문(전기사업법 외 다른 법 영역 등)에서 코드 변경 없이 확장 가능해야 한다.

## 목표

1. 고정 라벨 집합 없이, 새 라벨이 등장해도 코드 변경 없이 통과할 수 있는 검증 방식으로
   전환한다.
2. 모델이 만든 예시 값(`"라벨(예: 값)"`)을 있는 그대로 사용자에게 노출한다.
3. AGENTS.md "외부 입력은 시스템 경계에서 검증한다" 불변조건을 유지한다 — 신뢰하지 않는
   모델 출력을 무검증으로 내보내지 않는다.
4. clarification 재제출 시 사용자의 자유 답변("제안대로" 등 임의 표현 포함)이 여전히 그대로
   받아들여짐을 회귀 테스트로 확인한다.

## 비목표

- `openai_answerer.py`의 언어 계약(F-010 승인) 자체는 변경하지 않는다.
- 사용자 후속 답변 처리 경로(질문 재제출 파이프라인)의 구조 자체는 바꾸지 않는다 — 이미
  자유 텍스트를 그대로 받아들이는 구조이므로, 회귀 테스트만 추가한다.
- route classifier 로직(B-012 소관)은 다루지 않는다.

## 설계

`_SAFE_CLARIFICATION_FIELD_ALIASES` 고정 사전과 그 exact-match 조회를 삭제하고,
`safe_clarification_missing_fields()`를 **구조적 검증기**로 교체한다. 의미(라벨이 무엇인지)
가 아니라 형태(길이·문자셋·개수)만 검증해서 라벨 자체는 무엇이든 확장 가능하게 한다.

검증 규칙 (모델 출력 및 router `missing_fields` 양쪽에 동일 적용):

- **길이 상한**: 짧은 라벨(2~6자 한글 필드명)은 통과, 문장형 텍스트("전기사업법이
  적용됩니다" 같은 10자 이상 완결 문장)는 자연히 걸러지는 값으로 설정한다. 정확한 상한은
  구현 시 기존 회귀 테스트(아래 "호환성" 참고)로 역산해 고정한다.
- **허용 문자셋**: 한글 음절/자모, 영숫자, 공백, `()`, `:`, `/`, `·`, 기본 문장부호(`,` `.`
  `%`)만 허용. 마크다운 제어문자(`#` `*` `` ` `` `_` `[` `]` `<` `>`), URL 스킴(`http`,
  `://`), 개행 등은 거부.
- **중복 제거**: 처음 등장한 순서를 보존한 채 dedupe.
- **개수 상한**: 최대 8개 항목까지만 통과.
- **빈 문자열/공백만 있는 값**: strip 후 거부.

두 가지 입력 형태를 모두 같은 함수로 처리한다:

1. **Pre-routing classifier** 출력(`RouteDecision.missing_fields`) — 예시 값 없는 평문
   라벨(예: `"설비용량"`).
2. **모델 생성** `missing_information` — F-010 언어 계약에 따른 `"라벨(예: 값)"` 형식(예:
   `"발전설비용량(예: 50kW)")`).

`clarification_resubmission_summary()`의 `fields_block` 조립은 그대로 유지하되
(`- {검증된 문자열}: [ ]` 한 줄씩), 검증을 통과한 원본 문자열을 그대로 나열한다 — 평문
라벨이면 `- 설비용량: [ ]`, 예시 값 포함이면 `- 발전설비용량(예: 50kW): [ ]`로 렌더링된다.

## 호환성 (기존 테스트)

`apps/api/tests/test_clarification_answering.py`의 다음 테스트는 입력
`("설비용량", "전기사업법이 적용됩니다")`에 대해 요약이 정확히
`"추가 정보:\n- 설비용량: [ ]"`로 끝나고 `"전기사업법이 적용됩니다"`는 나타나지 않아야
한다고 이미 고정되어 있다 — 새 구조적 규칙(특히 길이 상한)이 이 두 문자열을 기존과
동일하게 분류해야 한다:

- `test_initial_clarification_route_preserves_clarification_action_in_core`
- `test_generated_clarification_core_with_retrieval_is_preserved`
- `test_successful_core_repair_persists_clarification_transition`

## 영향 범위

- `apps/api/app/application/answering.py` — `_SAFE_CLARIFICATION_FIELD_ALIASES` 삭제,
  `safe_clarification_missing_fields()` 구조적 검증으로 교체.
- `apps/api/tests/test_clarification_answering.py` — 새 라벨 확장성, 예시 값 보존, 위험
  패턴 거부, 개수 상한, dedupe 테스트 추가. 사용자 자유 답변 회귀 테스트 추가.
- 변경 없음: `apps/api/app/adapters/openai_answerer.py`(언어 계약), 사용자 후속 답변
  처리 경로.

## 완료 조건

- 새 라벨(6개 고정 집합에 없는 것)이 통과함을 테스트로 확인.
- 모델이 만든 `"라벨(예: 값)"`이 예시 값째로 사용자에게 노출됨을 테스트로 확인.
- 마크다운/URL/코드펜스/개행이 섞인 후보 문자열이 거부됨을 테스트로 확인.
- 위 "호환성" 절의 기존 3개 테스트가 코드 변경 없이 그대로 통과.
- clarification 재제출 시 사용자의 임의 자유 답변이 그대로 받아들여짐을 회귀 테스트로 확인.

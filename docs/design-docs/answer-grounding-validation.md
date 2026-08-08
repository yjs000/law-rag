# 답변 근거 검증 설계 (validate_draft)

상태: 승인
작성일: 2026-08-08
최종 갱신: 2026-08-08

전체 진단 과정·실측 수치는 [0032 실행 계획](../exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md)에 있다. 이 문서는 "왜 이 구조인가"의 현재 결론만 담는다. 답변 안전 게이트 전체 그림은 [AI 차별화](ai-differentiation.md)를 먼저 본다.

## 목표

모델이 생성한 초안(`DraftAnswer`)이 실제 제공된 근거(`SearchHit`)를 벗어난 주장을 하지 않는지, 생성·모델 호출 없이 결정론적 코드(`app/adapters/openai_answerer.py`의 `validate_draft`)로 검증한다. 실패하면 AI 답변 대신 검색 전용 응답으로 전환한다 — 틀린 답을 보여주는 것보다 답을 안 보여주는 게 안전하다는 원칙이다.

## 검증 계약: 왜 텍스트 추측이 아니라 모델의 명시적 신호인가

초기 버전은 `summary` 텍스트를 정규식으로 훑어 "이건 확신 있는 주장인가 겸양 표현인가"를 추측했다. 이 방식은 구조적으로 깨진다 — 한국어 "~할 수 없다"는 법적 금지(`"출입할 수 없다"`)와 모델의 인식론적 겸양(`"판단할 수 없다"`)에 표면 문법이 완전히 같아서, 텍스트만 보고는 구분할 수 없다. 실제로 E-10 실측에서 겸양 표현이 법적 금지 주장으로 오판돼 정상적으로 생성된 답변 6건 중 4건이 `grounding_failed`로 거부됐다.

해결책은 텍스트에서 신호를 추측하는 대신, 모델이 자기 답변의 완결성을 **구조화된 필드로 직접 선언**하게 하는 것이다. `DraftAnswer`에 `action`과 `missing_information`을 추가했다.

```python
action: Literal["fully_answerable", "partially_answerable", "clarification_required", "unanswerable"]
missing_information: list[str] = Field(default_factory=list)
```

## action 필드와 검증 강도 분기

`validate_draft`는 `action` 값에 따라 요구 수준을 달리한다.

- `fully_answerable` / `partially_answerable`: 기존과 동일하게 전부 엄격히 검증한다 — 모든 실질 주장·체크리스트 항목에 존재하는 인용 ID가 있어야 한다.
- `clarification_required`: 사용자의 개별 사실(설비용량·계약 조건 등)을 알아야만 좁힐 수 있는 경우다. 실질적 법적 주장이 아니므로 `sections`·`checklist`가 비어도 되고, `missing_information`만 있으면 통과한다. (이건 [사전 라우팅](pre-retrieval-question-routing.md)의 `clarification_required`와 다른 경로다 — 사전 라우팅은 검색 전에 걸러내고, 이건 실제 검색·생성을 해본 뒤에야 드러나는 부족함이다.)
- `unanswerable`: 근거를 못 찾았다는 정직한 진술이라 `sections`·`checklist`가 비어도 된다. 다만 `summary`·`limitations`는 여전히 검증한다 — 무근거 규범 주장(다른 법령·기관을 단정적으로 지목)은 계속 차단한다.

## unanswerable도 침묵하지 않는다

`unanswerable`을 정형화된 "법령 corpus로는 답할 수 없습니다"로 끝내지 않고, 모델이 왜 안 되는지 생성한 설명을 그대로 노출한다. 다만 두 가지 검증을 다르게 적용한다.

1. **용어 중첩 요구를 조건부로 뺀다.** 기존 검증은 답변 텍스트와 근거 사이 용어가 50% 이상 겹쳐야 통과였다. 그런데 "근거가 이 주제를 안 다룬다"는 설명은 정의상 근거와 용어가 안 겹치는 게 정상이다(예: 질문 주제인 "전력망 연결 공사비"를 근거가 다루지 않는다고 말하는 문장). `_text_matches_evidence(..., require_topic_overlap=draft.action != "unanswerable")`로 `unanswerable`일 때만 이 요구를 뺀다 — "주제가 다르다"와 "숫자·규범을 지어냈다"는 다른 문제이므로 후자의 검사(규범어·과장어·숫자 대조)는 그대로 유지한다.
2. **다른 법령·기관 언급은 권유형만 허용한다.** 프롬프트에서 `unanswerable`일 때 다른 법령·기관을 지목하려면 단정형(`"~법 소관이다"`)이 아니라 권유형(`"~에 확인해 보시기 바랍니다"`)만 쓰도록 지시하고, `limitations`의 무근거 규범 주장 차단은 계속 검증한다 — 근거 없는 다른 법령명을 단정적으로 주장하는 오탐 위험을 막기 위해서다.

## 발견하고 고친 오탐 두 가지

E-10 실측 진단([diagnose_grounding_failures.py](../../apps/api/scripts/diagnose_grounding_failures.py))으로 근본 원인 두 가지를 더 찾았다.

1. **겸양 표현이 법적 금지로 오판됨.** 메타인지 동사(판단/확인/특정/단정/파악/결론) 뒤에 오는 "~할 수 없다/하기 어렵다"만 겸양으로 보고, 신호 패턴 검사 직전에 그 부분만 제거한다(`_strip_epistemic_hedges`). `"출입할 수 없다"`처럼 메타인지 동사가 아닌 경우는 그대로 남아 실제 금지 주장은 계속 걸린다. 근거(evidence) 쪽에는 절대 적용하지 않는다 — 모델이 만든 텍스트에만 적용하는 관용이다.
2. **정확한 조문 인용이 무근거 숫자로 오판됨.** 근거 문자열을 만들 때 조문 경로(`hit.path`, 예: `"제44조의4"`)를 빠뜨리고 있었다 — 모델이 정확히 인용한 조문 번호가 근거 문자열 어디에도 없어 "무근거 숫자"로 잘못 걸렸다. `validate_draft`의 `all_evidence`와 `_evidence_for_citations`(섹션·체크리스트별 인용 검사에 쓰임) 둘 다에 `hit.path`를 포함하도록 고쳤다.

## 재검증 비용 문제와 replay 도구

검증기 코드를 고칠 때마다 "이제 통과하는지" 확인하려고 매번 NVIDIA를 다시 호출하는 건 반복되는 낭비였다(초기 진단 스크립트가 거부된 draft만 저장하고 검색 근거 원문은 저장하지 않았기 때문). [diagnose_grounding_failures.py](../../apps/api/scripts/diagnose_grounding_failures.py)가 이제 검색된 `SearchHit` 전체를 JSON에 저장하고, [replay_grounding_validation.py](../../apps/api/scripts/replay_grounding_validation.py)가 그 저장분으로 `validate_draft()`만 새 API 호출 없이 재실행한다. 판정(`passed`) 자체는 항상 실제 `validate_draft()`를 그대로 호출한 결과이며, 진단 스크립트의 재구현 로직은 실패 원인을 설명하는 보조용으로만 쓴다 — 재구현이 실제 로직과 갈리는 사고를 막기 위해서다.

## 결정 기록

- 2026-08-08: `DraftAnswer`에 `action`(4값)과 `missing_information`을 추가하고, 검증기가 summary 텍스트에서 확신도를 추측하는 대신 이 명시적 신호로 요구 수준을 분기하게 했다.
- 2026-08-08: `unanswerable` 응답도 정형화된 거부 문구 대신 모델이 생성한 근거 설명을 노출하되, 다른 법령·기관 지목은 권유형만 허용하고 무근거 규범 주장 차단은 유지했다.
- 2026-08-08: 메타인지 동사 뒤 겸양 표현을 신호 검사에서 제외하는 `_strip_epistemic_hedges`를 추가했다 — 법적 금지와 인식론적 겸양의 표면 문법이 같아 생기던 오탐을 없앴다.
- 2026-08-08: `unanswerable` summary에는 50% 용어 중첩 요구를 빼되(주제 불일치가 이 action의 정상 상태이므로), 규범어·과장어·숫자 대조 검사는 그대로 유지했다.
- 2026-08-08: 근거 문자열에 조문 경로(`hit.path`)를 포함해, 정확히 인용된 조문 번호가 무근거 숫자로 오판되던 버그를 고쳤다.
- 2026-08-08: 진단 스크립트가 검색 근거 원문 전체를 저장하도록 바꾸고, 별도 replay 스크립트로 검증기 코드 변경을 새 API 호출 없이 재검증할 수 있게 했다.

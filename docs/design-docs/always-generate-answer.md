# terra 모드에서 search_only 폴백 제거 (always-generate)

상태: 승인
작성일: 2026-08-10
최종 갱신: 2026-08-10

관련 문서: [답변 근거 검증](answer-grounding-validation.md), [질문 사전 라우팅](pre-retrieval-question-routing.md), [AI 차별화](ai-differentiation.md)

## 배경

`answer_mode=terra`(웹 UI에서 이제 유일한 선택지 — `search_only` 옵션은 드롭다운에서 제거됨,
2026-08-10)로 요청해도, 다음 세 경로는 지금까지 LLM을 한 번도 호출하지 않고 고정 템플릿으로
끝났다.

1. 검색 후 근거 0건 (`no_matching_evidence`, `embedding_failed`) — [main.py:515](../../apps/api/app/main.py:515)
2. 사전 라우팅 차단 `realtime_required` / `external_document_required` — tier1(키워드,
   0028 "비용 최소화 결정")과 tier2(LLM 분류, 이미 자연어 이유가 있음) 모두
   — [main.py:417](../../apps/api/app/main.py:417)
3. `clarification_required` — tier1/tier2 사전 차단 + 생성 후 발견
   (`post_generation_clarification_answer`)

세 경로 모두 `mode="search_only"`로 응답해 클라이언트 UI에는 "검색전용"으로 노출된다. UI가 이제
`terra`만 제공하는데도 응답이 검색전용으로 보이는 건 사용자에게 "AI가 답을 회피했다"는 인상을
주고, 실제로도 근거가 부족할 때 왜 부족한지에 대한 설명이 사전에 고정된 문구뿐이라 질문별
맥락이 없다.

## 결정

`answer_mode=terra`이고 AI가 가용(`_ai_available()`)한 요청은, 위 세 경로 모두 **고정
템플릿으로 바로 끝내지 않고 LLM을 호출**해서 실제 답변(주로 `action=unanswerable` 또는
`clarification_required`)을 생성한다. `mode="ai"`로 응답한다.

`search_only_answer`, `route_blocked_answer`, `post_generation_clarification_answer`는
삭제하지 않는다. `answer_mode != terra`이거나 AI가 불가용한 경우(`ai_mode=off`, API 키 없음,
quota 소진으로 `ai_quota_exhausted=True`)에는 지금과 동일하게 이 함수들이 그대로 쓰인다 —
LLM을 호출할 수 없는 상태이므로 이번 변경의 대상이 아니다.

## 변경 지점

### 1. `validate_draft` 완화 ([openai_answerer.py:289](../../apps/api/app/adapters/openai_answerer.py:289))

현재 `if not hits: return False`가 최상단에 있어 근거 0건이면 모델이 무엇을 답하든 무조건
구조 검증에서 탈락한다. 이를 다음으로 바꾼다.

```python
if not hits:
    return (
        draft.action == "unanswerable"
        and not draft.sections
        and not draft.checklist
    )
```

근거가 하나도 없을 때는 `unanswerable`이고 섹션·체크리스트가 완전히 비어 있을 때만 통과한다.
그 외 action이거나 섹션·체크리스트에 뭔가 채워져 있으면 여전히 거부된다 — "근거 없이 만든
법적 주장"은 계속 막는다. `hits`가 있을 때의 기존 검증(인용 ID 존재 여부 등)은 변경하지 않는다.

### 2. 검색 후 0건 경로 ([main.py:515-533](../../apps/api/app/main.py:515))

`if not use_ai or not hits: return fallback`에서 `not hits` 조건을 제거한다. `use_ai`가
참이면 `hits`가 비어 있어도 `generation_hits=[]`로 생성 단계까지 진행한다. `use_ai`가
거짓이면(비-terra 또는 AI 불가용) 지금처럼 즉시 `fallback` 반환.

`build_messages_v2`에는 "근거가 비어 있으면 반드시 `action=unanswerable`이고 `sections`·
`checklist`를 비운다"는 지시를 명시적으로 추가한다(현재 프롬프트는 근거가 항상 1건 이상
있다고 암묵적으로 가정하고 있어, 빈 근거에 대한 동작이 문서화돼 있지 않다).

### 3. 사전 라우팅 차단 경로 ([main.py:417-425](../../apps/api/app/main.py:417))

`route_decision.route != "legal_search"`일 때 바로 `route_blocked_answer`로 끝내지 않고,
검색 없이 LLM을 호출하는 새 경로 `generate_blocked_route_answer()`를 추가한다. 근거 없이
route와 reason만 주는 경량 프롬프트를 새로 만든다.

- `realtime_required` / `external_document_required`: LLM에게 route와 (tier2라면)
  `route_decision.explanation`을 주고, "이 데이터는 시스템에 연결되어 있지 않아 답할 수
  없다"는 취지의 문구를 생성하게 한다. tier1은 원래 자연어 이유가 없었으므로 이 호출에서
  처음으로 질문에 맞춘 설명을 받는다.
- `clarification_required`: LLM에게 질문 원문을 주고 부족한 사실(`missing_information`)을
  판단하게 한다. tier1의 `match_conditional_variance_phrase` 매칭은 원래 `missing_fields`가
  비어 있었는데(무엇이 부족한지 모름), 이제 LLM이 이걸 채운다.

생성된 `missing_information`은 **기존 `clarification_resubmission_summary()` 재제출
템플릿(빈칸 체크리스트 포맷)에 그대로 채워 넣는다** — 자유 서술형으로 바꾸지 않는다. 이
템플릿은 "다음 메시지에 이 필드를 채워 한 번에 보내라"는 사용자 행동 계약이라 포맷이 바뀌면
클라이언트 재제출 로직도 같이 바뀌어야 하기 때문이다.

### 4. 생성 후 발견되는 clarification_required

`post_generation_clarification_answer` 호출부는 변경하지 않는다 — 이미 실제 검색·생성을
거친 뒤 LLM이 스스로 `action=clarification_required`를 선언한 경우라 이번 변경 대상(LLM
호출 자체가 없던 경로)이 아니다.

### 5. 관측성

`diagnostics`에 `blocked_route_generation` stage를 추가해 새 LLM 호출의 성공/실패/소요
시간을 기존 stage-timing 로깅(`emit_question_stage_timing`)과 동일한 방식으로 남긴다.
실패 시(timeout/429/402/grounding 실패) 지금과 동일하게 `search_only` 템플릿으로 떨어진다
— 새 실패 모드를 만들지 않는다.

## 비용·성능 영향 (미확정 — 배포 후 실측 필요)

- NVIDIA hosted NIM은 현재 "무료 prototype 접근"이며 확정된 production 단가가 없다
  ([nvidia-local-inference-and-vercel-connectivity.md](../references/nvidia-local-inference-and-vercel-connectivity.md)
  "미확정 사항"). 오늘 기준 $ 비용 증분은 계산할 근거가 없다.
- **호출량 증가**: 늘어나는 대상은 "이미 파이프라인에 들어온 요청의 처리 비용"이 아니라
  "지금은 LLM을 아예 안 타던 요청이 처음으로 타는 것"이다. 경로별 호출 횟수:

  | 경로 | 지금 | 변경 후 | 증가 원인 |
  |---|---|---|---|
  | tier1 라우팅 차단 (`route_tier1`, 정규식만) | 0회 | 1회 | `generate_blocked_route_answer()` 신설 |
  | tier2 라우팅 차단 (`route_tier2`, 이미 분류 LLM 호출 있음) | 1회(분류) | 2회(분류+차단 메시지 생성) | 차단 메시지 생성 호출 추가 |
  | 검색 후 근거 0건 | 0회 | 1회 | `generation_hits=[]`로 생성 단계 최초 실행 |
  | 생성 후 clarification_required | 1회 | 1회(변경 없음) | 이미 생성 호출을 탄 뒤의 재포맷이라 대상 아님 |

  가장 큰 증가분은 tier1 라우팅 차단이다 — 이 경로는 0028에서 "정규식만으로 즉시 걸러
  embedding·검색·LLM을 전부 0회로 만드는" 것 자체가 설계 목적이었던 경로라, 이번 변경이
  그 목적을 정확히 뒤집는다. 실제 트래픽 중 tier1 비중이 전체 증가폭을 좌우하는데, 이
  비율은 Vercel Hobby 플랜의 런타임 로그 보존이 1시간뿐이라 이 문서 작성 시점에는 측정
  불가 — 배포 후 diagnostics/postgres_identity 저장 기록(인증 사용자 한정)으로 실측한다.
  각 신규 호출도 기존 `NvidiaNimAnswerer`의 재시도 정책(`max_attempts=3`)을 그대로
  물려받으므로, 일시적 오류 시 요청당 최대 3배까지 호출이 늘 수 있다(기존 generation
  경로도 이미 가진 특성).
- **지연시간 증가**: 위 세 경로는 지금 수백 ms 내 끝나지만, 배포 후에는 매번 생성 단계
  예산(`answer_timeout_seconds`, 최대 40초)을 타게 되어 체감 응답 시간이 늘어난다.
- **trial rate limit 소진 위험**: 무료 tier 호출 한도에 더 빨리 도달하면 `BILLING_OR_QUOTA_ERROR`
  fallback 빈도가 늘어 실제로 답할 수 있는 질문까지 튕길 수 있다.
- 실제 단가가 확정되면(NVIDIA build.nvidia.com 계정 결제 화면) `추가 호출 수 × 평균 토큰 수
  × 단가`로 계산한다. 이 계산식만 남겨두고 숫자는 채우지 않는다.

## 대안 (검토 후 기각)

- **근거 0건 경로만 우선 적용**: 호출량 증가를 작게 시작할 수 있으나, 사용자가 라우팅
  차단·clarification 경로도 명시적으로 포함하도록 요청했다(2026-08-10 대화 확정).
- **search_only_answer 등 관련 함수 삭제**: 비-terra/AI 불가용 fallback 경로에서 계속
  쓰이므로 삭제하면 그 경로가 깨진다. 사용자도 "코드는 지우지 말라"고 명시했다.

## 결과

- `mode="search_only"`는 `answer_mode != terra`이거나 AI 불가용일 때만 나타난다. terra +
  AI 가용 조합에서는 항상 `mode="ai"`.
- 되돌리려면: (1) `validate_draft`의 `if not hits` 분기를 원래대로, (2) main.py의 세 지점을
  원래 즉시-반환으로 되돌리면 된다. 관련 함수를 삭제하지 않았으므로 코드 되돌림은 국소적이다.

## 검증

- `test_ai_fallback.py`, `test_grounding_gate.py`, `test_routing_pipeline.py`,
  `test_answering.py`에 근거 0건/라우팅 차단/clarification 각각의 "LLM 호출 성공 시 mode=ai"
  "LLM 호출 실패 시 search_only 폴백" 정상·실패 케이스를 추가한다.
- 배포 후 1주일 diagnostics 기준으로 실제 호출량 증가율과 quota 소진 빈도를 재검토한다
  (재검토 항목으로 `docs/exec-plans/tech-debt-tracker.md` 또는 후속 todo에 등록).

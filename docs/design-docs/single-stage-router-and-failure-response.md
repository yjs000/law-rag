# 단일 단계 라우터와 라우터 불가 응답

상태: 승인 · 2026-08-25

## 목적

`legal_search`를 실제 법령 근거 답변 파이프라인에만 쓰고, 라우터 timeout·provider 오류를 검색을 시작하지 않는 별도 `routing_unavailable` 경로로 안전하게 종료한다. 이 변경은 라우터의 결정적 tier1 규칙을 제거하고 NVIDIA provider 한 단계만 사용한다.

## 정상 법령 답변 경로

`legal_search`는 독립 실행 단계가 아니라, 성공한 라우터가 선택하는 근거 기반 답변 경로의 이름이다. 정상 `terra` 요청은 아래 순서로 처리한다.

1. `legal_search` 라우팅 결정
2. `evidence_retrieval` — direct-path이면 query embedding을 생략하고, 일반 질의면 embedding을 만든 뒤 법령 근거를 검색한다.
3. `evidence_source_validation` — 검색 결과 중 국가법령정보원 공식 HTTPS 출처가 아닌 항목을 제거한다.
4. `answer_generation` — 검증된 검색 근거만 모델에 전달해 답변 초안을 생성한다.
5. `answer_validation` — 초안의 구조, action, section·checklist 인용 ID가 생성에 제공한 근거를 가리키는지 검증한다.

`answer_validation`이 실패하면 기존 fallback 계약을 유지한다. 이 fallback은 라우터 실패가 아니므로 D-010은 retrieval·generation 기존 실패 계약을 바꾸지 않는다.

## 단일 라우터 계약

- `route_tier1`, Kiwi 키워드·정규식 규칙, tier 번호와 nearest-example embedding hint를 제거한다.
- 단일 `QuestionRouter` port와 NVIDIA 구현체가 질문을 `legal_search`, `clarification_required`, `realtime_required`, `external_document_required` 중 하나로 판정한다.
- production composition root는 NVIDIA router만 주입한다. 테스트는 port에 fake를 주입하며, application code가 `MockRouteClassifier`의 reason 문자열을 특별 취급하지 않는다.
- 라우터 성공 reason code는 닫힌 값 `router_judgment`로, 실패 reason code는 `routing_timeout` 또는 `routing_provider_error`로 한정한다. 예외 메시지·provider 응답·질문 원문은 response, diagnostics, 구조화 로그 어느 곳에도 넣지 않는다.

## 라우터 불가 경로

라우터 호출이 stage timeout 또는 provider 예외로 끝나면 `RouteDecision`은 `route="routing_unavailable"`과 안전한 reason code를 가진다. 이 route는 embedding, `evidence_retrieval`, `evidence_source_validation`, `answer_generation`, `answer_validation`을 전혀 시작하지 않는다.

대신 `blocked_answer_generation`이 다음만 생성한다.

- 시스템이 질문 분류를 일시적으로 처리하지 못했으며 다시 시도해야 한다는 안내
- 법률 결론, 법령 인용, section, checklist가 없는 `unanswerable` action

`blocked_answer_generation`의 초안은 빈 근거로 answer validation을 통과해야 하며, timeout, provider 오류 또는 validation 실패 시에는 같은 의미의 결정적 `blocked_fallback`을 반환한다. 이 fallback은 `mode="ai"`, `action="unanswerable"`, 빈 citation·section·checklist를 사용한다.

기존의 정상 사용자 요구 route는 장애가 아니므로 별도 명칭으로 유지한다.

- `clarification_required`: `clarification_generation`
- `realtime_required`와 `external_document_required`: `required_source_guidance_generation`
- `routing_unavailable`: `blocked_answer_generation`

세 경로는 adapter·draft schema를 공유할 수 있지만 timing event, diagnostics status, 사용자 응답 계약은 서로 섞지 않는다.

## 외부 응답과 관측

`QuestionResponse.route`는 `routing_unavailable`을 허용한다. 안전 reason code는 route outcome 구조화 이벤트와 인증된 요청 diagnostics에만 기록하며, raw 예외 문자열이나 traceback은 기록하지 않는다. 사용자 응답은 route와 검토된 안내 문구만 사용한다. `search_only_enabled`는 계속 `False`로 유지하고, 어떤 route도 이 설정을 변경하거나 `search_only` mode를 응답에 사용하지 않는다.

관측 stage 명칭은 `answer_generation`, `answer_validation`, `clarification_generation`, `required_source_guidance_generation`, `blocked_answer_generation`으로 분리한다. 기존 generic `generation`과 `blocked_route_generation`은 제거한다. `evidence_source_validation`은 검색 결과 필터의 명칭이며, D-010에서는 별도의 provider 호출·타이머를 추가하지 않는다.

## 범위 밖

- `search_only` 요청의 라우팅 적용
- retrieval, embedding, normal answer generation의 timeout·fallback 정책 변경
- 인용의 의미적 정합성 평가 강화
- 다른 provider로 자동 전환하거나 외부 실시간·개인 문서 데이터를 조회하는 기능

## 결정 기록

| 날짜 | 결정 | 이유 |
| --- | --- | --- |
| 2026-08-25 | 정상 근거 경로를 `answer_generation` 뒤 `answer_validation`으로 명명 | 현재 `validate_draft`가 인용 ID와 action·구조를 함께 검증하므로 단순한 citation-only 명칭보다 정확하다. |
| 2026-08-25 | 라우터 오류는 `legal_search`로 진행하지 않고 `routing_unavailable`으로 종료 | provider 장애를 정상 법령 검색으로 위장하면 불필요한 embedding·검색·인용 경로를 실행하고 관측 의미도 흐려진다. |
| 2026-08-25 | `blocked_answer_generation`은 `routing_unavailable`에만 사용 | 사용자 사실·외부 출처가 필요한 정상 route와 인프라 장애 route를 동일한 blocked 의미로 묶지 않는다. |

# 질문 사전 라우팅 설계 (0028, 대체됨)

상태: 대체됨 (2026-08-25)
작성일: 2026-08-07
최종 갱신: 2026-08-25

이 문서는 0028에서 검토한 사전 라우팅 문제와 당시의 tier1/tier2 설계를 보존하는
역사 기록이다. 현재 런타임 계약과 실패 안전 경계는 [단일 단계 라우터와 라우터 불가
응답](single-stage-router-and-failure-response.md)과 [D-010 실행 계획](../exec-plans/active/0057-single-stage-router-and-failure-response.md)을
기준으로 한다.

## 현재 계약 (D-010)

현재 질문 라우터는 하나의 typed `QuestionRouter`와 NVIDIA 구현체다. provider가 판정할
수 있는 route는 `legal_search`, `clarification_required`, `realtime_required`,
`external_document_required` 네 가지이며, tier 번호·Kiwi 규칙·nearest-example
embedding hint·mock classifier는 현재 runtime 경로에 없다.

성공한 `legal_search`만 다음 grounded sequence로 들어간다.

1. `evidence_retrieval`
2. `evidence_source_validation` — 국가법령정보 공식 HTTPS 출처 filter
3. `answer_generation`
4. `answer_validation` — 초안 structure/action/citation ID 확인

`evidence_source_validation`은 기존 URL filter이며 provider 호출이나 timing event를
추가하지 않는다. `answer_validation`은 generation 뒤에 실행되는 별도 구조 검증이다.
`clarification_required`는 `clarification_generation`, `realtime_required`와
`external_document_required`는 `required_source_guidance_generation`을 사용한다.

router timeout/provider error는 `routing_unavailable`과 안전한 reason code
(`routing_timeout` 또는 `routing_provider_error`)로 끝난다. 이 route는 corpus temporal
조회, embedding, retrieval, evidence-source validation, 정상 answer generation,
정상 answer validation을 실행하지 않는다. 대신 `blocked_answer_generation` 뒤에
`blocked_response_validation`만 수행하며, 생성 초안이 malformed이면 `mode="ai"`,
`action="unanswerable"`, 빈 sections/checklist/citations의 deterministic fallback을
반환한다. `search_only_enabled`는 계속 false이고 어떤 route도 `search_only`를 반환하지
않는다.

## 0028의 문제 정의와 역사적 근거

0028은 `terra` 요청에서 embedding·법령 검색을 실행하기 전에 법령 corpus만으로 답할 수
있는 질문인지 판단하려는 문제에서 출발했다. 실시간 정보나 사용자 문서 대조가 필요한
질문을 억지로 검색하면 무관한 법령이 AI 문맥에 섞일 수 있다는 점이 실험 D-10/D-10-R1에서
관측됐다.

질문 embedding과 route 예시 embedding의 최근접 유사도는 주제 유사도는 재지만 화용론적
충분성을 재지 못했다. 예를 들어 일반 설명으로 충분한 질문과 설비용량 같은 사용자
사실이 필요한 질문은 어휘가 비슷해도 검색을 시작할 수 있는지 판단은 달라진다. 이
한계가 당시 규칙과 embedding hint를 검토하고 단일 provider 판단으로 재설계한 배경이다.

## 0028 결정 기록 (역사)

- 2026-08-07: 입력을 질문 텍스트와 법령 corpus로 제한하고, clarification은 서버 자동
  병합 없는 재제출 템플릿으로, realtime/external-document 요구는 후속 수집 없는 안내로
  범위를 좁혔다.
- 2026-08-08: embedding 최근접 threshold 방식이 화용론적 충분성 판단에 부적합하다는
  calibration 결과를 기록하고 LLM judgment 방식을 검토했다.
- 2026-08-25: 0028의 tier1/tier2 runtime 설계를 대체하고 D-010의 단일 NVIDIA router와
  `routing_unavailable` no-search failure contract를 현재 기준으로 확정했다.

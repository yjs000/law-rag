# 0057: 단일 단계 라우터와 라우터 불가 AI 응답

상태: 제안됨 · 미착수

## 목표

`legal_search`는 법령 검색과 근거 기반 AI 답변 생성만 뜻한다. tier1을 제거하고, NVIDIA 라우터 timeout·오류는 검색 없이 안전한 reason을 포함한 AI 안내로 처리한다.

## 간단한 계획

- `route_tier1`을 제거하고 단일 NVIDIA 라우터로 이름·계약을 정리한다.
- `legal_search`는 embedding·법령 검색·인용 검증을 수행하는 경우에만 사용한다.
- timeout/provider error는 별도 `routing_unavailable` 경로와 안전한 reason code로 표현한다. raw 예외는 응답·로그에 노출하지 않는다.
- 이 경로는 검색 없이 기존 blocked-route AI 응답 생성 경계를 사용한다. 법률 결론·인용은 생성하지 않고, 생성도 실패하면 결정적 fallback을 반환한다.
- 정상 검색, timeout, provider error, AI 안내 생성 실패를 회귀 테스트하고, 오류 경로의 embedding·retrieval 호출이 0회인지 확인한다.

## 완료 조건

- `legal_search`와 라우터 불가 AI 안내가 외부 route·관측·테스트에서 구분된다.
- 법률 실질 주장은 검색 근거와 인용이 있는 경우에만 반환된다.

## 승격 조건

사용자가 구현 착수를 요청하면 이 파일을 `active/`로 이동하고, 외부 route 명칭과 안내 문구를 확정한다.

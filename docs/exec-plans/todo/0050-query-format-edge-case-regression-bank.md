> 작업 ID: `B-002`
> 상태: `Todo`
> 유형: `Bug`
> 보조 라벨: `Evaluation`
> 선행 조건: 사용자가 우선 조사할 엣지케이스 범위를 확정해야 한다.
> 다음 행동: 우선 조사할 엣지케이스 범위를 확정
> 참고 범위:
> - `docs/exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md` L20-L24 — 실제 재질문 중복·누적 재현과 채워진 항목을 다시 묻지 않는 목표

# 0050: 질의 형식 엣지케이스 조사 및 회귀 테스트 뱅크 구축

## 계획 본문

상태: `제안됨 (2026-08-10)`

제안 출처: 사용자가 [0047](0047-clarification-loop-dedup-and-unanswered-handling.md),
`0048`(article subclause query-only returns parent article),
`0049`(abbreviated article reference routes to search-only)와 같은 실제 fetch
로그 기반 버그를 연달아 보고한 뒤, 이런 종류의 질의 형식 엣지케이스를 개별 제보에
의존하지 않고 먼저 찾아내어 테스트로 등록해 둘 필요가 있다고 지시했다.

## 목표

- 실제 사용자 재현 로그로만 드러나는 질의 형식(대화 맥락 재전송, 조문 축약 참조, 하위
  항·호 질의, 자유 텍스트 추가 정보 응답 등) 엣지케이스를 사전에 조사해 목록화한다.
- 조사한 엣지케이스를 재현 가능한 최소 fixture(질의문, `conversation_context`, 기대
  라우팅/응답 형태)로 정리해 회귀 테스트로 등록한다.
- 새 라우팅·답변 로직 변경 시 이 목록을 기준으로 회귀 여부를 확인할 수 있게 한다.

## 포함 범위

- `apps/api/tests/test_routing.py`, `test_routing_pipeline.py`, `test_answer_actions.py` 등
  기존 라우팅·답변 테스트 구조를 조사해 엣지케이스 fixture를 어디에 어떤 형태로 추가할지
  설계
- 조문 번호 축약 참조, 조문 하위 항·호 참조, 대화 맥락에 걸친 후속 질의, 추가 정보 요청에
  대한 자유 텍스트(비구조화) 응답 등 이번에 보고된 패턴 외에 유사한 질의 형식을 실제
  코퍼스·라우팅 로직 기준으로 추가 조사
- 각 엣지케이스별 현재 동작(정상/오류)과 기대 동작을 문서화

## 비범위

- 이번 조사에서 발견된 개별 버그의 수정 자체(발견되면 각각 별도 TODO 또는 tech-debt-tracker
  항목으로 분리)
- 프론트엔드 UI 변경

## 완료 조건

- 조사한 엣지케이스 목록과 각 항목의 현재 동작·기대 동작이 문서로 정리된다.
- 목록의 각 항목이 실행 가능한 회귀 테스트로 등록되어 CI에서 반복 검증된다.
- [0047](0047-clarification-loop-dedup-and-unanswered-handling.md),
  `0048`(article subclause query-only returns parent article),
  `0049`(abbreviated article reference routes to search-only)에서 정의한 재현
  시나리오가 이 뱅크에 포함된다.

## 승격 조건

- 사용자가 우선 조사할 엣지케이스 범위(조문 참조 형식 위주 vs 전체 질의 형식)를 확정한다.

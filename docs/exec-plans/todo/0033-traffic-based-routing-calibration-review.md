> 작업 ID: `E-004`
> 상태: `Todo`
> 유형: `Experiment`
> 보조 라벨: `Performance`, `Evaluation`
> 선행 조건: 단일 QuestionRouter 오분류 또는 D-10 수준 인증 표본이 실제로 누적되거나 사용자가 재검토를 요청해야 한다.
> 참고 범위:
> - `docs/exec-plans/completed/0028-pre-retrieval-question-routing.md` L3-L7 — 기존 오분류와 0033 후속 재검토 연결
> - `docs/exec-plans/completed/0028-pre-retrieval-question-routing.md` L40-L48 — route·reason code·검색 실행 관측 계약

# 0033: 트래픽 축적 후 라우팅·관측 재검토 묶음

상태: `역사적·superseded — D-010(0057) 단일 QuestionRouter로 대체됨; 실 트래픽/tracking 데이터 축적 후 정책 calibration만 재검토`

> 이 문서의 tier1/tier2 사전·counter·fixture 표현은 2026-08-08 당시의 역사 기록이다. 현재
> 실행 경로를 제안하지 않으며, 후속 작업은 D-010의 단일 `QuestionRouter` route/reason_code
> 정책과 fail-closed 관측을 대상으로 해야 한다.

제안 출처: 2026-08-08 사용자가 "트래픽이 쌓이면 tier1 사전 확장 검토"와 "인증 사용자뿐 아니라
비인증 사용자 이력도 검토"를 후속 작업으로 지정하며, 함께 실행 가능한 항목을 그룹화해 남기도록
요청했다.

## 왜 묶었는가

두 항목 모두 **같은 선행 조건**(실 서비스 트래픽이 쌓여야 판단 가능)을 공유하고, 같은 산출물
(`app/observability.py`의 counter들, 인증 사용자 diagnostics 이력)을 입력으로 쓴다. 별도로
착수하면 같은 데이터를 두 번 모으는 셈이라 하나의 검토 라운드로 묶었다.

## 포함 항목

### A. (역사 기록) tier 1 사전 확장 재검토

- `scripts/build_tier1_term_dictionary.py`가 v1 질문은행 1,000문항 중 BUILD 200개만 분석했다
  (2026-08-08, [0028](../completed/0028-pre-retrieval-question-routing.md) 참고) - 나머지 EVAL 800개는
  커버리지 확인에만 썼지 사전에 반영하지 않았다.
- `emit_route_outcome()`의 `_route_by_route_tier`/`_route_by_reason`/
  `_clarification_missing_fields` counter(2026-08-07 tier1 구현 시 추가)가 쌓이면, 실제 tier1이
  못 잡고 tier2로 넘어가는 빈도가 높은 reason_code·route 조합을 확인할 수 있다.
- **역사 기록의 한계**: EVAL 800개 + 당시 tracking 데이터로 새 키워드/패턴 후보를 채굴하던
  접근은 tier1/tier2 runtime 제거로 superseded 되었다. 같은 데이터를 다시 실행하거나 사전을
  확장하지 않는다. 후속 calibration에서는 단일 router의 route/reason_code 오분류를 사람이
  검토하고, `boundary-document-keyword-false-positive` 같은 과거 위양성은 회귀 참고로만 둔다.

### B. 인증·비인증 사용자 이력 검토

- **인증 사용자**: `_save_if_authenticated()` → `postgres_identity.save_question()`이 이미
  안전한 `diagnostics`(route/reason_code/confidence, 2026-08-08 추가)를 저장한다. tier 필드나
  설명 원문은 현재 계약에 포함하지 않는다.
  D-10 gold 검토와 같은 방식으로 사람이 표본 검토할 수 있다 - 새 인프라 불필요, 그대로 쓰면 된다.
- **비인증 사용자**: 개인정보 불변조건상 질문 원문·설명 텍스트는 저장하지 않는다(의도된 설계,
  바꾸지 않는다). 대신 `emit_route_outcome()`/`emit_question_outcome()`(2026-08-08
  `fallback_reason` 추가)의 process-local counter로 **집계 수준**의 분포만 확인 가능하다 -
  "비인증 사용자 이력 검토"는 개별 질문 재구성이 아니라 이 집계 분포를 인증 사용자 표본 검토
  결과와 대조하는 것으로 범위를 정한다(예: 인증 사용자 표본에서 발견한 패턴이 비인증 집계
  분포에서도 비슷한 비율로 나타나는지).
- **현재 calibration 방향**: 인증 사용자 표본을 D-10 방식으로 사람이 검토해 단일 router의
  route/reason_code 오분류 패턴을 찾고, 같은 기간 비인증 집계 분포(`route_metrics_snapshot()`,
  `fallback_reason_metrics_snapshot()`)와 비교해 일반화 가능한 패턴인지 확인한다.

## 승격 조건

- 다음 중 하나 이상이 실제로 관측됐을 때: (a) 단일 `QuestionRouter`의 route/reason_code
  오분류가 유의미하게 누적됐다, (b) 인증 사용자 질문 이력이 D-10 표본 검토를 할 만큼 쌓였다,
  (c) 사용자가 명시적으로 재검토를 요청했다.
- 승격 시 이 문서를 `active/`로 옮기고, 그 시점의 실제 counter 수치·표본 크기·비교 기준을
  명시한다.

## 완료 조건

- D-010 route fixture는 역사 artifact로 보존하고, 재검토가 승인된 경우에만 현재 router schema로
  별도 calibration 결과를 기록한다. tier1 사전 변경이나 tier script 재실행을 완료 조건으로 삼지 않는다.
- 인증·비인증 비교 결과를 문서로 남기고, 발견된 체계적 오분류 패턴은 `tech-debt-tracker.md` 또는
  0028 결정 기록에 반영한다.

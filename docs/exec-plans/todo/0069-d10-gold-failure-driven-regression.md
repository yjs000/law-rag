> 작업 ID: `E-006`
> 상태: `Todo`
> 유형: `Experiment`
> 보조 라벨: `Evaluation`, `Reliability`
> 선행 조건: D-10 Gold가 사용자 adjudication을 거쳐 `approved_gold` 상태여야 하며, 읽기 전용 평가 DB, NVIDIA embedding credential, clean code provenance가 준비되어야 한다.
> 다음 행동: D-10 승인 상태와 runner의 case 단위 실행 경계를 preflight로 확인하고, 안전한 문항별 실행 기록 계약의 실패 테스트부터 작성한다.
> 참고 범위:
> - `experiments/d_gold_10/README.md` L1-L31 — D-10의 10문항 범위, 사용자 검토 gate, 허용 preflight 명령
> - `apps/api/scripts/evaluate_experiment_d_gold.py` L1140-L1205 — approved Gold runner의 credential·DB 사전조건과 안전한 오류 payload
> - `apps/api/scripts/experiment_d_metrics.py` L1-L140 — gold case와 retrieval metric의 문항별 계약

# D-10 Gold 순차 실패-회귀 평가 기록

## 목표

기존 D-10 Gold 10문항을 정해진 순서로 실행하고, 각 시도와 재시도의 결과를 재현 가능하게 남긴다. 오류, 근거 0건, 인용·grounding 계약 위반은 해당 문항을 통과시키기 전에는 다음 문항으로 진행하지 않는다. 코드 결함은 재현 회귀 테스트를 먼저 작성해 TDD로 수정하고, 외부 gate는 우회하지 않고 차단 기록으로 보존한다.

## 범위와 비범위

- 포함: 승인 D-10 Gold runner의 문항별 실행 경계, 안전한 실행 기록, 실패 triage, 회귀 테스트, TDD 수정, 재실행, 최종 집계.
- 제외: D-10 qrel·adjudication의 임의 수정, `pending_user_review`의 승인 우회, D-full Gold 제작, 운영 DB 쓰기, 원문·프롬프트·API 키·개인자료 기록.

## 실행 전 gate

1. `preflight-contract`와 승인 artifact binding을 실행해 D-10이 `approved_gold`인지 확인한다.
2. 평가 DB는 읽기 전용 연결만 사용하고, NVIDIA credential·clean code provenance를 확인한다.
3. 현재 D-10이 `pending_user_review`이면 이를 첫 시도 기록에 `approval_gate_not_satisfied`로 남기고 `Blocked` 상태로 둔다. 상태값이나 artifact를 코드·데이터 수정으로 우회하지 않는다.

## 문항별 실행·기록 계약

1. 평가 runner가 case ID 한 건을 실행·재실행할 수 있는 기존 경계를 확인한다. 경계가 없으면 전체 Gold 계약을 바꾸지 않는 최소 case runner를 실패 테스트부터 추가한다.
2. 10개 문항을 dataset의 고정 순서로 한 문항씩 실행한다. 모든 최초 실행과 재실행은 전역 `attempt_number`를 1씩 증가시킨다.
3. `.data/experiments/d-gold-10/<run-id>/failure-driven-log.jsonl`에 다음 허용 필드만 기록한다: `attempt_number`, `case_id`, 실행 명령의 식별자, 결과 상태, 안전한 오류 코드, evidence/citation count, 실패 분류, 회귀 테스트 경로·명령, 해결 요약, 재실행 결과, timestamp, code revision.
4. 각 실행 결과는 `pass`, `failure`, `blocked` 중 하나다. 원문, 질문 전문, 프롬프트, 예외 문자열, API 키, 개인자료는 기록하지 않는다.

## 실패 처리와 TDD

1. 오류, evidence/citation count 0, 또는 인용·grounding 계약 위반을 발견하면 즉시 기록한다: 증상, 재현 명령, 안전한 오류 코드, 원인 조사 근거, 해결 방법.
2. 코드 결함이면 실패 문항을 재현하는 회귀 테스트를 먼저 추가하고 실패를 확인한다. 가장 작은 구현으로 테스트를 통과시킨 뒤 관련 focused test와 문항 재실행을 모두 통과시킨다.
3. Gold 미승인, credential 부재, 읽기 전용 DB 부재, corpus mutation lock 등 외부 gate는 코드 결함으로 분류하지 않는다. 해결을 가장하지 않고 차단 원인과 재개 조건을 기록해 중단한다.
4. 한 문항이 최종 `pass`가 되기 전에는 다음 문항을 실행하지 않는다.

## 완료 조건

- 승인된 D-10의 모든 10문항이 순차적으로 최종 `pass`이며 각 문항의 evidence/citation count가 기록돼 있다.
- 총 `attempt_number` 수와 문항별 최초 실행·재실행 횟수가 일치한다.
- 모든 코드 결함에는 실패를 재현한 회귀 테스트, 원인, 해결, focused test 성공 증거, 문항 재실행 성공 증거가 있다.
- 최종 요약은 통과 문항 수, 총 시도 수, 실패 유형별 건수, 해결된 문제, 남은 `Blocked` 사유를 포함한다.

## 검증

1. 새 case runner·실행 기록·분류 코드의 unit/API 회귀 테스트를 실행한다.
2. Gold contract preflight와 승인 artifact binding을 실행한다.
3. 문항마다 focused regression test와 단일 문항 재실행을 성공시킨다.
4. 마지막에 D-10 10문항 전체 runner를 실행하고, 실행 기록의 attempt 집계·금지 필드 부재를 검증한다.

## 결정 기록

- 2026-09-04: D-10의 현재 `pending_user_review` gate를 코드나 artifact 수정으로 우회하지 않는다. 승인 전 실행 불가 결과는 실패가 아니라 외부 `Blocked` 기록으로 남긴다.
- 2026-09-04: 실패 발견 뒤 즉시 다음 문항으로 진행하지 않고, 문항별 회귀 테스트·수정·재실행을 완료한 후에만 진행한다.

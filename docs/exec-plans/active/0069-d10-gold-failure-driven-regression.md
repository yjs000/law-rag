> 작업 ID: `E-006`
> 상태: `Blocked`
> 유형: `Experiment`
> 보조 라벨: `Evaluation`, `Reliability`
> 선행 조건: D-10 Gold가 사용자 adjudication을 거쳐 `approved_gold` 상태여야 하며, 읽기 전용 평가 DB, NVIDIA embedding credential, clean code provenance가 준비되어야 한다.
> 다음 행동: 사용자 reviewer가 D-10 adjudication을 `approved_gold`로 seal한 뒤 Task 0 preflight를 재실행한다.
> 참고 범위:
> - `experiments/d_gold_10/README.md` L1-L31 — D-10의 10문항 범위, 사용자 검토 gate, 허용 preflight 명령
> - `apps/api/scripts/evaluate_experiment_d_gold.py` L1140-L1205 — approved Gold runner의 credential·DB 사전조건과 안전한 오류 payload
> - `apps/api/scripts/experiment_d_metrics.py` L1-L140 — gold case와 retrieval metric의 문항별 계약

# D-10 Gold 순차 실패-회귀 평가 기록

## 고정 계약

- D-10의 기존 case 순서를 변경하지 않는다. 단일 문항 실행은 전체 dataset의 부분 실행일 뿐, 전체 Gold metric 또는 정식 결과라고 표기하지 않는다.
- 현재 retrieval runner는 answer citation을 만들지 않는다. 따라서 ledger는 `retrieved_evidence_count`를 기록하고 `citation_count`는 `null`과 `not_generated_by_retrieval_runner` 사유만 허용한다. citation 0으로 거짓 실패를 만들지 않는다.
- 모든 기록은 `.data/experiments/d-gold-10/<run-id>/`에만 쓴다. 질문·원문·prompt·예외 문자열·credential은 허용 필드가 아니다.
- `pending_user_review`, credential 부재, 읽기 전용 DB 부재, corpus mutation lock은 코드 결함이 아닌 외부 gate다. 이를 우회하는 변경은 금지한다.

## Task 0 — approval gate를 먼저 판정한다

**변경 파일:** 없음.

1. `uv run --directory apps/api python -m scripts.experiment_d_10_gold_review preflight-contract`를 실행한다.
2. D-10 review artifact에 `approved_gold` binding이 있는지 확인한다.
3. 현재처럼 `pending_user_review`이면 `.data/.../gate.json`에 `approval_gate_not_satisfied`와 재개 조건(사용자 seal)을 기록하고 계획을 `Blocked`로 전이한다. 이후 Task 1을 시작하지 않는다.

**완료 증거:** preflight stdout의 안전한 상태 코드와 `gate.json`의 schema 검증 성공.

## Task 1 — 전체 Gold를 훼손하지 않는 case 선택 경계를 TDD로 만든다

**Files**

- Modify: `apps/api/scripts/evaluate_experiment_d_gold.py`
- Modify: `apps/api/tests/test_experiment_d_gold_runner.py`

1. 실패 테스트를 추가한다: 선택한 ID는 원 dataset 순서로 반환되고, 알 수 없는 ID·중복 ID·빈 선택은 `GoldRunError`가 된다.
2. `select_cases(dataset, case_ids)`와 `evaluate_approved_gold(..., case_ids=None)`를 최소 구현한다. `None`은 기존 전체 실행과 byte-for-byte 호환되는 결과를 유지한다.
3. 선택 실행 결과에 `execution_scope=partial`과 선택 case ID만 기록하고, `metrics`를 전체 Gold metric으로 게시하지 못하게 한다.
4. `pytest apps/api/tests/test_experiment_d_gold_runner.py -q`를 통과시킨다.

**완료 증거:** 1개 case 선택, 전체 기본 경로, 세 종류 invalid selector의 회귀 테스트가 모두 통과.

## Task 2 — 안전한 attempt ledger를 순수 모듈로 TDD 구현한다

**Files**

- Create: `apps/api/scripts/d10_failure_ledger.py`
- Create: `apps/api/tests/test_d10_failure_ledger.py`

1. `AttemptRecord`의 허용 필드와 `append_attempt`, `summarize_attempts`의 실패 테스트를 작성한다.
2. `attempt_number`가 1부터 연속이고, `case_id`가 고정 10문항 중 하나이며, 상태가 `pass|failure|blocked` 중 하나인지 검증한다.
3. `retrieved_evidence_count`가 0이면 `failure`가 되고, retrieval runner의 `citation_count`는 반드시 `null`과 지정 사유인지 검증한다.
4. `question`, `source_text`, `prompt`, `exception_message`, `api_key`가 입력 또는 JSONL에 있으면 직렬화 전에 거부하는 테스트와 구현을 추가한다.
5. `pytest apps/api/tests/test_d10_failure_ledger.py -q`를 통과시킨다.

**완료 증거:** ledger JSONL의 연속 시도 번호·집계·금지 필드 거부가 테스트로 고정됨.

## Task 3 — 한 문항만 실행하고 실패에서 멈추는 orchestrator를 만든다

**Files**

- Create: `apps/api/scripts/run_d10_failure_driven.py`
- Create: `apps/api/tests/test_run_d10_failure_driven.py`

1. 첫 case만 실행하고 `pass`일 때만 다음 case를 선택하는 실패 테스트를 작성한다.
2. provider/DB error, evidence 0, contract error에서 다음 case가 호출되지 않고 ledger에 안전한 코드가 쓰이는 테스트를 추가한다.
3. `--case-id`(한 번만 허용), `--resume <run-id>`, `--output-dir` CLI를 구현한다. resume은 마지막 `pass` 다음 case만 실행한다.
4. orchestrator는 Task 1의 partial runner와 Task 2 ledger만 호출한다. gold qrel·adjudication 파일을 수정하지 않는다.
5. `pytest apps/api/tests/test_run_d10_failure_driven.py -q`를 통과시킨다.

**완료 증거:** pass 시 전진, failure/blocked 시 정지, resume 시 정확한 다음 case 선택을 각각 unit test로 확인.

## Task 4 — 실제 문항은 한 건씩 실행하고, 코드 결함만 TDD로 고친다

**변경 파일:** 실행 중 발견한 최소 production file과 해당 regression test; 원인 확정 전에는 추가하지 않는다.

각 case에 대해 다음 loop를 반복한다.

1. `run_d10_failure_driven.py --case-id <현재-case>`를 실행하고 ledger attempt를 확인한다.
2. `failure`이면 안전한 error code와 evidence count로 원인을 분류한다.
3. 코드 결함이면 현재 case를 재현하는 실패 regression test를 먼저 작성하고, 최소 수정 → focused test → 같은 case 재실행 순서로 통과시킨다.
4. 외부 gate이면 `blocked` attempt와 재개 조건만 남기고 중단한다.
5. case가 `pass`인 경우에만 다음 고정 case로 진행한다.

**완료 증거:** 각 case의 최종 ledger 상태와, failure마다 regression test·수정 commit·재실행 attempt 연결.

## Task 5 — 전체 요약과 최종 회귀를 봉인한다

1. 10개가 모두 `pass`일 때만 full runner를 한 번 실행한다.
2. `summary.json`에 총 attempts, case별 attempts, pass/failure/blocked 수, failure code histogram, 해결한 코드 결함과 회귀 테스트 경로를 쓴다.
3. ledger와 summary의 attempt 수·case 상태·금지 필드 부재를 검증한다.
4. 관련 pytest와 `graphify update .`를 실행하고 생성 graph 산출물을 코드 변경 커밋에 포함한다.

**완료 증거:** 10개 pass, full runner 성공, summary/ledger 검증 성공, 관련 regression suite 성공.

## 결정 기록

- 2026-09-04: D-10의 현재 `pending_user_review` gate를 코드나 artifact 수정으로 우회하지 않는다. 승인 전 실행 불가 결과는 실패가 아니라 외부 `Blocked` 기록으로 남긴다.
- 2026-09-04: 단일 case 결과는 전체 Gold metric으로 게시하지 않는다. 부분 실행 결과와 전체 실행 결과의 의미를 분리한다.
- 2026-09-04: 실패 발견 뒤 즉시 다음 문항으로 진행하지 않고, 문항별 회귀 테스트·수정·재실행을 완료한 후에만 진행한다.

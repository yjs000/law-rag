> 작업 ID: `E-006`
> 상태: `Blocked`
> 유형: `Experiment`
> 보조 라벨: `Evaluation`, `Reliability`
> 선행 조건: D-10 Gold가 사용자 adjudication을 거쳐 `approved_gold` 상태여야 하며, 읽기 전용 평가 DB, NVIDIA embedding credential, clean code provenance가 준비되어야 한다.
> 다음 행동: D-10 embedding과 DB credential의 `aws-1-ap-northeast-2.pooler.supabase.com` 전송을 승인받고 `lay-energy-0111`을 재실행한다.
> 참고 범위:
> - `docs/design-docs/experiment-d-10-end-to-end-failure-regression.md` L1-L59 — end-to-end 판정 계약과 완료 조건
> - `apps/api/scripts/d10_failure_runner.py` L1-L147 — native D-10 sealed input·retrieval 안전 경계
> - `apps/api/scripts/run_d10_failure_driven.py` L1-L175 — 한 문항씩 진행하는 failure-driven orchestrator와 CLI

# D-10 Gold 순차 실패-회귀 평가 기록

## 고정 계약

- D-10의 기존 10개 case 순서를 변경하지 않는다. 이 작업은 1,000-case Gold runner를 부분 실행하거나 그 계약으로 변환하지 않는다.
- native runner는 sealed D-10 artifact의 승인 상태·hash와 frozen D-10 corpus/date binding을 검증한 뒤, 정확히 한 case만 retrieval 경계에 전달한다. 결과는 진단용 calibration run이며 전체 Gold metric 또는 held-out 결과라고 표기하지 않는다.
- answer 평가 결과는 실제 답변 본문·검색 원문·prompt·예외 전문을 노출하지 않는다. safe ledger에는 case ID, 상태, 안전 code, evidence/citation 수, action 판정만 남긴다.
- 자동 판정은 `expected_action`, evidence/citation binding, clarification/insufficient-evidence action leak, partial limit처럼 결정적인 계약에 한정한다. 주관적 문체 평점이나 모델 자기채점으로 법률 정확성을 대체하지 않는다.
- 모든 기록은 `.data/experiments/d-gold-10/<run-id>/`에만 쓴다. 질문·원문·prompt·예외 문자열·credential은 허용 필드가 아니다.
- `pending_user_review`, credential 부재, 읽기 전용 DB 부재, corpus mutation lock은 코드 결함이 아닌 외부 gate다. 이를 우회하는 변경은 금지한다.

## Task 0 — sealed·외부 실행 gate를 먼저 판정한다

**변경 파일:** 없음.

1. `uv run --directory apps/api python -m scripts.experiment_d_10_gold_review preflight-contract`를 실행한다.
2. D-10 review artifact에 `approved_gold` binding이 있는지 확인한다.
3. 현재처럼 `pending_user_review`이면 `.data/.../gate.json`에 `approval_gate_not_satisfied`와 재개 조건(사용자 seal)을 기록하고 계획을 `Blocked`로 전이한다. 이후 Task 1을 시작하지 않는다.

**완료 증거:** preflight stdout의 안전한 상태 코드와 `gate.json`의 schema 검증 성공.

## Task 1 — answer 평가 결과와 safe ledger 계약을 TDD로 확장한다

**Files:** `apps/api/scripts/d10_failure_ledger.py`, `apps/api/tests/test_d10_failure_ledger.py`.

1. `actual_action`, `judge_codes`, `citation_count`를 포함하는 answer attempt record의 실패 테스트를 작성한다.
2. question, answer text, source text, prompt, exception, credential가 input·JSONL·summary 어디에도 직렬화되지 않는 실패 테스트를 추가한다.
3. 기존 retrieval-only record와 answer record를 구분하는 최소 schema를 구현한다. 외부 gate의 `blocked + 0`과 실제 0 evidence의 `failure` 의미는 유지한다.
4. focused pytest와 ruff를 통과시킨다.

**완료 증거:** answer 판정 결과를 안전하게 보존하고 민감/원문 필드를 거부하는 회귀 테스트.

## Task 2 — 실제 RAG answer 경계를 호출하는 native case runner를 TDD로 만든다

**Files:** `apps/api/scripts/d10_failure_runner.py`, `apps/api/tests/test_d10_failure_runner.py`, 필요한 최소 application adapter.

1. `answer`, `clarification`, `insufficient_evidence`, provider/DB failure의 public-safe output 실패 테스트를 작성한다.
2. sealed/frozen input의 fixed question/date/corpus binding을 application request에 넘기고, routing·retrieval·answer·citation metadata를 내부에서 수집하는 최소 runner를 구현한다.
3. public output에서 answer/evidence text를 제거하고, action/evidence/citation count와 안전 code만 반환하게 한다.
4. focused pytest와 ruff를 통과시킨다.

**완료 증거:** 실제 answer 경계가 한 native D-10 case에서 호출되고, external gate가 안전한 `blocked`로 정규화됨.

## Task 3 — expected_action별 결정적 answer judge를 TDD로 만든다

**Files:** Create `apps/api/scripts/d10_answer_judge.py`, Create `apps/api/tests/test_d10_answer_judge.py`.

1. 네 expected action의 정상 케이스와 금지 케이스를 실패 테스트로 작성한다.
2. answer에는 evidence와 citation binding이 필요하고, partial answer에는 한계 표지가 필요하며, clarification/insufficient-evidence에는 실질 답변 leak가 없어야 한다는 규칙을 구현한다.
3. citation이 retrieval evidence에 없을 때와 빈 answer일 때의 안전 failure code를 구현한다.
4. focused pytest와 ruff를 통과시킨다.

**완료 증거:** `expected_action_mismatch`, grounding/citation, clarification, insufficient-evidence, partial-limit 경계가 결정적으로 판정됨.

## Task 4 — answer judge를 failure-driven orchestrator와 CLI에 연결한다

**Files:** `apps/api/scripts/run_d10_failure_driven.py`, `apps/api/tests/test_run_d10_failure_driven.py`.

1. judge pass일 때만 다음 case로 진행하고, judge failure/blocked이면 멈추는 실패 테스트를 작성한다.
2. `--sealed-dir`, `--case-id`, `--resume`, `--output-dir` CLI를 추가한다. case ID는 한 번만 허용하고 resume은 마지막 pass의 다음 case만 선택한다.
3. runtime settings에서 read-only DB와 NVIDIA credential을 조립하며, 부재 시 안전한 blocked attempt를 쓴다.
4. focused pytest와 ruff를 통과시킨다.

**완료 증거:** 실행 가능한 한-case CLI, pass/failure/blocked stop-resume 회귀 테스트.

## Task 5 — 실제 문항은 한 건씩 실행하고, 코드 결함만 TDD로 고친다

**변경 파일:** 실행 중 발견한 최소 production file과 해당 regression test; 원인 확정 전에는 추가하지 않는다.

각 case에 대해 다음 loop를 반복한다.

1. `run_d10_failure_driven.py --sealed-dir <sealed-dir> --case-id <현재-case>`를 실행하고 ledger attempt를 확인한다.
2. `failure`이면 routing, retrieval, temporal/corpus binding, grounding/citation, answer policy, guardrail, 문법/논리로 원인을 분류한다.
3. 코드 결함이면 현재 case를 재현하는 실패 regression test를 먼저 작성하고, 최소 수정 → focused test → 같은 case 재실행 순서로 통과시킨다.
4. 외부 gate이면 `blocked` attempt와 재개 조건만 남기고 중단한다.
5. case가 `pass`인 경우에만 다음 고정 case로 진행한다.

**완료 증거:** 각 case의 최종 ledger 상태와, failure마다 regression test·수정 commit·재실행 attempt 연결.

## Task 6 — 전체 요약과 최종 회귀를 봉인한다

1. 10개가 모두 `pass`일 때만 native D-10 runner로 10개를 순서대로 재검증한다. 1,000-case full runner는 실행하지 않는다.
2. `summary.json`에 총 attempts, case별 attempts, pass/failure/blocked 수, failure code histogram, 해결한 코드 결함과 회귀 테스트 경로를 쓴다.
3. ledger와 summary의 attempt 수·case 상태·금지 필드 부재를 검증한다.
4. 관련 pytest와 `graphify update .`를 실행하고 생성 graph 산출물을 코드 변경 커밋에 포함한다.

**완료 증거:** 10개 pass, full runner 성공, summary/ledger 검증 성공, 관련 regression suite 성공.

## 결정 기록

- 2026-09-04: D-10의 현재 `pending_user_review` gate를 코드나 artifact 수정으로 우회하지 않는다. 승인 전 실행 불가 결과는 실패가 아니라 외부 `Blocked` 기록으로 남긴다.
- 2026-09-04: 단일 case 결과는 전체 Gold metric으로 게시하지 않는다. 부분 실행 결과와 전체 실행 결과의 의미를 분리한다.
- 2026-09-04: 실패 발견 뒤 즉시 다음 문항으로 진행하지 않고, 문항별 회귀 테스트·수정·재실행을 완료한 후에만 진행한다.
- 2026-09-10: D-10은 이미 RAG 개발에 쓰인 calibration 10문항이다. 이를 별도 1,000-case Gold runner에 adapter로 주입하지 않고, sealed D-10 계약을 직접 검증하는 native runner로 실행한다. 기존 partial runner 변경은 이 결정과 맞지 않아 되돌린다.
- 2026-09-10: E-006은 retrieval-only가 아니라 routing·retrieval·answer·citation·guardrail의 end-to-end 경계를 점검한다. 자동 판정은 결정적 contract 위반에 한정한다.
- 2026-09-10: Task 4의 one-case CLI는 `lay-energy-0111`을 안전한 answer-stage ledger로 실행했다. 현재 DB와 NVIDIA credential이 모두 미설정이므로 `answer_unavailable`/`blocked`가 기록됐으며, 이는 코드 failure가 아닌 Task 5의 외부 gate다.
- 2026-09-10: `.env.local`로 live DB와 sealed corpus snapshot의 일치를 확인한 뒤 `lay-energy-0111`을 재실행했다. NVIDIA route classifier timeout은 v1의 `routing_unavailable` 응답으로 변환되며, D-10 runner가 이를 `insufficient_evidence` failure로 오인하던 결함을 회귀 테스트와 함께 수정했다. 재실행은 `routing_unavailable`/`blocked`로 안전하게 기록됐고, provider 복구 전에는 다음 case로 진행하지 않는다.
- 2026-09-10: 공식 NVIDIA 카탈로그는 configured model과 `guided_json`/`enable_thinking=false` 계약을 현재 지원한다. 로컬 회귀는 모두 통과했지만 provider latency는 protected sealed 질문의 destination-specific egress 승인 없이 재검증할 수 없어 E-006을 다시 `Blocked`로 전이한다.
- 2026-09-10: 사용자가 sealed D-10 질문과 `NVIDIA_API_KEY`를 `https://integrate.api.nvidia.com/v1`로 전송하는 destination-specific egress를 승인했다. `lay-energy-0111`부터 Task 5의 one-case pass/fix loop를 재개한다.
- 2026-09-10: live case는 실행 전에 승인 심사에서 차단되어 새 attempt나 외부 전송이 발생하지 않았다. NVIDIA 외에도 질문에서 파생된 embedding vector와 read-only DB credential이 `aws-1-ap-northeast-2.pooler.supabase.com`으로 전송되므로 이 두 번째 destination-specific egress 승인을 재개 조건으로 기록한다.

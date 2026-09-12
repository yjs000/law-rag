> 작업 ID: `E-006`
> 상태: `Done`
> 유형: `Experiment`
> 보조 라벨: `Evaluation`, `Reliability`
> 선행 조건: D-10 Gold의 `approved_gold` 상태, `.env.local`, NVIDIA와 Supabase V2 E2E 전체 접근 승인, clean code provenance가 준비되어야 한다.
> 다음 행동: none
> 참고 범위:
> - `docs/design-docs/experiment-d-10-end-to-end-failure-regression.md` L1-L76 — V2 end-to-end 실행·승인·예산 계약과 완료 조건
> - `apps/api/scripts/d10_failure_runner.py` L1-L147 — native D-10 sealed input·retrieval 안전 경계
> - `apps/api/scripts/run_d10_failure_driven.py` L1-L175 — 한 문항씩 진행하는 failure-driven orchestrator와 CLI

# D-10 Gold batch defect 평가·봉인 기록

## 고정 계약

- D-10의 기존 10개 case 순서를 변경하지 않는다. 이 작업은 1,000-case Gold runner를 부분 실행하거나 그 계약으로 변환하지 않는다.
- native runner는 sealed D-10 artifact의 승인 상태·hash와 frozen D-10 corpus/date binding을 검증한 뒤, 정확히 한 case만 retrieval 경계에 전달한다. 결과는 진단용 calibration run이며 전체 Gold metric 또는 held-out 결과라고 표기하지 않는다.
- answer 평가 결과는 실제 답변 본문·검색 원문·prompt·예외 전문을 노출하지 않는다. safe ledger에는 case ID, 상태, 안전 code, evidence/citation 수, action 판정만 남긴다.
- 자동 판정은 `expected_action`, evidence/citation binding, clarification/insufficient-evidence action leak, partial limit처럼 결정적인 계약에 한정한다. 주관적 문체 평점이나 모델 자기채점으로 법률 정확성을 대체하지 않는다.
- 모든 기록은 `.data/experiments/d-gold-10/<run-id>/`에만 쓴다. 질문·원문·prompt·예외 문자열·credential은 허용 필드가 아니다.
- E-006은 V2 prepare→core→finalize endpoint를 사용하고 V2 phase 57초/provider 55초 예산을 적용한다. V1 `_answer_question`, `RequestBudget`, routing 8초 예산을 사용하지 않는다.
- `.env.local`, NVIDIA 질문·근거·prompt 전송, Supabase corpus 읽기와 `question_executions`·events·issues 쓰기/정리, 로컬 안전 ledger, Vercel read-only 로그 조회는 승인됐다. corpus mutation·배포·push는 금지한다.
- E-006A는 평가기·safe ledger·결정적 judge·V2 실행 계약 구현으로 보며 사실상 완료했다. 남은 E-006B 범위는 현재 정의된 계약과 고정 D-10 10개를 고정 revision에서 진단하고, 그 한 번의 진단 패스에서 확인된 결정적 P0/P1만 일괄 수정·검증·봉인하는 것이다.
- provider timeout, HTTP 503, `routing_unavailable`과 동일한 외부 가용성 실패는 코드 결함이 아니다. 케이스별 외부 재시도는 최초 시도를 포함해 최대 3회로 제한하며, 모두 외부 차단이면 safe ledger의 `blocked` 증거로 종결한다.
- 진단 패스에서 동결한 결함 외에 뒤늦게 발견된 비차단 경계 사례와 추가 hardening은 현재 E-006에 편입하지 않고 E-007 후속 계획으로 기록한다. NVIDIA 안정성·timeout은 별도 Operations 계획으로 분리한다.

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
3. runtime settings에서 V2 prepare→core→finalize transport, Supabase V2 실행상태 persistence, NVIDIA credential을 조립하고 V2 phase 57초/provider 55초 예산을 사용한다. 부재 시 안전한 blocked attempt를 쓴다.
4. focused pytest와 ruff를 통과시킨다.

**완료 증거:** 실행 가능한 한-case CLI, pass/failure/blocked stop-resume 회귀 테스트.

## Task 5 — 1단계: 고정 revision 결함 탐색과 목록 동결

**상태:** 완료 — 두 진단 패스에서 10개 case를 각각 모두 확인하고 결정적 P1 두 건을 근본 원인별로 동결했다.

**변경 파일:** 없음. 진단 중에는 production code와 test를 수정하지 않고 별도의 diagnostic ledger와 안전한 결함 목록만 생성한다.

1. 시작 revision, working-tree diff identity, sealed D-10 hash, corpus/date binding을 기록하고 코드 기준을 고정한다.
2. 고정된 D-10 10개를 순서대로 한 번 모두 진단한다. 한 case의 `failure` 또는 `blocked`가 다음 case 진단을 막지 않게 하며, 이 진단 원장은 final 원장으로 취급하지 않는다.
3. provider timeout, HTTP 503, `routing_unavailable` 등 외부 실패는 같은 case만 재시도한다. 최초 시도를 포함해 case당 최대 3회이며, 세 번 모두 외부 실패이면 `blocked`로 기록하고 다음 case로 진행한다.
4. 각 비통과 결과를 외부 provider 변동과 결정적 코드 결함으로 분리한다. 결정적 결함은 고정 입력에서 재현 가능한 계약 위반만 인정하고, 중복 증상은 근본 원인별로 묶는다.
5. 이 단일 진단 패스에서 확인한 결정적 P0/P1만 E-006 결함 목록에 포함하고 목록을 동결한다. P2 이하, 비차단 경계 사례, 진단 종료 뒤 발견한 hardening은 E-007 후보로, NVIDIA 가용성·timeout은 별도 Operations 후보로 기록한다.

**완료 증거:** 동일 코드 identity에서 10개 모두 진단됨, case별 최대 3회 준수, 외부 blocked와 결정적 결함의 분리, 중복 제거된 P0/P1 결함 목록과 동결 시각.

## Task 6 — 2단계: 동결 결함의 일괄 TDD 수정과 단일 검증 묶음

**상태:** 완료 — 동결 P1 두 건의 RED·수정, 관련 회귀, 독립 review fix-loop, 전체 verify를 완료했다.

**변경 파일:** 동결된 결함 목록에 연결된 최소 production file과 regression test만 허용한다.

1. 동결 목록의 각 결함마다 가장 작은 RED 회귀 테스트를 먼저 작성하고 개별 실패를 확인한다. 개별 RED 확인은 생략하지 않는다.
2. 모든 RED가 준비된 뒤 동결 결함 전체를 한 묶음으로 수정한다. 결함 하나를 고칠 때마다 전체 검증이나 새 final 원장을 시작하지 않는다.
3. 동결 결함에 연결된 관련 회귀 묶음을 한 번 실행한다. 수정 과정의 작은 focused test는 허용하지만 관련 회귀 묶음의 공식 실행은 이 단계 끝에서 한 번으로 집계한다.
4. 전체 변경에 대한 독립 whole-branch review를 한 번 수행한다. 리뷰가 찾은 동결 결함의 미해결 P0/P1은 같은 batch에서 RED로 보완하고 affected focused test만 재확인한다. 새 비차단 경계 사례는 E-007 후보로 넘긴다.
5. `scripts/verify.ps1` 전체 검증을 batch 끝에서 한 번 실행한다. 실패하면 Task 6은 완료되지 않으며 final 원장을 시작하지 않는다. 원인을 동결 결함의 미해결 회귀 또는 후속 범위로 분류한 뒤 수정 batch 경계를 새로 확정한다.

**완료 증거:** 결함별 RED 증거, 동결 결함 전체 수정, 관련 회귀 묶음 성공 1회, 독립 review 1회, 최신 전체 verify 성공 1회.

## Task 7 — 3단계: 변경 없는 코드의 단일 최종 봉인

**상태:** 완료 — 고정 identity `bb9f3fdaa611a2a05615af0be21c3130e2cb3aa6` + `8c9bf955b3ff6b54ee304ed8689317b84ef85bca`로 10개 case를 단일 원장에 기록하고 `코드 검증 통과 + provider 변동 blocked`로 봉인했다.

1. Task 6의 review와 전체 verify가 통과한 implementation revision/diff identity를 고정한다. 이후 final 원장 생성 중에는 implementation code를 변경하지 않는다.
2. 새 final 원장 하나만 시작해 D-10 10개를 고정 순서로 실행한다. provider 외부 실패는 같은 case에만 최초 시도 포함 최대 3회 적용하고, 모두 실패하면 안전한 `blocked`로 기록한다.
3. final 실행에서 새로운 결정적 P0/P1 코드 결함이 확인되면 해당 원장을 폐기하고 Task 5의 새 진단 패스로 돌아간다. 외부 provider 차단은 원장 폐기나 코드 수정 사유가 아니다.
4. `summary.json`에 시도 수, case별 최종 상태, pass/failure/blocked 수, 외부 차단 code histogram, 동결 결함과 회귀 테스트 경로를 기록하고 ledger와 집계·금지 필드 부재를 검증한다.
5. 완료 판정은 `코드 검증 통과 + final 원장 안전성 검증 + 결정적 P0/P1 없음`이다. 10개 전부 pass이면 그대로 봉인하고, 일부 case가 3회 모두 외부 차단이어도 나머지 조건이 충족되면 `코드 검증 통과 + 외부 의존성 blocked`로 E-006을 종결할 수 있다.

**완료 증거:** 고정 implementation identity, 새 final 원장 정확히 1개, case별 3회 상한, 안전 summary/ledger 검증, 전부 pass 또는 명시적 외부 의존성 blocked 종결 판정.

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
- 2026-09-10: 사용자는 `.env.local`, NVIDIA 질문·근거·prompt 전송, Supabase corpus 읽기와 V2 실행상태 쓰기·정리, 로컬 안전 ledger, Vercel read-only 로그 조회를 포함한 E-006 외부 접근 범위 전체를 승인했다. corpus mutation·배포·push는 승인하지 않았다.
- 2026-09-10: 기존 Task 4 구현이 V1 `_answer_question`과 V1 `RequestBudget`을 사용한 것은 E2E 목표와 맞지 않는다. V2 prepare→core→finalize endpoint와 V2 phase 57초/provider 55초 예산으로 교체한 뒤 Task 5를 재개한다.
- 2026-09-10: `lay-energy-0111`에서 V2 router가 누락된 사업 결정사실을 `legal_search`로 분류하고, 수정 뒤에는 core가 `clarification_required`를 `unanswerable`로 덮으며, 마지막으로 ledger가 의도된 비검색 0-evidence pass를 거부하는 세 결함을 순서대로 재현했다. prompt 우선순위, non-legal core action 보존, `ask_clarifying_question`/`insufficient_evidence` 전용 zero-evidence 허용 테스트를 추가한 뒤 r6 실행이 pass했다.
- 2026-09-10: `lay-energy-0201` attempt 2는 `blocked/answer_unavailable`였다. read-only 진단 결과 원격 DB는 Alembic `0016`이고 `clarification_cases`가 없어 `create_or_get`에서 `UndefinedTableError`가 발생한다. 명시적 `--case-id`가 기존 nonpass 뒤 재시도되지 않는 runner 결함은 실패 테스트 후 수정했으며, migration `0017` schema write 승인 뒤 같은 r6 ledger에 재시도한다.
- 2026-09-10: 사용자의 승인으로 migration `0017`을 적용하고 table·index·version을 검증했다. `lay-energy-0201`에서는 개별 가능 여부와 조건부 허가 절차를 구분하도록 router/core action prompt를 정렬하고, 비어 있지 않은 summary를 answer-present로 보도록 judge를 수정했다. 간헐적 NVIDIA router 503은 새 attempt로 재실행했으며 attempt 9가 근거·citation 각 5건, `partial_answer_with_limits`, judge code 없음으로 pass했다.
- 2026-09-10: `lay-energy-0251` attempts 10~12는 결정축의 실제 값이 없는데도 `partial_answer_with_limits`를 반환했다. 동일 질문의 provider `missing_fields`가 0개와 2개 사이에서 변동해 prompt-only 판정이 재현 불가능함을 확인했다. 명시적 설비 적용 표지, 또는 기준값 없는 “소규모 설비”와 `결정축에 따라 달라지는가`가 함께 나타난 미해결 비교에서만 용량·전압·사용 방식·공사 종류의 값을 검사하는 좁은 router guardrail을 추가했다. provider 자유형 누락값만으로 승격하지 않고 로컬 검증 누락값만 `legal_search` 후보보다 우선하며, 일반 taxonomy·소규모 설비 축별 기준·일반 설비 비교 질문은 검색 가능하게 유지한다. 관련 회귀 65개와 이미 통과한 일반 절차 질문의 실제 `legal_search` 비회귀를 확인했다. attempt 13의 NVIDIA 503은 새 시도로 처리했고, 최종 리뷰 수정 후 attempt 17이 `ask_clarifying_question`, judge code 없음으로 pass했다.
- 2026-09-10: `lay-energy-0346` attempt 18은 검색 전 `routing_unavailable`로 blocked됐지만 새 V2 시도에서 회복됐다. 코드 수정 없이 attempt 19가 근거·citation 각 5건, `partial_answer_with_limits`, judge code 없음으로 pass했다.
- 2026-09-11: `lay-energy-0521` attempts 20~33에서 검색 상위 10건과 정답 조문 4건이 존재했지만 생성 입력 압축이 같은 조의 하위 항을 하나만 남겨 정답 조문 중첩을 2건으로 줄였고, core의 action·summary grounding도 실행마다 달랐다. 최대 5개 조·60,000자 예산은 유지하면서 선택된 조의 여러 하위 항을 순위대로 보존해 생성 근거 9건·정답 조문 중첩 4건으로 회복했다. core action 판정용 `decision_limitations`는 공개 저장에서 자동 제외한다. prompt만으로 오분류를 막을 수 없다는 리뷰 P1을 반영해, 비-clarification `CORE_REPAIR_REQUIRED`에서는 같은 core 재생성 대신 동일 동결 근거의 detail이 `partially_answerable`이고 citations·sections·checklist가 존재하며 기존 grounding 검증을 통과한 경우에만 final 응답으로 보존한다. raw hit·score·Gold/qrel·case ID·REC keyword로 partial을 강제하지 않는다. 일시적 `routing_unavailable`은 새 시도로 분리했고, attempt 34가 근거·citation 각 9건, `partial_answer_with_limits`, judge code 없음으로 pass했다.
- 2026-09-11: `lay-energy-0561` attempts 35~41은 일반적인 대조 자료 질문의 route 변동, `전기 판매` 검색어와 corpus 표현 불일치, `하여야`/`해야` 형태 차이 및 근거 검토 권고를 법적 의무형으로 생성하는 문제를 차례로 드러냈다. 일반 자료 유형 질문은 `legal_search`로 고정하고 실제 첨부 문서 분석은 유지했으며, 검색어 alias와 의무 어미 등가 정규화를 추가했다. 리뷰에서 근거 검토 문구를 grounding 예외로 허용하면 법적 의무가 우회됨을 확인해 예외를 제거하고 V2 prompt가 `확인하세요`/`대조하세요` 권고형을 쓰도록 했다. 관련 회귀 74개와 독립 리뷰를 통과했고, provider timeout은 별도 새 시도로 분리한 뒤 attempt 42가 근거·citation 각 6건, `partial_answer_with_limits`, judge code 없음으로 pass했다.
- 2026-09-11: `lay-energy-0601` attempts 43~44는 route와 동결 인용 6건이 정상인데도 core action이 `unanswerable`로 생성되어 최종 `insufficient_evidence`로 내려갔다. 안전 메타데이터 진단에서 동일 동결 근거의 core가 인용 6건과 grounding을 통과하면서 action만 `unanswerable`인 모순을 확인했다. 기존의 빈 인용 unanswerable core 해소 규칙을 인용 보유 core에도 확장하되, detail이 비-clarification `partially_answerable`이고 results·citations·sections·checklist·frozen-citation grounding을 모두 통과할 때만 우선하도록 유지했다. 다른 detail action 거부 회귀와 관련 테스트 44개, 독립 리뷰를 통과했고 attempt 45가 근거·citation 각 6건, `partial_answer_with_limits`, judge code 없음으로 pass했다.
- 2026-09-11: `lay-energy-0605`는 코드 수정 없이 attempt 46에서 검색·citation 0건, `insufficient_evidence`, judge code 없음으로 pass했다.
- 2026-09-11: `lay-energy-0836`은 코드 수정 없이 attempt 47에서 검색·citation 0건, `insufficient_evidence`, judge code 없음으로 pass했다.
- 2026-09-11: `lay-energy-0943`은 코드 수정 없이 attempt 48에서 검색·citation 0건, `insufficient_evidence`, judge code 없음으로 pass했다. calibration 원장의 10개 case 최신 상태가 모두 pass임을 검증했으며 Task 6은 기존 48회 원장을 보존하고 새 `e006-v2-20260911-final-01` 원장에서 고정 순서 전체 재검증한다.
- 2026-09-11: 새 전체 재검증 원장 `e006-v2-20260911-final-01`은 고정된 10개 case를 순서대로 완료했다. 총 22회 중 pass 10, failure 6, 외부 blocked 6이며 각 case의 최신 상태가 모두 pass다. `lay-energy-0561`의 안전하지 않은 사후 문구 정규화 제안은 독립 리뷰에서 법적 의무 약화 가능성이 확인되어 폐기했고, 기존 엄격 grounding을 유지한 attempt 16이 통과했다. 원장·`summary.json`의 연속 번호, 허용 필드, 집계 일치, 금지 필드 부재와 회귀 테스트 경로를 검증했다.
- 2026-09-11: 최종 whole-branch review에서 sealed snapshot이 V2 active index에 실제 결속되지 않고, answer judge가 응답 citation을 retrieval/citation 양쪽에 재사용하며 action만으로 leak 부재를 추정하고, 의미 지지 검증 없이 grounded partial detail이 실패 core를 덮을 수 있다는 P1 세 건을 확인했다. `final-01`은 진단 원장으로 보존하되 최종 완료 증거에서 제외하고, 수정 후 새 원장으로 전체 재검증한다.
- 2026-09-11: Task 6 전체 재검증의 `lay-energy-0111` attempt 1은 provider가 구체적인 소유 땅의 태양광 설치 가능성 질문을 `legal_search`로 분류해 `clarification_answer_leak`로 실패했다. 보호 질문을 노출하지 않는 특징 진단으로 토지 지목·용도지역 누락을 확인하고, 소유·지시된 특정 땅/부지의 설치 가능성에서만 두 축을 결정적으로 추출하도록 보강했다. 일반 토지 조건, 단일 값 제공, 복수 대안, 가족·친척 소유 경계를 포함한 라우팅 회귀 27개와 독립 리뷰를 통과했으며, 전체 재검증 attempt 2가 `ask_clarifying_question`, 0 evidence/citation, judge code 없음으로 pass했다.
- 2026-09-11: Task 6 `lay-energy-0201` attempts 3~4는 route와 동결 근거 8건이 정상이나 provider detail 생성·grounding이 제한시간 내 안정되지 않아 `insufficient_evidence`였고, attempt 5는 `routing_unavailable` blocked였다. 코드 변경 없이 외부 변동 시도를 분리했으며 attempt 6이 근거·citation 각 8건, `partial_answer_with_limits`, judge code 없음으로 pass했다.
- 2026-09-11: Task 6 `lay-energy-0251`은 attempt 7에서 0 evidence/citation, `ask_clarifying_question`, judge code 없음으로 pass했다.
- 2026-09-11: Task 6 `lay-energy-0346` attempt 8은 동결 근거 5건 뒤 core grounding fallback으로 실패했고 attempt 9는 `routing_unavailable` blocked였다. 코드 변경 없이 외부 변동을 분리했으며 attempt 10이 근거·citation 각 5건, `partial_answer_with_limits`, judge code 없음으로 pass했다.
- 2026-09-11: Task 6 `lay-energy-0521`은 attempt 11에서 근거·citation 각 9건, `partial_answer_with_limits`, judge code 없음으로 pass했다.
- 2026-09-11: 사용자는 E-006의 남은 운영을 batch defect workflow로 제한했다. 현재 고정 revision에서 D-10 10개를 코드 수정 없이 모두 진단하고, 그 패스에서 재현된 결정적 P0/P1만 근본 원인별로 중복 제거해 동결한다. 동결 뒤 결함별 RED는 유지하되 수정은 일괄 수행하고, 관련 회귀·독립 review·전체 verify는 batch 경계에서 각각 한 번만 수행한다. provider timeout·503·`routing_unavailable`은 case당 최초 시도 포함 최대 3회 뒤 safe `blocked`로 코드 완료와 분리한다. 기존 및 진행 중 재검증 원장은 역사적 diagnostic evidence로만 보존하고, review와 code identity가 고정된 뒤 final 원장 하나만 새로 시작한다. 동결 뒤 발견한 비차단 hardening은 E-007, NVIDIA 안정성·timeout은 별도 Operations 계획 후보로 넘긴다.
- 2026-09-11: Task 5 진단 `e006-v2-20260911-diagnostic-batch-01`은 동일 HEAD `bb9f3fdaa611a2a05615af0be21c3130e2cb3aa6`와 implementation diff hash `0a955ed278b32f23abad0d9b042c5126a09f1655`에서 D-10 10개를 모두 실행했다. 총 14 attempts는 pass 6, failure 4, 외부 blocked 4였고 case당 3회 상한 위반은 없다. `routing_unavailable`/`answer_unavailable`과 stochastic action mismatch는 provider 변동으로 분리했다. `response_is_grounded`가 substantive summary와 citation 0건을 허용하는 합성 재현을 확인해 `E006-P1-001 citationless_summary_is_accepted_as_grounded` 한 건만 결정적 P1로 동결했다.
- 2026-09-12: 첫 final 원장에서 `lay-energy-0521`이 citation 0건의 substantive action으로 안전 judge에 거부됐다. 원장을 `e006-v2-20260912-invalid-citation-regression-01`로 무효 보존하고, 고정 diff `0a747c5f2fa3755dc776e7a9252bd37dc4f7c3b9`의 두 번째 전체 진단 `e006-v2-20260912-diagnostic-batch-02`를 코드 수정 없이 수행했다. 10개 case·17 attempts에서 latest pass 9, 외부 blocked 1이었고 상한 위반은 없었다.
- 2026-09-12: 검증 실패한 detail을 안전 fallback으로 바꾼 뒤 citation 없는 저장 core의 summary/action을 다시 적용하는 경로를 합성 RED로 재현해 `E006-P1-002 grounding_fallback_is_overwritten_by_uncited_verified_core`로 동결했다. substantive action에 citation이 없을 때만 core를 폐기하도록 최소 수정했고, fully/partially 양쪽과 citation-backed degraded 보존을 회귀로 고정했다. 독립 리뷰의 노출면 assertion 지적을 반영한 뒤 focused 14 tests와 Ruff, 전체 `scripts/verify.ps1`이 core 27, API 902(+2 skip), collector 97(+5 skip), web 107와 production build까지 통과했다.
- 2026-09-12: 최종 implementation identity는 HEAD `bb9f3fdaa611a2a05615af0be21c3130e2cb3aa6`, diff hash `8c9bf955b3ff6b54ee304ed8689317b84ef85bca`다. `e006-v2-20260912-final-batch-02`의 단일 ledger는 10개 case·19 attempts이며 pass 7, failure 3, blocked 9다. latest outcome은 pass 7, provider action 변동 blocked 1, provider grounding 변동 blocked 1, provider availability blocked 1이고 case별 시도는 모두 3회 이하다. 확률적 action/citation 결과는 judge가 안전 거부했으며 열린 결정적 P0/P1은 없다. `summary.json`의 집계·허용 필드·금지 키 부재·왕복 일치를 검증하고 임시 staging ledger를 삭제해 최종 원장 하나만 남겼다. E-006은 `코드 검증 통과 + provider 변동 blocked`로 종결하며 NVIDIA 안정성과 stochastic action 품질은 별도 운영·E-007 후보로 분리한다.

# 실험 D-10 end-to-end 실패-회귀 평가

## 상태

승인됨 — 2026-09-10 사용자는 V2 실행 계약·고정 예산과 아래 NVIDIA·Supabase egress 및 원격 V2 상태 변경의 scope-specific 범위를 승인했다.

## 목표와 범위

D-10의 고정 10문항을 calibration 평가셋으로 사용해 실제 RAG 경로의 routing, retrieval, answer, citation, guardrail을 검증한다. 고정 revision의 단일 진단 패스에서는 실패해도 다음 문항을 계속 진단하고, 발견한 결정적 P0/P1을 동결해 batch로 수정한다. 이는 1,000-case Gold 평가나 held-out 품질 주장이 아니다.

## 고정 입력과 신뢰 경계

- sealed D-10 Gold의 hash·`approved_gold` 상태, frozen D-10의 case 순서·질문 hash·기준일·corpus binding을 실행 전에 검증한다.
- 질문, 검색 원문, prompt, credential, 예외 원문은 public result·ledger·summary에 기록하지 않는다.
- 승인된 credential 또는 외부 서비스가 실제로 사용 불가능한 경우만 외부 gate다. 실행하지 못했음을 `blocked`와 안전 code로만 기록한다.
- retrieval을 실행한 뒤 근거가 0개이면 `failure`다. `blocked`와 0건은 안전한 외부-gate code가 있을 때만 허용한다.
- `clarification_required`, `realtime_required`, `external_document_required`처럼 정책상 검색을 시작하지 않는 route는 예외다. 기대 action과 일치하는 `ask_clarifying_question` 또는 `insufficient_evidence` answer 결과만 근거·citation 0건 `pass`를 허용한다.

## 승인된 외부 접근 계약

2026-09-10 사용자는 E-006 D-10 E2E 실행에 필요한 다음 범위 전체를 승인했다. 외부 서비스의
기존 계정 사용량 외에 별도 구매는 하지 않으며, credential 원문은 출력·ledger·summary·문서에
기록하지 않는다.

| Boundary | Destination or resource | Operation | Data/credential involved | Mutation/retention | Purpose | Status and date | Runtime gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Harness and local tools | `C:\Users\Family\plugins\agent-operating-harness\scripts\harness.mjs` | `node` CLI start/status/evidence/review/check/complete | E-006 목표·검증 상태만 사용 | `.codex/harness/task.json` 갱신 | 완료조건과 증거 강제 | Approved — 2026-09-10 | PATH alias는 없으므로 direct script를 사용; MCP reload 불필요 |
| Local configuration | repository `.env.local` | read | NVIDIA·Supabase·Vercel credential과 V2 timeout 설정 | 외부 보존 없음; 원문 로그 금지 | production-equivalent E2E 구성 | Approved — 2026-09-10 | sandbox/keyring 접근 시 platform runtime 승인이 별도로 나타날 수 있음 |
| NVIDIA egress | `https://integrate.api.nvidia.com/v1` | routing·embedding·V2 core·finalize provider call | `NVIDIA_API_KEY`, sealed 질문, 검색 근거, prompt/context | 공급자 요청 처리 범위; 별도 구매 승인 없음 | 실제 모델 기반 V2 답변 생성 | Approved — 2026-09-10 | network escalation prompt는 설계 승인과 별도로 통과해야 함 |
| Supabase corpus read | `aws-1-ap-northeast-2.pooler.supabase.com` active generation·corpus·vector index | read-only query/search | DB credential, query embedding, 기준일·snapshot identifier | corpus mutation 없음 | 근거 검색과 corpus binding 검증 | Approved — 2026-09-10 | network escalation prompt는 설계 승인과 별도로 통과해야 함 |
| Supabase V2 execution state | `question_executions`, `question_execution_events`, `question_execution_issues` | create·update·expire/cancel/delete current temporary execution | DB credential, execution id/capability, phase/event/issue metadata | E-006 임시 execution 상태만 변경·정리 | prepare→core→finalize 및 실패 cleanup | Approved — 2026-09-10 | corpus 원문·청크·embedding mutation은 금지 |
| Supabase clarification schema | pooler가 가리키는 개발·테스트 DB, migration `0017_clarification_cases.py` | Alembic `0016`→`0017` upgrade: `clarification_cases` table과 status/expiry index 생성 | DB schema credential; 이후 clarification 질문·facts·capability hash가 임시 저장됨 | schema DDL 및 private clarification state 보존; downgrade/drop은 실행하지 않음 | `clarification_required` V2 prepare의 필수 저장소 제공 | Approved and applied — 2026-09-10 | corpus table·데이터는 변경하지 않음; table·index·version `0017` read-only 검증 완료 |
| Local evaluation artifacts | `.data/experiments/d-gold-10/<run-id>/` | create/update | public-safe case id·status·error code·counts·judge codes | 로컬 ledger·summary 보존 | stop/resume 및 회귀 증거 | Approved — 2026-09-10 | 질문·근거·prompt·credential·raw response 기록 금지 |
| External diagnostics | Vercel logs for this application | read-only query | request/execution identifier와 인증정보 | 로그 변경·삭제 없음 | 외부 실패 원인 확인 | Approved — 2026-09-10 | 필요한 경우에만 사용; raw 민감 로그 재기록 금지 |
| Repository state | local `main` checkout | local edit·test·Graphify update·commit | source, tests, design/plan, generated graph | 로컬 커밋만 생성 | 결함 수정과 증거 보존 | Approved — 2026-09-10 | `git push`, PR, deploy는 out of scope; DB migration은 위 별도 행의 승인 필요 |
| Excluded operations | production corpus, remote Git, deployment, persistent Docker/local DB | no operation | 해당 없음 | corpus mutation·push·PR·deploy·상주 서비스 없음 | 범위 제한 | Not required — 2026-09-10 | 필요해지면 별도 설계 변경과 승인 필요 |

## 실행 구조

`D10AnswerCaseRunner`는 native D-10 loader가 만든 한 문항 입력을 실제 V2 HTTP application 경계에 전달한다. 실행 순서는 `POST /v2/question-executions` prepare, `POST /v2/question-executions/{execution_id}/core`, `POST /v2/question-executions/{execution_id}/finalize`이며 core·finalize의 SSE 결과를 판정 입력으로 사용한다. 중단·정리에는 기존 `DELETE /v2/question-executions/{execution_id}`만 사용한다. 현재 제품 계약에 없는 `GET /v2/question-executions/{execution_id}`를 E-006을 위해 새로 만들지 않는다. runner의 내부 입력에는 질문·기준일·corpus binding이 있지만, public output에는 `case_id`, `status`, `error_code`, `retrieved_evidence_count`, `citation_count`, `citation_reason`, `actual_action`, `judge_codes`만 둔다.

E-006은 V1 내부 함수 `_answer_question`을 호출하지 않고 V1 `RequestBudget`도 생성하지 않는다. 따라서 V1의 routing 8초, embedding 5초, retrieval 8초, answer 40초 예산은 이 평가에 적용하지 않는다. `POST /v2/question-executions`는 전체 prepare deadline `57초`를 적용하고, 그 안의 V2 router provider 호출은 재시도 없이 한 번만 최대 `55초` 실행한다. provider가 먼저 timeout되면 안전한 `routing_unavailable` 결정을 저장하고, prepare 전체가 57초를 넘으면 `504 v2_prepare_timeout`을 반환한다.

`D10AnswerJudge`는 sealed case의 `expected_action`과 public answer metadata를 비교한다. 답변 본문과 citation evidence는 runner 내부에서만 검사하고, 통과/실패 code만 외부로 내보낸다. judge는 모델에게 채점시키지 않으며 결정적 규칙만 사용한다.

`run_d10_failure_driven`의 단일 case 실행 경계와 safe ledger는 유지한다. 운영 orchestration은 진단 원장에서는 한 case의 `failure` 또는 `blocked` 뒤에도 다음 고정 case를 실행하고, provider timeout·503·`routing_unavailable`만 같은 case에 최초 시도 포함 최대 3회 허용한다. 결정적 P0/P1 목록을 동결한 뒤 각 결함의 RED를 개별 확인하고 전체를 batch로 수정한다.

## expected_action 판정 계약

| expected_action | 반드시 충족 | 반드시 금지 |
| --- | --- | --- |
| `answer` | 실질 답변, 검색된 근거, 인용 위치 | 근거 없는 법률 주장 |
| `partial_answer_with_limits` | 확인된 범위의 답변과 한계 명시, 근거 | 완전한 답변으로 과장 |
| `ask_clarifying_question` | 필요한 사용자 사실을 구체적으로 질문 | 추측성 실질 법률 답변 |
| `insufficient_evidence` | 근거 부족을 명시 | 법률 결론 또는 허위 인용 |

모든 실질 법률 주장은 retrieval evidence와 citation 위치로 추적 가능해야 한다. citation이 answer에 있으면 retrieval evidence 중 하나에 결속되어야 한다.

## 판정 코드

- `expected_action_mismatch`
- `answer_missing_retrieved_evidence`
- `citation_not_in_retrieval_evidence`
- `clarification_answer_leak`
- `clarification_question_missing`
- `insufficient_evidence_answer_leak`
- `partial_limit_missing`
- `answer_empty`
- `retrieval_unavailable`
- `routing_unavailable`

코드는 원문이나 provider 응답을 포함하지 않는다. 문법·논리 오류는 answer policy/grounding rule 위반으로 재현 가능한 코드와 regression test로 기록한다. 자연어 문체 자체의 주관적 평가는 자동 pass 기준에 넣지 않는다.

## 검증과 완료 조건

각 action별 정상·금지·경계 unit test, native loader의 contract mismatch test와 safe ledger 검증을 유지한다. 고정 revision의 전체 진단 패스에서 확인된 결정적 P0/P1만 동결해 수정하고, 관련 회귀·독립 review·전체 verify를 batch 끝에서 각각 한 번 수행한다. 그 뒤 implementation code를 변경하지 않은 채 final 원장 하나를 만든다. 10개 모두 pass이면 정상 봉인하며, case별 최대 3회가 모두 provider timeout·503·`routing_unavailable` 같은 외부 차단이면 safe `blocked` 증거와 함께 `코드 검증 통과 + 외부 의존성 blocked`로도 완료할 수 있다. 새로운 결정적 P0/P1만 final 원장을 폐기하고 새 진단 패스로 돌아가는 사유다.

## 결정 기록

- 2026-09-10: D-10은 이미 RAG 개발에 사용된 calibration 문항이므로, answer 평가 역시 D-10 native contract를 사용한다. 1,000-case Gold 계약으로 adapter하지 않는다.
- 2026-09-10: answer quality의 자동 판정은 expected action, grounding, citation binding, 금지된 action leak처럼 결정적인 경계에 한정한다. 법률적 정확성을 모델 자기평가나 문체 점수로 대체하지 않는다.
- 2026-09-10: 앞선 일반 승인 표현은 platform runtime reviewer가 NVIDIA·Supabase의 데이터 종류와 mutation 범위를 명시한 scope-specific 승인으로 인정하지 않았다. 외부 전송은 발생하지 않았고 해당 세 행을 `Pending`으로 둔다.
- 2026-09-10: E-006은 V2 prepare→core→finalize production 계약과 V2 phase 57초/provider 55초 예산을 사용한다. V1 `_answer_question`, `RequestBudget`, routing 8초 예산은 사용하지 않는다.
- 2026-09-10: 사용자의 `design-document-grounding 승인함` 응답은 platform runtime reviewer에서 스킬 사용 승인으로만 해석됐다. scope-specific 외부 전송 승인을 받기 전에는 E2E 명령을 재시도하지 않는다.
- 2026-09-10: 사용자는 “`.env.local`의 NVIDIA·Supabase 인증정보 사용, sealed D-10 질문·embedding·검색 근거·prompt의 NVIDIA 및 Supabase 전송, Supabase V2 execution 상태 생성·갱신·취소·삭제, corpus read-only 검색” 범위를 제시받고 `응승인`으로 승인했다. 운영 corpus 변경·배포·push는 제외한다.
- 2026-09-10: 사용자는 `POST /v2/question-executions`에 V1 예산을 언급하거나 적용하지 않고, V2 router를 재시도 없는 단일 55초 provider 호출로 제한하며 endpoint 전체에는 57초 hard deadline을 두는 계약을 승인했다. 이번 변경은 V2 answerer와 다른 phase를 변경하지 않는다.
- 2026-09-10: 첫 live case에서 특정 사업의 누락 결정사실은 `clarification_required`를 우선하도록 router 계약을 보강했다. V2 core는 비검색 route에 `route_guidance_fallback`을 사용해 clarification action을 보존하며, 의도적으로 검색하지 않는 clarification/insufficient-evidence 정답만 zero-evidence pass를 허용한다.
- 2026-09-10: 두 번째 live case는 `answer_unavailable`로 중단됐다. read-only schema 진단에서 원격 DB가 Alembic `0016`, `question_executions` 존재, `clarification_cases` 부재임을 확인했고, 재현 traceback은 `PostgresClarificationCaseRepository.create_or_get`의 `UndefinedTableError`였다. migration `0017` 적용은 기존 row-level 승인에 포함되지 않는 schema write이므로 별도 승인 전까지 `Pending`이다.
- 2026-09-10: 사용자가 migration `0017` 적용을 승인했고, `0016`→`0017` transactional upgrade 뒤 `clarification_cases` table, `clarification_cases_status_expires_at` index, Alembic version `0017`을 read-only로 검증했다. 운영 corpus는 변경하지 않았다.
- 2026-09-10: 사용자는 E-006 완료에 예상되는 NVIDIA 전송, Supabase corpus read-only, V2 execution·clarification case 상태 변경, 관련 로그 read-only, 로컬 ledger·테스트·Graphify·commit 권한 전체를 승인했다. 미지정 추가 DDL, corpus mutation, 배포, 구매, push/PR, force 작업은 이 승인에 포함하지 않는다.
- 2026-09-10: `lay-energy-0201`은 첫 case의 clarification prompt가 “결정 사실 하나라도 누락”으로 과도했고 V2 core action prompt도 같은 경계를 반복했다. 최종 개별 가능 여부는 clarification, 조건부 허가·신고·절차 설명은 legal search와 partial answer로 분리했다. 또한 summary가 존재해도 sections만 보던 D-10 judge의 `answer_empty` 오판을 구조적 summary-or-sections 판정으로 수정했고, NVIDIA router HTTP 503은 코드 재시도 없이 새 E-006 attempt로 처리했다. attempt 9가 근거·citation 각 5건, `partial_answer_with_limits`, judge code 없음으로 pass했다.
- 2026-09-10: 결정 사실 누락 우선순위는 prompt-only 분류로 구현하지 않는다. 동일 질문에서도 NVIDIA의 `missing_fields`가 변동했기 때문이다. 내·제·해당 설비 같은 명시적 적용 표지, 또는 기준값 없는 “소규모 설비”와 `결정축에 따라 달라지는가`가 함께 나타난 미해결 적용 비교에서만 용량·전압·사용 방식·공사 종류의 실제 값을 검사하는 좁은 deterministic 온톨로지 guardrail을 적용한다. provider 자유형 `missing_fields`만으로 route를 승격하지 않으며, 로컬에서 검증한 누락 사실이 있을 때만 `legal_search` 후보를 `clarification_required`로 바꾼다. 일반 허가·신고 taxonomy, 소규모 설비의 축별 기준, 일반 “설비는 용량에 따라 어떻게 달라지는가” 비교 질문은 검색 가능 상태를 유지한다. 관련 회귀 65개 뒤 `lay-energy-0251` attempt 17이 이 계약으로 `ask_clarifying_question` pass했다.
- 2026-09-10: `lay-energy-0346`은 코드 변경 없이 통과했다. 첫 시도의 `routing_unavailable`은 새 E-006 시도로 재실행했고, attempt 19가 근거·citation 각 5건과 `partial_answer_with_limits`로 pass했다.
- 2026-09-11: `lay-energy-0521`은 검색 실패가 아니라 생성 근거 압축과 core/detail 판정 조정 결함이었다. 검색 상위 10건에는 정답 조문 4건이 있었지만 “조당 한 leaf” 정책이 하나의 조에 나뉜 발급 대상·신청·제외 항을 분리해 생성 입력의 정답 중첩을 2건으로 낮췄다. 최대 5개 조와 60,000자 budget은 유지하고 선택된 조 안의 ranked leaf를 모두 보존하며 bare 조 header만 하위 항이 있을 때 제거한다. V2 core의 action 판정용 `decision_limitations`는 provider schema에만 두고 model dump·DB·SSE에서는 제외한다. prompt-only 수정은 강제력이 없다는 리뷰를 반영해, 비-clarification core grounding 실패는 같은 core를 다시 생성하지 않는다. 동일 frozen evidence로 만든 detail이 `partially_answerable`이고 citations·sections·checklist가 존재하며 기존 구조·grounding 검증을 모두 통과할 때만 authoritative final response로 보존한다. 다른 action·빈 구조·grounding 실패는 기존 안전 fallback을 유지하고 clarification의 structural claim repair도 바꾸지 않는다. 변경 후 선택 근거 9건·정답 중첩 4건으로 회복됐고 attempt 34가 citation 9건과 `partial_answer_with_limits`로 pass했다. production 판정에는 case ID·Gold qrel·REC keyword·미검증 cosine threshold를 넣지 않았다.
- 2026-09-11: E-006 완료 조건을 batch defect workflow로 제한했다. 고정 revision의 단일 D-10 진단 패스에서 재현된 결정적 P0/P1만 동결해 결함별 RED 후 일괄 수정하고, 관련 회귀·독립 review·전체 verify는 batch 경계에서 각각 한 번 수행한다. provider timeout·503·`routing_unavailable`은 case당 최초 시도 포함 최대 3회 뒤 safe `blocked`로 코드 완료와 분리하므로, 10개 모두 pass가 E-006 완료의 필수조건은 아니다. final 원장은 code/review 고정 뒤 하나만 만들며 새로운 결정적 P0/P1만 폐기·재진단 사유로 삼는다. 동결 뒤의 비차단 hardening과 NVIDIA 운영 안정성은 별도 후속 계획으로 분리한다.

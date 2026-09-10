# 실험 D-10 end-to-end 실패-회귀 평가

## 상태

승인됨 — 2026-09-10 사용자 대화에서 retrieval 전용 E-006을 answer·citation·guardrail까지 확장하고, 아래 V2 실행 계약·고정 예산·외부 접근 범위 전체를 승인했다.

## 목표와 범위

D-10의 고정 10문항을 calibration 평가셋으로 사용해 실제 RAG 경로의 routing, retrieval, answer, citation, guardrail을 한 문항씩 검증한다. 각 문항은 통과할 때만 다음 문항으로 진행한다. 이는 1,000-case Gold 평가나 held-out 품질 주장이 아니다.

## 고정 입력과 신뢰 경계

- sealed D-10 Gold의 hash·`approved_gold` 상태, frozen D-10의 case 순서·질문 hash·기준일·corpus binding을 실행 전에 검증한다.
- 질문, 검색 원문, prompt, credential, 예외 원문은 public result·ledger·summary에 기록하지 않는다.
- 승인된 credential 또는 외부 서비스가 실제로 사용 불가능한 경우만 외부 gate다. 실행하지 못했음을 `blocked`와 안전 code로만 기록한다.
- retrieval을 실행한 뒤 근거가 0개이면 `failure`다. `blocked`와 0건은 안전한 외부-gate code가 있을 때만 허용한다.

## 승인된 외부 접근 계약

2026-09-10 사용자는 E-006 D-10 E2E 실행에 필요한 다음 범위 전체를 승인했다.

- 로컬 `.env.local`에서 credential과 실행 설정을 읽는다. credential 원문은 출력·ledger·summary·문서에 기록하지 않는다.
- `https://integrate.api.nvidia.com/v1`에 sealed D-10 질문을 routing·embedding 입력으로 보내고, V2 core·finalize에 필요한 검색 근거와 prompt/context를 보낸다. `NVIDIA_API_KEY` 사용을 포함한다.
- `aws-1-ap-northeast-2.pooler.supabase.com`에 DB credential과 query embedding을 보내고 active generation·corpus·vector index를 읽는다.
- V2 E2E 실행상태를 위해 Supabase의 `question_executions`, `question_execution_events`, `question_execution_issues`를 생성·갱신하고, 해당 임시 실행을 만료·취소 처리할 수 있다. 법률 corpus 원문·청크·embedding의 생성·수정·삭제는 승인 범위가 아니다.
- `.data/experiments/d-gold-10/<run-id>/`에 public-safe ledger·summary를 기록한다.
- 원인 확인에 필요한 Vercel 로그는 read-only로 조회할 수 있다.
- 승인 범위에는 배포, `git push`, PR 생성·수정, 운영 corpus mutation, 상주형 Docker/로컬 DB 기동이 포함되지 않는다.

## 실행 구조

`D10AnswerCaseRunner`는 native D-10 loader가 만든 한 문항 입력을 실제 V2 HTTP application 경계에 전달한다. 실행 순서는 `POST /v2/question-executions` prepare, `POST /v2/question-executions/{execution_id}/core`, `POST /v2/question-executions/{execution_id}/finalize`이며 core·finalize의 SSE 결과를 판정 입력으로 사용한다. 중단·정리에는 기존 `DELETE /v2/question-executions/{execution_id}`만 사용한다. 현재 제품 계약에 없는 `GET /v2/question-executions/{execution_id}`를 E-006을 위해 새로 만들지 않는다. runner의 내부 입력에는 질문·기준일·corpus binding이 있지만, public output에는 `case_id`, `status`, `error_code`, `retrieved_evidence_count`, `citation_count`, `citation_reason`, `actual_action`, `judge_codes`만 둔다.

E-006은 V1 내부 함수 `_answer_question`을 호출하지 않고 V1 `RequestBudget`도 생성하지 않는다. 따라서 V1의 routing 8초, embedding 5초, retrieval 8초, answer 40초 예산은 이 평가에 적용하지 않는다. `POST /v2/question-executions`는 전체 prepare deadline `57초`를 적용하고, 그 안의 V2 router provider 호출은 재시도 없이 한 번만 최대 `55초` 실행한다. provider가 먼저 timeout되면 안전한 `routing_unavailable` 결정을 저장하고, prepare 전체가 57초를 넘으면 `504 v2_prepare_timeout`을 반환한다.

`D10AnswerJudge`는 sealed case의 `expected_action`과 public answer metadata를 비교한다. 답변 본문과 citation evidence는 runner 내부에서만 검사하고, 통과/실패 code만 외부로 내보낸다. judge는 모델에게 채점시키지 않으며 결정적 규칙만 사용한다.

`run_d10_failure_driven`은 한 번에 한 문항만 실행한다. `pass`면 다음 고정 case를 선택하고, `failure` 또는 `blocked`면 멈춘다. 실패의 코드 결함은 회귀 테스트를 먼저 추가한 뒤 최소 수정과 동일 문항 재실행으로 해결한다.

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

각 action별 정상·금지·경계 unit test, native loader의 contract mismatch test, orchestrator의 stop/resume test를 유지한다. 외부 조건이 준비된 경우 실제 D-10을 한 문항씩 실행한다. 10개 모두 pass인 경우에만 native D-10 전체 재검증 및 안전 summary를 만든다.

## 결정 기록

- 2026-09-10: D-10은 이미 RAG 개발에 사용된 calibration 문항이므로, answer 평가 역시 D-10 native contract를 사용한다. 1,000-case Gold 계약으로 adapter하지 않는다.
- 2026-09-10: answer quality의 자동 판정은 expected action, grounding, citation binding, 금지된 action leak처럼 결정적인 경계에 한정한다. 법률적 정확성을 모델 자기평가나 문체 점수로 대체하지 않는다.
- 2026-09-10: 사용자는 `.env.local`, NVIDIA 전송, Supabase corpus 읽기와 V2 실행상태 쓰기·정리, 로컬 안전 ledger, Vercel read-only 로그 조회를 포함한 E-006 외부 접근 범위 전체를 승인했다. corpus mutation·배포·push는 제외한다.
- 2026-09-10: E-006은 V2 prepare→core→finalize production 계약과 V2 phase 57초/provider 55초 예산을 사용한다. V1 `_answer_question`, `RequestBudget`, routing 8초 예산은 사용하지 않는다.

# 실험 D-10 end-to-end 실패-회귀 평가

## 상태

승인 전 초안 — 2026-09-10 사용자 대화에서 retrieval 전용 E-006을 answer·citation·guardrail까지 확장하는 방향을 승인했다. 이 문서는 구현 전 최종 검토 대상이다.

## 목표와 범위

D-10의 고정 10문항을 calibration 평가셋으로 사용해 실제 RAG 경로의 routing, retrieval, answer, citation, guardrail을 한 문항씩 검증한다. 각 문항은 통과할 때만 다음 문항으로 진행한다. 이는 1,000-case Gold 평가나 held-out 품질 주장이 아니다.

## 고정 입력과 신뢰 경계

- sealed D-10 Gold의 hash·`approved_gold` 상태, frozen D-10의 case 순서·질문 hash·기준일·corpus binding을 실행 전에 검증한다.
- 질문, 검색 원문, prompt, credential, 예외 원문은 public result·ledger·summary에 기록하지 않는다.
- DB, NVIDIA credential, provider, corpus mutation lock 부재는 외부 gate다. retrieval을 실행하지 못했음을 `blocked`와 안전 code로만 기록한다.
- retrieval을 실행한 뒤 근거가 0개이면 `failure`다. `blocked`와 0건은 안전한 외부-gate code가 있을 때만 허용한다.

## 실행 구조

`D10AnswerCaseRunner`는 native D-10 loader가 만든 한 문항 입력을 실제 application answer 경계에 전달한다. runner의 내부 입력에는 질문·기준일·corpus binding이 있지만, public output에는 `case_id`, `status`, `error_code`, `retrieved_evidence_count`, `citation_count`, `citation_reason`, `actual_action`, `judge_codes`만 둔다.

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

> 작업 ID: `B-016`
> 상태: `Todo`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `Security`
> 선행 조건: `B-015` 완료 후
> 다음 행동: 저장된 원 질문·누적 fact를 검색과 답변에 전달할 최소 데이터 경계 및 보존 방식을 설계하고 구현 계획을 작성한다.
> 참고 범위:
> - `apps/api/app/api/v2/executions.py` L81-L93 — 현재 요청 질문을 쓰는 검색 query
> - `apps/api/app/application/v2/grounding.py` L23-L81 — execution snapshot에 fact 값이 없는 현재 계약
> - `apps/api/app/adapters/openai_answerer.py` L275-L315 — answer prompt가 현재 요청 질문과 fact ID·상태를 받는 경계

# Clarification 원 질문·누적 사실 기반 답변 입력

## 배경과 목표

현재 continuation 요청의 `question`은 사용자가 방금 입력한 답변 문장이다. 검색 query와 답변 prompt가 이 문장을 질문으로 사용한다. 저장된 원 질문과 이전 턴에서 병합한 fact 값은 답변 생성에 명시적으로 전달되지 않으며, Web의 bounded conversation context는 생략될 수 있다.

후속 턴에서 원 질문과 검증된 누적 사실을 사용해 관련 법률 근거를 검색하고, 마지막 답변이 그 사실관계에 적용되도록 한다.

## 범위와 안전 계약

- case repository의 소유권·capability·만료 확인 후 저장된 `original_question`과 answered fact만 사용한다. 미답변·거부·무효 fact의 값을 추측하지 않는다.
- 검색 query, answer prompt, `prepare → core → finalize` snapshot 사이의 최소 데이터 전달 방식을 설계한다. 10분 execution 보존기간과 기존 case TTL을 늘리거나 별도 transcript 저장소를 추가하지 않는다.
- 민감한 사실을 공개 SSE, 로그, capability, citation 근거로 취급하지 않는다. 법률 주장은 검색된 출처와 인용으로 검증하고, 사용자 사실은 법률 근거와 구분한다.
- conversation context가 비거나 잘려도 같은 case의 원 질문과 누적 fact를 바탕으로 답할 수 있어야 한다. 기존 non-clarification 질문 경로는 유지한다.

## 완료 조건

- 최초 질문과 다른 짧은 후속 답변에서도 검색은 원 질문의 법률 주제를 유지하고, 생성 입력에는 저장된 answered fact가 반영된다.
- 여러 턴에 나눠 받은 사실, 일부 미답변인 조건부 답변, context 생략, 실패·만료·다른 소유자 경계를 테스트한다.
- fact 값의 비공개 경계와 인용 검증을 유지한 채 근거 있는 최종 답변이 생성된다.

## 후속 연결

`B-015`의 사실 병합 결과를 사용한다. 구현 후 `B-014`에서 실제 continuation 요청·응답을 교차 계층 회귀로 고정하고 `B-009`에서 브라우저 acceptance를 실행한다.

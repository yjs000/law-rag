# Clarification Workflow Context State Contract

**상태:** 승인됨 — 실행계획 작성
**관련 작업:** B-013, 후속 B-014, 최종 검증 B-009
**목적:** LlamaIndex Workflow run 안의 임시 상태와 여러 HTTP 턴에 걸친 clarification case의 저장 책임을 분명히 하고, V2 question execution phase와의 경계를 고정한다.

## 이해한 목표와 제약

- 사용자 추가 사실과 진행 중 case는 후속 HTTP 턴에서도 이어져야 한다.
- 한 LlamaIndex Workflow run의 각 step은 같은 요청 상태를 안전하게 공유해야 한다.
- 사용자 사실이나 전체 case를 Workflow 이벤트나 로그로 노출하지 않는다.
- 기존의 bounded conversation context와 question execution 보존기간을 유지하고 별도 이력 저장소를 추가하지 않는다.
- `prepare → core → finalize`는 question execution의 단계다. clarification Workflow는 `prepare` 안에서 실행되며, 이를 위해 Context를 phase 사이에 넘기거나 HTTP 요청 사이에 재사용하지 않는다.
- 저장소의 기존 case 이력을 사용할 수 있다면 별도 transcript나 중복 저장을 도입하지 않는다.

## 결정 제안

매 `run_turn()` 호출마다 새 LlamaIndex `Context`를 만들고 해당 run의 `request`, `owner`, 조회된 `ClarificationCaseRecord`, `judgment`를 Context store에 둔다. 모든 Workflow step은 전달받은 같은 Context에서 이 상태를 읽고 갱신한다. Workflow 이벤트는 현재의 비공개 case/fact payload 경계를 지키고 `request_id`만 전달한다.

Context는 한 번의 Workflow run에만 유효하다. 완료·실패 후 보관하거나 직렬화하지 않는다. 다음 HTTP 요청에서는 요청에 포함된 case ID로 repository에서 소유권·만료를 확인하고 최신 case를 다시 읽는다.

## 저장된 case를 이력 정본으로 사용

현재 `clarification_cases` 테이블은 `original_question` 및 case 메타데이터와 함께 JSONB `facts`를 저장한다. 각 fact에는 식별자, 설명, blocking 여부, 상태, 사용자 답변 값, 선택적 source turn ID가 포함된다. 후속 Workflow는 case ID로 소유권과 만료를 확인하고 저장된 snapshot을 다시 읽는다. 제출된 사실은 version 조건이 있는 repository merge로 저장하며, 만료 처리 시 capability hash, 원 질문, facts를 비운다.

case facts와 별도로, Web은 현재 대화의 이전 질문·답변 중 최대 20턴을 `conversation_context`로 구성해 다음 요청에 보낸다. API는 질문과 context 합계 24,576자를 제한하고, answer prompt는 전달된 turn들을 사용한다. V2 prepare는 이 request를 clarification capability 없이 question execution private payload에 저장하며 execution 만료는 현재 10분이다. 이는 기존 단기 실행 snapshot이다.

따라서 B-013은 사용자 사실 이력을 위한 테이블이나 별도 transcript 저장을 추가하지 않고 기존 수명도 늘리지 않는다. 구조화 extractor는 현재 turn의 structured input 또는 의도만 해석하지만, answer prompt는 기존 `conversation_context`를 받는다. `ClarificationGrounding`의 execution snapshot은 fact ID·blocking·status만 보존하고 `RequiredFact.value`는 복사하지 않는다. 이 작업은 extractor 의미, client history 정책, answer prompt, 실행 보존기간을 바꾸지 않는다. 과거 원문을 더 오래 보관해야 한다는 요구가 생기면 개인정보·보존기간·사용 목적을 정한 별도 설계가 필요하다.

## Question execution과의 데이터 흐름

V2 `POST /v2/question-executions`의 prepare handler가 clarification Workflow를 실행한다. Workflow가 반환한 구조화 outcome은 grounding 입력으로 사용된다. question execution의 비공개 payload에는 bounded request context, grounding용 fact ID·blocking·status, finalize 후 전이할 case ID·version·다음 상태가 담긴다. `ClarificationGrounding`은 사용자 fact value를 포함하지 않는다. `core`와 `finalize`는 bounded request context와 고정된 execution snapshot으로 답변 생성·검증·case 상태 전이를 수행한다. Workflow `Context` 객체 자체는 이 경계를 넘지 않는다.

이 구조는 workflow 단계의 요청 상태와 question execution phase의 재생 가능한 작업 snapshot을 분리한다. 실행 phase가 여러 개인 것은 `_turns` 공유 map을 요구하지 않으며, Context를 다음 phase로 넘기는 근거가 되지 않는다.

## 실패와 동시성

- 서로 다른 Workflow run은 각자 생성한 Context만 읽고 써야 한다. Workflow 인스턴스의 `_turns` mutable map을 공유 상태로 사용하지 않는다.
- interpreter 실패는 기존의 중립적인 안전 결과를 유지하고 원 예외나 사용자 사실을 응답·로그로 노출하지 않는다.
- 같은 case에 대한 stale write는 repository의 optimistic version 계약으로 거부한다. API는 B-014에서 이를 case 존재 여부나 capability를 노출하지 않는 안정된 conflict 응답으로 변환한다.
- 원 질문과 구조화 facts는 기존 만료·소유권 정책을 따른다. Context에는 별도 보존 정책을 만들지 않는다.

## 작업별 검증 소유권

- **B-013:** 같은 Workflow 인스턴스에서 서로 다른 요청·소유자의 run을 겹쳐 실행해 Context 격리를 검증한다. 성공과 interpreter 실패 뒤 다른 run으로 상태가 새지 않는지도 확인한다. 저장소의 기존 case/fact 필드를 사용하고 이벤트에 비공개 payload가 들어가지 않는지 확인한다.
- **B-014:** 같은 case의 stale continuation API 응답과 상태 미덮어쓰기, Web의 continuation case ID/capability 전달 및 terminal 상태 정리를 검증한다. B-013의 adapter 상태 격리 검사를 반복하지 않는다.
- **B-009:** 두 선행 작업의 증거를 대조하고 브라우저에서 최초 추가 질문부터 부분 답변, 남은 질문, 최종 답변까지 acceptance한다.

## 범위 밖

- 원문 대화 turn transcript의 저장·조회·보존기간 추가
- LlamaIndex Context의 HTTP 요청 간 재사용 또는 직렬화
- Workflow Context를 `core`/`finalize` phase로 전달
- continuation 모델이나 사용자에게 보이는 답변 정책 변경

## 결정 기록

| 날짜 | 결정 | 이유 |
| --- | --- | --- |
| 2026-09-23 | 승인됨: run별 Context를 Workflow 임시 상태로 사용하고 PostgreSQL clarification case를 cross-turn 정본으로 사용한다. 기존 bounded conversation context와 10분 execution snapshot 수명은 유지한다. | 사용자 facts와 case 구조가 이미 PostgreSQL에 저장되어 재사용 가능하고, 별도 transcript 저장이나 Context 직렬화는 이력 수명·개인정보 범위를 중복 확장한다. 사용자가 설계 설명을 확인하고 학습 흐름도와 실행계획 작성을 요청했다. |

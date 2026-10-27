# Context · case DB · execution snapshot 비교

확인: 2026-10-27 · 코드 기준: `14bc357` · 로컬 소스 기준. 운영 DB의 실제 설정·데이터는 조회하지 않았다.

[질문 처리 흐름도](law-rag-current-pipeline.html) · [다이어그램 색인](README.md)

## 프로젝트를 설명하는 한 문장

**Context로 이번 턴을 처리하고, case DB로 여러 턴의 사실을 이어가며,
execution snapshot으로 이번 답변의 입력·법령 근거를 고정한다.**

## 역할과 저장 위치 비교

| 비교 항목 | Context | clarification case DB | execution snapshot |
| --- | --- | --- | --- |
| 무엇인가 | LlamaIndex Workflow의 실행별 작업 공간 | 추가 질문 한 건의 진행 상태를 저장하는 프로젝트 데이터 | 한 번의 v2 질문 실행에 저장한 입력·검색 근거·정책 |
| 핵심 질문 | “이번 턴을 지금 어떻게 처리하고 있나?” | “이 사건에서 무엇을 물었고 어떤 사실을 받았나?” | “이번 답변은 어떤 입력과 근거로 만들어야 하나?” |
| 단위 | `run_turn()` 한 번 | 같은 `case_id`로 이어지는 여러 HTTP 턴 | `execution_id` 하나의 prepare/core/finalize |
| 소유 계층 | LlamaIndex adapter | 프로젝트 case repository | 프로젝트 execution service/repository |
| 실제 저장 위치 | 질문을 처리 중인 Python 프로세스 메모리, `ctx.store['turn_state']` | PostgreSQL 구성 시 `clarification_cases` 테이블. fact 목록은 `facts` JSONB | PostgreSQL 구성 시 `question_executions` 행의 `private_payload`, `frozen_citations` JSONB 등 |
| 저장 내용 | 현재 request·owner, 조회한 case record, 모델 judgment | 원 질문, 기준일, 사업 단계, fact ID·label·값·상태, case 상태·version·만료·소유권 | request, route·missing_fields, hits·generation_hits, corpus 시점, generation ID, frozen citations, clarification 정책·fact ID/상태 |
| 원 질문·fact 값 | 이번 턴에 읽은 case 사본으로 접근 가능 | 구조화된 누적 사실의 정본 | case의 fact 값은 구조화해 복사하지 않음. 다만 request의 현재 문장·conversation_context에는 사용자 사실이 포함될 수 있음 |
| 생성 시점 | `run_turn()` 시작마다 새 Context | 최초 clarification 판단 후 case 생성 | prepare가 신규 실행을 저장할 때. 같은 owner·멱등 key면 기존 execution 재사용 |
| 누가 읽나 | 같은 run의 load/interpret/merge/policy/format step | 후속 턴 Workflow와 case 상태 변경 처리 | core·finalize와 execution 재연결/결과 재생 처리 |
| 누가 쓰나 | 이번 run의 Workflow step | fact 병합, 취소, 대기·완료 전이, 만료 처리 | prepare의 초기 저장, 이후 phase 결과·상태 저장 |
| 수명 | 한 Workflow run의 임시 상태. HTTP 턴 사이에 저장·재사용하지 않음 | 현재 구성은 생성 시각 기준 1일 TTL | 현재 prepare는 생성 시각 기준 10분 TTL |
| 재시작·다른 인스턴스 | 같은 메모리를 그대로 이어 쓸 수 없음 | PostgreSQL에 저장했으면 다음 요청에서 다시 읽음 | PostgreSQL에 저장했으면 입력·근거·상태·기록한 결과를 다시 읽음 |
| 동시성 보호 | run별 Context로 요청 상태 분리 | `expected_version`으로 오래된 fact 병합·상태 덮어쓰기 거부 | prepare 멱등 key와 phase claim/version 등으로 중복 실행 보호 |
| 식별자 | run별 `request_id`; 대화 영속 ID가 아님 | `case_id` | `execution_id`; case ID와 다름 |
| LlamaIndex 기능인가 | 예. 생성·사용 방식을 프로젝트 adapter가 정함 | 아니오. 프로젝트 저장소 | 아니오. 프로젝트 실행 계약 |

`execution snapshot`은 별도 테이블 이름이 아니다. 저장된 execution에서 후속 phase가 사용할
입력·근거를 뜻한다. execution 행의 status·version·phase 결과는 계속 갱신된다.
도메인의 `ExecutionSnapshot(status, version)` 타입과도 구분한다. 이 타입은 상태 전이용 작은 객체이며
검색 hits·질문을 담은 DB snapshot 전체가 아니다.

## 질문 한 건이 진행되는 순서

```text
첫 질문 → case A 생성 → “설비용량을 알려주세요”
                       ↓ 사용자가 “100kW입니다” 제출
새 HTTP 턴 → 새 Context → case A 조회 → fact 추출·검증·병합
                       ↓ Workflow가 policy·case 결과 반환
prepare → execution B에 이번 입력·route·검색 근거·정책 저장
                       ↓ HTTP 요청이 나뉘어도 같은 execution B 사용
core → 저장된 근거로 핵심 답변 생성·검증
finalize → 상세/보정·검증 → 대기 또는 완료 상태 반영
                       ↓ 추가 사실이 필요하면
다음 HTTP 턴 → 또 새 Context → 같은 case A 조회 → 새 execution C
```

이는 상태의 관계를 보여주는 예다. **현재 구현이 위 예시의 원 질문 기반 최종 답변까지 모두
완성됐다는 뜻은 아니다.** 실제 route별 검색·생성 여부는 [흐름도 ①](law-rag-current-pipeline.html#question-flow)를 따른다.

## 설명할 때 알아두면 좋은 점

1. **Context는 LLM prompt/context window와 다르다.** 여기서 Context는 Python Workflow 상태 객체다.
   저장한 모든 값이 모델에 자동 전달되는 것은 아니다. 모델이 보는 내용은 judge·extractor·answerer가
   명시적으로 만드는 prompt에 달려 있다.
2. **새 Context가 대화 초기화를 뜻하지 않는다.** 기존 case ID로 원 질문·누적 fact를 DB에서 다시 읽는다.
   반대로 Context만 메모리에 유지해도 다른 서버 인스턴스로 이동한 요청까지 자동으로 이어지는 것은 아니다.
3. **매 턴 새 Context는 프로젝트의 선택이다.** LlamaIndex가 재사용을 금지해서가 아니다.
   현재 구조는 DB case를 정본으로 두어 중복 저장을 피하고 요청 간 상태를 분리한다. 대신 매 턴 DB 조회와
   다음 단계에 필요한 데이터의 명시적 전달이 필요하다. 동시성·실패 격리와 새 Workflow의 case 복원은
   기존 `test_clarification_workflow.py`에서 검증한다.
4. **case와 execution의 ID·상태를 섞으면 안 된다.** case의 `waiting_for_user`는 사용자의 다음 입력을
   기다린다는 뜻이다. execution의 `completed`는 이번 응답 실행이 끝났다는 뜻이다.
   따라서 추가 질문을 반환한 execution은 완료되어도 case는 대기 중일 수 있다.
5. **fact 저장과 답변 적용은 다른 문제다.** 현재 후속 extractor는 저장된 원 질문·미해결 fact를 사용한다.
   하지만 이후 검색은 현재 입력 문장을 사용하고, 답변 snapshot에는 구조화된 fact 값이 없다.
   policy가 `full`이어도 service route를 자동으로 `legal_search`로 바꾸지 않는다. 이 연결 문제는 기존
   B-016이며 B-014·B-009가 후속 회귀·acceptance를 담당한다.
6. **법령 근거와 사용자 사실은 다른 역할이다.** case fact는 개별 적용의 조건이고, 법률 주장의 근거는
   검색된 공식 법령과 인용이다. 사용자가 말한 사실이나 이전 답변을 법률 근거로 대신 쓰지 않는다.
7. **재연결과 모델 재실행은 같지 않다.** execution은 같은 phase의 중복 실행을 막고 기록한 결과를
   재생하는 데 사용한다. provider 완료 여부가 불명확한 경우에는 자동 재호출 대신 복구 필요 상태로
   끝날 수 있다. 프로세스 메모리에 있는 진행 중 task 자체가 DB에 저장되는 것은 아니다.
8. **세 저장소는 무제한 채팅 이력이 아니다.** case는 필요한 구조화 사실, execution은 짧은 실행 자료다.
   일반 대화 context·로그인 질문 이력·법령 vector index는 각각 별도 기능·저장소다.

## 저장·만료·접근 경계

- PostgreSQL 구성에서는 두 repository가 DB에 저장한다. 현재 bootstrap은 기본 repository가
  `PostgresLegalRepository`일 때 PostgreSQL 구현을 선택하고, 그렇지 않으면 memory 대체 구현을 쓴다.
  memory 구현은 프로세스 종료 뒤 유지되지 않는다. 표의 DB 주소는 환경 설정에 따라 달라지며 이 문서에
  credential이나 실제 접속 문자열을 기록하지 않는다.
- Context는 코드에서 영속 저장하지 않는다. `PickleSerializer`는 run 시작 시 신뢰된 로컬 객체를
  메모리에서 다루기 위한 설정이다. 이것을 DB 저장이나 외부 pickle 입력을 받는 API로 설명하면 안 된다.
- case 접근은 owner scope, 익명 capability hash, 만료 조건으로 제한하며 version으로 stale 쓰기를 막는다.
  execution 접근도 owner·capability를 확인한다. UUID를 아는 것만으로 접근을 허용하는 구조가 아니다.
- TTL은 유효성 기한이다. **1일/10분이 되는 순간 DB 행이 자동 삭제된다는 뜻은 아니다.**
  repository의 만료 정리 함수가 실행되어야 payload를 비운다. execution 서비스는 prepare/phase 경계에서
  execution 만료 처리를 호출한다. case 정리 함수도 존재하지만, 이 문서에서는 배포된 정리 주기를 확인하지 않았다.
- case 만료 정리는 원 질문·facts·capability hash를 비우고 expired로 표시한다. execution 만료 정리는
  private payload·frozen citations·verified response·capability hash를 비우며 행을 통째로 지우지는 않는다.
  별도 `question_execution_events`·`question_execution_issues`도 존재하므로 이것을 모든 관련 기록의
  일괄 삭제로 해석하지 않는다.

## 코드 위치

| 확인할 내용 | 코드 |
| --- | --- |
| Context 생성·turn_state·step·policy | [llamaindex_clarification_workflow.py](../../apps/api/app/adapters/llamaindex_clarification_workflow.py) |
| case DB 필드·version·만료 정리 | [postgres_clarification_case.py](../../apps/api/app/adapters/postgres_clarification_case.py) |
| execution 저장·phase·event·만료 정리 | [postgres_question_execution.py](../../apps/api/app/adapters/postgres_question_execution.py) |
| prepare payload·10분 TTL·core/finalize | [phase_service.py](../../apps/api/app/application/v2/phase_service.py) |
| fact ID·상태만 snapshot에 담는 경계 | [grounding.py](../../apps/api/app/application/v2/grounding.py) |
| PostgreSQL/memory 선택·case 1일 TTL | [bootstrap.py](../../apps/api/app/bootstrap.py) |
| execution 상태 전이용 작은 타입 | [question_execution.py](../../apps/api/app/domain/question_execution.py) |
| Context 격리·case 복원 테스트 | [test_clarification_workflow.py](../../apps/api/tests/test_clarification_workflow.py) |
| 새 Context를 채택한 승인 근거 | [2026-09-23 상태 계약 설계](../superpowers/specs/2026-09-23-clarification-context-state-contract-design.md) |
| 원 질문·누적 fact 입력 후속 작업 | [B-016](../exec-plans/todo/0087-clarification-case-grounded-answer-input.md) |

# Agent Workflows

아래 문서는 공식 문서 사이트의 **LlamaAgents → Agent Workflows** 탐색 항목을 기준으로 정리했습니다. 위에서 아래로 읽으면 기본 구조부터 동시성, 실행 제어, 운영·배포 순으로 이어집니다.

## 기초

- [소개](introduction.md): Workflow, step, event의 실행 모델과 기본 구성
- [분기와 반복](branches-and-loops.md): event 타입을 이용한 branching과 looping
- [동시 실행](concurrent-execution.md): fan-out/fan-in, worker 수, 동적 event 전달
- [비동기 Workflow 작성](async-workflows.md): async step과 비동기 작업 구성
- [이벤트 스트리밍](streaming.md): 실행 중 event와 결과를 스트리밍하는 방법

## 상태와 의존성

- [상태 관리](managing-state.md): `Context`와 Workflow 실행 간 상태 유지
- [사용자 정의 시작·종료 event](custom-start-stop-events.md): 시작 및 종료 입력·결과의 타입 지정
- [Resource 객체](resources.md): 실행 간 공유할 의존성 관리
- [unbound function으로 Workflow 만들기](unbound-functions.md): 함수로 정의한 step을 조합하는 방법

## 실행 제어와 운영

- [오류 처리](error-handling.md): 실패와 retry 처리
- [Human in the Loop](human-in-the-loop.md): 사람의 입력을 기다리는 Workflow
- [내구성 있는 Workflow 작성](durable-workflows.md): checkpoint와 재개
- [DBOS Durable Execution](dbos-durable-execution.md): DBOS 기반 내구성 실행
- [Workflow 그리기](drawing-a-workflow.md): Workflow 구조 시각화
- [Workflow 테스트](testing-workflows.md): 단계와 전체 Workflow 검증
- [관측 가능성](observability.md): 실행 진단과 계측
- [Workflow를 서버로 실행](workflow-server.md): Workflow를 서비스로 노출
- [Python Client](python-client.md): 서버 Workflow 호출

## 원문

[LlamaIndex Agent Workflows 문서](https://developers.llamaindex.ai/python/llamaagents/workflows/)

# Workflow를 서버로 실행하기

`workflows` library에는 Workflow를 HTTP API로 쉽게 노출할 수 있는 `WorkflowServer` class가 포함되어 있습니다. 이를 통해 HTTP를 지원하는 모든 client에서 Workflow를 유연하게 실행하고 관리할 수 있습니다.

또한 `WorkflowServer`에는 Workflow를 시각화하고 실행하고 디버깅할 수 있는 정적 디버깅 애플리케이션이 함께 배포됩니다. 이 애플리케이션은 실행 중인 서버의 root 경로 `/`에 자동으로 mount됩니다.

## 설치

workflow server는 핵심 `llama-index-workflows` library와 별개의 package입니다.

```bash
pip install llama-agents-server
```

## 프로그램에서 사용하기

server를 만들고 Workflow를 추가한 뒤 프로그램에서 실행할 수 있습니다. 더 큰 애플리케이션에 workflow server를 포함할 때 유용합니다.

먼저 Python file을 만듭니다(예: `my_server.py`).

```python
# my_server.py
import asyncio
from workflows import Workflow, step
from workflows.context import Context
from workflows.events import Event, StartEvent, StopEvent
from llama_agents.server import WorkflowServer


class StreamEvent(Event):
    sequence: int


# Define a simple workflow
class GreetingWorkflow(Workflow):
    @step
    async def greet(self, ctx: Context, ev: StartEvent) -> StopEvent:
        for i in range(3):
            ctx.write_event_to_stream(StreamEvent(sequence=i))
            await asyncio.sleep(0.3)

        name = ev.get("name", "World")
        return StopEvent(result=f"Hello, {name}!")

greet_wf = GreetingWorkflow()


# Create a server instance
server = WorkflowServer()

# Add the workflow to the server
server.add_workflow("greet", greet_wf)

# To run the server programmatically (e.g., from your own script)
# import asyncio
#
# async def main():
#     await server.serve(host="0.0.0.0", port=8080)
#
# if __name__ == "__main__":
#     asyncio.run(main())
```

## 명령줄 인터페이스(CLI)

library는 `WorkflowServer` instance를 포함한 file에서 server를 실행하는 편리한 CLI도 제공합니다.

위 예제의 `my_server.py` file을 사용하면 다음 명령으로 server를 시작할 수 있습니다.

```bash
python -m llama_agents.server my_server.py
```

기본적으로 server는 `0.0.0.0:8080`에서 시작합니다. `WORKFLOWS_PY_SERVER_HOST` 및 `WORKFLOWS_PY_SERVER_PORT` environment variable로 host와 port를 설정할 수 있습니다.

## Workflow Debugger UI

`WorkflowServer`에는 Workflow를 시각화하고 실행하고 디버깅할 수 있는 정적 디버깅 애플리케이션이 함께 배포됩니다. 이 애플리케이션은 실행 중인 server의 root 경로 `/`에 자동으로 mount됩니다.

![Workflow Debugger UI](https://developers.llamaindex.ai/python/llamaagents/workflows/deployment/assets/ui_sample.png)

Workflow Debugging UI의 주요 기능은 다음과 같습니다.

- **Workflow 시각화**: 정적으로 표시하거나 실행 중에 표시하는 방식으로 Workflow 구조를 시각화합니다. 필요하면 node를 다시 배치할 수 있습니다.
- **Schema 자동 감지**: start/stop event나 internal event의 schema를 사용자 지정하면, UI가 schema에 맞는 UI를 자동으로 감지해 표시합니다.
- **Human-in-the-loop**: Workflow 실행 중 Workflow에 임의의 event를 보낼 수 있습니다. 사람의 입력으로 실행을 계속하는 Workflow에 유용합니다. event log 위쪽의 `Send Event` button을 확인하세요.
- **Event log**: 스트리밍된 모든 event를 UI에 기록하므로 오른쪽 side panel에서 Workflow 실행을 실시간으로 확인할 수 있습니다.
- **여러 run**: 여러 run을 디버깅하고 비교합니다. Workflow를 실행할 때마다 왼쪽 side panel에 해당 run이 기록됩니다.
- **여러 Workflow**: `WorkflowServer`에 mount된 모든 Workflow를 실행할 수 있습니다.

### "Hidden" event 처리

Workflow에서 `ctx.wait_for_event()`를 사용하는 경우처럼, Workflow에 주석으로 표시된 event를 보내거나 받는 경우가 있습니다. 이런 경우에도 `server.add_workflow(..., additional_events=[...])` API로 event를 추가해 UI에 알릴 수 있습니다. 그러면 `Send Event` 같은 UI 요소에서 해당 event를 사용할 수 있습니다.

## API endpoint

`WorkflowServer`는 다음 REST endpoint를 제공합니다.

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | health check 응답(`{"status": "healthy"}`)을 반환합니다. |
| `GET` | `/workflows` | 등록된 모든 Workflow의 이름을 나열합니다. |
| `POST` | `/workflows/{name}/run` | 지정한 Workflow를 동기적으로 실행하고 최종 결과를 반환합니다. |
| `POST` | `/workflows/{name}/run-nowait` | 지정한 Workflow를 비동기적으로 시작하고 `handler_id`를 반환합니다. |
| `GET` | `/handlers/{handler_id}` | 비동기로 실행한 Workflow의 결과를 가져옵니다. 실행 중이면 `202 Accepted`, 실패하면 `500`, 완료되면 `200`을 반환합니다. |
| `GET` | `/events/{handler_id}` | 실행 중인 Workflow의 모든 event를 줄바꿈으로 구분된 JSON(`application/x-ndjson`, SSE를 사용하면 `text/event-stream`)으로 스트리밍합니다. |
| `POST` | `/events/{handler_id}` | Workflow 실행 중 event를 보냅니다(human-in-the-loop에 유용). |
| `GET` | `/handlers` | 모든 Workflow handler(실행 중 및 완료)를 가져옵니다. |
| `POST` | `/handlers/{handler_id}/cancel` | Workflow 실행을 중지하고 취소합니다. |

### Workflow 실행(`/run`)

Workflow가 완료될 때까지 기다리며 실행하려면 `/workflows/{name}/run`에 `POST` 요청을 보냅니다.

**요청 본문:**

```json
{
  "start_event": {},
  "context": {},
  "handler_id": "",
}
```

- `start_event`: StartEvent 또는 그 하위 class의 직렬화된 표현입니다. Workflow 입력으로 사용하는 것이 좋습니다.
- `context`: Workflow context의 직렬화된 표현입니다.
- `handler_id`: 이전에 완료된 run에서 이어서 실행할 Workflow handler 식별자입니다.

**성공 응답(`200 OK`):**

```json
{
  "result": "The workflow has been successfully run"
}
```

### Workflow 비동기 실행(`/run-nowait`)

완료될 때까지 기다리지 않고 Workflow를 시작하려면 `/run-nowait` endpoint를 사용합니다.

**요청 본문:**

```json
{
  "start_event": {},
  "context": {},
  "handler_id": ""
}
```

요청 본문은 `/run` endpoint와 동일한 인자를 사용합니다.

**성공 응답(`200 OK`):**

```json
{
  "handler_id": "someUniqueId123",
  "status": "started"
}
```

그런 다음 `handler_id`를 사용해 결과를 확인하거나 event를 스트리밍할 수 있습니다.

## event 스트리밍(`GET /events/{handler_id}`)

> _이 endpoint는 `/run-nowait`로 Workflow를 비동기적으로 시작한 경우에만 작동합니다._

event를 Server-Sent Events(SSE)나 여러 줄의 JSON payload로 스트리밍하려면, 앞서 비동기 Workflow run을 시작할 때 받은 handler ID와 함께 `/events/{handler_id}` endpoint로 요청을 보냅니다.

**Query parameter**

- `sse`(필수 아님, `"true"` 또는 `"false"`): `true`이면 event를 Server Sent Events(`text/event-stream`)로 스트리밍하고, 아니면 여러 줄의 JSON payload(`application/x-ndjson`)로 스트리밍합니다. 기본값은 `true`입니다.
- `acquire_timeout`(필수 아님, float으로 변환할 수 있는 문자열): event 순회를 위한 lock 획득 timeout입니다.
- `include_internal`(필수 아님, `"true"` 또는 `"false"`): `true`이면 internal Workflow event를 스트리밍합니다. 기본값은 `false`입니다.
- `include_qualified_name`(필수 아님, `"true"` 또는 `"false"`): 응답 본문에 event의 qualified name을 포함합니다. 기본값은 `true`입니다.

**요청 예시**

```bash
curl http://localhost:80/events/someUniqueId123?sse=false&acquire_timeout=1&include_internal=false&include_qualified_name=true
```

**성공 응답(`200 OK`)**

단일 event payload:

```json
{
  "value": {"result": 12},
  "qualified_name": "__main__.MathEvent",
  "type": "__main__.MathEvent",
  "types": ["workflows.events.Event", "__main__.MathEvent"],
}
```

**중요 고려사항**

- 각 Workflow run에서 event를 스트리밍할 수 있는 reader는 하나뿐입니다.
- event를 한 번 스트리밍하고 나면 복구할 수 없습니다(client 쪽에서 persistence logic을 구현한 경우는 제외).

> _이 두 가지를 개선하고 있으며, 이에 따라 server 동작이 변경될 수 있습니다._

## Workflow 실행 결과 가져오기(`/results/{handler_id}`)

> _이 endpoint는 `/run-nowait`로 Workflow를 비동기적으로 시작한 경우에만 작동합니다._

앞서 비동기로 시작한 Workflow run의 결과를 가져오려면 해당 run의 handler ID를 전달해 `/results/{handler_id}` endpoint를 사용합니다.

**요청 예시**

```bash
curl http://localhost:80/results/someUniqueId123
```

**성공 응답(`200 OK`)**

```json
{
  "handler_id": "someUniqueId123",
  "workflow_name": "math_workflow",
  "run_id": "uniqueRunId456",
  "error": null,
  "result": {
    "sum": 15,
    "subtraction": 9,
    "multiplication": 36,
    "division": 4,
  },
  "status": "completed",
  "started_at": "2024-10-21T14:32:15.123Z",
  "updated_at": "2024-10-21T14:45:30.456Z",
  "completed_at": "2024-10-21T14:45:30.456Z"
}
```

**수락 응답(`202 ACCEPTED`)**

Workflow가 아직 실행 중이고 결과를 내지 않은 경우 상태 코드 `202`를 반환합니다.

## event 보내기(`POST /events/{handler_id}`)

human-in-the-loop처럼 Workflow 실행에 외부 입력이 필요한 경우, event 데이터를 `events/{handler_id}` endpoint로 `POST` 요청을 보내면 됩니다. Workflow의 어느 step으로 보낼지 선택적으로 지정할 수도 있습니다.

**요청 본문**

```json
{
  "event": {"__is_pydantic": true, "value": {"feedback": "This is great!", "approved": true}, "qualified_name": "__main__.HumanFeedbackEvent"},
  "step": "process_human_feedback"
}
```

- `event`: Workflow Event의 직렬화된 표현입니다.
- `step`(선택 사항): event를 보낼 step의 이름입니다.

**성공 응답(`200 OK`)**

```json
{
  "status": "sent"
}
```

## Workflow run 취소하기(`/handlers/{handler_id}/cancel`)

task를 취소해 실행 중인 Workflow handler를 중지하고, 선택적으로 persistence store에서 연결된 handler를 제거하려면 `/handlers/{handler_id}/cancel`을 사용합니다.

**Query parameter**

- `purge`(필수 아님, `"true"` 또는 `"false"`): Workflow와 연결된 handler를 persistence store에서 제거할지 여부입니다. 기본값은 `false`입니다.

**요청 예시**

```bash
curl -X POST http://localhost:80/handlers/someUniqueId123/cancel?purge=true
```

**성공 응답(`200 OK`)**

```js
{
  "status": "deleted", // or canceled if purge is false
}
```

## 영속성

기본적으로 `WorkflowServer`는 메모리 내 store(`MemoryWorkflowStore`)를 사용하므로 process가 다시 시작되면 모든 handler state와 event가 사라집니다. 영속성을 유지하려면 database를 사용하는 `workflow_store`를 전달하세요.

### SQLite

단일 process 배포에 가장 간단한 방법은 handler state, event, 결과를 로컬 file에 저장하는 `SqliteWorkflowStore`입니다.

```python
from llama_agents.server import WorkflowServer, SqliteWorkflowStore

store = SqliteWorkflowStore(db_path="workflows.db")

server = WorkflowServer(workflow_store=store)
server.add_workflow("greet", greet_wf)
```

### DBOS(Postgres)

Postgres 기반 영속성, durable execution, 분산 worker 실행이 필요한 production 배포에는 `llama-agents-dbos` package의 `DBOSRuntime`을 사용하세요. 기본 runtime을 [DBOS](https://docs.dbos.dev/) 기반 runtime으로 대체해 process가 다시 시작되어도 transactional state 관리와 복구가 가능합니다.

```python
from dbos import DBOS
from llama_agents.dbos import DBOSRuntime
from llama_agents.server import WorkflowServer

# Configure DBOS. It uses SQLite by default, or set system_database_url for Postgres.
DBOS(config={"name": "my-app", "run_admin_server": False})

runtime = DBOSRuntime()

server = WorkflowServer(
    workflow_store=runtime.create_workflow_store(),
    runtime=runtime.build_server_runtime(),
)
server.add_workflow("greet", GreetingWorkflow())
```

DBOS는 기본적으로 SQLite를 사용하므로 별도 설정이 필요하지 않습니다. Postgres를 사용하려면 DBOS config에 `system_database_url`을 전달하세요. 여러 replica로 구성하려면 각 replica에 고유한 `executor_id`를 지정해야 합니다.

```python
DBOS(config={
    "name": "my-app",
    "system_database_url": "postgresql://user:pass@localhost:5432/mydb",
    "run_admin_server": False,
    "executor_id": "replica-1",  # unique per replica
})
```

Postgres를 사용하면 여러 server replica가 같은 database를 공유해 분산 실행 및 복구를 수행할 수 있습니다. 다중 replica demo 전체 예제는 `examples/dbos/` 디렉터리에서 확인하세요.

## Python Client

`WorkflowServer`와 프로그램에서 상호작용하는 방법은 [Python Client](python-client.md) 문서를 참고하세요.

Server의 JSON decoding은 Workflow에서 선언한 event와 `additional_events`를 사용합니다. `server.add_workflow(name, workflow, additional_events=[MyEvent])`로 API event를 추가하세요. `serializer=` 설정은 internal context와 checkpoint에만 적용됩니다.

출처: https://developers.llamaindex.ai/python/llamaagents/workflows/deployment/

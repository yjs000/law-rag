# Python Client

`WorkflowClient` class는 실행 중인 `WorkflowServer`와 상호작용하는 Python interface를 제공합니다. Workflow 목록 조회, 동기 또는 비동기 실행, event 스트리밍, human-in-the-loop Workflow를 위한 event 전송을 지원합니다.

## 설치

client는 핵심 `llama-index-workflows` library와 별도의 package입니다.

```bash
pip install llama-agents-client
```

## 설정

```python
from llama_agents.client import WorkflowClient

client = WorkflowClient(base_url="http://0.0.0.0:8080")
```

`base_url` 대신 사전 설정된 `httpx.AsyncClient`도 전달할 수 있습니다.

```python
import httpx

httpx_client = httpx.AsyncClient(base_url="http://0.0.0.0:8080", headers={"Authorization": "Bearer ..."})
client = WorkflowClient(httpx_client=httpx_client)
```

## 기본 사용법

```python
from llama_agents.client import WorkflowClient
from workflows.events import StartEvent

async def main():
    client = WorkflowClient(base_url="http://0.0.0.0:8080")

    # Check server health
    await client.is_healthy()

    # List available workflows
    workflows = await client.list_workflows()
    print(workflows)

    # Run a workflow synchronously (blocks until completion)
    result = await client.run_workflow("greet", start_event=StartEvent(name="John"))
    print(result.result)
```

## 비동기 run 및 event 스트리밍

오래 실행되는 Workflow에서는 Workflow를 비동기로 시작하고 event가 생성되는 대로 스트리밍합니다.

```python
handler = await client.run_workflow_nowait("greet", start_event=StartEvent(name="John"))
handler_id = handler.handler_id

async for event in client.get_workflow_events(handler_id):
    print("Received:", event.type, event.value)

result = await client.get_handler(handler_id)
print(f"Final result: {result.result}")
```

### Cursor 동작(`after_sequence`)

`get_workflow_events`는 event history의 어느 위치에서 스트림을 시작할지 제어하는 `after_sequence` parameter를 받습니다.

| Value | 동작 |
|---|---|
| `-1`(기본값) | 시작 시점부터 모든 event를 스트리밍합니다. listening을 시작하기 전에 생성된 event도 포함됩니다. |
| `"now"` | 기존 event를 모두 건너뛰고 요청이 도착한 뒤 생성된 event만 스트리밍합니다. |
| 정수 `N` | sequence number가 `N`보다 큰 event를 스트리밍합니다. |

이 기능은 다음과 같은 용도에 유용합니다.

- **전체 재생**(`-1`): run이 이미 진행 중이거나 완료되었더라도 모든 event를 확인하려는 경우입니다.
- **실시간 이어보기**(`"now"`): Workflow를 직접 시작했고 이후 새 event만 필요한 경우입니다. Workflow가 이미 완료되어 모든 event가 생성된 상태라면 server는 HTTP 204를 반환하고 스트림을 즉시 종료합니다.
- **checkpoint부터 재개**(정수): 이전에 연결이 끊겼고 마지막으로 확인한 event부터 이어서 재개하려는 경우입니다.

스트림 위치를 확인하려면 `get_workflow_events`를 사용하세요. 이 method는 `last_sequence` property가 있는 `EventStream` object를 반환합니다.

```python
stream = client.get_workflow_events(handler_id)
async for event in stream:
    print(event.type, "at sequence", stream.last_sequence)

# Save the position for later
saved_sequence = stream.last_sequence
```

저장한 위치에서 다시 시작할 수 있습니다.

```python
stream = client.get_workflow_events(handler_id, after_sequence=saved_sequence)
async for event in stream:
    print(event)
```

또는 기존 event를 건너뛰고 새 event만 받을 수도 있습니다.

```python
stream = client.get_workflow_events(handler_id, after_sequence="now")
async for event in stream:
    print(event)
```

연결이 끊기면 `get_workflow_events`는 마지막으로 받은 sequence에서 자동으로 다시 연결합니다(`max_reconnect_attempts` 기본값은 3입니다).

## Human-in-the-Loop

외부 입력이 필요한 Workflow에서는 event 스트리밍과 `send_event`를 함께 사용합니다.

```python
from workflows import Workflow, step
from workflows.context import Context
from workflows.events import (
    StartEvent,
    StopEvent,
    InputRequiredEvent,
    HumanResponseEvent,
)
from llama_agents.server import WorkflowServer

class RequestEvent(InputRequiredEvent):
    prompt: str

class ResponseEvent(HumanResponseEvent):
    response: str

class OutEvent(StopEvent):
    output: str

class HumanInTheLoopWorkflow(Workflow):
    @step
    async def prompt_human(self, ev: StartEvent, ctx: Context) -> RequestEvent:
        return RequestEvent(prompt="What is your name?")

    @step
    async def greet_human(self, ev: ResponseEvent) -> OutEvent:
        return OutEvent(output=f"Hello, {ev.response}")

server = WorkflowServer()
server.add_workflow("human", HumanInTheLoopWorkflow(timeout=1000))
await server.serve("0.0.0.0", "8080")
```

그런 다음 client에서 다음과 같이 사용합니다.

```python
from llama_agents.client import WorkflowClient

client = WorkflowClient(base_url="http://0.0.0.0:8080")
handler = await client.run_workflow_nowait("human")
handler_id = handler.handler_id

async for event in client.get_workflow_events(handler_id):
    # load_event() reconstructs the typed Event class by qualified name
    loaded = event.load_event()
    if isinstance(loaded, RequestEvent):
        print("Workflow is requiring human input:", loaded.prompt)
        name = input("Reply here: ")
        await client.send_event(
            handler_id=handler_id,
            event=ResponseEvent(response=name.capitalize().strip()),
        )

result = await client.get_handler(handler_id)
res = OutEvent.model_validate(result.result)
print("Received final message:", res.output)
```

`load_event()`는 event class를 qualified name으로 import할 수 있으면 자동으로 작동합니다. client가 resolve할 class를 제한하려면 `serializer=JsonSerializer(allowed_types=[RequestEvent, ResponseEvent])`를 전달하거나 같은 class를 `registry` list로 전달하세요. typed event가 필요하지 않으면 raw `event.type`과 `event.value` dict를 항상 사용할 수 있습니다.

출처: https://developers.llamaindex.ai/python/llamaagents/workflows/client/

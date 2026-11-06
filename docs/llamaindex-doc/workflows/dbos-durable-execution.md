# DBOS Durable Execution

[내구성 있는 Workflow](durable-workflows.md) 문서에서는 수동 context snapshot을 사용해 Workflow가 재시작과 오류 이후에도 살아남도록 하는 방법을 설명합니다. `llama-agents-dbos` 패키지는 [DBOS](https://www.dbos.dev/) 기반 runtime을 Workflow에 연결해 수동 작업을 없앱니다. 각 step 전환이 자동으로 영속화되므로, 중단된 Workflow가 snapshot 코드를 작성하지 않아도 마지막 진행 지점부터 재개됩니다.

## 설치

```bash
pip install llama-agents-dbos
```

## 빠른 시작 — 독립형 durable Workflow

DBOS를 사용하는 가장 간단한 방법은 SQLite를 사용하는 것입니다. 별도의 외부 의존성이 필요하지 않습니다. 평소처럼 Workflow를 정의하고 `DBOSRuntime`을 전달하면 state가 자동으로 영속화됩니다.

```python
import asyncio

from dbos import DBOS
from llama_agents.dbos import DBOSRuntime
from pydantic import Field
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent


# 1. Configure DBOS — SQLite by default
DBOS(config={"name": "counter-example", "run_admin_server": False})


# 2. Define events and workflow (nothing DBOS-specific here)
class Tick(Event):
    count: int = Field(description="Current count")


class CounterResult(StopEvent):
    final_count: int = Field(description="Final counter value")


class CounterWorkflow(Workflow):
    @step
    async def start(self, ctx: Context, ev: StartEvent) -> Tick:
        await ctx.store.set("count", 0)
        print("[Start] Initializing counter to 0")
        return Tick(count=0)

    @step
    async def increment(self, ctx: Context, ev: Tick) -> Tick | CounterResult:
        count = ev.count + 1
        await ctx.store.set("count", count)
        print(f"[Tick {count:2d}] count = {count}")

        if count >= 20:
            return CounterResult(final_count=count)

        await asyncio.sleep(0.5)
        return Tick(count=count)


# 3. Create runtime, attach to workflow, and launch
runtime = DBOSRuntime()
workflow = CounterWorkflow(runtime=runtime)


async def main() -> None:
    await runtime.launch()
    result = await workflow.run(run_id="counter-run-1")
    print(f"Result: final_count = {result.final_count}")


asyncio.run(main())
```

실행 도중 process를 종료하더라도(예: 8번째 tick에서 Ctrl+C), `workflow.run(run_id="counter-run-1")`를 다시 호출하면 처음부터 시작하지 않고 8번째 tick부터 이어서 진행합니다.

| `run` 호출 사이에 유지되는가 | ✅ |
| --- | --- |
| process 재시작 후에도 유지되는가 | ✅ |
| runtime 오류 이후에도 복구되는가 | ✅ |

## Durable Workflow 서버

`DBOSRuntime`은 `WorkflowServer`와 통합되어, 서버에서 제공하는 모든 Workflow에 기본으로 durable execution을 제공합니다. runtime은 persistence store와 서버 runtime을 모두 제공합니다.

```python
import asyncio

from dbos import DBOS
from llama_agents.dbos import DBOSRuntime
from llama_agents.server import WorkflowServer
from pydantic import Field
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent

DBOS(config={"name": "quickstart", "run_admin_server": False})


class Tick(Event):
    count: int = Field(description="Current count")


class CounterResult(StopEvent):
    final_count: int = Field(description="Final counter value")


class CounterWorkflow(Workflow):
    """Counts to 5, emitting stream events along the way."""

    @step
    async def start(self, ctx: Context, ev: StartEvent) -> Tick:
        return Tick(count=0)

    @step
    async def tick(self, ctx: Context, ev: Tick) -> Tick | CounterResult:
        count = ev.count + 1
        ctx.write_event_to_stream(Tick(count=count))
        print(f"  tick {count}")
        await asyncio.sleep(0.5)
        if count >= 5:
            return CounterResult(final_count=count)
        return Tick(count=count)


async def main() -> None:
    runtime = DBOSRuntime()

    server = WorkflowServer(
        workflow_store=runtime.create_workflow_store(),
        runtime=runtime.build_server_runtime(),
    )
    server.add_workflow("counter", CounterWorkflow(runtime=runtime))

    print("Serving on http://localhost:8000")
    print("Try: curl -X POST http://localhost:8000/workflows/counter/run")
    await server.start()
    try:
        await server.serve(host="0.0.0.0", port=8000)
    finally:
        await server.stop()


asyncio.run(main())
```

Workflow debugger UI(`http://localhost:8000/`)는 기본 runtime을 사용할 때와 똑같이 동작합니다. DBOS는 서버 layer에서 투명하게 처리됩니다.

## 유휴 상태 해제

외부 입력(human-in-the-loop, webhook 등)을 기다리는 장기 실행 Workflow는 메모리에서 오랜 시간 유휴 상태로 머물 수 있습니다. `idle_timeout` parameter를 사용하면 DBOS runtime이 유휴 Workflow를 메모리에서 해제하고 새 event가 도착했을 때 자동으로 다시 시작하도록 할 수 있습니다.

```python
import asyncio

from dbos import DBOS
from llama_agents.dbos import DBOSRuntime
from llama_agents.server import WorkflowServer
from pydantic import Field
from workflows import Context, Workflow, step
from workflows.events import (
    HumanResponseEvent,
    InputRequiredEvent,
    StartEvent,
    StopEvent,
)

DBOS(config={"name": "idle-release-demo", "run_admin_server": False})


class AskName(InputRequiredEvent):
    prompt: str = Field(default="What is your name?")


class UserInput(HumanResponseEvent):
    response: str = Field(default="")


class GreeterWorkflow(Workflow):
    @step
    async def ask(self, ctx: Context, ev: StartEvent) -> AskName:
        return AskName()

    @step
    async def greet(self, ctx: Context, ev: UserInput) -> StopEvent:
        return StopEvent(result={"greeting": f"Hello, {ev.response}!"})


async def main() -> None:
    runtime = DBOSRuntime()

    server = WorkflowServer(
        workflow_store=runtime.create_workflow_store(),
        # Release workflows after 30 seconds of inactivity
        runtime=runtime.build_server_runtime(idle_timeout=30.0),
    )
    server.add_workflow("greeter", GreeterWorkflow(runtime=runtime))

    await server.start()
    try:
        await server.serve(host="0.0.0.0", port=8000)
    finally:
        await server.stop()


asyncio.run(main())
```

greeter Workflow가 `AskName`을 내보낸 뒤 30초 동안 입력이 없으면 runtime은 이를 메모리에서 해제합니다. `UserInput` event가 전달되면(`POST /events/{handler_id}`) runtime은 database에서 Workflow를 투명하게 복원해 event를 전달합니다. 호출자는 Workflow가 해제되었다는 사실을 알 필요가 없습니다.

## 다중 replica 배포에 Postgres 사용

SQLite는 단일 process 설정에서 잘 동작합니다. 여러 서버 replica가 필요한 production 배포에서는 Postgres로 전환하세요. 각 replica는 고유한 `executor_id`를 가져야 합니다.

```python
from dbos import DBOS

DBOS(config={
    "name": "my-app",
    "system_database_url": "postgresql://user:pass@localhost:5432/mydb",
    "run_admin_server": False,
    "executor_id": "replica-1",  # unique per replica
})
```

다중 replica 전체 예제는 `examples/dbos/server_replicas.py`를 참조하세요. replica 간 조정에 관한 자세한 내용은 [DBOS architecture overview](https://docs.dbos.dev/architecture)를 참조하세요.

production 다중 replica 배포에서는 [DBOS Conductor](https://docs.dbos.dev/production/conductor)를 사용해 core runtime 위에 자동 확장과 모니터링 dashboard를 추가할 수 있습니다.

## 실행 모델

DBOS 실행 모델을 이해하면 재시작과 replica 간에도 올바르게 동작하는 Workflow를 작성할 수 있습니다.

### Workflow identity

Workflow의 이름은 durable identity입니다. journal entry, step 등록, admission queue가 모두 이름을 기준으로 저장되므로 DBOS가 해당 Workflow에 대해 기록한 내용은 모두 그 이름 아래에 정리됩니다. 기본값은 module을 포함한 class 이름(예: `my_app.CounterWorkflow`)입니다. 따라서 class를 이동하거나 이름을 바꾸면 identity도 조용히 바뀝니다. 오래 유지되는 Workflow라면 이름을 명시적으로 설정하고 영구적인 값으로 취급하세요.

```python
wf = CounterWorkflow(runtime=runtime, workflow_name="counter-v1")
```

worker는 자신이 등록한 이름에 해당하는 기록만 찾습니다. 이름을 바꾼 뒤에는 이전 이름으로 기록된 진행 중 run과 대기 중 run이 새 배포에서 보이지 않습니다. 이전 이름을 등록한 worker는 해당 작업이 끝날 때까지 실행 상태를 유지하세요.

server를 사용할 때 `add_workflow`에 전달하는 이름은 HTTP route 이름이며, Workflow의 durable 이름과 별개입니다.

```python
server.add_workflow("counter", CounterWorkflow(runtime=runtime, workflow_name="counter-v1"))
```

### Replica 소유권

각 replica는 `executor_id`로 식별되며 자신이 시작한 모든 Workflow를 **소유합니다**. Workflow와 그 모든 step은 같은 process에서 실행됩니다. 개별 step을 replica 사이에 분산하지 않습니다. 따라서 step은 in-memory cache, local file, process 수준 singleton 같은 로컬 state를 안전하게 사용할 수 있습니다. 대신 하나의 Workflow 작업을 여러 replica에 나누어 실행할 수는 없습니다.

### Journal 기록과 replay

step 완료와 stream event는 database에 journal로 기록됩니다. crash 또는 유휴 상태 해제 후 Workflow를 재개할 때 runtime은 journal을 replay해 Workflow의 `Context`와 `store`를 재구성한 다음 마지막으로 기록된 step부터 계속 실행합니다.

복구가 replay를 기반으로 하기 때문에 journal entry가 commit되기 전에 중단된 step은 **두 번 이상 실행될 수 있습니다**. 가능한 경우 step을 idempotent하게 설계하거나, [내구성 있는 Workflow](durable-workflows.md) 문서처럼 context store를 사용해 step 안의 진행 상황을 추적하세요.

### 확장 및 drain

replica ID와 replica 수는 안정적이어야 합니다. replica 수를 줄이며 replica를 제거하면, 그 replica가 소유한 Workflow는 해당 `executor_id`가 다시 나타날 때까지 중단됩니다. replica를 제거하기 전에 진행 중인 Workflow가 완료될 때까지 기다리고 새 작업을 해당 replica로 보내지 않는 방식으로 drain하세요.

[DBOS Conductor](https://docs.dbos.dev/production/conductor)는 heartbeat를 이용해 drain되었거나 timeout된 replica를 감지하고 진행 중인 Workflow를 정상 replica에 다시 할당하므로 이 과정을 자동으로 처리합니다.

### 코드 변경과 버전 관리

재개가 journal replay를 기반으로 하므로 과거 run이 진행 중인 동안 Workflow 코드를 변경하면 비결정적인 동작이 발생할 수 있습니다. 예를 들어 step이 이전에 시작한 run과 다른 event 집합을 받도록 바뀔 수 있습니다. 이를 방지하려면 다음 중 하나를 선택하세요.

- 코드 변경을 배포하기 전에 진행 중인 Workflow를 drain합니다.
- 업데이트된 Workflow를 새 이름(예: `workflow_name="counter-v2"`)으로 등록합니다. 그러면 이전 run은 기존 버전에서 계속되고 새 run은 업데이트된 버전을 사용합니다. 이는 의도적인 identity 변경입니다. 이름이 어떤 항목을 식별하는지는 [Workflow identity](#workflow-identity)를 참조하세요.

### Run 동시성 제한

`Workflow(num_concurrent_runs=N)`은 replica당 해당 Workflow의 활성 run을 `N`개로 제한합니다. 따라서 배포 용량은 대략 `N`에 replica 수를 곱한 값입니다. 제한을 넘는 run은 DBOS queue에서 대기하고, 실행 slot이 열리면 약 1초 이내에 시작합니다. queue는 replica 사이에서 공유됩니다. 대기 중인 run은 요청을 제출한 replica에 고정되지 않으며, 여유 slot이 있는 replica가 가져갈 수 있습니다. 값을 설정하지 않으면 queue를 거치지 않고 run이 바로 시작됩니다.

```python
wf = CounterWorkflow(runtime=runtime, num_concurrent_runs=4)
```

queue는 Workflow의 durable 이름을 기준으로 합니다([Workflow identity](#workflow-identity) 참조). 따라서 이름을 바꾸면 이전 이름으로 대기 중인 run은 보이지 않습니다. 제한 값을 바꾸거나 제거하는 것은 안전합니다. 대기 중인 run은 기존 queue에 남아 계속 처리됩니다. 새 제한은 이미 시작된 run을 계산하지 않으므로, 해당 run이 끝날 때까지 replica가 잠시 제한을 넘을 수 있습니다.

대기 중인 run은 시작되기 전에는 취소할 수 없습니다. 취소는 실행 중인 Workflow로 전달되는 message이기 때문입니다. 취소 요청은 저장되며, run이 queue에서 허가되는 즉시 스스로 중지합니다.

DBOS는 일반적으로 모든 queue를 자동으로 감시합니다. 애플리케이션이 대신 `DBOS.listen_queues`에 명시적인 목록을 전달한다면 Workflow를 등록한 뒤 `runtime.workflow_queues`를 확인해 목록에 추가하고 runtime을 실행하기 전에 설정해야 합니다.

### Event streaming 동작

서버 외부에서 process 내부의 `handler.stream_events()`를 사용하면 DBOS stream은 호출할 때마다 처음부터 replay됩니다. 따라서 새 event만 받는 것이 아니라 Workflow가 지금까지 내보낸 모든 event를 받습니다.

[Workflow server](https://developers.llamaindex.ai/python/llamaagents/workflows/deployment/)는 대신 cursor 기반 방식을 사용합니다. `GET /events/{handler_id}` endpoint가 위치를 추적하므로 각 consumer는 event를 한 번씩만 받습니다.

### Crash 복구

replica가 재시작되면 DBOS는 해당 `executor_id`에 속한 미완료 Workflow를 자동으로 감지해 다시 실행합니다. 수동 개입은 필요하지 않습니다. replica는 journal을 replay해 마지막 진행 지점부터 이어갑니다.

원문: https://developers.llamaindex.ai/python/llamaagents/workflows/dbos/

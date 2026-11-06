# 내구성 있는 Workflow 작성

Workflow는 기본적으로 일시적입니다. `run()`이 반환되면 state가 사라지고, 다음 `run()`은 새로 시작합니다. 하지만 Workflow는 흔히 임시 동시성 process를 작성하는 곳입니다. 100개의 문서로 fan-out하고, 각 chunk에 대해 LLM을 호출한 다음 결과를 모읍니다. process가 중간에 종료되었을 때 처음부터 다시 시작하고 싶지 않은 종류의 실행입니다.

이 문서에서는 실행을 checkpoint로 저장하고 재시작 후 이어서 진행하는 방법을 설명합니다.

## context snapshot 저장하기

실행은 event를 제어된 방식으로 처리해 나가므로, 각 step 경계에서 state가 명확히 정의됩니다. 이 state는 아직 처리 중인 event와 [state store](managing-state.md)로 구성됩니다. `Context.to_dict()`는 이를 직렬화하고, `Context.from_dict()`는 복원합니다. `run(ctx=...)`은 다른 process에서도 저장된 state부터 계속 실행합니다.

```python
w = MyWorkflow()
handler = w.run()
result = await handler

# Persist the snapshot
db.save("my-run", json.dumps(handler.ctx.to_dict()))

# ...new process...
w = MyWorkflow()
ctx = Context.from_dict(w, json.loads(db.load("my-run")))
result = await w.run(ctx=ctx)   # continues with the restored state
```

이 방법은 재시작 후에는 복구되지만, 실행 중 발생하는 crash에는 대응하지 못합니다. 마지막 `to_dict()` 시점의 state만 보존됩니다. crash에도 대응하려면 실행이 진행되는 동안 snapshot을 저장해야 합니다.

재개할 때 복원된 실행은 아직 대기 중인 event를 다시 dispatch하고 부분적으로 수집된 fan-in buffer를 복원합니다. 완료된 step은 출력이 이미 복원된 state에 있으므로 다시 실행되지 않습니다. state를 저장한 시점에 실행 중이던 step은 처음부터 다시 실행됩니다. 재개는 at-least-once 방식이므로 step의 side effect는 반복 실행해도 안전해야 합니다.

## checkpoint loop

활성화할 built-in checkpointer는 없습니다. Workflow stream은 step의 state가 바뀔 때마다 내부 event를 내보냅니다. step 하나가 끝난 것을 확인하면 snapshot을 저장하면 됩니다. `stream_events(expose_internal=True)`로 내부 event를 노출할 수 있으며, `StepStateChanged`의 `StepState.NOT_RUNNING`은 step이 끝났음을 나타냅니다.

```python
from workflows.events import StepStateChanged, StepState

handler = w.run()
async for ev in handler.stream_events(expose_internal=True):
    if isinstance(ev, StepStateChanged) and ev.step_state == StepState.NOT_RUNNING:
        db.save("my-run", json.dumps(handler.ctx.to_dict()))
result = await handler
```

crash 후 재개하려면 마지막 snapshot을 불러와 `run()`에 전달하세요.

```python
w = MyWorkflow()
ctx = Context.from_dict(w, json.loads(db.load("my-run")))
result = await w.run(ctx=ctx)
```

바쁜 실행에서는 모든 경계에서 기록할 필요가 없습니다. snapshot마다 직렬화와 쓰기가 발생하므로 Workflow에서 event가 자주 나오면 저장 간격을 조절하세요. 그러면 crash가 발생해도 해당 간격 안에서 다시 실행해야 하는 작업만 생깁니다.

snapshot은 저장하는 순간의 state입니다. 저장을 시작하게 한 event 이후 다른 worker가 더 진행했을 수도 있지만, snapshot은 일관된 상태이므로 재개할 수 있습니다.

## 재시작 후에도 복구되는 동시 fan-out

아래 Workflow는 작업을 fan-out하고, 항목을 동시에 처리한 다음 결과를 모읍니다. 실행 도중 종료되어도 완료된 항목을 다시 처리하지 않도록 checkpoint를 저장합니다.

```python
import json, os
from typing import Annotated
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StepState, StepStateChanged, StopEvent
from workflows.resource import Resource


class WorkItem(Event):
    item_id: int

class WorkDone(Event):
    item_id: int
    result: str


# Heavy inputs come from a Resource (see below). They aren't serialized into
# the snapshot; they're re-created on resume.
def get_client() -> MyApiClient:
    return MyApiClient(...)


class EnrichBatch(Workflow):
    @step
    async def dispatch(self, ev: StartEvent) -> list[WorkItem]:
        return [WorkItem(item_id=item_id) for item_id in ev.item_ids]

    @step(num_workers=8)
    async def enrich(
        self,
        ev: WorkItem,
        client: Annotated[MyApiClient, Resource(get_client)],
    ) -> WorkDone:
        result = await client.enrich(ev.item_id)   # the expensive, repeatable work
        return WorkDone(item_id=ev.item_id, result=result)

    @step
    async def collect(self, events: list[WorkDone]) -> StopEvent:
        return StopEvent(result={ev.item_id: ev.result for ev in events})
```

checkpoint loop로 실행하고, process가 종료되면 마지막 snapshot부터 재개합니다.

```python
CKPT = "enrich-batch.json"

async def run_batch(item_ids):
    wf = EnrichBatch()
    if os.path.exists(CKPT):
        # Resume from the snapshot. The pending work and partial fan-in state
        # are already in the context, so don't send the StartEvent again.
        handler = wf.run(ctx=Context.from_dict(wf, json.load(open(CKPT))))
    else:
        handler = wf.run(item_ids=item_ids)

    async for ev in handler.stream_events(expose_internal=True):
        if isinstance(ev, StepStateChanged) and ev.step_state == StepState.NOT_RUNNING \
           and ev.name == "enrich":
            json.dump(handler.ctx.to_dict(), open(CKPT, "w"))
    return await handler
```

100개 항목 중 60개를 처리한 뒤 process가 종료되었다고 가정해 봅시다. 완료된 `enrich` 호출은 복원된 Workflow state에 포함되고, 아직 처리하지 않은 `WorkItem`은 대기 상태로 남습니다. 재개할 때 `dispatch`는 다시 실행되지 않고, 완료된 항목도 다시 enrich하지 않습니다. 전체 실행에 걸쳐 100개의 `WorkDone`이 모두 준비되면 list fan-in이 한 번 실행됩니다.

실행 중이던 작업은 반복됩니다. 어떤 시점이든 최대 `num_workers`개의 `enrich` 호출이 진행 중이며 아직 끝나지 않았을 수 있습니다. 이 호출들은 재개 시 처음부터 다시 실행됩니다. `num_workers=8`이면 최대 8개 항목이 다시 실행될 수 있습니다. 계산만 낭비될 뿐 결과는 틀리지 않습니다. 따라서 `enrich`는 반복 실행해도 안전해야 합니다.

## 저렴하고 올바른 snapshot 유지

snapshot 비용과 신뢰성은 snapshot에 포함하는 항목에 따라 달라집니다.

Workflow instance attribute는 snapshot에 포함되지 않습니다. Workflow instance가 살아 있는 동안 유지되는 일반 Python 객체를 담는 데는 유용하지만, durable state는 아닙니다. 재시작 후에도 남아야 하는 값은 event나 state store에 저장하세요.

무겁거나 직렬화할 수 없는 입력은 event나 state가 아니라 [Resource](resources.md)에 두세요. `Resource` factory는 한 번 해석되고 Workflow에 캐시되며 context에 직렬화되지 않습니다. 재개할 때 factory를 다시 호출해 재생성합니다. 따라서 API client, model handle, 큰 참조 데이터는 resource에 두고, event에는 작은 식별자를 담으세요. 이렇게 하면 snapshot 크기를 줄이고 아래 직렬화 규칙도 지킬 수 있습니다.

처리 중인 event와 state store의 모든 값은 직렬화할 수 있어야 합니다. snapshot은 JSON serializer를 사용하며 Pydantic model도 포함됩니다. 직렬화할 수 없는 값이 있으면 해당 field만 실패하는 것이 아니라 `to_dict()` 전체가 예외를 발생시킵니다. 따라서 raw bytes나 열린 connection을 event에 넣지 마세요.

## 내구성을 위한 runtime plugin

checkpoint loop는 직접 제어하는 durability 방식입니다. 언제 snapshot을 저장할지 정하고, 재개 코드는 몇 줄이면 됩니다. 이 작업을 직접 관리하고 싶지 않다면 persistence와 recovery를 맡는 runtime plugin을 사용할 수 있습니다.

기본 runtime은 Workflow를 process 내부에서 실행합니다. plugin runtime을 사용하면 Workflow 코드 변경 없이 다른 실행 모델로 바꿀 수 있습니다. 예를 들어 [DBOS runtime](dbos-durable-execution.md)은 step 전환을 database에 journal로 기록하므로, Workflow가 중단된 뒤 checkpoint loop 없이 재개할 수 있습니다. `WorkflowServer`에서도 같은 runtime plugin으로 Workflow를 실행할 수 있으므로, 서버에서 제공하는 Workflow도 동일한 persistence와 recovery 동작을 얻습니다.

원문: https://developers.llamaindex.ai/python/llamaagents/workflows/durable_workflows/

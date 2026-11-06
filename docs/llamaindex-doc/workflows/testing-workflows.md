# Workflow 테스트

Workflow는 event-driven 시스템으로 테스트하기 가장 쉽습니다. Workflow를 실행하고, 스트리밍된 event를 수집한 뒤, 최종 결과를 검증합니다. state가 중요하면 Context state도 확인합니다.

`workflows.testing` module에는 이를 위한 간단한 runner가 포함되어 있습니다.

```python
from workflows.testing import WorkflowTestRunner
```

## End-to-end 테스트

`WorkflowTestRunner`는 Workflow를 시작하고, event stream을 모두 소비하고, 최종 결과를 기다린 다음 모든 내용을 하나의 object로 반환합니다.

```python
import pytest

from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent
from workflows.testing import WorkflowTestRunner


class Progress(Event):
    message: str


class Done(Event):
    value: str


class ExampleWorkflow(Workflow):
    @step
    async def start(self, ctx: Context, ev: StartEvent) -> Done:
        ctx.write_event_to_stream(Progress(message="started"))
        return Done(value=ev.topic.upper())

    @step
    async def finish(self, ev: Done) -> StopEvent:
        return StopEvent(result=ev.value)


@pytest.mark.asyncio
async def test_workflow_streams_progress_and_returns_result() -> None:
    result = await WorkflowTestRunner(ExampleWorkflow()).run(
        start_event=StartEvent(topic="docs")
    )

    assert result.result == "DOCS"
    assert result.event_types[Progress] == 1
    assert any(
        isinstance(ev, Progress) and ev.message == "started"
        for ev in result.collected
    )
```

반환되는 object에는 다음 항목이 있습니다.

| Field | 설명 |
|---|---|
| `result` | Workflow handler를 await했을 때 반환되는 최종 값입니다. |
| `collected` | 제외되지 않은 모든 스트리밍 event입니다. |
| `event_types` | event class별로 수집된 event의 개수입니다. |
| `ctx` | state assertion이나 snapshot에 유용한 최종 `Context`입니다. |

## 내부 event

기본적으로 runner는 `StepStateChanged`를 포함한 internal event를 노출합니다. 실행 구조를 검증할 때 유용합니다.

```python
from workflows.events import StepStateChanged


@pytest.mark.asyncio
async def test_step_state_events_are_emitted() -> None:
    result = await WorkflowTestRunner(ExampleWorkflow()).run(
        start_event=StartEvent(topic="docs")
    )

    assert result.event_types[StepStateChanged] > 0
```

사용자 event만 확인하는 테스트라면 internal event를 끄세요.

```python
result = await WorkflowTestRunner(ExampleWorkflow()).run(
    start_event=StartEvent(topic="docs"),
    expose_internal=False,
)
```

또는 internal event를 계속 사용할 수 있게 두되, 수집 목록에서 불필요하게 많이 발생하는 event를 제외할 수 있습니다.

```python
result = await WorkflowTestRunner(ExampleWorkflow()).run(
    start_event=StartEvent(topic="docs"),
    exclude_events=[StepStateChanged]
)
```

## State 검증

Workflow가 `ctx.store`에 쓰는 경우 반환된 context를 사용하세요.

```python
from pydantic import BaseModel, Field


class CounterState(BaseModel):
    count: int = Field(default=0)


class CounterWorkflow(Workflow):
    @step
    async def count(self, ctx: Context[CounterState], ev: StartEvent) -> StopEvent:
        async with ctx.store.edit_state() as state:
            state.count += 1
        return StopEvent(result="done")


@pytest.mark.asyncio
async def test_workflow_updates_state() -> None:
    result = await WorkflowTestRunner(CounterWorkflow()).run()

    state = await result.ctx.store.get_state()
    assert state.count == 1
```

durable Workflow 코드에서는 실제 snapshot과 restore 이후의 동작을 검증하는 편이 좋습니다.

```python
workflow = CounterWorkflow()
first = await WorkflowTestRunner(workflow).run()

ctx_dict = first.ctx.to_dict()
restored_workflow = CounterWorkflow()
restored = Context.from_dict(restored_workflow, ctx_dict)

resumed = await WorkflowTestRunner(restored_workflow).run(ctx=restored)
```

이렇게 하면 unit test에서 놓치기 쉬운 문제, 즉 serialize할 수 없는 state, restore 후 import할 수 없는 event, 반복 실행에 안전하지 않은 side effect를 발견할 수 있습니다.

출처: https://developers.llamaindex.ai/python/llamaagents/workflows/testing/

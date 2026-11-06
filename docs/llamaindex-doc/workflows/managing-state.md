# 상태 관리

각 Workflow 실행에는 `Context`가 있고, 각 Context에는 state store가 있습니다. 한 번의 실행 중 여러 step이 공유해야 하는 값이나, 같은 Context를 다시 사용하거나 복원해 다음 실행으로 이어갈 값에 state store를 사용하세요.

State에는 무거운 client, index, file handle 또는 다른 runtime dependency를 두지 않습니다. 이런 객체는 [Resource](resources.md)에 넣으세요. State에는 Workflow를 snapshot하거나 재개할 때 직렬화해도 되는 데이터를 저장해야 합니다.

기본적으로 Workflow는 타입이 지정되지 않은 state store를 초기화합니다. `ctx.store`를 통해 읽고 쓸 수 있습니다.

```python
from workflows import Workflow, Context, step
from workflows.events import StartEvent, StopEvent


class MyWorkflow(Workflow):

    @step
    async def my_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        current_count = await ctx.store.get("count", default=0)
        current_count += 1
        await ctx.store.set("count", current_count)
        return StopEvent(result=current_count)
```

## State 잠그기

여러 step이 동시에 state를 수정할 수 있습니다. 이런 경우 `edit_state()`로 state를 잠가 update를 atomic하게 처리하세요.

```python
@step
async def my_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
    async with ctx.store.edit_state() as state:
        current_count = state.get("count", 0)
        state["count"] = current_count + 1
        result = state["count"]
    return StopEvent(result=result)
```

이 block이 실행되는 동안 다른 step은 state를 수정할 수 없습니다. Block은 짧게 유지하세요. 읽고 수정하고 쓰는 작업만 block 안에서 수행하고, 느린 LLM이나 network 호출은 바깥에 두세요.

## 타입이 있는 State 추가하기

Workflow state의 형태가 정해져 있는 경우가 많습니다. 이를 위해 Pydantic model을 사용하세요. 다음과 같은 장점이 있습니다.

- State에 대한 type hint를 사용할 수 있습니다.
- State가 자동으로 validation됩니다.
- [validator](https://docs.pydantic.dev/latest/concepts/validators/)와 [serializer](https://docs.pydantic.dev/latest/concepts/serialization/#custom-serializers)를 사용해 state의 직렬화·역직렬화를 선택적으로 완전히 제어할 수 있습니다.

> **참고:** 모든 field에 default가 지정된 Pydantic model을 사용하세요. 그래야 `Context`가 state를 자동으로 초기화할 수 있습니다.

다음은 Workflows와 Pydantic을 함께 사용해 이런 기능을 활용하는 간단한 예제입니다.

```python
from pydantic import BaseModel, Field


class CounterState(BaseModel):
    count: int = Field(default=0)
```

그런 다음 Workflow state의 타입을 state model로 지정합니다.

```python
from workflows import Workflow, Context, step
from workflows.events import (
    StartEvent,
    StopEvent,
)


class MyWorkflow(Workflow):
    @step
    async def start(
        self,
        ctx: Context[CounterState], ev: StartEvent
    ) -> StopEvent:
        # Allows for atomic state updates
        async with ctx.store.edit_state() as state:
            state.count += 1

        return StopEvent(result="Done!")
```

타입이 있는 state의 field를 하나씩 다룰 수도 있습니다.

```python
@step
async def start(self, ctx: Context[CounterState], ev: StartEvent) -> StopEvent:
    current = await ctx.store.get("count")
    await ctx.store.set("count", current + 1)
    state = await ctx.store.get_state()
    return StopEvent(result=state.count)
```

## 여러 실행에서 Context 유지하기

Workflow의 여러 실행에 걸쳐 state를 유지하려면 Context를 만들고 `.run()`에 같은 Context를 전달합니다.

```python
workflow = MyWorkflow()
ctx = Context(workflow)

handler = workflow.run(ctx=ctx)
result = await handler

# Optional: save the ctx somewhere and restore
# ctx_dict = ctx.to_dict()
# ctx = Context.from_dict(workflow, ctx_dict)

# continue with next run
handler = workflow.run(ctx=ctx)
result = await handler
```

Workflow가 아직 실행 중일 때 `run(ctx=ctx)`를 호출하면 새 `StartEvent`를 보내지 않고 해당 실행을 재개합니다. 이전 실행이 완료된 뒤 호출하면 저장된 state를 유지한 채 새 실행을 시작합니다.

## 직렬화 가능한 State

여기에 저장한 state는 Workflow를 snapshot해 [내구성 있게](durable-workflows.md) 만들 때 직렬화되므로, JSON serializer가 인코딩할 수 있는 값만 저장하세요. Client나 그 밖의 직렬화할 수 없는 객체는 [Resource](resources.md)에 넣으세요.

사용자 정의 값은 Pydantic에서 직렬화할 수 있도록 만들거나, `Context.to_dict()`와 `Context.from_dict()`를 호출할 때 custom serializer를 지정하세요.

Workflow에 `serializer=`를 설정해 내부 Context 및 checkpoint의 encoding을 선택할 수 있습니다. 또는 `WorkflowServer`에 설정해 server의 기본값을 지정할 수 있습니다. Workflow 설정이 우선 적용됩니다. Appserver는 Workflow를 host할 때 설정된 serializer를 유지합니다. 이 설정은 HTTP API JSON format을 바꾸지 않습니다.

---

원문: [Managing State](https://developers.llamaindex.ai/python/llamaagents/workflows/managing_state/)

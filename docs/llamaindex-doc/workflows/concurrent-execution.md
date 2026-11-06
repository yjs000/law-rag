# Workflow 동시 실행

Workflow는 여러 step을 동시에 실행할 수 있습니다. 여러 step이 서로 독립적이고 각자 오래 걸리는 작업을 기다린다면, 병렬로 실행하는 편이 더 빠릅니다.

일반적인 패턴은 fan-out과 fan-in입니다. 작업을 여러 조각으로 나누고 동시에 실행한 다음, 결과를 다시 모읍니다. 이를 step signature에 직접 표현합니다. 한 step에서 `list`를 반환하면 요소마다 event가 하나씩 발생해 fan-out됩니다. 다른 step이 `list` 매개변수를 받으면 전체 묶음을 한 번에 받아 fan-in합니다. `@step` decorator가 이런 타입을 읽습니다. Validator와 [시각화](drawing-a-workflow.md)는 별도 설정 없이 producer step과 event를 받는 step을 연결합니다. signature만으로 발생하지 않는 event를 보내야 한다면 `ctx.send_event`를 직접 사용할 수 있습니다. 이 페이지 끝의 [dynamic API](#dynamic-api)에서 설명합니다.

## 동시 실행 중인 Workflow 실행 수 제한

Workflow 전체의 동시 실행과 step의 동시 실행은 서로 별개입니다. `num_concurrent_runs`를 Workflow에 지정하면 동시에 활성화할 수 있는 `run()` 호출 수를 제한합니다.

```python
workflow = ParallelFlow(num_concurrent_runs=4)
```

값은 양의 정수 또는 `None`이어야 합니다. 기본값은 `None`이며, 이 경우 실행 수를 제한하지 않습니다. 이 제한은 프로세스 안의 동시 실행에 적용됩니다. 추가 호출은 실행 중인 Workflow가 끝날 때까지 기다립니다. [DBOS 기반 Workflow](dbos-durable-execution.md)에서도 지원되며, worker별로 적용됩니다.

각 실행 내부의 동시성에는 `@step(num_workers=...)`를 사용합니다. 이 값은 해당 step의 여러 인스턴스가 동시에 event를 처리할 수 있는 수를 제어하며, Workflow 실행 수는 제한하지 않습니다.

## 여러 실행에 걸친 활성 step 수 제한

예를 들어 외부 API를 동시에 호출하는 횟수를 제한하려면, 실행 전체에서 공유하는 `asyncio.Semaphore`를 사용합니다. step은 일반적인 async 함수이므로 별도의 라이브러리 지원이 필요하지 않습니다.

```python
import asyncio

API_SLOTS = asyncio.Semaphore(3)


class Fetcher(Workflow):
    @step
    async def fetch(self, ev: FetchRequest) -> FetchResult:
        async with API_SLOTS:
            data = await call_external_api(ev.url)
        return FetchResult(data=data)
```

모든 실행이 하나의 semaphore를 공유하므로 어떤 Workflow 실행에 속해 있든 `fetch` step은 최대 세 개까지 API를 호출합니다. 이 semaphore는 하나의 Python process 안에서만 공유됩니다. 여러 process로 배포하면 process마다 별도의 semaphore가 생깁니다.

## Fan-out: list 반환

step에서 `list`를 반환하면 각 요소가 독립적인 event로 발생합니다. 다음 예제에서는 다섯 개의 `Task`가 동시에 `work`로 전달됩니다.

```python
import asyncio
import random
from workflows import Workflow, step
from workflows.events import Event, StartEvent, StopEvent


class Task(Event):
    n: int


class Done(Event):
    n: int


class ParallelFlow(Workflow):
    @step
    async def fan_out(self, ev: StartEvent) -> list[Task]:
        return [Task(n=i) for i in range(5)]

    @step(num_workers=5)
    async def work(self, ev: Task) -> Done:
        await asyncio.sleep(random.randint(0, 5))
        return Done(n=ev.n)
```

전체 list가 하나의 batch입니다. `num_workers=5`를 지정하면 `work` 인스턴스가 최대 다섯 개까지 동시에 실행됩니다. 빈 list인 `[]`를 반환하면 아무 event도 발생하지 않지만 step은 완료되고 batch도 즉시 닫힙니다.

## Fan-in: list 받기

단일 event 대신 `list` 매개변수를 받으면 step이 전체 batch를 모은 뒤, 모든 항목을 한 번에 받아 **한 번 실행**됩니다.

```python
class ConcurrentFlow(Workflow):
    @step
    async def fan_out(self, ev: StartEvent) -> list[Task]:
        return [Task(n=i) for i in range(5)]

    @step(num_workers=5)
    async def work(self, ev: Task) -> Done:
        await asyncio.sleep(random.randint(0, 5))
        return Done(n=ev.n)

    @step
    async def join(self, events: list[Done]) -> StopEvent:
        return StopEvent(result=sorted(e.n for e in events))
```

`fan_out`은 `list[Task]`를 반환하고 `join`은 `list[Done]`을 받으므로, framework는 타입만 보고 batch를 파악해 모든 항목이 끝나면 `join`을 한 번 실행합니다.

list에 담긴 event는 각 worker가 완료된 순서대로 들어옵니다. `fan_out`이 event를 보낸 순서와는 다를 수 있습니다. 순서를 고정해야 한다면 여기의 `join`처럼 직접 정렬하세요.

worker는 `None`을 반환해 자기 branch를 끝낼 수 있습니다. Framework는 어떤 branch가 값을 반환하는지 추적하므로, `join`은 값이 반환된 branch만 포함해 한 번 실행됩니다.

```python
    @step(num_workers=5)
    async def work(self, ev: Task) -> Done | None:
        if ev.n % 2 == 0:
            return None  # drop this branch
        return Done(n=ev.n)
```

이 예제에서 짝수 번호 task는 `None`을 반환하므로 `join`에는 홀수에 해당하는 `Done` event만 전달됩니다.

## 먼저 도착한 결과로 계속 진행하기

기본적으로 list를 받는 join은 batch 전체가 끝날 때까지 기다립니다. 첫 번째 결과로 진행하려면 매개변수를 `Collect`로 감싸세요. `Take(n)`은 n번째 결과가 도착할 때, 먼저 도착한 n개 event를 전달합니다. 처음 몇 개 결과만 필요하거나 가장 먼저 완료되는 결과 하나만 필요할 때 사용합니다.

```python
from typing import Annotated
from workflows.collect import Collect, Take


class FastestWins(Workflow):
    @step
    async def fan_out(self, ev: StartEvent) -> list[Task]:
        return [Task(n=i) for i in range(5)]

    @step(num_workers=5)
    async def work(self, ev: Task) -> Done:
        await asyncio.sleep(random.randint(1, 5))
        return Done(n=ev.n)

    @step
    async def first(
        self, events: Annotated[list[Done], Collect(Take(1))]
    ) -> StopEvent:
        return StopEvent(result=events[0].n)
```

`Take(1)`은 어떤 task든 가장 먼저 끝나는 즉시 다음 단계로 진행합니다. 다른 task는 계속 실행됩니다. 취소되지는 않으며 join으로 전달되지 않을 뿐입니다. 일반 `list[Done]` 매개변수는 `Annotated[list[Done], Collect(All())]`과 같습니다. 인수 없는 `Collect()`를 사용하면 같은 기본 동작을 더 쉽게 검색할 수 있는 형태로 표시할 수 있습니다.

## 서로 다른 event 타입을 함께 모으기

하나의 batch에 event 타입을 여러 개 넣을 수 있습니다. `list[A | B]`는 두 타입을 평평한 하나의 batch로 모으며, step은 둘 중 하나의 타입을 받습니다.

```python
    @step
    async def join(
        self, events: list[StepACompleteEvent | StepBCompleteEvent]
    ) -> StopEvent:
        ...
```

list를 받는 대신 각 타입의 event가 하나씩 도착하기를 기다리려면 event마다 매개변수를 하나씩 지정하세요. 각 매개변수에 event가 도착하면 step이 한 번 실행됩니다. 매개변수는 타입으로 구분됩니다.

```python
from workflows import Workflow, step
from workflows.events import Event, StartEvent, StopEvent


class StepACompleteEvent(Event):
    result: str


class StepBCompleteEvent(Event):
    result: str


class StepCCompleteEvent(Event):
    result: str


class ConcurrentFlow(Workflow):
    @step
    async def step_a(self, ev: StartEvent) -> StepACompleteEvent:
        return StepACompleteEvent(result="Query 1")

    @step
    async def step_b(self, ev: StartEvent) -> StepBCompleteEvent:
        return StepBCompleteEvent(result="Query 2")

    @step
    async def step_c(self, ev: StartEvent) -> StepCCompleteEvent:
        return StepCCompleteEvent(result="Query 3")

    @step
    async def assemble(
        self,
        a: StepACompleteEvent,
        b: StepBCompleteEvent,
        c: StepCCompleteEvent,
    ) -> StopEvent:
        return StopEvent(result=[a.result, b.result, c.result])
```

`step_a`, `step_b`, `step_c`는 모두 같은 `StartEvent`에서 시작하므로 동시에 실행됩니다. `assemble`은 각 event를 받는 매개변수를 하나씩 가지므로 세 event가 모두 도착하면 한 번 실행됩니다.

## 중첩

fan-out을 중첩할 수 있습니다. 다른 fan-out 안에서 fan-out하면 중첩 batch가 만들어집니다. 내부 join은 바깥 요소마다 한 번 실행되고, 바깥 join은 모든 내부 결과를 모아 한 번 실행됩니다.

```python
class InnerTask(Event):
    outer: int
    inner: int


class InnerDone(Event):
    outer: int
    inner: int


class InnerSummary(Event):
    outer: int
    total: int


class Nested(Workflow):
    @step
    async def outer(self, ev: StartEvent) -> list[Task]:
        return [Task(n=o) for o in range(3)]

    @step
    async def inner(self, ev: Task) -> list[InnerTask]:
        return [InnerTask(outer=ev.n, inner=i) for i in range(2)]

    @step
    async def inner_work(self, ev: InnerTask) -> InnerDone:
        return InnerDone(outer=ev.outer, inner=ev.inner)

    @step
    async def per_inner(self, events: list[InnerDone]) -> InnerSummary:
        return InnerSummary(outer=events[0].outer, total=len(events))

    @step
    async def per_outer(self, events: list[InnerSummary]) -> StopEvent:
        return StopEvent(result=sorted((s.outer, s.total) for s in events))
```

각 join은 자신이 속한 수준에서 실행됩니다. `per_inner`는 바깥 `Task`마다 한 번씩, 총 세 번 실행되고 `per_outer`는 summary 세 개를 받아 한 번 실행됩니다.

## Dynamic API

step이 반환하기 전에 event를 보내야 한다면 `ctx.send_event`로 직접 보내고, `ctx.collect_events`로 모으세요. 조건에 따라 일부 event만 보내거나, 보낼 event 수를 미리 알 수 없거나, producer가 계속 실행되는 동안 downstream 작업을 시작하고 싶을 때 사용합니다.

여기에는 차이가 있습니다. `list` 반환은 한꺼번에 처리됩니다. step이 반환할 때 batch 전체가 전달되므로 그 전에 step에서 오류가 발생하면 아무 event도 전달되지 않습니다. `ctx.send_event`는 호출 즉시 event를 발생시킵니다. Producer step이 끝나기 전에 downstream step이 시작될 수 있지만, 이미 보낸 event는 나중에 step이 실패해도 취소되지 않습니다.

`ctx.send_event`는 event를 하나씩 발생시킵니다.

```python
import asyncio
import random
from workflows import Workflow, Context, step
from workflows.events import Event, StartEvent, StopEvent


class StepTwoEvent(Event):
    query: str


class ParallelFlow(Workflow):
    @step
    async def start(self, ctx: Context, ev: StartEvent) -> StepTwoEvent | None:
        ctx.send_event(StepTwoEvent(query="Query 1"))
        ctx.send_event(StepTwoEvent(query="Query 2"))
        ctx.send_event(StepTwoEvent(query="Query 3"))

    @step(num_workers=4)
    async def step_two(self, ev: StepTwoEvent) -> StopEvent:
        print("Running slow query ", ev.query)
        await asyncio.sleep(random.randint(0, 5))
        return StopEvent(result=ev.query)
```

`start`는 event를 반환하는 대신 `ctx.send_event`로 event를 발생시킵니다. 함수는 실제로 `None`을 반환하지만 반환 타입에 `StepTwoEvent`를 포함합니다. 따라서 validation과 diagram은 이 단계가 해당 event를 만들 수 있다는 점을 알 수 있습니다. 전송하는 event를 signature에서 빼더라도 runtime에서 event를 보낼 수는 있지만, static validation과 visualization은 연결 관계를 추론하지 못합니다.

직접 보낸 event 여러 개가 도착할 때까지 기다리려면 `ctx.collect_events`를 사용합니다.

```python
import asyncio
import random
from workflows import Workflow, Context, step
from workflows.events import Event, StartEvent, StopEvent


class StepTwoEvent(Event):
    query: str


class StepThreeEvent(Event):
    result: str


class ConcurrentFlow(Workflow):
    @step
    async def start(self, ctx: Context, ev: StartEvent) -> StepTwoEvent | None:
        ctx.send_event(StepTwoEvent(query="Query 1"))
        ctx.send_event(StepTwoEvent(query="Query 2"))
        ctx.send_event(StepTwoEvent(query="Query 3"))

    @step(num_workers=4)
    async def step_two(self, ctx: Context, ev: StepTwoEvent) -> StepThreeEvent:
        print("Running query ", ev.query)
        await asyncio.sleep(random.randint(1, 5))
        return StepThreeEvent(result=ev.query)

    @step
    async def step_three(
        self, ctx: Context, ev: StepThreeEvent
    ) -> StopEvent | None:
        # wait until we receive 3 events
        result = ctx.collect_events(ev, [StepThreeEvent] * 3)
        if result is None:
            return None

        # do something with all 3 results together
        print(result)
        return StopEvent(result="Done")
```

`ctx.collect_events`에는 현재 처리를 유발한 event와 기다릴 타입 목록을 전달합니다. `step_three`는 `StepThreeEvent`가 도착할 때마다 실행되지만, 세 개가 모두 도착하기 전에는 `collect_events`가 `None`을 반환합니다. 세 개가 도착하면 event가 도착한 순서대로 list를 반환합니다. 여기서 `3`으로 표시한 것처럼, 기다릴 event 수는 직접 추적해야 합니다.

같은 타입을 반복하는 것뿐 아니라 서로 다른 타입 조합도 기다릴 수 있습니다. 전달하는 타입 목록의 순서대로 반환되며, event가 실제로 도착한 순서와는 관계없습니다.

```python
    @step
    async def step_three(
        self,
        ctx: Context,
        ev: StepACompleteEvent | StepBCompleteEvent | StepCCompleteEvent,
    ) -> StopEvent | None:
        if (
            ctx.collect_events(
                ev,
                [StepCCompleteEvent, StepACompleteEvent, StepBCompleteEvent],
            )
            is None
        ):
            return None
        return StopEvent(result="Done")
```

## Fan-out을 내구성 있게 만들기

오래 걸리는 fan-out은 checkpointing에 적합합니다. 대기 중인 event와 일부 완료된 fan-in 상태를 직렬화하고 재시작 뒤 다시 이어갈 수 있습니다. checkpoint와 실제 예제는 [내구성 있는 Workflow 작성](durable-workflows.md)을 참고하세요.

---

원문: [Concurrent execution of workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/concurrent_execution/)

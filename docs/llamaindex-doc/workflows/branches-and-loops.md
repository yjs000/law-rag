# 분기와 반복

Workflows의 핵심 기능 중 하나는 graph 기반 접근 방식보다 더 단순하고 유연하게 branching과 looping logic을 지원한다는 점입니다.

## Workflow의 Loop

반복을 만들기 위해 무작위로 loop하는 `LoopingWorkflow`를 사용해 보겠습니다. `LoopEvent`라는 단일 event를 사용하지만, event 이름은 자유롭게 지정할 수 있습니다.

```
from workflows.events import Event


class LoopEvent(Event):
    num_loops: int
```

이제 `random`을 가져오고 `step_one` 함수를 수정해 반복할지 계속 진행할지 무작위로 결정합니다.

```
import random
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent


class LoopingWorkflow(Workflow):
    @step
    async def prepare_input(self, ev: StartEvent) -> LoopEvent:
        num_loops = random.randint(0, 10)
        return LoopEvent(num_loops=num_loops)


    @step
    async def loop_step(self, ev: LoopEvent) -> LoopEvent | StopEvent:
        if ev.num_loops <= 0:
            return StopEvent(result="Done looping!")


        return LoopEvent(num_loops=ev.num_loops-1)
```

아래는 이 흐름의 시각화입니다.

![간단한 loop](https://developers.llamaindex.ai/python/llamaagents/workflows/branches_and_loops/assets/loop.png)

적절한 event type과 반환 type을 정의하면 어떤 step에서든 다른 step으로 돌아가는 loop를 만들 수 있습니다.

## Workflow의 Branch

Branch는 loop와 밀접한 기능입니다. 앞서 본 것처럼 조건에 따라 서로 다른 event를 반환할 수 있습니다. 두 경로로 분기하는 Workflow를 살펴보겠습니다.

```
import random
from workflows import Workflow, step
from workflows.events import Event, StartEvent, StopEvent


class BranchA1Event(Event):
    payload: str




class BranchA2Event(Event):
    payload: str




class BranchB1Event(Event):
    payload: str




class BranchB2Event(Event):
    payload: str




class BranchWorkflow(Workflow):
    @step
    async def start(self, ev: StartEvent) -> BranchA1Event | BranchB1Event:
        if random.randint(0, 1) == 0:
            print("Go to branch A")
            return BranchA1Event(payload="Branch A")
        else:
            print("Go to branch B")
            return BranchB1Event(payload="Branch B")


    @step
    async def step_a1(self, ev: BranchA1Event) -> BranchA2Event:
        print(ev.payload)
        return BranchA2Event(payload=ev.payload)


    @step
    async def step_b1(self, ev: BranchB1Event) -> BranchB2Event:
        print(ev.payload)
        return BranchB2Event(payload=ev.payload)


    @step
    async def step_a2(self, ev: BranchA2Event) -> StopEvent:
        print(ev.payload)
        return StopEvent(result="Branch A complete.")


    @step
    async def step_b2(self, ev: BranchB2Event) -> StopEvent:
        print(ev.payload)
        return StopEvent(result="Branch B complete.")
```

가져오는 module은 앞 예제와 같지만, 새로운 event type 네 개를 만들었습니다. `start`는 무작위로 경로 A 또는 경로 B를 선택한 뒤, 각 경로의 여러 step을 실행합니다. 아래는 이를 시각화한 것입니다.

![간단한 branch](https://developers.llamaindex.ai/python/llamaagents/workflows/branches_and_loops/assets/branching.png)

필요에 따라 branching과 looping을 어떤 순서로든 조합할 수 있습니다. 이 튜토리얼 뒤에서는 `send_event`로 여러 branch를 병렬 실행하고 `collect_events`로 동기화하는 방법을 배웁니다.

## Event 하위 클래스 라우팅

기본적으로 event routing은 정확히 일치하는 type만 처리합니다. `ParentEvent`를 받도록 지정한 step은 `ChildEvent`가 그 하위 class여도 자동으로 받지 않습니다. Event model이 확장될 때 실수로 지나치게 넓은 event 매칭이 생기는 것을 방지합니다.

상위 event를 routing 계약으로 사용해야 한다면 step별로 명시해 사용하세요.

```
from workflows import Workflow, step
from workflows.events import Event, StartEvent, StopEvent




class ToolEvent(Event):
    tool_name: str




class SearchEvent(ToolEvent):
    query: str




class ToolWorkflow(Workflow):
    @step
    async def start(self, ev: StartEvent) -> SearchEvent:
        return SearchEvent(tool_name="search", query=ev.query)


    @step(accept_event_subclasses=True)
    async def handle_tool(self, ev: ToolEvent) -> StopEvent:
        return StopEvent(result=ev.tool_name)
```

이 기능은 필요한 경우에만 사용하세요. 대부분의 Workflow에서는 구체적인 event type을 쓰는 편이 branch 구조를 더 분명하게 보여 주고 validation 오류도 더 쉽게 이해할 수 있게 합니다.

---

원문: [Branches and loops](https://developers.llamaindex.ai/python/llamaagents/workflows/branches_and_loops/)

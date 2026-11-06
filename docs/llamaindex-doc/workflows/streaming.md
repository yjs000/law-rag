# 이벤트 스트리밍

Workflow가 완료되기까지 시간이 걸리는 경우가 많습니다. 느린 provider를 호출하거나, branch를 만들거나, batch를 여러 갈래로 fan-out하거나, 사람의 응답을 기다릴 수 있습니다. Streaming을 사용하면 실행이 진행되는 동안 상태를 보여 줄 수 있습니다.

Streaming에는 두 가지 사용 위치가 있습니다.

| 위치 | API |
|---|---|
| Step 내부 | `ctx.write_event_to_stream(...)` |
| Workflow 외부 | `handler.stream_events()` |

`workflow.run(...)`은 Workflow를 시작하고 `WorkflowHandler`를 반환합니다. Handler는 최종 결과를 기다릴 수 있는 awaitable이며, 해당 실행의 event stream도 관리합니다.

필요한 의존성을 가져옵니다.

```python
import asyncio
from llama_index.llms.openai import OpenAI

from workflows import (
    Workflow,
    Context,
    step,
)
from workflows.events import (
    StartEvent,
    StopEvent,
    Event,
)
```

간단한 3단계 Workflow와 진행 상황을 스트리밍하기 위한 event를 정의합니다.

```python
class FirstEvent(Event):
    first_output: str


class SecondEvent(Event):
    second_output: str
    response: str


class ProgressEvent(Event):
    msg: str
```

이제 event를 보내는 Workflow class를 정의합니다.

```python
class MyWorkflow(Workflow):
    @step
    async def step_one(self, ctx: Context, ev: StartEvent) -> FirstEvent:
        ctx.write_event_to_stream(ProgressEvent(msg="Step one is happening"))
        return FirstEvent(first_output="First step complete.")

    @step
    async def step_two(self, ctx: Context, ev: FirstEvent) -> SecondEvent:
        llm = OpenAI(model="gpt-4o-mini")
        generator = await llm.astream_complete(
            "Please give me the first 3 paragraphs of Moby Dick, a book in the public domain."
        )
        full_resp = ""
        async for response in generator:
            # Allow the workflow to stream this piece of response
            ctx.write_event_to_stream(ProgressEvent(msg=response.delta))
            full_resp += response.delta

        return SecondEvent(
            second_output="Second step complete, full response attached",
            response=full_resp,
        )

    @step
    async def step_three(self, ctx: Context, ev: SecondEvent) -> StopEvent:
        ctx.write_event_to_stream(ProgressEvent(msg="Step three is happening"))
        return StopEvent(result="Workflow complete.")
```

> **팁**
> 이 예제의 `OpenAI()`는 환경 변수에 `OPENAI_API_KEY`가 설정되어 있다고 가정합니다. `api_key` 매개변수로 전달할 수도 있습니다.

`step_one`과 `step_three`에서는 개별 event를 event stream에 씁니다. `step_two`에서는 `astream_complete`를 사용해 LLM 응답의 iterable generator를 만든 다음, LLM에서 데이터 조각을 받을 때마다 최종 응답을 반환하기 전에 event를 발생시킵니다.

이 결과를 받으려면 Workflow를 비동기 방식으로 실행하고 event를 수신해야 합니다.

```python
async def main():
    w = MyWorkflow(timeout=30, verbose=True)
    handler = w.run(first_input="Start the workflow.")

    async for ev in handler.stream_events():
        if isinstance(ev, ProgressEvent):
            print(ev.msg)

    final_result = await handler
    print("Final result", final_result)


if __name__ == "__main__":
    asyncio.run(main())
```

`run`은 Workflow를 background에서 예약합니다. `stream_events()`는 stream에 기록된 event를 하나씩 내보내고 `StopEvent`가 도착하면 멈춥니다. 그 뒤 handler를 await하면 최종 결과를 받을 수 있습니다.

Handler stream은 한 번만 소비할 수 있습니다. Workflow event를 여러 client에 전달해야 한다면 애플리케이션에서 stream을 한 번 소비한 뒤 직접 fan-out하세요.

## Workflow 종료 처리

Workflow가 정상적으로 끝나지 않으면 예외가 `await handler`에서 발생하기 전에 구체적인 `StopEvent` 하위 클래스가 stream에 게시됩니다.

- **`WorkflowTimedOutEvent`**: Workflow가 timeout을 초과했을 때 게시됩니다. `timeout`(초)과 실행 중이던 step 이름의 `active_steps` list를 포함합니다.
- **`WorkflowCancelledEvent`**: 사용자가 Workflow를 취소했을 때 게시됩니다.
- **`WorkflowFailedEvent`**: retry를 모두 소진한 뒤 step이 최종 실패했을 때 게시됩니다. `step_name`, `exception`, `attempts`, `elapsed_seconds`를 포함합니다.

```python
from workflows.events import (
    WorkflowTimedOutEvent,
    WorkflowCancelledEvent,
    WorkflowFailedEvent,
)

async for ev in handler.stream_events():
    if isinstance(ev, WorkflowTimedOutEvent):
        print(f"Workflow timed out after {ev.timeout}s")
    elif isinstance(ev, WorkflowCancelledEvent):
        print("Workflow was cancelled")
    elif isinstance(ev, WorkflowFailedEvent):
        print(f"Step '{ev.step_name}' failed after {ev.attempts} attempts: {ev.exception}")
```

---

원문: [Streaming events](https://developers.llamaindex.ai/python/llamaagents/workflows/streaming/)

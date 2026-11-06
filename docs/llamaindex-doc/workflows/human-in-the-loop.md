# Human in the Loop

Human-in-the-loop Workflow에서는 Workflow가 일시 중지하고, 필요한 입력이 무엇인지 호출자에게 알린 다음, 호출자가 응답을 보내면 계속 진행해야 합니다. Workflows는 일반 event를 사용해 이를 지원합니다.

가장 직접적인 패턴은 두 개의 step을 사용하는 것입니다. 하나는 `InputRequiredEvent`를 반환하고, 다른 하나는 `HumanResponseEvent`를 소비합니다. 호출자는 stream을 살펴보다가 같은 handler에 응답을 다시 보냅니다.

```python
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent, InputRequiredEvent, HumanResponseEvent


class NumberWorkflow(Workflow):
    @step
    async def ask(self, ev: StartEvent) -> InputRequiredEvent:
        return InputRequiredEvent(prefix="Enter a number: ")

    @step
    async def answer(self, ev: HumanResponseEvent) -> StopEvent:
        return StopEvent(result=ev.response)


workflow = NumberWorkflow()

handler = workflow.run()
async for event in handler.stream_events():
    if isinstance(event, InputRequiredEvent):
        # This could be input(), a websocket reply, a web form submission, etc.
        response = input(event.prefix)
        await handler.send_event(HumanResponseEvent(response=response))

final_result = await handler
```

여기서 Workflow는 `HumanResponseEvent`가 전달될 때까지 기다립니다. prompt나 response에 더 구조화된 내용이 필요하면 두 event를 모두 subclass할 수 있습니다.

## 사람의 응답 사이에서 일시 중지 및 재개

웹 앱에서는 prompt를 확인하는 process와 답변을 받는 request가 서로 다른 경우가 많습니다. prompt를 받은 뒤 context를 snapshot으로 저장하고, response가 도착하면 context를 복원하세요.

```python
import json
from workflows import Context

handler = workflow.run()
async for event in handler.stream_events():
    if isinstance(event, InputRequiredEvent):
        await db.save("run-123", json.dumps(handler.ctx.to_dict()))
        await handler.cancel_run()
        break

# Later, when the human response arrives:
response = form_data["response"]
ctx_dict = json.loads(await db.load("run-123"))
restored_ctx = Context.from_dict(workflow, ctx_dict)
handler = workflow.run(ctx=restored_ctx)

await handler.send_event(HumanResponseEvent(response=response))
async for event in handler.stream_events():
    continue

final_result = await handler
```

실행을 다른 request나 process로 넘기려는 경우 snapshot을 저장한 뒤 원래 handler를 취소하세요. 그러면 복원된 실행에 전달될 답변을 기다리면서 메모리에 남아 있는 실행이 생기는 일을 막을 수 있습니다.

## `wait_for_event` 사용

다른 방법으로는 `ctx.wait_for_event()`를 사용해 단일 step 안에서 입력을 기다릴 수 있습니다.

```python
@step
async def ask_user(self, ctx: Context, ev: StartEvent) -> StopEvent:
    response = await ctx.wait_for_event(
        HumanResponseEvent,
        waiter_event=InputRequiredEvent(prefix="Enter a number: "),
        waiter_id="get_number",
    )
    return StopEvent(result=response.response)
```

같은 step이 여러 번 기다릴 수 있다면 `waiter_id`를 사용하세요. 여러 waiter가 같은 event type을 소비하며 응답을 올바른 waiter로 보내야 한다면 `requirements`를 사용하세요.

```python
response = await ctx.wait_for_event(
    HumanResponseEvent,
    waiter_event=InputRequiredEvent(prefix="Approve draft? "),
    waiter_id="approve-draft",
    requirements={"request_id": ev.request_id},
)
```

`wait_for_event`는 step이 시작 event 또는 일치하는 대기 event를 받을 때마다 해당 호출 앞에 있는 모든 코드를 다시 실행합니다. step은 waiter에 도달할 때까지 최소 한 번 실행되며, waiter는 실행을 일시 중지하기 위해 내부 예외를 발생시킵니다. 따라서 `wait_for_event` 호출 전의 코드는 반복 실행해도 안전해야 합니다.

이 동작은 복잡하므로, 일반적으로 event 기반의 별도 step 패턴을 권장합니다.

자세한 내용은 [API reference](https://developers.llamaindex.ai/python/workflows-api-reference/context/#workflows.context.Context.wait_for_event)를 참조하세요.

원문: https://developers.llamaindex.ai/python/llamaagents/workflows/human_in_the_loop/

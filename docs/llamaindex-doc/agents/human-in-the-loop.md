# Human in the Loop

사람의 입력을 받는 도구도 정의할 수 있습니다. 도구 호출을 확인하거나 feedback을 받는 등 사람의 입력이 필요한 작업에 유용합니다.

[Workflows 튜토리얼](../workflows/README.md)에서 살펴보듯 AgentWorkflow 내부의 Workflows는 event를 내보내고 받는 step을 실행합니다. 아래 그림은 AgentWorkflow를 구성하는 step(파란색)과 step 사이에서 데이터를 전달하는 event(초록색)를 보여줍니다. 앞서 output stream을 다룰 때 보았던 event와 같습니다.

![Workflows 다이어그램](https://developers.llamaindex.ai/_astro/agentworkflow.DbdQWYoM_28jF5r.jpg?dpl=dpl_6m4kx998VjssYTMc17BxzNwMwcb9)

Human in the Loop을 구현하려면 다른 Workflow step이 받지 않는 event를 도구에서 내보내도록 합니다. 그런 다음 특정한 “reply” event를 받을 때까지 도구가 기다리게 합니다.

이 목적으로 기본 제공되는 `InputRequiredEvent`와 `HumanResponseEvent`를 사용할 수 있습니다. 다른 형태의 human input을 받으려면 필요한 방식에 맞춰 이 event를 subclass할 수 있습니다. 다음 event를 import합니다.

```python
from llama_index.core.workflow import (
    InputRequiredEvent,
    HumanResponseEvent,
)
```

다음으로 사람의 확인이 필요한 가상의 위험 작업을 수행하는 도구를 만듭니다.

- `wait_for_event`는 `HumanResponseEvent`를 기다리는 데 사용합니다.
- `waiter_event`는 응답을 기다리는 중임을 호출자에게 알리기 위해 event stream에 기록되는 event입니다.
- `waiter_id`는 이 대기 호출을 위한 고유 식별자입니다. 각 `waiter_id`마다 `waiter_event`를 한 번만 전송하도록 돕습니다.
- `requirements` 인자는 특정 `user_name`을 가진 `HumanResponseEvent`를 기다리도록 지정합니다.

```python
from llama_index.core.workflow import Context




async def dangerous_task(ctx: Context) -> str:
    """A dangerous task that requires human confirmation."""


    # emit a waiter event (InputRequiredEvent here)
    # and wait until we see a HumanResponseEvent
    question = "Are you sure you want to proceed? "
    response = await ctx.wait_for_event(
        HumanResponseEvent,
        waiter_id=question,
        waiter_event=InputRequiredEvent(
            prefix=question,
            user_name="Laurie",
        ),
        requirements={"user_name": "Laurie"},
    )


    # act on the input from the event
    if response.response.strip().lower() == "yes":
        return "Dangerous task completed successfully."
    else:
        return "Dangerous task aborted."
```

평소처럼 agent를 만들고 방금 작성한 도구를 전달합니다.

```python
workflow = FunctionAgent(
    tools=[dangerous_task],
    llm=llm,
    system_prompt="You are a helpful assistant that can perform dangerous tasks.",
)
```

이제 평소처럼 `InputRequiredEvent`를 다른 streaming event와 함께 처리하고, `send_event` method로 `HumanResponseEvent`를 전달해 Workflow를 실행할 수 있습니다.

```python
handler = workflow.run(user_msg="I want to proceed with the dangerous task.")


async for event in handler.stream_events():
    if isinstance(event, InputRequiredEvent):
        # capture keyboard input
        response = input(event.prefix)
        # send our response back
        handler.ctx.send_event(
            HumanResponseEvent(
                response=response,
                user_name=event.user_name,
            )
        )


response = await handler
print(str(response))
```

입력을 받는 방식은 무엇이든 사용할 수 있습니다. GUI, audio input을 사용하거나 별개의 다른 agent를 참여시킬 수도 있습니다. 입력에 시간이 오래 걸리거나 다른 process에서 입력을 처리한다면, context를 serialize해 database나 file에 저장한 뒤 나중에 Workflow를 재개할 수 있습니다.

다른 agent를 참여시키는 방법에 이어 다음은 [multi-agent 시스템](https://developers.llamaindex.ai/python/framework/understanding/agent/multi_agent/)입니다.

원문: [Human in the loop — LlamaIndex](https://developers.llamaindex.ai/python/framework/understanding/agent/human_in_the_loop/)

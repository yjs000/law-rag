# Function Calling Agent용 Workflow

이 노트북에서는 처음부터 Function Calling Agent를 구성하는 `Workflow` 설정을 안내합니다.

Function calling agent는 OpenAI, Ollama, Anthropic 등 API에서 tools/functions를 지원하는 LLM을 사용해 함수를 호출하고 tools를 이용합니다.

이 Workflow는 memory를 가진 stateful Workflow이며, LLM이 tools를 선택하고 들어오는 사용자 메시지를 처리하도록 호출할 수 있습니다.

```
!pip install -U llama-index
```

```
import os


os.environ["OPENAI_API_KEY"] = "sk-proj-..."
```

### [선택] Llamatrace로 관측성 설정

Workflow의 각 단계를 시각화할 수 있도록 tracing을 설정합니다.

Workflow는 비동기 실행을 기본으로 하므로 노트북에서는 이 코드가 그대로 실행됩니다. 직접 작성한 코드에서 실행하는 경우에는 이미 비동기 이벤트 루프가 실행 중이 아니라면 `asyncio.run()`을 사용해 시작해야 합니다.

```
async def main():
    <async code>


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Workflow 설계

agent는 다음과 같은 여러 단계로 구성됩니다.

1. 최신 사용자 메시지를 처리합니다. 여기에는 메시지를 memory에 추가하고 최신 chat history를 가져오는 과정이 포함됩니다.
2. tools와 chat history를 사용해 LLM을 호출합니다.
3. tool call이 있는지 파싱합니다.
4. tool call이 있으면 호출하고, 더 이상 없을 때까지 반복합니다.
5. tool call이 없으면 LLM 응답을 반환합니다.

### Workflow 이벤트

이 단계를 처리하려면 몇 가지 event를 정의해야 합니다.

1. 새 메시지를 처리하고 chat history를 준비하는 event
2. streaming 응답을 처리하는 event
3. tool call을 시작하는 event
4. tool call 결과를 처리하는 event

나머지 단계에서는 내장 `StartEvent` 및 `StopEvent` event를 사용합니다.

```
from llama_index.core.llms import ChatMessage
from llama_index.core.tools import ToolSelection, ToolOutput
from llama_index.core.workflow import Event




class InputEvent(Event):
    input: list[ChatMessage]




class StreamEvent(Event):
    delta: str




class ToolCallEvent(Event):
    tool_calls: list[ToolSelection]




class FunctionOutputEvent(Event):
    output: ToolOutput
```

### Workflow 자체

event를 정의했으므로 이제 Workflow와 step을 구성할 수 있습니다.

Workflow는 type annotation을 사용해 자체를 자동으로 검증합니다. 따라서 step의 type annotation이 큰 도움이 됩니다.

```
from typing import Any, List


from llama_index.core.llms.function_calling import FunctionCallingLLM
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools.types import BaseTool
from llama_index.core.workflow import (
    Context,
    Workflow,
    StartEvent,
    StopEvent,
    step,
)
from llama_index.llms.openai import OpenAI




class FuncationCallingAgent(Workflow):
    def __init__(
        self,
        *args: Any,
        llm: FunctionCallingLLM | None = None,
        tools: List[BaseTool] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools or []


        self.llm = llm or OpenAI()
        assert self.llm.metadata.is_function_calling_model


    @step
    async def prepare_chat_history(
        self, ctx: Context, ev: StartEvent
    ) -> InputEvent:
        # clear sources
        await ctx.store.set("sources", [])


        # check if memory is setup
        memory = await ctx.store.get("memory", default=None)
        if not memory:
            memory = ChatMemoryBuffer.from_defaults(llm=self.llm)


        # get user input
        user_input = ev.input
        user_msg = ChatMessage(role="user", content=user_input)
        memory.put(user_msg)


        # get chat history
        chat_history = memory.get()


        # update context
        await ctx.store.set("memory", memory)


        return InputEvent(input=chat_history)


    @step
    async def handle_llm_input(
        self, ctx: Context, ev: InputEvent
    ) -> ToolCallEvent | StopEvent:
        chat_history = ev.input


        # stream the response
        response_stream = await self.llm.astream_chat_with_tools(
            self.tools, chat_history=chat_history
        )
        async for response in response_stream:
            ctx.write_event_to_stream(StreamEvent(delta=response.delta or ""))


        # save the final response, which should have all content
        memory = await ctx.store.get("memory")
        memory.put(response.message)
        await ctx.store.set("memory", memory)


        # get tool calls
        tool_calls = self.llm.get_tool_calls_from_response(
            response, error_on_no_tool_call=False
        )


        if not tool_calls:
            sources = await ctx.store.get("sources", default=[])
            return StopEvent(
                result={"response": response, "sources": [*sources]}
            )
        else:
            return ToolCallEvent(tool_calls=tool_calls)


    @step
    async def handle_tool_calls(
        self, ctx: Context, ev: ToolCallEvent
    ) -> InputEvent:
        tool_calls = ev.tool_calls
        tools_by_name = {tool.metadata.get_name(): tool for tool in self.tools}


        tool_msgs = []
        sources = await ctx.store.get("sources", default=[])


        # call tools -- safely!
        for tool_call in tool_calls:
            tool = tools_by_name.get(tool_call.tool_name)
            additional_kwargs = {
                "tool_call_id": tool_call.tool_id,
                "name": tool.metadata.get_name(),
            }
            if not tool:
                tool_msgs.append(
                    ChatMessage(
                        role="tool",
                        content=f"Tool {tool_call.tool_name} does not exist",
                        additional_kwargs=additional_kwargs,
                    )
                )
                continue


            try:
                tool_output = tool(**tool_call.tool_kwargs)
                sources.append(tool_output)
                tool_msgs.append(
                    ChatMessage(
                        role="tool",
                        content=tool_output.content,
                        additional_kwargs=additional_kwargs,
                    )
                )
            except Exception as e:
                tool_msgs.append(
                    ChatMessage(
                        role="tool",
                        content=f"Encountered error in tool call: {e}",
                        additional_kwargs=additional_kwargs,
                    )
                )


        # update memory
        memory = await ctx.store.get("memory")
        for msg in tool_msgs:
            memory.put(msg)


        await ctx.store.set("sources", sources)
        await ctx.store.set("memory", memory)


        chat_history = memory.get()
        return InputEvent(input=chat_history)
```

이것으로 끝입니다! 작성한 Workflow를 조금 더 살펴보겠습니다.

- `prepare_chat_history()`: 주요 진입점입니다. 사용자 메시지를 memory에 추가하고 memory에서 최신 chat history를 가져옵니다. `InputEvent`를 반환합니다.
- `handle_llm_input()`: `InputEvent`가 발생하면 실행됩니다. chat history와 tools를 사용해 LLM에 prompt를 보냅니다. tool call이 있으면 `ToolCallEvent`를 내보냅니다. 없으면 Workflow가 끝난 것으로 보고 `StopEvent`를 내보냅니다.
- `handle_tool_calls()`: `ToolCallEvent`가 발생하면 실행됩니다. 오류를 처리하면서 tools를 호출하고 결과를 반환합니다. `InputEvent`를 내보내 다시 `handle_llm_input()`으로 돌아가므로 반복이 발생합니다.

## Workflow 실행

주의: 반복이 있으면 실행 시간에 유의해야 합니다. 여기서는 timeout을 120초로 설정합니다.

```
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI




def add(x: int, y: int) -> int:
    """Useful function to add two numbers."""
    return x + y




def multiply(x: int, y: int) -> int:
    """Useful function to multiply two numbers."""
    return x * y




tools = [
    FunctionTool.from_defaults(add),
    FunctionTool.from_defaults(multiply),
]


agent = FuncationCallingAgent(
    llm=OpenAI(model="gpt-4o-mini"), tools=tools, timeout=120, verbose=True
)


ret = await agent.run(input="Hello!")
```

```
Running step prepare_chat_history
Step prepare_chat_history produced event InputEvent
Running step handle_llm_input
Step handle_llm_input produced event StopEvent
```

```
print(ret["response"])
```

```
assistant: Hello! How can I assist you today?
```

```
ret = await agent.run(input="What is (2123 + 2321) * 312?")
```

```
Running step prepare_chat_history
Step prepare_chat_history produced event InputEvent
Running step handle_llm_input
Step handle_llm_input produced event ToolCallEvent
Running step handle_tool_calls
Step handle_tool_calls produced event InputEvent
Running step handle_llm_input
Step handle_llm_input produced event ToolCallEvent
Running step handle_tool_calls
Step handle_tool_calls produced event InputEvent
Running step handle_llm_input
Step handle_llm_input produced event StopEvent
```

## Chat History

기본적으로 Workflow는 실행할 때마다 새로운 `Context`를 만듭니다. 따라서 실행 사이에 chat history가 유지되지 않습니다. 직접 `Context`를 전달하면 chat history를 유지할 수 있습니다.

```
from llama_index.core.workflow import Context


ctx = Context(agent)


ret = await agent.run(input="Hello! My name is Logan.", ctx=ctx)
print(ret["response"])


ret = await agent.run(input="What is my name?", ctx=ctx)
print(ret["response"])
```

```
Running step prepare_chat_history
Step prepare_chat_history produced event InputEvent
Running step handle_llm_input
Step handle_llm_input produced event StopEvent
assistant: Hello, Logan! How can I assist you today?
Running step prepare_chat_history
Step prepare_chat_history produced event InputEvent
Running step handle_llm_input
Step handle_llm_input produced event StopEvent
assistant: Your name is Logan.
```

## Streaming

`.run()` 메서드가 반환한 handler를 사용하면 streaming event에도 접근할 수 있습니다.

```
agent = FuncationCallingAgent(
    llm=OpenAI(model="gpt-4o-mini"), tools=tools, timeout=120, verbose=False
)


handler = agent.run(input="Hello! Write me a short story about a cat.")


async for event in handler.stream_events():
    if isinstance(event, StreamEvent):
        print(event.delta, end="", flush=True)


response = await handler
# print(ret["response"])
```

```
Once upon a time in a quaint little village, there lived a curious cat named Whiskers. Whiskers was no ordinary cat; he had a beautiful coat of orange and white fur that shimmered in the sunlight, and his emerald green eyes sparkled with mischief.


Every day, Whiskers would explore the village, visiting the bakery for a whiff of freshly baked bread and the flower shop to sniff the colorful blooms. The villagers adored him, often leaving out little treats for their favorite feline.


One sunny afternoon, while wandering near the edge of the village, Whiskers stumbled upon a hidden path that led into the woods. His curiosity piqued, he decided to follow the path, which was lined with tall trees and vibrant wildflowers. As he ventured deeper, he heard a soft, melodic sound that seemed to beckon him.


Following the enchanting music, Whiskers soon found himself in a clearing where a group of woodland creatures had gathered. They were having a grand celebration, complete with dancing, singing, and a feast of berries and nuts. The animals welcomed Whiskers with open paws, inviting him to join their festivities.


Whiskers, delighted by the warmth and joy of his new friends, danced and played until the sun began to set. As the sky turned shades of pink and orange, he realized it was time to return home. The woodland creatures gifted him a small, sparkling acorn as a token of their friendship.


From that day on, Whiskers would often visit the clearing, sharing stories of the village and enjoying the company of his woodland friends. He learned that adventure and friendship could be found in the most unexpected places, and he cherished every moment spent in the magical woods.


And so, Whiskers continued to live his life filled with curiosity, laughter, and the warmth of friendship, reminding everyone that sometimes, the best adventures are just a whisker away.
```

원문: [Function Calling Agent — LlamaIndex](https://developers.llamaindex.ai/python/examples/workflow/function_calling_agent/)

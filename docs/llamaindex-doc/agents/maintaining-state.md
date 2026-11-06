# 상태 유지

기본적으로 `AgentWorkflow`는 실행 사이에 stateless합니다. 즉, agent는 이전 실행을 기억하지 않습니다.

상태를 유지하려면 이전 상태를 추적해야 합니다. LlamaIndex Workflows에는 실행 중과 실행 사이에 상태를 유지하는 데 사용할 수 있는 `Context` class가 있습니다. `AgentWorkflow` 자체가 미리 만들어진 Workflow이므로 여기서도 사용할 수 있습니다.

```python
from llama_index.core.workflow import Context
```

상태를 실행 사이에 유지하려면 `ctx`라는 새 `Context`를 만듭니다. 이 `Context`를 사용할 Workflow를 전달해 올바르게 설정합니다.

```python
ctx = Context(workflow)
```

설정한 `Context`를 첫 실행에 전달할 수 있습니다.

```python
response = await workflow.run(user_msg="Hi, my name is Laurie!", ctx=ctx)
print(response)
```

결과:

```text
Hello Laurie! How can I assist you today?
```

이제 후속 질문을 위해 Workflow를 다시 실행하면 agent가 해당 정보를 기억합니다.

```python
response2 = await workflow.run(user_msg="What's my name?", ctx=ctx)
print(response2)
```

결과:

```text
Your name is Laurie!
```

## 더 오랜 기간 상태 유지하기

`Context`는 serialize할 수 있으므로 database, file 등에 저장하고 나중에 다시 불러올 수 있습니다.

`JsonSerializer`는 `json.dumps`와 `json.loads`를 사용하는 간단한 serializer입니다.

`JsonPickleSerializer`는 `pickle`을 사용해 `Context`를 serialize하고 deserialize합니다. `Context`에 JSON으로 serialize할 수 없는 object가 있다면 이 serializer를 사용할 수 있습니다.

다른 import와 마찬가지로 serializer를 가져옵니다.

```python
from llama_index.core.workflow import JsonPickleSerializer, JsonSerializer
```

그런 다음 `Context`를 dictionary로 serialize해 file에 저장할 수 있습니다.

```python
ctx_dict = ctx.to_dict(serializer=JsonSerializer())
```

이를 다시 `Context` object로 deserialize하면 이전처럼 질문할 수 있습니다.

```python
restored_ctx = Context.from_dict(
    workflow, ctx_dict, serializer=JsonSerializer()
)


response3 = await workflow.run(user_msg="What's my name?", ctx=restored_ctx)
```

## 도구와 상태

도구를 Workflow context에 접근할 수 있도록 정의할 수 있습니다. 이를 통해 도구 안에서 context의 값을 설정하거나 가져오고, 도구 간에 정보를 전달할 수 있습니다.

`AgentWorkflow`는 `state`라는 context variable을 사용하며 모든 agent가 사용할 수 있습니다. `state`의 정보는 별도로 전달하지 않아도 사용할 수 있습니다.

`Context`에 접근하려면 아래처럼 `Context` parameter를 도구의 첫 번째 parameter로 둡니다. 이 도구는 이름을 state에 추가합니다.

```python
async def set_name(ctx: Context, name: str) -> str:
    async with ctx.store.edit_state() as ctx_state:
        ctx_state["state"]["name"] = name


    return f"Name set to {name}"
```

이제 방금 정의한 도구를 전달해 agent를 만들 수 있습니다.

```python
workflow = AgentWorkflow.from_tools_or_functions(
    [set_name],
    llm=llm,
    system_prompt="You are a helpful assistant that can set a name.",
    initial_state={"name": "unset"},
)
```

이제 `Context`를 만들고 state에 대해 agent에게 물어봅니다.

```python
ctx = Context(workflow)


# check if it knows a name before setting it
response = await workflow.run(user_msg="What's my name?", ctx=ctx)
print(str(response))
```

결과:

```text
Your name has been set to "unset."
```

그런 다음 agent를 새로 실행해 이름을 명시적으로 설정합니다.

```python
response2 = await workflow.run(user_msg="My name is Laurie", ctx=ctx)
print(str(response2))
```

```text
Your name has been updated to "Laurie."
```

이제 agent에게 다시 이름을 물어볼 수도 있고, state에서 직접 값을 가져올 수도 있습니다.

```python
state = await ctx.store.get("state")
print("Name as stored in state: ", state["name"])
```

결과:

```text
Name as stored in state: Laurie
```

원문: [Maintaining state — LlamaIndex](https://developers.llamaindex.ai/python/framework/understanding/agent/state/)

# 사용자 정의 시작·종료 event

대부분의 Workflow는 [시작하기](introduction.md)에서 소개한 기본 `StartEvent`와 `StopEvent`를 사용할 수 있습니다. Workflow의 경계 자체에 유용한 schema가 있을 때 사용자 정의 시작·종료 event를 정의하세요. 예를 들어 시작 지점에는 타입이 지정된 request object를, 종료 지점에는 타입이 지정된 result object를 둘 수 있습니다.

## 사용자 정의 `StartEvent` 사용하기

`run()`을 keyword argument와 함께 호출하면 Workflows가 그 인수들로 Workflow의 시작 event를 만듭니다. 기본 `StartEvent`에서는 추가 field를 모두 사용할 수 있습니다.

```python
result = await workflow.run(topic="pirates")
```

작은 입력에는 편리합니다. Production code에서는 사용자 정의 `StartEvent`를 사용하면 진입점에 실제 schema가 생기고 첫 step이 실행되기 전에 Pydantic이 누락되거나 잘못된 입력을 검증할 수 있습니다.

`StartEvent`를 상속하는 사용자 정의 class를 만듭니다.

```python
from workflows.events import StartEvent


class JokeStartEvent(StartEvent):
    topic: str
    tone: str = "funny"
```

그런 다음 Workflow를 시작하는 step에서 해당 event type을 사용합니다.

```python
class JokeFlow(Workflow):
    @step
    async def generate_joke(self, ev: JokeStartEvent) -> JokeEvent:
        prompt = f"Write a {ev.tone} joke about {ev.topic}."
        response = await self.llm.acomplete(prompt)
        return JokeEvent(joke=str(response))
```

Field를 keyword argument로 계속 전달할 수 있습니다.

```python
w = JokeFlow(timeout=60)
result = await w.run(topic="pirates", tone="dry")
```

입력이 큰 object라면 `start_event`를 통해 event instance를 전달하세요.

```python
start_event = JokeStartEvent(topic="pirates", tone="dry")
w = JokeFlow(timeout=60)
result = await w.run(start_event=start_event)
```

Event에는 직렬화할 수 있는 데이터를 사용하세요. Workflow에 LLM client, index, database connection 또는 file handle이 필요하다면 시작 event에 넣는 대신 [Resource](resources.md)로 주입하세요. 시작 event는 Workflow를 snapshot하거나 serve할 때 직렬화될 수 있지만, 무거운 runtime object는 대개 직렬화할 수 없습니다.

## 사용자 정의 `StopEvent` 사용하기

기본 제공 `StopEvent`는 `result`에 넣은 값을 무엇이든 반환합니다.

```python
return StopEvent(result={"critique": critique, "score": score})
```

간단한 Workflow에서는 괜찮지만, 결과 타입은 `Any`입니다. 사용자 정의 stop event를 사용하면 output 형태를 명시할 수 있습니다.

`StopEvent` 하위 class를 만듭니다.

```python
from workflows.events import StopEvent


class JokeResult(StopEvent):
    joke: str
    critique: str
```

이제 Workflow의 `StopEvent`를 `JokeResult`로 바꿀 수 있습니다.

```python
class JokeFlow(Workflow):
    ...

    @step
    async def critique_joke(self, ev: JokeEvent) -> JokeResult:
        prompt = f"Give a thorough analysis and critique of the following joke: {ev.joke}"
        response = await self.llm.acomplete(prompt)
        return JokeResult(joke=ev.joke, critique=str(response))
```

Step이 기본 `StopEvent`를 반환하면 `await workflow.run(...)`은 `stop_event.result`를 반환합니다. 사용자 정의 `StopEvent` 하위 class를 반환하면 `await workflow.run(...)`은 event instance를 반환합니다.

```python
w = JokeFlow(timeout=60)
result = await w.run(topic="pirates")
print(result.joke)
print(result.critique)
```

그러면 type checker와 editor autocomplete를 활용할 수 있고, Workflow schema를 확인하는 caller도 결과를 더 쉽게 다룰 수 있습니다.

---

원문: [Custom start and stop events](https://developers.llamaindex.ai/python/llamaagents/workflows/customizing_entry_exit_points/)

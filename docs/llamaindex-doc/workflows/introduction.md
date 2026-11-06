# 소개

## Workflow란 무엇인가요?

Workflow는 애플리케이션의 실행 흐름을 제어하는 event-driven 단계별 방식입니다.

애플리케이션은 step이라는 여러 부분으로 나뉩니다. 한 step은 event를 받고, 작업을 수행한 다음 다른 event를 반환합니다. 반환된 event는 타입 주석이 해당 event를 받도록 지정된 다음 step을 실행합니다.

이것이 전체 모델입니다. 각 step은 LLM을 호출하거나, retrieval을 실행하거나, 사람의 입력을 요청하거나, 공유 상태를 갱신하거나, 작업 묶음을 전달할 수 있습니다. Event type은 Workflow의 연결 관계를 설명하고, 일반 Python은 각 연결 안의 로직을 표현합니다.

## Workflow를 사용하는 이유

생성형 AI 애플리케이션이 복잡해질수록 데이터 흐름과 제어 흐름, 애플리케이션 실행을 관리하기 어려워집니다. Workflow는 애플리케이션을 더 작고 관리하기 쉬운 부분으로 나누어 이 복잡성을 다룹니다.

다른 framework와 LlamaIndex 자체도 이전에 directed acyclic graph(DAG)로 이 문제를 해결하려 했지만, DAG에는 Workflow가 갖지 않는 몇 가지 한계가 있습니다.

- loop나 branch 같은 로직을 graph의 edge에 표현해야 해서 읽고 이해하기 어려웠습니다.
- DAG의 node 사이에 데이터를 전달할 때 선택적 값과 기본값, 전달해야 할 매개변수를 처리하는 일이 복잡해졌습니다.
- 복잡한 loop·branch형 AI 애플리케이션을 개발하는 입장에서 DAG 방식은 자연스럽지 않았습니다.

Workflow의 event-based pattern과 일반 Python 접근 방식은 이런 문제를 해결합니다.

Branch는 서로 다른 event type을 반환하는 일반 `if` 문입니다. Loop는 앞 단계에서 처리하는 event를 반환하는 step입니다. Concurrent work는 `list[Event]`를 반환하는 step과 `list[Event]`를 받는 다른 step을 조합해 표현합니다. 흐름을 동적으로 만들어야 할 때는 `Context`에서 직접 event를 보낼 수 있습니다.

> **참고**
> Workflows library는 `pip install llama-index-workflows` 명령으로 단독 설치할 수 있습니다. 하지만 `llama-index-core`에는 Workflows가 포함되어 있습니다.
>
> `llama_index` API를 안정적으로 유지하고 호환성을 깨는 변경을 피하기 위해, `llama-index-core` 또는 통합 `llama-index` package를 설치하면 `llama_index.core.workflow` 경로로 Workflows를 가져올 수 있습니다.

## 시작하기

> **팁**
> Workflows는 async를 핵심 기능으로 지원하며, 이 페이지에서는 async environment에서 실행한다고 가정합니다. 즉, 코드의 async 처리를 올바르게 설정해야 합니다. FastAPI 같은 server나 notebook처럼 이미 `await`를 사용할 수 있는 environment라면 그대로 사용할 수 있습니다.
>
> 직접 Python script를 실행한다면 async 진입점을 하나만 두는 것이 일반적인 권장 방식입니다.

```
async def main():
    w = MyWorkflow(...)
    result = await w.run(...)
    print(result)




if __name__ == "__main__":
    import asyncio


    asyncio.run(main())
```

다음은 생성한 결과를 다른 step으로 전달한 뒤 결과와 함께 종료하는 가장 작은 유용한 형태입니다.

```
from workflows import Workflow, step
from workflows.events import (
    Event,
    StartEvent,
    StopEvent,
)


# `pip install llama-index-llms-openai` if you don't already have it
from llama_index.llms.openai import OpenAI




class JokeEvent(Event):
    joke: str




class JokeFlow(Workflow):
    llm = OpenAI(model="gpt-4.1")


    @step
    async def generate_joke(self, ev: StartEvent) -> JokeEvent:
        topic = ev.topic


        prompt = f"Write your best joke about {topic}."
        response = await self.llm.acomplete(prompt)
        return JokeEvent(joke=str(response))


    @step
    async def critique_joke(self, ev: JokeEvent) -> StopEvent:
        joke = ev.joke


        prompt = f"Give a thorough analysis and critique of the following joke: {joke}"
        response = await self.llm.acomplete(prompt)
        return StopEvent(result=str(response))




w = JokeFlow(timeout=60, verbose=False)
result = await w.run(topic="pirates")
print(str(result))
```

![농담](https://developers.llamaindex.ai/python/llamaagents/workflows/assets/joke.png)

여기에는 몇 가지 구성 요소가 있으므로 하나씩 살펴보겠습니다.

### Workflow event 정의하기

```
class JokeEvent(Event):
    joke: str
```

Event는 사용자가 정의하는 Pydantic object입니다. 속성과 기타 보조 method를 자유롭게 정할 수 있습니다. 이 경우 Workflow는 사용자가 정의한 단일 event인 `JokeEvent`를 사용합니다.

### Workflow class 설정하기

```
class JokeFlow(Workflow):
    llm = OpenAI(model="gpt-4.1")
    ...
```

`Workflow` class를 상속해 Workflow를 구현합니다. 간단하게 하기 위해 정적 `OpenAI` LLM instance를 연결했습니다.

### Workflow 진입점

```
class JokeFlow(Workflow):
    ...


    @step
    async def generate_joke(self, ev: StartEvent) -> JokeEvent:
        topic = ev.topic


        prompt = f"Write your best joke about {topic}."
        response = await self.llm.acomplete(prompt)
        return JokeEvent(joke=str(response))


    ...
```

여기서 Workflow의 진입점을 살펴봅니다. 대부분의 event는 사용자가 정의하지만, framework가 기본 제공하는 특별한 event로 `StartEvent`와 `StopEvent`가 있습니다. 이 예제에서 `StartEvent`는 초기 Workflow 입력을 전달할 위치를 나타냅니다.

`StartEvent`는 임의의 속성을 담을 수 있는 특별한 object입니다. 여기서는 `ev.topic`으로 주제에 접근했습니다. 해당 속성이 없으면 오류가 발생합니다. 속성이 없을 때 오류 없이 처리하려면 `ev.get("topic")`을 사용할 수도 있습니다.

타입 안정성을 더 높이려면 `StartEvent`를 상속해 사용할 수도 있습니다.

어떤 step이 어떤 event를 처리하는지 Workflow에 명시적으로 알려주지 않았다는 점을 알아차렸을 수 있습니다. 대신 `@step` decorator가 각 step의 입력·출력 type을 추론합니다. 추론한 입력·출력 type은 실행 전에 Workflow가 유효한지도 확인합니다.

### Workflow 종료점

```
class JokeFlow(Workflow):
    ...


    @step
    async def critique_joke(self, ev: JokeEvent) -> StopEvent:
        joke = ev.joke


        prompt = f"Give a thorough analysis and critique of the following joke: {joke}"
        response = await self.llm.acomplete(prompt)
        return StopEvent(result=str(response))


    ...
```

이 step은 Workflow의 두 번째이자 마지막 단계입니다. 특별한 `StopEvent`를 반환하므로 마지막 단계임을 알 수 있습니다. Workflow가 반환된 `StopEvent`를 만나면 즉시 실행을 멈추고 `result` 매개변수에 전달된 값을 반환합니다.

이 예제에서는 결과가 string이지만 dictionary, list 또는 다른 어떤 object도 사용할 수 있습니다.

타입 안정성을 더 높이기 위해 `StopEvent` class를 상속할 수도 있습니다.

### Workflow 실행하기

```
w = JokeFlow(timeout=60, verbose=False)
result = await w.run(topic="pirates")
print(str(result))
```

마지막으로 Workflow를 만들고 실행합니다. 디버깅에 도움이 되는 timeout(초 단위), 상세 출력 등의 설정이 있습니다.

`.run()` method는 Workflow를 시작하고 `WorkflowHandler`를 반환합니다. Handler는 awaitable이므로 `await w.run(...)`을 실행하면 최종 결과를 기다립니다. Workflow가 실행되는 동안 event를 streaming해야 한다면 handler를 저장합니다.

```
handler = w.run(topic="pirates")
async for ev in handler.stream_events():
    ...
result = await handler
```

`run()`에 전달한 keyword argument는 Workflow를 시작할 때 자동으로 발생하는 특별한 `StartEvent`의 field가 됩니다. 앞에서 본 것처럼 이 경우 step 안에서 `ev.topic`으로 `topic`에 접근합니다.

## 적절한 Workflow API 선택하기

대부분의 Workflow code는 타입이 지정된 step 입력과 반환값을 사용해야 합니다. 이렇게 하면 validation과 diagram 생성이 가능하고 code도 읽기 쉬워집니다.

```
@step
async def retrieve(self, ev: StartEvent) -> Retrieved:
    ...


@step
async def synthesize(self, ev: Retrieved) -> StopEvent:
    ...
```

작업 형태에 따라 다음 API를 사용하세요.

| 사용 방법 | 사용 시점 |
|---|---|
| `A | B` 반환 | 한 step에서 두 event type 가운데 하나를 반환할 수 있을 때 |
| `list[A]` 반환 | step이 유한한 batch를 만들 수 있고, downstream worker가 시작하기 전에 모든 작업 항목을 생성할 때 |
| `list[A]` 받기 | 계속 진행하기 전에 전체 batch 결과가 필요할 때 |
| `ctx.send_event(...)` | event를 점진적으로 발생시키거나, 개수를 미리 알 수 없거나, Workflow 실행 중 외부에서 event를 보내야 할 때 |
| `ctx.collect_events(...)` | `ctx.send_event`를 사용했고 정해진 event 집합을 직접 기다려야 할 때 |
| `ctx.store` | step들이 실행별로 공유할 상태가 필요할 때 |
| `Resource(...)` | 직렬화 상태에 두지 않아야 하는 client, index, model, config 또는 다른 dependency가 step에 필요할 때 |

타입을 우선하는 API는 validation과 시각화가 쉽습니다. Context API는 더 유연하지만 필요한 bookkeeping을 직접 관리해야 합니다.

## Validation

Workflow를 실행하기 전에 Workflows는 step signature에 선언된 event graph를 검증합니다. 시작·종료 event가 있는지, 생성된 event를 처리하는 step이 있는지, 처리되는 event를 생성하는 step이 있는지, graph에 의도치 않은 막다른 지점이 없는지 확인합니다.

대부분의 validation 실패는 유용한 설계 피드백입니다. 보통 다음 중 하나를 의미합니다.

| 증상 | 일반적인 원인 |
|---|---|
| 어떤 step이 생성되지 않는 event를 받음 | 반환 type 주석이 빠졌거나 해당 event가 `ctx.send_event`로만 동적으로 전송됨 |
| 어떤 step이 아무도 처리하지 않는 event를 생성함 | 다음 step의 event type이 잘못되었거나 branch가 끝나지 않음 |
| Workflow에 terminal event가 없음 | 도달 가능한 step 중 `StopEvent` 또는 사용자 정의 `StopEvent` 하위 class를 반환하는 step이 없음 |

의도적으로 동적인 Workflow에서는 가능한 한 많은 정보를 타입 주석에 담고, event를 보내는 시점은 `ctx.send_event`로 조정하세요. 정적 분석상 의도적으로 도달할 수 없는 step이 있다면 그 step의 해당 검사만 건너뛸 수 있습니다.

```
@step(skip_graph_checks=["reachability"])
async def receive_webhook(self, ev: WebhookEvent) -> StopEvent:
    ...
```

Test나 startup code에서 `workflow.validate()`를 직접 호출할 수도 있습니다. Resource config file은 기본적으로 검증됩니다. Resource factory는 `validate(validate_resources=True)`를 호출한 경우에만 확인됩니다.

## 예제

Workflow 개념과 기능에 익숙해질 수 있도록 LlamaIndex 문서에서는 직접 실행해 볼 수 있는 예제 notebook을 제공합니다.

- [일반적인 Workflow 패턴](https://developers.llamaindex.ai/python/examples/workflow/workflows_cookbook/)은 간단한 Workflow를 사용해 loop와 상태 관리 같은 일반적인 사용 패턴을 설명합니다. 보통 여기서 시작하면 좋습니다.
- [RAG + reranking](https://developers.llamaindex.ai/python/examples/workflow/rag/)은 ingestion과 query를 모두 수행하는 비교적 단순한 Workflow로 실제 사용 사례를 구현합니다.
- [Citation Query Engine](../examples/citation-query-engine.md)은 RAG + reranking과 비슷하지만 retrieval과 generation 사이의 중간 단계 구현에 초점을 둡니다. Workflow에서 [`Context`](managing-state.md) object를 사용하는 좋은 예입니다.
- [Corrective RAG](../examples/corrective-rag-pack.md)는 evaluation step 뒤에 web search engine에 질의하는 기능을 추가해 RAG Workflow를 더 복잡하게 확장합니다.
- [Concurrency 활용](https://developers.llamaindex.ai/python/examples/workflow/parallel_execution/)은 Workflow가 복잡해질 때 중요한 step의 병렬 실행 관리 방법을 설명합니다.

RAG application은 이해하기 쉽고 Workflow 기초를 익히기에 좋습니다. 하지만 tool calling, memory, routing이 포함된 더 복잡한 agent 시나리오에서 Workflow의 강점이 드러납니다.

다음 예제들은 이런 사용 사례를 보여 줍니다.

- [ReAct Agent](https://developers.llamaindex.ai/python/examples/workflow/react_agent/)는 Workflow에서 tool을 구현하는 방법을 보여 줍니다.
- [Function Calling Agent](../examples/function-calling-agent.md)는 복잡한 function calling 시나리오에서도 code를 작고 깔끔하게 유지하면서 Workflow에서 LlamaIndex framework의 기본 요소를 사용하는 좋은 예입니다.
- [CodeAct Agent](https://developers.llamaindex.ai/python/examples/agent/from_scratch_code_act_agent/)는 처음부터 CodeAct Agent를 만드는 좋은 예입니다.
- [Human In The Loop: Story Crafting](../examples/human-in-the-loop-story-crafting.md)은 사람의 입력을 수집하는 것처럼 Workflow 실행을 대화형·상태 유지형으로 만드는 유용한 예입니다.
- [신뢰할 수 있는 구조화 생성](../examples/reflection.md)은 reflection loop를 사용해 구조화된 output을 개선하는 방법을 보여 줍니다.
- [Workflow를 이용한 Query Planning](https://developers.llamaindex.ai/python/examples/workflow/planning_workflow/)은 query를 작은 항목으로 나누어 계획하고 실행하는 예입니다. Workflow event streaming, step 병렬 실행, 조건이 충족될 때까지 반복하는 방법을 설명합니다.
- [내구성 있는 Workflow 작성](durable-workflows.md)은 Workflow context를 checkpoint로 저장하고 재시작 뒤 실행을 재개하는 방법을 보여 줍니다.

마지막으로 문헌을 바탕으로 빠르게 prototype을 구현할 때 Workflow가 유용한 고급 사용 사례도 있습니다.

- [고급 Text-to-SQL](https://developers.llamaindex.ai/python/examples/workflow/advanced_text_to_sql/)
- [JSON Query Engine](https://developers.llamaindex.ai/python/examples/workflow/jsonalyze_query_engine/)
- [Long RAG](https://developers.llamaindex.ai/python/examples/workflow/long_rag_pack/)
- [다단계 Query Engine](https://developers.llamaindex.ai/python/examples/workflow/multi_step_query_engine/)
- [멀티 전략 Workflow](https://developers.llamaindex.ai/python/examples/workflow/multi_strategy_workflow/)
- [Router Query Engine](https://developers.llamaindex.ai/python/examples/workflow/router_query_engine/)
- [Self Discover Workflow](https://developers.llamaindex.ai/python/examples/workflow/self_discover_workflow/)
- [Sub-Question Query Engine](https://developers.llamaindex.ai/python/examples/workflow/sub_question_query_engine/)

---

원문: [Introduction](https://developers.llamaindex.ai/python/llamaagents/workflows/)

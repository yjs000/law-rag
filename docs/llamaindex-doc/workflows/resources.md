# Resource 객체

Resource는 Workflow step에 주입할 수 있는 외부 dependency입니다.

Runtime이 만들도록 해야 하는 object에는 Resource를 사용하세요. Event로 전달하거나 `ctx.store`에 저장하는 대신 LLM client, retriever, index, database handle, model config, 비용이 크거나 상태를 가진 dependency, JSON으로 직렬화할 수 없는 다른 object를 Resource로 둘 수 있습니다.

간단한 예로, 다음 Workflow에서 LlamaIndex의 `Memory`를 사용합니다.

```python
from typing import Annotated

from workflows import Workflow, step
from workflows.events import Event, StartEvent, StopEvent
from workflows.resource import Resource
from llama_index.core.llms import ChatMessage
from llama_index.core.memory import Memory


def get_memory() -> Memory:
    return Memory.from_defaults("user_id_123", token_limit=60000)


class SecondEvent(Event):
    msg: str


class WorkflowWithResource(Workflow):
    @step
    async def first_step(
        self,
        ev: StartEvent,
        memory: Annotated[Memory, Resource(get_memory)],
    ) -> SecondEvent:
        print("Memory before step 1", memory)
        await memory.aput(
            ChatMessage(role="user", content="This is the first step")
        )
        print("Memory after step 1", memory)
        return SecondEvent(msg="This is an input for step 2")

    @step
    async def second_step(
        self, ev: SecondEvent, memory: Annotated[Memory, Resource(get_memory)]
    ) -> StopEvent:
        print("Memory before step 2", memory)
        await memory.aput(ChatMessage(role="user", content=ev.msg))
        print("Memory after step 2", memory)
        return StopEvent(result="Messages put into memory")
```

Resource를 주입하려면 step signature에 매개변수를 추가하고, 타입을 `Annotated`로 감싼 다음 `Resource()`에 factory를 전달합니다.

```python
memory: Annotated[Memory, Resource(get_memory)]
```

Factory의 반환 타입은 주석으로 지정한 매개변수 타입과 일치해야 합니다. 기본적으로 Resource는 Workflow 실행 동안 cache됩니다. 따라서 두 step은 같은 `Memory` object를 받고 factory도 한 번만 호출됩니다. 매번 새 object가 필요하다면 `cache=False`를 전달하세요.

```python
memory: Annotated[Memory, Resource(get_memory, cache=False)]
```

Factory는 동기식일 수도 있고 async일 수도 있습니다.

## Config를 사용하는 Resource

JSON file에 저장된 설정 데이터에는 `Resource` 대신 `ResourceConfig`를 사용하세요. JSON file을 읽고 Pydantic model로 파싱합니다.

```python
from typing import Annotated
from pydantic import BaseModel
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent
from workflows.resource import ResourceConfig


class ClassifierConfig(BaseModel):
    categories: list[str]
    threshold: float


class DocumentClassifier(Workflow):
    @step
    async def classify(
        self,
        ev: StartEvent,
        config: Annotated[
            ClassifierConfig,
            ResourceConfig(config_file="classifier.json"),
        ],
    ) -> StopEvent:
        # config is loaded from classifier.json and validated as ClassifierConfig
        return StopEvent(result=f"Using threshold: {config.threshold}")
```

### 매개변수

- `config_file`: 설정이 들어 있는 JSON file의 경로
- `path_selector`: JSON file에서 중첩된 값을 가져올 때 사용하는 선택적 `.` 구분 JSON path. 예: `"settings.classifier"`
- `label`: Workflow 시각화에서 사용할 선택적 표시 이름
- `description`: Workflow 시각화를 위한 선택적 설명

### 중첩된 값 선택

JSON file에 여러 설정이 들어 있다면 `path_selector`로 특정 section을 선택하세요.

```python
# Given config.json: {"classifier": {"categories": [...], "threshold": 0.8}, "other": {...}}
config: Annotated[
    ClassifierConfig,
    ResourceConfig(config_file="config.json", path_selector="classifier"),
]
```

### 시각화의 label과 description

Debugger나 다른 visualization tool에서 Workflow를 볼 때 `label`과 `description`을 지정하면 config를 식별하기 쉽습니다.

```python
config: Annotated[
    ClassifierConfig,
    ResourceConfig(
        config_file="classifier.json",
        label="Document Classifier",
        description="Categories and confidence threshold for classification",
    ),
]
```

`label`을 지정하지 않으면 Pydantic model의 타입 이름을 사용합니다. 예: `"ClassifierConfig"`.

## Resource 연결하기

Resource와 ResourceConfig를 연결할 수 있습니다. `Resource` factory function은 같은 `Annotated` pattern으로 다른 Resource에 대한 dependency를 선언할 수 있습니다.

```python
from typing import Annotated
from pydantic import BaseModel
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent
from workflows.resource import Resource, ResourceConfig
from llama_index.llms.anthropic import Anthropic


class LLMConfig(BaseModel):
    model: str
    temperature: float
    max_tokens: int


def get_llm(
    config: Annotated[LLMConfig, ResourceConfig(config_file="llm.json")],
) -> Anthropic:
    return Anthropic(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


class MyWorkflow(Workflow):
    @step
    async def generate(
        self,
        ev: StartEvent,
        llm: Annotated[Anthropic, Resource(get_llm)],
    ) -> StopEvent:
        response = await llm.acomplete(ev.input)
        return StopEvent(result=response.text)
```

Dependency chain은 자동으로 해석됩니다. 이 예제에서 Workflow가 실행되면 다음 순서로 처리됩니다.

1. `llm.json`을 불러와 `LLMConfig`로 파싱합니다.
2. 해당 config를 인수로 `get_llm`을 호출해 LLM client를 만듭니다.
3. 만들어진 client를 step에 전달합니다.

이 패턴은 `Resource`와 `ResourceConfig` dependency를 어떤 조합으로 사용해도 동작합니다.

---

원문: [Resource Objects](https://developers.llamaindex.ai/python/llamaagents/workflows/resources/)

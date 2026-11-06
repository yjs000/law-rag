# 구조화된 출력을 위한 Reflection Workflow

이 노트북에서는 오류를 되돌아보고 재시도해 안정적인 구조화 출력을 제공하는 `Workflow`를 설정하는 방법을 안내합니다.

이 노트북은 오픈 소스 LLM을 사용할 때 가장 잘 작동하므로 `Ollama`를 사용합니다. 아직 Ollama를 실행하고 있지 않다면 [Ollama](https://ollama.com/)에서 시작 방법을 확인하고 원하는 model을 다운로드하세요. (이 노트북을 실행하기 전에 `ollama pull llama3.1`을 실행했습니다.)

```
!pip install -U llama-index llama-index-llms-ollama
```

Workflow는 비동기 실행을 기본으로 하므로 노트북에서는 이 코드가 그대로 실행됩니다. 직접 작성한 코드에서 실행하는 경우에는 이미 비동기 이벤트 루프가 실행 중이 아니라면 `asyncio.run()`을 사용해 시작해야 합니다.

```
async def main():
    <async code>


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Workflow 설계

LLM의 구조화된 출력을 검증하는 데는 다음 두 단계만 있으면 됩니다.

1. 구조화된 출력을 생성합니다.
2. 출력이 올바른 JSON인지 검증합니다.

핵심은 출력이 잘못된 경우 유효해질 때까지 반복하고, 다음 생성 단계에 오류 피드백을 전달하는 것입니다.

### Workflow 이벤트

이 단계를 처리하려면 몇 가지 event를 정의해야 합니다.

1. 생성한 extraction을 전달하는 event
2. extraction이 유효하지 않을 때 피드백을 전달하는 event

나머지 단계에서는 내장 `StartEvent` 및 `StopEvent` event를 사용합니다.

```
from llama_index.core.workflow import Event




class ExtractionDone(Event):
    output: str
    passage: str




class ValidationErrorEvent(Event):
    error: str
    wrong_output: str
    passage: str
```

### 추출할 항목

모델에 prompt를 보내기 위해 추출할 Pydantic model을 정의합니다.

```
from pydantic import BaseModel




class Car(BaseModel):
    brand: str
    model: str
    power: int




class CarCollection(BaseModel):
    cars: list[Car]
```

### Workflow 자체

event를 정의했으므로 이제 Workflow와 step을 구성할 수 있습니다.

Workflow는 type annotation을 사용해 자체를 자동으로 검증합니다. 따라서 step의 type annotation이 큰 도움이 됩니다.

```
import json


from llama_index.core.workflow import (
    Workflow,
    StartEvent,
    StopEvent,
    Context,
    step,
)
from llama_index.llms.ollama import Ollama


EXTRACTION_PROMPT = """
Context information is below:
---------------------
{passage}
---------------------


Given the context information and not prior knowledge, create a JSON object from the information in the context.
The JSON object must follow the JSON schema:
{schema}


"""


REFLECTION_PROMPT = """
You already created this output previously:
---------------------
{wrong_answer}
---------------------


This caused the JSON decode error: {error}


Try again, the response must contain only valid JSON code. Do not add any sentence before or after the JSON object.
Do not repeat the schema.
"""




class ReflectionWorkflow(Workflow):
    max_retries: int = 3


    @step
    async def extract(
        self, ctx: Context, ev: StartEvent | ValidationErrorEvent
    ) -> StopEvent | ExtractionDone:
        current_retries = await ctx.store.get("retries", default=0)
        if current_retries >= self.max_retries:
            return StopEvent(result="Max retries reached")
        else:
            await ctx.store.set("retries", current_retries + 1)


        if isinstance(ev, StartEvent):
            passage = ev.get("passage")
            if not passage:
                return StopEvent(result="Please provide some text in input")
            reflection_prompt = ""
        elif isinstance(ev, ValidationErrorEvent):
            passage = ev.passage
            reflection_prompt = REFLECTION_PROMPT.format(
                wrong_answer=ev.wrong_output, error=ev.error
            )


        llm = Ollama(
            model="llama3",
            request_timeout=30,
            # Manually set the context window to limit memory usage
            context_window=8000,
        )
        prompt = EXTRACTION_PROMPT.format(
            passage=passage, schema=CarCollection.schema_json()
        )
        if reflection_prompt:
            prompt += reflection_prompt


        output = await llm.acomplete(prompt)


        return ExtractionDone(output=str(output), passage=passage)


    @step
    async def validate(
        self, ev: ExtractionDone
    ) -> StopEvent | ValidationErrorEvent:
        try:
            CarCollection.model_validate_json(ev.output)
        except Exception as e:
            print("Validation failed, retrying...")
            return ValidationErrorEvent(
                error=str(e), wrong_output=ev.output, passage=ev.passage
            )


        return StopEvent(result=ev.output)
```

이것으로 끝입니다! 작성한 Workflow를 조금 더 살펴보겠습니다.

- 진입점은 하나이며, `extract` 단계가 `StartEvent`를 받습니다.
- `extract`가 끝나면 `ExtractionDone` event를 내보냅니다.
- `validate`가 실행되어 extraction을 확인합니다.
  - 올바르면 `StopEvent`를 내보내 Workflow를 종료합니다.
  - 올바르지 않으면 오류 정보가 포함된 `ValidationErrorEvent`를 반환합니다.
- 생성된 `ValidationErrorEvent`가 반복을 시작하고 `extract`가 다시 실행됩니다.
- 구조화된 출력이 검증될 때까지 이 과정이 이어집니다.

## Workflow 실행

주의: 반복이 있으면 실행 시간에 유의해야 합니다. 여기서는 timeout을 120초로 설정합니다.

```
w = ReflectionWorkflow(timeout=120, verbose=True)


# Run the workflow
ret = await w.run(
    passage="I own two cars: a Fiat Panda with 45Hp and a Honda Civic with 330Hp."
)
```

```
Running step extract
Step extract produced event ExtractionDone
Running step validate
Validation failed, retrying...
Step validate produced event ValidationErrorEvent
Running step extract
Step extract produced event ExtractionDone
Running step validate
Step validate produced event StopEvent
```

```
print(ret)
```

```
{ "cars": [ { "brand": "Fiat", "model": "Panda", "power": 45 }, { "brand": "Honda", "model": "Civic", "power": 330 } ] }
```

원문: [Reliable Structured Generation — LlamaIndex](https://developers.llamaindex.ai/python/examples/workflow/reflection/)

# 관측 가능성

Workflow를 디버깅하려면 observability가 중요합니다. `print()` 문을 추가하는 데 그치지 않고, `workflows`는 모든 Workflow step의 입력과 출력을 추적하는 포괄적인 instrumentation system을 제공합니다.

또한 이 instrumentation system을 활용하면 Workflow step 밖의 모든 함수에도 observability를 추가할 수 있습니다. 자세한 예제는 [observability 예제 폴더](https://github.com/run-llama/llama-agents/tree/main/examples/observability)에서 확인할 수 있습니다.

## 내부 event로 step 상태 관찰하기

step이 발생시키는 event 외에도 runtime은 자체 실행을 설명하는 internal event를 게시합니다. 기본적으로 `stream_events()`에서는 이 event를 제외합니다. 보려면 `expose_internal=True`를 전달하세요.

```python
from workflows.events import StepStateChanged, StepState

handler = workflow.run()
async for ev in handler.stream_events(expose_internal=True):
    if isinstance(ev, StepStateChanged):
        print(ev.name, ev.step_state, ev.worker_id)
```

`StepStateChanged`는 step 실행 상태가 바뀔 때마다 발생합니다. `step_state`는 `StepState.PREPARING`(큐에 들어가 worker slot을 기다리는 상태), `StepState.RUNNING`(실행 중), `StepState.NOT_RUNNING`(실행을 마친 상태) 중 하나입니다. 이 event에는 `name`, `worker_id`, `input_event_name`, `output_event_name`도 포함됩니다. step 실행마다 한 번씩 발생하므로 `@step(num_workers=N)`이 지정된 step이나 fan-out에서는 항목마다 event가 하나씩 발생합니다.

[durable workflows](durable-workflows.md)의 checkpoint loop는 이 event를 사용해 step 실행이 끝난 뒤 snapshot을 만듭니다.

## OpenTelemetry 통합

Workflows는 trace를 내보내기 위해 OpenTelemetry와 통합됩니다. `llama-index-observability-otel` package를 설치하세요.

```bash
pip install llama-index-observability-otel
```

그런 다음 애플리케이션에서 설정합니다.

```python
from llama_index.observability.otel import LlamaIndexOpenTelemetry

# Initialize with your span exporter
instrumentor = LlamaIndexOpenTelemetry(
    span_exporter=your_span_exporter,
    service_name_or_resource="your_service_name",
)

# Start registering traces
instrumentor.start_registering()
```

모든 Workflow step, LLM call, 사용자 지정 event는 다음과 같은 상세 attribute를 포함한 OpenTelemetry span으로 자동 수집 및 내보내기됩니다.

- 각 Workflow step의 span 이름
- 시작 및 종료 시각
- event attribute(입력 데이터, 출력 데이터 등)
- 실행 흐름을 보여주는 중첩 span 관계

## 서드파티 관측 도구

Workflows는 널리 사용되는 observability platform과 원활하게 통합됩니다.

### Arize Phoenix

![Arize Phoenix](https://developers.llamaindex.ai/python/llamaagents/workflows/observability/assets/arize.png)

[Arize Phoenix](https://docs.arize.com/phoenix/integrations/frameworks/llamaindex/llamaindex-workflows-tracing)는 Workflow의 trace와 시각화를 실시간으로 제공합니다.

[예제 notebook](https://github.com/run-llama/llama-agents/blob/main/examples/observability/workflows_observablitiy_arize_phoenix.ipynb)에서 더 자세히 확인할 수 있습니다.

### Langfuse

[Langfuse](https://github.com/langfuse/langfuse)는 Workflows에 포함된 instrumentation system과 직접 통합됩니다.

[예제 notebook](https://github.com/run-llama/llama-agents/blob/main/examples/observability/workflows_observablitiy_langfuse.ipynb)에서 더 자세히 확인할 수 있습니다.

### Opik

Opik은 Workflows가 사용하는 것과 같은 OpenTelemetry pipeline을 통해 Workflow trace를 받을 수 있습니다.

Opik으로 내보내려면 위의 OpenTelemetry 설정을 사용하고 exporter가 Opik의 OTLP endpoint를 가리키게 하세요. [Opik OpenTelemetry Python SDK 가이드](https://www.comet.com/docs/opik/integrations/opentelemetry-python-sdk)를 참고하세요.

## 사용자 지정 Span과 Event

코드에 세밀한 tracing을 추가하기 위해 LlamaIndex dispatcher로 사용자 지정 span과 event를 정의할 수 있습니다.

```python
from llama_index_instrumentation import get_dispatcher
from llama_index_instrumentation.base import BaseEvent

dispatcher = get_dispatcher()

# Define custom events
class ExampleEvent(BaseEvent):
    data: str

class AnotherExampleEvent(BaseEvent):
    print_statement: str

# Use the @dispatcher.span decorator
@dispatcher.span
def example_fn(data: str) -> None:
    dispatcher.event(ExampleEvent(data=data))
    s = "This are example string data: " + data
    dispatcher.event(AnotherExampleEvent(print_statement=s))
    print(s)
```

계측된 함수를 호출하면 구성된 모든 tracing backend가 span과 event를 자동으로 수집합니다.

[examples/observability](https://github.com/run-llama/llama-agents/tree/main/examples/observability) 디렉터리에서 전체 예제를 확인하세요.

출처: https://developers.llamaindex.ai/python/llamaagents/workflows/observability/

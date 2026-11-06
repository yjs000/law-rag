# Workflow 그리기

Workflow는 runtime이 validation에 사용하는 것과 같은 type annotation으로 시각화할 수 있습니다. 따라서 다이어그램은 두 시점에 유용합니다. 실행 전에는 가능한 모든 경로를 확인하고, 실행 후에는 실제로 발생한 경로를 살펴볼 수 있습니다.

Workflow를 시각화하는 주요 방법은 두 가지입니다.

## 다이어그램 파일 생성

먼저 설치합니다.

```bash
pip install llama-index-utils-workflow
```

그런 다음 import하여 사용합니다.

```python
from llama_index.utils.workflow import (
    draw_all_possible_flows,
    draw_all_possible_flows_mermaid,
    draw_most_recent_execution,
    draw_most_recent_execution_mermaid,
)

# Draw every statically possible path as HTML
draw_all_possible_flows(MyWorkflow, filename="all_paths.html")

# Draw the same static graph as Mermaid
mermaid = draw_all_possible_flows_mermaid(MyWorkflow)

# Draw one completed execution as HTML
w = MyWorkflow()
handler = w.run(topic="Pirates")
await handler
draw_most_recent_execution(handler, filename="most_recent.html")

# Draw the same completed execution as Mermaid
execution_mermaid = draw_most_recent_execution_mermaid(handler)
```

`draw_all_possible_flows`에는 Workflow class나 Workflow instance를 전달할 수 있습니다. 실행 함수는 `WorkflowHandler`를 받으므로 먼저 Workflow를 실행해야 합니다.

event 이름이 길면 다이어그램을 읽기 어려울 수 있습니다. `max_label_length=...`를 전달해 node label을 줄일 수 있습니다.

```python
draw_all_possible_flows(MyWorkflow, filename="all_paths.html", max_label_length=24)
```

기본적으로 정적 다이어그램에는 하위 Workflow가 포함됩니다. 상위 Workflow의 graph만 보려면 `include_child_workflows=False`를 전달하세요.

## debugger UI 사용

[`WorkflowServer`](https://developers.llamaindex.ai/python/llamaagents/workflows/deployment/)는 `/` 경로에서 debugger UI를 제공합니다. Workflow를 실행하고 event를 살펴보거나 브라우저에서 human-in-the-loop response를 보낼 때 사용하세요.

이 서버 앱으로 Workflow를 시각화하고 실행할 수 있습니다.

![Workflow debugger UI](https://raw.githubusercontent.com/run-llama/llama-agents/main/docs/src/content/docs/llamaagents/workflows/assets/ui_sample.png)

서버 설정은 간단합니다.

```python
import asyncio
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent
from llama_agents.server import WorkflowServer


class MyWorkflow(Workflow):
    @step
    async def my_step(self, ev: StartEvent) -> StopEvent:
        return StopEvent(result="Done!")


async def main():
    server = WorkflowServer()
    server.add_workflow("my_workflow", MyWorkflow())
    await server.serve("0.0.0.0", 8080)

if __name__ == "__main__":
    asyncio.run(main())
```

원문: https://developers.llamaindex.ai/python/llamaagents/workflows/drawing/

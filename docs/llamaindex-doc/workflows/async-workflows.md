# 비동기 Workflow 작성

Workflow는 Python의 `asyncio` event loop에서 실행됩니다. Runtime은 cooperative multitasking을 사용합니다. 한 step이 `await` 상태일 때(예를 들어 LLM 응답이나 network 호출을 기다릴 때) 다른 step과 Workflow가 계속 진행될 수 있습니다.

Python async programming이 처음이라면 먼저 [Introduction to async Python](https://developers.llamaindex.ai/python/framework/getting_started/async_python/)에서 `asyncio`, event loop, `await`를 전반적으로 살펴보세요.

Step은 `async def` 또는 일반 `def`로 정의할 수 있습니다. 이 페이지에서는 각각의 실행 방식과 event loop를 멈추지 않으면서 blocking 또는 CPU 집약 작업을 처리하는 방법을 설명합니다.

## Sync step (`async def` 대신 `def` 사용)

Workflow step은 `async def` 대신 일반 `def` 함수로 정의할 수 있습니다. Runtime이 sync step을 만나면 함수 전체를 `asyncio.get_event_loop().run_in_executor()`로 기본 thread pool에 자동 전달하므로 event loop가 막히지 않습니다.

```python
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent
import requests


class SyncStepWorkflow(Workflow):
    @step
    def fetch_data(self, ev: StartEvent) -> StopEvent:
        # This runs in a thread automatically, so the event loop stays free
        response = requests.get("https://api.example.com/data")
        return StopEvent(result=response.json())
```

Step 본문 전체가 동기식일 때 가장 간단한 방법입니다. Framework가 thread 경계에서 `contextvars`를 유지하는 것까지 포함해 thread 전달을 처리합니다.

다만 `async def` step 내부에서 더 세밀하게 제어해야 하는 경우가 있습니다. 예를 들어 step의 일부만 blocking하거나 CPU 집약 작업에 전용 executor를 사용하려는 경우입니다. 다음 절에서 이런 상황을 다룹니다.

## Async step의 blocking I/O

많은 Python 라이브러리는 동기식 API만 제공합니다. 데이터베이스 driver, HTTP client, 파일 시스템 작업, SDK 호출 등이 여기에 포함됩니다. `async def` Workflow step에서 이런 API를 사용해야 한다면 `asyncio.to_thread`로 thread pool에 전달하세요.

```python
import asyncio
import requests
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent


class BlockingIOWorkflow(Workflow):
    @step
    async def fetch_data(self, ev: StartEvent) -> StopEvent:
        # Bad: this blocks the event loop until the request completes
        # response = requests.get("https://api.example.com/data")

        # Good: run the blocking call in a thread so the event loop stays free
        response = await asyncio.to_thread(
            requests.get, "https://api.example.com/data"
        )
        return StopEvent(result=response.json())
```

`asyncio.to_thread`는 함수를 기본 `ThreadPoolExecutor`에 예약하고 awaitable을 반환합니다. Blocking call이 별도 thread에서 실행되는 동안 event loop는 다른 step과 Workflow를 계속 처리합니다.

파일 읽기, 데이터베이스 질의, 외부 API 호출 등 I/O를 수행하는 모든 동기식 library 호출에 같은 방법을 적용할 수 있습니다.

```python
import asyncio
import json
from pathlib import Path
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent


def read_large_file(path: str) -> dict:
    """A synchronous function that reads and parses a large JSON file."""
    return json.loads(Path(path).read_text())


class FileReaderWorkflow(Workflow):
    @step
    async def process_file(self, ev: StartEvent) -> StopEvent:
        data = await asyncio.to_thread(read_large_file, ev.file_path)
        return StopEvent(result=data)
```

## CPU 집약 작업

데이터 변환, 이미지 처리, 수치 계산 같은 CPU-bound 작업은 다른 문제를 일으킵니다. thread에서 실행해도 CPU 집약적인 Python code가 GIL(Global Interpreter Lock)을 두고 event loop와 경쟁할 수 있습니다.

CPU 집약 작업에는 전용의 더 작은 thread pool(또는 process pool)을 사용하세요. 이렇게 하면 해당 작업이 queue에 쌓여 기본 executor를 모두 차지하지 않습니다.

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from workflows import Workflow, step
from workflows.events import Event, StartEvent, StopEvent


# A small, dedicated pool for CPU-bound work.
# Keeping this small ensures CPU tasks are queued rather than
# overwhelming the system with parallel CPU-bound threads.
cpu_pool = ThreadPoolExecutor(max_workers=2)


def expensive_computation(data: str) -> str:
    """A CPU-intensive operation, e.g. data parsing or transformation."""
    # Simulate heavy work
    result = data
    for _ in range(1_000_000):
        result = result.strip()
    return result


class ComputeEvent(Event):
    data: str


class CPUWorkflow(Workflow):
    @step
    async def start(self, ev: StartEvent) -> ComputeEvent:
        return ComputeEvent(data=ev.input_data)

    @step
    async def compute(self, ev: ComputeEvent) -> StopEvent:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(cpu_pool, expensive_computation, ev.data)
        return StopEvent(result=result)
```

I/O 작업과 비교하면 주요 차이는 다음과 같습니다.

- **`loop.run_in_executor` 사용**: `asyncio.to_thread` 대신 executor를 명시합니다. pool의 크기와 종류를 직접 제어할 수 있습니다.
- **pool을 작게 유지**: worker가 1~2개인 pool을 사용하면 CPU 작업이 CPU 시간을 두고 경쟁하지 않고 queue에 쌓입니다. 작업량과 사용 가능한 core 수에 맞춰 조정하세요.
- **`ProcessPoolExecutor` 고려**: GIL 밖에서 실행하고 싶은 순수 CPU-bound 작업에는 `ProcessPoolExecutor`를 고려하세요. API는 같고 executor 종류만 바꾸면 됩니다.

```python
from concurrent.futures import ProcessPoolExecutor

cpu_pool = ProcessPoolExecutor(max_workers=2)
```

`ProcessPoolExecutor`에 전달하는 함수는 pickle 가능해야 합니다. 즉, lambda나 closure가 아니라 top-level function이어야 합니다.

## 요약

| 상황 | 해결 방법 | 이유 |
|---|---|---|
| Step 전체가 동기식 | `async def` 대신 `def`로 step을 정의 | Runtime이 자동으로 thread pool에서 실행 |
| `async def` step 안에서 blocking call 사용 | `await asyncio.to_thread(fn, ...)` | I/O가 thread에서 끝날 때까지 event loop를 다른 작업에 사용 가능 |
| CPU 집약 작업 | 작은 전용 pool과 함께 `await loop.run_in_executor(pool, fn, ...)` 사용 | 무거운 계산이 event loop나 다른 task를 굶기지 않도록 queue에 적재 |

핵심 원칙은 단순합니다. **`asyncio` event loop를 block하지 마세요.** Step 전체가 동기식이면 일반 `def`를 사용해 framework에 thread 처리를 맡기세요. `async def` step 안에서 blocking call을 해야 한다면 thread나 process로 넘기고 결과를 `await`하세요.

---

원문: [Writing async workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/async_workflows/)

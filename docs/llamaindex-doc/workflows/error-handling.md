# Error Handling과 Retry

step 실행이 실패하면 Workflow 전체도 실패할 수 있지만, 오류가 예상 가능한 경우가 많으며 안전하게 재시도할 수 있습니다. 예를 들어 일시적인 네트워크 혼잡으로 HTTP request가 timeout되거나, 외부 API 호출이 rate limiter에 걸릴 수 있습니다.

step을 다시 시도하려면 **retry policy**를 사용합니다. retry policy는 step을 여러 번 실행하도록 지시하며, 각 새 시도 전에 대기할 시간, 재시도할 수 있는 오류, 포기할 시점을 제어합니다.

재시도는 같은 입력 event에 대해 step 본문 전체를 다시 실행합니다. 실패하는 호출 전에 수행하는 side effect는 idempotent하게 유지하거나, 재시도 가능한 작업이 끝난 뒤로 옮기세요. step이 오류를 발생시키기 전에 state를 쓰거나 외부 service를 호출했다면 해당 작업이 다시 실행될 수 있습니다.

retry module은 조합 가능한 세 가지 building block으로 구성됩니다.

- **Retry condition**은 예외를 재시도할 수 있는지 결정합니다.
- **Wait strategy**는 다음 시도 전 대기 시간을 결정합니다.
- **Stop condition**은 Workflow가 언제 포기할지 결정합니다.

이들을 `retry_policy(retry=..., wait=..., stop=...)`로 조합한 뒤 `@step` decorator에 전달합니다. Retry condition은 `|`와 `&`, wait strategy는 `+`, stop condition은 `|`와 `&` 연산자를 지원합니다.

## 기본 사용법

```python
from workflows import Workflow, Context, step
from workflows.events import StartEvent, StopEvent
from workflows.retry_policy import (
    retry_policy,
    stop_after_attempt,
    wait_fixed,
)


class MyWorkflow(Workflow):
    @step(
        retry_policy=retry_policy(
            wait=wait_fixed(5),
            stop=stop_after_attempt(10),
        )
    )
    async def flaky_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        result = flaky_call()  # this might raise
        return StopEvent(result=result)
```

인자를 지정하지 않은 `retry_policy()`는 모든 예외를 최대 3회 시도하고, 각 시도 사이에 5초 고정 지연을 둡니다. 구성 요소를 사용자 지정하려면 `retry=`, `wait=`, `stop=`을 전달하세요.

## 예외 필터링

Retry condition으로 어떤 예외를 재시도할지 제어할 수 있습니다.

```python
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent
from workflows.retry_policy import (
    retry_policy,
    retry_if_exception_message,
    retry_if_exception_type,
    stop_after_attempt,
    stop_before_delay,
    wait_fixed,
    wait_random,
)


class MyWorkflow(Workflow):
    @step(
        retry_policy=retry_policy(
            retry=retry_if_exception_type((TimeoutError, ConnectionError))
            | retry_if_exception_message(match="rate limit|temporarily unavailable"),
            wait=wait_fixed(1) + wait_random(0, 1),
            stop=stop_after_attempt(5) | stop_before_delay(30),
        )
    )
    async def call_provider(self, ev: StartEvent) -> StopEvent:
        result = await flaky_call()
        return StopEvent(result=result)
```

더 명시적인 스타일이 필요하면 이름이 지정된 combinator를 사용할 수 있습니다.

```python
from workflows.retry_policy import (
    retry_policy,
    retry_any,
    retry_if_exception_message,
    retry_if_exception_type,
    stop_any,
    stop_after_attempt,
    stop_before_delay,
    wait_combine,
    wait_fixed,
    wait_random,
)

policy = retry_policy(
    retry=retry_any(
        retry_if_exception_type((TimeoutError, ConnectionError)),
        retry_if_exception_message(match="rate limit|temporarily unavailable"),
    ),
    wait=wait_combine(wait_fixed(1), wait_random(0, 1)),
    stop=stop_any(stop_after_attempt(5), stop_before_delay(30)),
)
```

## Exponential backoff

LLM provider 또는 rate-limited API를 호출하는 step에서는 exponential backoff를 사용해 thundering-herd 현상을 방지할 수 있습니다.

```python
from workflows import Workflow, Context, step
from workflows.events import StartEvent, StopEvent
from workflows.retry_policy import (
    retry_policy,
    stop_after_attempt,
    wait_exponential_jitter,
)


class MyWorkflow(Workflow):
    @step(
        retry_policy=retry_policy(
            wait=wait_exponential_jitter(initial=1, exp_base=2, max=30, jitter=1),
            stop=stop_after_attempt(5),
        )
    )
    async def call_llm(self, ctx: Context, ev: StartEvent) -> StopEvent:
        result = await llm_call()  # this might raise on rate-limit
        return StopEvent(result=result)
```

## 전체 API reference

이 module은 여기에 소개한 것보다 더 많은 retry condition, wait strategy, stop condition을 제공합니다. 전체 building block 목록과 매개변수는 [API reference](https://developers.llamaindex.ai/python/workflows-api-reference/retry_policy/)를 참고하세요.

## Custom retry policy

조합형 API가 사용 사례를 지원하지 않으면 custom policy를 작성할 수 있습니다. `RetryPolicy` protocol과 일치하는 `next` method를 가진 class면 됩니다.

```python
def next(
    self,
    elapsed_time: float,
    attempts: int,
    error: Exception,
    *,
    seed: int | None = None,
) -> float | None:
    ...
```

재시도 전 대기할 초 단위 시간을 반환하거나, 중지하려면 `None`을 반환합니다. `attempts`는 지금까지 실패한 횟수이며 첫 번째 실패부터 1로 시작합니다. 선택적 `seed`는 durable runtime에서 replay 중 jitter를 결정적으로 만들 때 사용됩니다.

예를 들어 다음 policy는 금요일에만 재시도합니다.

```python
from datetime import datetime


class RetryOnFridayPolicy:
    def next(
        self,
        elapsed_time: float,
        attempts: int,
        error: Exception,
        *,
        seed: int | None = None,
    ) -> float | None:
        if datetime.today().strftime("%A") == "Friday":
            return 5  # retry in 5 seconds
        return None  # don't retry
```

## Deprecated convenience constructor

:::caution
`ConstantDelayRetryPolicy`와 `ExponentialBackoffRetryPolicy`는 조합형 API보다 먼저 만들어졌으며, 하위 호환성을 위해서만 유지됩니다. 명시적인 retry, wait, stop 인자를 사용하는 `retry_policy(...)`를 권장합니다.
:::

```python
from workflows.retry_policy import ConstantDelayRetryPolicy

# Deprecated, equivalent to:
#   retry_policy(wait=wait_fixed(5), stop=stop_after_attempt(10))
policy = ConstantDelayRetryPolicy(delay=5, maximum_attempts=10)
```

```python
from workflows.retry_policy import ExponentialBackoffRetryPolicy

# Deprecated, equivalent to:
#   retry_policy(wait=wait_random_exponential(multiplier=1, exp_base=2, max=30),
#                stop=stop_after_attempt(5))
policy = ExponentialBackoffRetryPolicy(
    initial_delay=1, multiplier=2, max_delay=30, maximum_attempts=5,
)
```

## Step 안에서 retry state 확인하기

`Context.retry_info()`는 현재 시도를 설명하는 `RetryInfo`를 반환합니다. 이를 사용해 재시도 사이에 동작을 조정할 수 있습니다. 예를 들어 검색 범위를 넓히거나 timeout을 줄이거나 warning을 기록할 수 있습니다.

```python
from workflows import Context, Workflow, step
from workflows.events import StartEvent, StopEvent
from workflows.retry_policy import retry_policy, stop_after_attempt


class MyWorkflow(Workflow):
    @step(retry_policy=retry_policy(stop=stop_after_attempt(3)))
    async def flaky(self, ctx: Context, ev: StartEvent) -> StopEvent:
        info = ctx.retry_info()
        if info.last_exception is not None:
            logger.warning(
                "retry %d after %s", info.retry_number, str(info.last_exception)
            )
        ...
```

첫 실행에서 `retry_number`는 `0`입니다. 첫 실패 전까지 `last_exception`과 `last_failed_at`은 `None`이며, 실패가 발생한 뒤에는 가장 최근의 이전 실패를 설명합니다.

## Retry 소진 후 복구하기

Policy가 포기하면 예외가 전파되어 Workflow가 실패합니다. 단, `@catch_error` handler가 선언된 경우는 예외입니다. `StepFailedEvent`를 받는 step인 handler는 `StopEvent`를 반환해 실행을 정상 종료하거나, 다른 event를 반환해 Workflow를 다른 경로로 보내거나, 새 예외를 발생시켜 실패시킬 수 있습니다. 판단에 `ev.step_name`과 `ev.exception`을 사용하세요. 전체 field 목록은 [`StepFailedEvent` API reference](https://developers.llamaindex.ai/python/workflows-api-reference/events/#workflows.events.StepFailedEvent)를 참고하세요.

```python
from workflows import Context, Workflow, catch_error, step
from workflows.events import StartEvent, StepFailedEvent, StopEvent
from workflows.retry_policy import retry_policy, stop_after_attempt, wait_fixed


class Pipeline(Workflow):
    @step(retry_policy=retry_policy(wait=wait_fixed(1), stop=stop_after_attempt(3)))
    async def fetch(self, ev: StartEvent) -> StopEvent:
        return StopEvent(result=await call_api())

    @catch_error
    async def on_failure(
        self, ctx: Context, ev: StepFailedEvent
    ) -> StopEvent:
        return StopEvent(
            result={"failed_step": ev.step_name, "error": str(ev.exception)}
        )
```

인자 없는 `@catch_error`는 **wildcard** handler입니다. retry가 소진된 모든 step 중 더 구체적인 handler가 맡지 않은 오류를 잡습니다. Workflow마다 wildcard는 하나만 허용됩니다.

### 특정 step에 범위 지정하기

handler가 담당할 step을 제한하려면 `for_steps=[...]`를 전달합니다. 하나의 step 이름은 최대 하나의 범위 지정 handler에만 포함될 수 있으며, 알 수 없는 이름은 Workflow 생성 시 거부됩니다.

```python
class Pipeline(Workflow):
    @step(retry_policy=...)
    async def fetch(self, ev: StartEvent) -> FetchedEvent: ...

    @step(retry_policy=...)
    async def parse(self, ev: FetchedEvent) -> StopEvent: ...

    @catch_error(for_steps=["fetch"])
    async def on_fetch_failure(
        self, ctx: Context, ev: StepFailedEvent
    ) -> StopEvent:
        return StopEvent(result={"fallback": True})

    @catch_error  # wildcard; covers `parse` and anything else
    async def on_any_failure(
        self, ctx: Context, ev: StepFailedEvent
    ) -> StopEvent:
        return StopEvent(result={"aborted": ev.step_name})
```

### Recovery budget

handler가 그래프로 다시 전달되는 event를 발생시키면 하나의 lineage가 같은 handler에 다시 들어올 수 있습니다. `max_recoveries`(기본값 `1`)는 Workflow가 재진입 대신 실패하기 전에 event lineage별로 허용할 횟수를 제한합니다. 제한된 retry loop에 참여하는 handler에는 더 큰 값을 지정하고, 종료용 handler에는 `1`을 유지하세요.

```python
@catch_error(for_steps=["fetch", "retry_fetch"], max_recoveries=2)
async def on_failure(self, ctx: Context, ev: StepFailedEvent) -> RetryFetch:
    return RetryFetch()
```

출처: [Retry steps — LlamaIndex Workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/retry_steps/)

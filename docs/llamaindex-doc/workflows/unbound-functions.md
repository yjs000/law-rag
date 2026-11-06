# Unbound function으로 Workflow 만들기

대부분의 예제에서는 `Workflow` 하위 class의 method로 step을 정의합니다. `@step(workflow=...)`를 사용해 독립 function을 Workflow class에 연결할 수도 있습니다. 재사용 가능한 function으로 Workflow를 조립하거나, integration에서 Workflow를 상속하지 않고 step을 추가하려 할 때 유용합니다.

먼저 step을 담을 빈 class를 만듭니다.

```python
from workflows import Workflow


class TestWorkflow(Workflow):
    pass
```

이제 function을 정의하고 `@step()` decorator로 꾸며 Workflow에 step을 추가합니다.

```python
from workflows import step
from workflows.events import StartEvent, StopEvent


@step(workflow=TestWorkflow)
async def some_step(ev: StartEvent) -> StopEvent:
    return StopEvent()
```

이 예제에서 decorator는 `some_step`을 `TestWorkflow` class에 등록합니다. `self` 매개변수가 없다는 점을 제외하면 function signature는 method로 정의한 step과 같습니다.

등록은 import 시점에 이루어집니다. Workflow를 instantiate하거나 validate하기 전에 function을 정의한 module이 import되었는지 확인하세요. Step 이름은 여전히 고유해야 합니다. 기존 method 또는 free-function step과 같은 이름의 free function을 등록하면 validation 오류가 발생합니다.

---

원문: [Workflows from unbound functions](https://developers.llamaindex.ai/python/llamaagents/workflows/unbound_functions/)

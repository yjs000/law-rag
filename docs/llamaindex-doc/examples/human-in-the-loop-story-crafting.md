# 직접 선택하는 모험 Workflow (Human In The Loop)

일부 Workflow 애플리케이션에서는 실행 과정에 사람이 참여하는 것이 바람직하거나 필수일 수 있습니다. 예를 들어 Workflow의 한 step을 실행하는 데 사람의 전문 지식이나 입력이 필요할 수 있습니다. 또는 Workflow의 첫 출력 결과를 사람이 검증해야 할 수도 있습니다.

이 노트북에서는 Workflows로 human-in-the-loop 패턴을 구현하는 방법을 보여줍니다. LLM이 이야기 한 구간과 선택 가능한 행동을 만들고, 사람은 그중 하나를 골라야 하는 Choose Your Own Adventure 형식의 이야기를 생성하는 Workflow를 만듭니다.

## LLM으로 이야기 구간 생성

여기서는 LLM이 구조화된 출력을 생성하는 기능을 사용합니다. LLM에 앞서 생성된 이야기 구간과 행동 선택을 이어서 이야기의 다음 구간을 만들도록 요청합니다.

```
from typing import Any, List


from llama_index.llms.openai import OpenAI
from llama_index.core.bridge.pydantic import BaseModel, Field
from llama_index.core.prompts import PromptTemplate
```

```
class Segment(BaseModel):
    """Data model for generating segments of a story."""


    plot: str = Field(
        description="The plot of the adventure for the current segment. The plot should be no longer than 3 sentences."
    )
    actions: List[str] = Field(
        default=[],
        description="The list of actions the protaganist can take that will shape the plot and actions of the next segment.",
    )
```

```
SEGMENT_GENERATION_TEMPLATE = """
You are working with a human to create a story in the style of choose your own adventure.


The human is playing the role of the protaganist in the story which you are tasked to
help write. To create the story, we do it in steps, where each step produces a BLOCK.
Each BLOCK consists of a PLOT, a set of ACTIONS that the protaganist can take, and the
chosen ACTION.


Below we attach the history of the adventure so far.


PREVIOUS BLOCKS:
---
{running_story}


Continue the story by generating the next block's PLOT and set of ACTIONs. If there are
no previous BLOCKs, start an interesting brand new story. Give the protaganist a name and an
interesting challenge to solve.




Use the provided data model to structure your output.
"""
```

```
FINAL_SEGMENT_GENERATION_TEMPLATE = """
You are working with a human to create a story in the style of choose your own adventure.


The human is playing the role of the protaganist in the story which you are tasked to
help write. To create the story, we do it in steps, where each step produces a BLOCK.
Each BLOCK consists of a PLOT, a set of ACTIONS that the protaganist can take, and the
chosen ACTION. Below we attach the history of the adventure so far.


PREVIOUS BLOCKS:
---
{running_story}


The story is now coming to an end. With the previous blocks, wrap up the story with a
closing PLOT. Since it is a closing plot, DO NOT GENERATE a new set of actions.


Use the provided data model to structure your output.
"""
```

```
# Let's see an example segment
llm = OpenAI("gpt-4o")
segment = llm.structured_predict(
    Segment,
    PromptTemplate(SEGMENT_GENERATION_TEMPLATE),
    running_story="",
)
```

```
segment
```

```
Segment(plot="In the bustling city of Eldoria, a young adventurer named Aric discovered a mysterious map hidden inside an old bookshop. The map hinted at a hidden treasure buried deep within the enchanted Whispering Woods. Intrigued and eager for adventure, Aric decided to follow the map's clues.", actions=['Follow the map to the Whispering Woods', 'Seek advice from the old bookshop owner', 'Gather supplies for the journey', 'Ignore the map and continue with daily life'])
```

### 이전 구간 이어 붙이기

이야기 구간들을 이어 붙여 `running_story` 값으로 prompt에 전달해야 합니다. 각 `Segment`와 선택한 행동을 보관하는 `Block` data class를 정의합니다.

```
import uuid
from typing import Optional


BLOCK_TEMPLATE = """
BLOCK
===
PLOT: {plot}
ACTIONS: {actions}
CHOICE: {choice}
"""




class Block(BaseModel):
    id_: str = Field(default_factory=lambda: str(uuid.uuid4()))
    segment: Segment
    choice: Optional[str] = None
    block_template: str = BLOCK_TEMPLATE


    def __str__(self):
        return self.block_template.format(
            plot=self.segment.plot,
            actions=", ".join(self.segment.actions),
            choice=self.choice or "",
        )
```

```
block = Block(segment=segment)
print(block)
```

```
BLOCK
===
PLOT: In the bustling city of Eldoria, a young adventurer named Aric discovered a mysterious map hidden inside an old bookshop. The map hinted at a hidden treasure buried deep within the enchanted Whispering Woods. Intrigued and eager for adventure, Aric decided to follow the map's clues.
ACTIONS: Follow the map to the Whispering Woods, Seek advice from the old bookshop owner, Gather supplies for the journey, Ignore the map and continue with daily life
CHOICE:
```

## Choose Your Own Adventure Workflow 만들기

이 Workflow는 최대 단계 수, 즉 생성할 구간 수에 도달할 때까지 반복되는 두 개의 step으로 구성됩니다. 첫 번째 step에서는 LLM이 새로운 `Segment`를 만듭니다. 이 `Segment`를 사용해 새로운 이야기 `Block`을 생성합니다. 두 번째 step에서는 새로 만들어진 `Segment`에 지정된 행동 목록 중에서 사람이 선택하도록 요청합니다.

```
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
```

```
class NewBlockEvent(Event):
    block: Block




class HumanChoiceEvent(Event):
    block_id: str
```

```
class ChooseYourOwnAdventureWorkflow(Workflow):
    def __init__(self, max_steps: int = 3, **kwargs):
        super().__init__(**kwargs)
        self.llm = OpenAI("gpt-4o")
        self.max_steps = max_steps


    @step
    async def create_segment(
        self, ctx: Context, ev: StartEvent | HumanChoiceEvent
    ) -> NewBlockEvent | StopEvent:
        blocks = await ctx.store.get("blocks", [])
        running_story = "\n".join(str(b) for b in blocks)


        if len(blocks) < self.max_steps:
            new_segment = self.llm.structured_predict(
                Segment,
                PromptTemplate(SEGMENT_GENERATION_TEMPLATE),
                running_story=running_story,
            )
            new_block = Block(segment=new_segment)
            blocks.append(new_block)
            await ctx.store.set("blocks", blocks)
            return NewBlockEvent(block=new_block)
        else:
            final_segment = self.llm.structured_predict(
                Segment,
                PromptTemplate(FINAL_SEGMENT_GENERATION_TEMPLATE),
                running_story=running_story,
            )
            final_block = Block(segment=final_segment)
            blocks.append(final_block)
            return StopEvent(result=blocks)


    @step
    async def prompt_human(
        self, ctx: Context, ev: NewBlockEvent
    ) -> HumanChoiceEvent:
        block = ev.block


        # get human input
        human_prompt = f"\n===\n{ev.block.segment.plot}\n\n"
        human_prompt += "Choose your adventure:\n\n"
        human_prompt += "\n".join(ev.block.segment.actions)
        human_prompt += "\n\n"
        human_input = input(human_prompt)


        blocks = await ctx.store.get("blocks")
        block.choice = human_input
        blocks[-1] = block
        await ctx.store.set("block", blocks)


        return HumanChoiceEvent(block_id=ev.block.id_)
```

### Workflow 실행

Workflow는 비동기 실행을 기본으로 하므로 노트북에서는 이 코드가 그대로 실행됩니다. 직접 작성한 코드에서 실행하는 경우에는 이미 비동기 이벤트 루프가 실행 중이 아니라면 `asyncio.run()`을 사용해 시작해야 합니다.

```
async def main():
    <async code>


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

```
import nest_asyncio


nest_asyncio.apply()
```

```
w = ChooseYourOwnAdventureWorkflow(timeout=None)
```

```
result = await w.run()
```

```
===
In the bustling city of Eldoria, a young adventurer named Aric discovered a mysterious map hidden in an old bookshop. The map hinted at a hidden treasure buried deep within the Whispering Woods, a place known for its eerie silence and ancient secrets. Determined to uncover the treasure, Aric set off on his journey, leaving the city behind.


Choose your adventure:


Follow the map into the Whispering Woods
Seek help from a local guide
Study the map for hidden clues


 Seek help from a local guide


===
Aric found a seasoned guide named Elara, who knew the Whispering Woods like the back of her hand. Elara agreed to help Aric, intrigued by the promise of hidden treasure. Together, they ventured into the forest, the map leading them to a fork in the path where the trees seemed to whisper secrets.


Choose your adventure:


Take the left path
Take the right path
Ask Elara for advice


 Ask Elara for advice


===
Elara examined the map closely and listened to the whispers of the trees. She suggested taking the left path, as it seemed to align with the ancient markings on the map. Trusting her expertise, Aric and Elara proceeded down the left path, where the forest grew denser and the air filled with an eerie stillness.


Choose your adventure:


Continue down the left path
Turn back and take the right path
Look for hidden clues along the path


 Look for hidden clues along the path
```

### 최종 이야기 출력

```
final_story = "\n\n".join(b.segment.plot for b in result)
print(final_story)
```

```
In the bustling city of Eldoria, a young adventurer named Aric discovered a mysterious map hidden in an old bookshop. The map hinted at a hidden treasure buried deep within the Whispering Woods, a place known for its eerie silence and ancient secrets. Determined to uncover the treasure, Aric set off on his journey, leaving the city behind.


Aric found a seasoned guide named Elara, who knew the Whispering Woods like the back of her hand. Elara agreed to help Aric, intrigued by the promise of hidden treasure. Together, they ventured into the forest, the map leading them to a fork in the path where the trees seemed to whisper secrets.


Elara examined the map closely and listened to the whispers of the trees. She suggested taking the left path, as it seemed to align with the ancient markings on the map. Trusting her expertise, Aric and Elara proceeded down the left path, where the forest grew denser and the air filled with an eerie stillness.


As Aric and Elara searched for hidden clues along the dense path, they stumbled upon an ancient stone altar covered in moss and vines. Upon closer inspection, they discovered a hidden compartment within the altar containing the long-lost treasure—a chest filled with gold, jewels, and ancient artifacts. With their mission complete, Aric and Elara returned to Eldoria, their bond strengthened by the adventure and their hearts filled with the thrill of discovery.
```

### Human In The Loop를 구현하는 다른 방법

사람의 입력을 수집하는 별도의 Workflow를 만들고 nested Workflow를 사용하는 방법으로도 human-in-the-loop를 구현할 수 있습니다. 사람의 입력을 받는 기능을 Workflow의 나머지 부분과 별도 서비스로 분리해야 할 때 이 설계를 사용할 수 있습니다. 예를 들어 nested Workflow를 `llama-deploy`로 배포하면 이런 구성이 됩니다.

원문: [Human in the Loop: Story Crafting — LlamaIndex](https://developers.llamaindex.ai/python/examples/workflow/human_in_the_loop_story_crafting/)

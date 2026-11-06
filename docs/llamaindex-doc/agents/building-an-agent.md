# 에이전트 만들기

LlamaIndex에서 agent는 LLM이 구동하는 반자율형 소프트웨어로, 작업을 받아 해결을 향한 여러 단계를 수행합니다. agent에는 도구가 제공됩니다. 도구는 임의의 함수부터 LlamaIndex query engine까지 무엇이든 될 수 있으며, agent는 각 단계를 완료하는 데 가장 적합한 도구를 선택합니다. 각 단계가 끝나면 agent는 작업이 완료되어 사용자에게 결과를 반환할지, 아니면 다음 단계를 더 수행해야 하므로 처음으로 돌아갈지 판단합니다.

LlamaIndex에서는 [agentic Workflow를 처음부터 직접 만들거나](../workflows/README.md), `FunctionAgent`(간단한 function/tool calling agent) 또는 `AgentWorkflow`(여러 agent를 관리할 수 있는 agent) 같은 사전 구축된 agentic Workflow를 사용할 수 있습니다. 이 튜토리얼에서는 `FunctionAgent`로 function calling agent를 만드는 방법을 다룹니다.

multi-agent 시스템을 만드는 여러 방법은 [Multi-agent systems](https://developers.llamaindex.ai/python/framework/understanding/agent/multi_agent/) 문서를 참고하세요.

![agent 흐름](https://developers.llamaindex.ai/_astro/agent_flow.CYyT8PAN_EDU2I.png?dpl=dpl_6m4kx998VjssYTMc17BxzNwMwcb9)

## 시작하기

이 코드 전체는 [agents 튜토리얼 저장소](https://github.com/run-llama/python-agents-tutorial)에서 확인할 수 있습니다.

충돌을 피하고 작업 환경을 깔끔하게 유지하기 위해 새 Python virtual environment를 만들겠습니다. 어떤 virtual environment manager든 사용할 수 있지만 여기서는 `poetry`를 사용합니다.

```console
poetry init
poetry shell
```

이제 LlamaIndex library와 유용한 종속성을 설치합니다.

```console
pip install llama-index-core llama-index-llms-openai python-dotenv
```

여기서 문제가 발생하면 더 자세한 [설치 안내](https://developers.llamaindex.ai/python/framework/getting_started/installation/)를 참고하세요.

## OpenAI Key

agent는 OpenAI의 `gpt-4o-mini` LLM으로 구동할 예정이므로 [API key](https://platform.openai.com/)가 필요합니다. key를 준비한 뒤 프로젝트 root의 `.env` 파일에 넣을 수 있습니다.

```dotenv
OPENAI_API_KEY=sk-proj-xxxx
```

OpenAI를 사용하고 싶지 않다면 local model을 포함해 [다른 LLM](https://developers.llamaindex.ai/python/framework/understanding/using_llms/)을 사용할 수 있습니다. agent에는 성능이 충분한 model이 필요하므로 작은 model은 신뢰성이 낮을 수 있습니다.

## 종속성 가져오기

필요한 LlamaIndex component를 import하고 `.env` 파일에서 environment variable을 불러옵니다.

```python
from dotenv import load_dotenv


load_dotenv()


from llama_index.llms.openai import OpenAI
from llama_index.core.agent.workflow import FunctionAgent
```

## 기본 도구 만들기

이 간단한 예제에서는 숫자를 곱하는 도구와 더하는 도구 두 개를 만듭니다.

```python
def multiply(a: float, b: float) -> float:
    """Multiply two numbers and returns the product"""
    return a * b




def add(a: float, b: float) -> float:
    """Add two numbers and returns the sum"""
    return a + b
```

보시다시피 일반적인 Python function입니다. agent는 사용할 도구를 결정할 때 도구 이름, parameter, docstring을 이용해 도구가 어떤 일을 하며 지금 작업에 적절한지 판단합니다. 따라서 docstring은 설명이 명확하고 유용해야 합니다. type hint도 예상 parameter와 return type을 파악하는 데 사용합니다.

## LLM 초기화

이번 예제의 작업은 `gpt-4o-mini`가 수행합니다.

```python
llm = OpenAI(model="gpt-4o-mini")
```

API로 사용할 수 있는 다른 인기 model, 예를 들면 [Mistral](https://developers.llamaindex.ai/python/examples/llm/mistralai/), [Anthropic의 Claude](https://developers.llamaindex.ai/python/examples/llm/anthropic/), [Google의 Gemini](https://developers.llamaindex.ai/python/examples/llm/google_genai/)를 선택할 수도 있습니다.

## Agent 초기화

이제 agent를 만듭니다. agent에는 도구 배열, LLM, 그리고 agent의 역할을 알려주는 system prompt가 필요합니다. 실제 system prompt는 보통 여기보다 구체적이어야 합니다.

```python
workflow = FunctionAgent(
    tools=[multiply, add],
    llm=llm,
    system_prompt="You are an agent that can perform basic mathematical operations using tools.",
)
```

GPT-4o-mini는 이렇게 간단한 수학에는 도구가 필요 없을 정도로 똑똑합니다. 그래서 prompt에서 도구를 사용하라고 지정했습니다.

`FunctionAgent` 외에도 LlamaIndex에는 `ReActAgent`와 `CodeActAgent` 같은 agent가 있습니다. 이들은 서로 다른 prompting strategy를 사용해 도구를 실행합니다.

## 질문하기

이제 agent에게 수학 문제를 요청할 수 있습니다.

```python
response = await workflow.run(user_msg="What is 20+(2*4)?")
print(response)
```

이 코드는 비동기식입니다. notebook 환경에서는 실행할 수 있지만 일반 Python에서 실행하려면 다음처럼 asynchronous function으로 감싸야 합니다.

```python
async def main():
    response = await workflow.run(user_msg="What is 20+(2*4)?")
    print(response)




if __name__ == "__main__":
    import asyncio


    asyncio.run(main())
```

다음과 비슷한 결과가 출력됩니다.

```text
The result of (20 + (2 times 4)) is 28.
```

Tip

일부 model은 streaming LLM output을 지원하지 않을 수 있습니다. streaming은 기본적으로 활성화되어 있지만 오류가 발생하면 `FunctionAgent(..., streaming=False)`로 비활성화할 수 있습니다.

최종 코드 형태는 [저장소의 예제](https://github.com/run-llama/python-agents-tutorial/blob/main/1_basic_agent.py)에서 확인하세요.

축하합니다! 가장 기본적인 형태의 agent를 만들었습니다. 다음으로 [사전 구축된 도구](https://developers.llamaindex.ai/python/framework/understanding/agent/tools/)를 알아보세요.

원문: [Building an agent — LlamaIndex](https://developers.llamaindex.ai/python/framework/understanding/agent/)

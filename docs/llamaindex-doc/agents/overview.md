# Agents

“agent”는 자동화된 추론 및 의사결정 엔진입니다. 사용자 입력이나 질문을 받아 그에 맞는 결과를 반환하기 위해 내부 결정을 내릴 수 있습니다. agent의 주요 구성 요소는 다음을 포함할 수 있으며, 이에 한정되지 않습니다.

- 복잡한 질문을 더 작은 질문으로 나누기
- 사용할 외부 도구를 선택하고 호출 parameter 정하기
- 작업 집합 계획하기
- memory module에 이전에 완료한 작업 저장하기

LlamaIndex는 다양한 복잡도의 agentic 시스템을 구축할 수 있는 포괄적인 framework를 제공합니다.

- **빠르게 agent를 만들고 싶다면**: 사전 구축된 [agent](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/)와 [tool](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/tools/) architecture를 사용해 agentic 시스템을 빠르게 구성할 수 있습니다.
- **agentic 시스템을 완전히 제어하고 싶다면**: [Workflows](https://developers.llamaindex.ai/python/framework/module_guides/workflow/)를 사용해 처음부터 custom agentic Workflow를 만들고 배포할 수 있습니다.

## 사용 사례

agent의 사용 사례는 매우 넓고 계속 확장되고 있습니다. 지금 바로 실질적인 가치를 얻을 수 있는 사용 사례는 다음과 같습니다.

- **Agentic RAG**: 데이터에 기반한 context-augmented research assistant를 만들어 단순한 질문뿐 아니라 복잡한 연구 작업에도 답합니다. [시작 안내](https://developers.llamaindex.ai/python/framework/getting_started/starter_example/)에서 시작할 수 있습니다.
- **Report generation**: multi-agent researcher와 writer Workflow, LlamaParse를 사용해 multimodal report를 생성합니다. [Notebook](https://github.com/run-llama/llama_cloud_services/examples/parse/multimodal/multimodal_report_generation_agent.ipynb)을 참고하세요.
- **Customer support**: Workflows를 사용해 multi-agent concierge를 만드는 [starter template](https://github.com/run-llama/multi-agent-concierge/)을 참고하세요.

그 밖의 예:

- **Productivity assistant**: email, calendar처럼 일반적인 Workflow 도구를 처리하는 agent입니다. [GSuite agent 튜토리얼](https://github.com/run-llama/llama_index/blob/main/llama-index-integrations/tools/llama-index-tools-google/examples/advanced_tools_usage.ipynb)을 참고하세요.
- **Coding assistant**: 코드에 대해 작업할 수 있는 agent입니다. [code interpreter 튜토리얼](https://github.com/run-llama/llama_index/blob/main/llama-index-integrations/tools/llama-index-tools-code-interpreter/examples/code_interpreter.ipynb)을 참고하세요.

## 자료

**사전 구축된 Agent와 Tool**

agent를 시작하는 데 필요한 중심 component guide입니다.

- [Agents](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/)
- [Tools](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/tools/)

**Custom Agentic Workflow**

LlamaIndex Workflows는 event-driven orchestration 기반을 제공해 높은 수준으로 사용자 지정할 수 있는 agentic Workflow를 만듭니다.

- [Workflows 문서](../workflows/README.md)
- [ReAct agent Workflow 만들기](https://developers.llamaindex.ai/python/examples/workflow/react_agent/)
- [Workflow 배포](https://developers.llamaindex.ai/python/llamaagents/llamactl/getting-started/)

**Agent 구성 요소로 만들기**

Workflow에 agent의 핵심 요소를 사용하고 싶다면 LlamaIndex는 각 agent 하위 요소에 대한 강력한 abstraction을 제공합니다.

- **Query planning**: [Routing](https://developers.llamaindex.ai/python/framework/module_guides/querying/router/), [Sub-Questions](https://developers.llamaindex.ai/python/examples/query_engine/sub_question_query_engine/), [Query Transformations](https://developers.llamaindex.ai/python/framework/optimizing/advanced_retrieval/query_transformations/)
- **Function calling과 Tool use**: 예시로 [OpenAI](https://developers.llamaindex.ai/python/examples/llm/openai/), [Mistral](https://developers.llamaindex.ai/python/examples/llm/mistralai/) 안내를 확인하세요.

## Ecosystem

- **커뮤니티 제작 Agent**: [tool integrations](https://github.com/run-llama/llama_index/tree/main/llama-index-integrations/tools)에서 agent와 함께 사용할 수 있는 40개 이상의 agent tool을 제공합니다.

원문: [Agents — LlamaIndex](https://developers.llamaindex.ai/python/framework/use_cases/agents/)

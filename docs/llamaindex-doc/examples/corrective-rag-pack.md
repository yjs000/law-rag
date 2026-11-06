# Corrective RAG Workflow

이 노트북에서는 [이 논문](https://arxiv.org/abs/2401.15884)을 바탕으로 LlamaIndex Workflows를 사용해 Corrective RAG를 구현하는 방법을 보여줍니다.

논문의 핵심을 간단히 살펴보겠습니다.

Corrective Retrieval Augmented Generation (CRAG)은 evaluator를 통해 검색된 문서의 관련성을 평가하고 보완하며, 대규모 웹 검색을 활용해 언어 모델 생성의 견고성을 높이는 방법입니다. 이를 통해 생성 과정에서 더 정확하고 신뢰할 수 있는 정보를 사용합니다.

여기서는 관련성 평가기로 `GPT-4`를, 웹 검색에는 `Tavily AI`를 사용합니다. 따라서 진행하기 전에 `OPENAI_API_KEY`와 `tavily_ai_api_key`를 준비하는 것을 권장합니다.

```
import nest_asyncio


nest_asyncio.apply()
```

```
%pip install -U llama-index llama-index-tools-tavily-research
```

```
import os


os.environ["OPENAI_API_KEY"] = "sk-proj-..."
tavily_ai_api_key = "<Your Tavily AI API Key>"
```

```
!mkdir -p 'data/'
!wget 'https://arxiv.org/pdf/2307.09288.pdf' -O 'data/llama2.pdf'
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

Corrective RAG는 다음 단계로 구성됩니다.

1. 데이터 수집 — 데이터를 index에 적재하고 Tavily AI를 설정합니다. 수집 단계는 start event를 받아 stop event를 반환하며 별도로 실행합니다.
2. 검색 — query를 바탕으로 가장 관련성이 높은 nodes를 검색합니다.
3. 관련성 평가 — LLM이 nodes의 내용을 고려해 검색된 nodes가 query와 관련 있는지 판단합니다.
4. 관련 텍스트 추출 — LLM이 관련 있다고 판단한 nodes를 추출합니다.
5. Query 변환 및 Tavily 검색 — node가 관련 없으면 LLM이 웹 검색에 맞게 query를 변환합니다. Tavily로 query에 맞는 답을 웹에서 검색합니다.
6. 응답 생성 — 관련 nodes와 Tavily 검색에서 얻은 텍스트로 SummaryIndex를 만들고, 원래 query에 대한 결과를 가져옵니다.

다음 event가 필요합니다.

1. `PrepEvent` — index와 기타 객체가 준비되었음을 나타냅니다.
2. `RetrieveEvent` — 검색된 nodes 정보를 담습니다.
3. `RelevanceEvalEvent` — 관련성 평가 결과 목록을 담습니다.
4. `TextExtractEvent` — 관련 nodes에서 추출한 텍스트를 연결한 문자열을 담습니다.
5. `QueryEvent` — 관련 텍스트와 검색용 텍스트를 함께 담습니다.

```
from llama_index.core.workflow import Event
from llama_index.core.schema import NodeWithScore




class PrepEvent(Event):
    """Prep event (prepares for retrieval)."""


    pass




class RetrieveEvent(Event):
    """Retrieve event (gets retrieved nodes)."""


    retrieved_nodes: list[NodeWithScore]




class RelevanceEvalEvent(Event):
    """Relevance evaluation event (gets results of relevance evaluation)."""


    relevant_results: list[str]




class TextExtractEvent(Event):
    """Text extract event. Extracts relevant text and concatenates."""


    relevant_text: str




class QueryEvent(Event):
    """Query event. Queries given relevant text and search text."""


    relevant_text: str
    search_text: str
```

다음은 Corrective RAG Workflow 코드입니다.

```
from llama_index.core.workflow import (
    Workflow,
    step,
    Context,
    StartEvent,
    StopEvent,
)
from llama_index.core import (
    VectorStoreIndex,
    Document,
    PromptTemplate,
    SummaryIndex,
)
from llama_index.llms.openai import OpenAI
from llama_index.tools.tavily_research.base import TavilyToolSpec
from llama_index.core.base.base_retriever import BaseRetriever


DEFAULT_RELEVANCY_PROMPT_TEMPLATE = PromptTemplate(
    template="""As a grader, your task is to evaluate the relevance of a document retrieved in response to a user's question.


    Retrieved Document:
    -------------------
    {context_str}


    User Question:
    --------------
    {query_str}


    Evaluation Criteria:
    - Consider whether the document contains keywords or topics related to the user's question.
    - The evaluation should not be overly stringent; the primary objective is to identify and filter out clearly irrelevant retrievals.


    Decision:
    - Assign a binary score to indicate the document's relevance.
    - Use 'yes' if the document is relevant to the question, or 'no' if it is not.


    Please provide your binary score ('yes' or 'no') below to indicate the document's relevance to the user question."""
)


DEFAULT_TRANSFORM_QUERY_TEMPLATE = PromptTemplate(
    template="""Your task is to refine a query to ensure it is highly effective for retrieving relevant search results. \n
    Analyze the given input to grasp the core semantic intent or meaning. \n
    Original Query:
    \n ------- \n
    {query_str}
    \n ------- \n
    Your goal is to rephrase or enhance this query to improve its search performance. Ensure the revised query is concise and directly aligned with the intended search objective. \n
    Respond with the optimized query only:"""
)




class CorrectiveRAGWorkflow(Workflow):
    @step
    async def ingest(self, ctx: Context, ev: StartEvent) -> StopEvent | None:
        """Ingest step (for ingesting docs and initializing index)."""
        documents: list[Document] | None = ev.get("documents")


        if documents is None:
            return None


        index = VectorStoreIndex.from_documents(documents)


        return StopEvent(result=index)


    @step
    async def prepare_for_retrieval(
        self, ctx: Context, ev: StartEvent
    ) -> PrepEvent | None:
        """Prepare for retrieval."""


        query_str: str | None = ev.get("query_str")
        retriever_kwargs: dict | None = ev.get("retriever_kwargs", {})


        if query_str is None:
            return None


        tavily_ai_apikey: str | None = ev.get("tavily_ai_apikey")
        index = ev.get("index")


        llm = OpenAI(model="gpt-4")


        await ctx.store.set("llm", llm)
        await ctx.store.set("index", index)
        await ctx.store.set(
            "tavily_tool", TavilyToolSpec(api_key=tavily_ai_apikey)
        )


        await ctx.store.set("query_str", query_str)
        await ctx.store.set("retriever_kwargs", retriever_kwargs)


        return PrepEvent()


    @step
    async def retrieve(
        self, ctx: Context, ev: PrepEvent
    ) -> RetrieveEvent | None:
        """Retrieve the relevant nodes for the query."""
        query_str = await ctx.store.get("query_str")
        retriever_kwargs = await ctx.store.get("retriever_kwargs")


        if query_str is None:
            return None


        index = await ctx.store.get("index", default=None)
        tavily_tool = await ctx.store.get("tavily_tool", default=None)
        if not (index or tavily_tool):
            raise ValueError(
                "Index and tavily tool must be constructed. Run with 'documents' and 'tavily_ai_apikey' params first."
            )


        retriever: BaseRetriever = index.as_retriever(**retriever_kwargs)
        result = retriever.retrieve(query_str)
        await ctx.store.set("retrieved_nodes", result)
        await ctx.store.set("query_str", query_str)
        return RetrieveEvent(retrieved_nodes=result)


    @step
    async def eval_relevance(
        self, ctx: Context, ev: RetrieveEvent
    ) -> RelevanceEvalEvent:
        """Evaluate relevancy of retrieved documents with the query."""
        retrieved_nodes = ev.retrieved_nodes
        query_str = await ctx.store.get("query_str")


        relevancy_results = []
        for node in retrieved_nodes:
            llm = await ctx.store.get("llm")
            resp = await llm.acomplete(
                DEFAULT_RELEVANCY_PROMPT_TEMPLATE.format(
                    context_str=node.text, query_str=query_str
                )
            )
            relevancy_results.append(resp.text.lower().strip())


        await ctx.store.set("relevancy_results", relevancy_results)
        return RelevanceEvalEvent(relevant_results=relevancy_results)


    @step
    async def extract_relevant_texts(
        self, ctx: Context, ev: RelevanceEvalEvent
    ) -> TextExtractEvent:
        """Extract relevant texts from retrieved documents."""
        retrieved_nodes = await ctx.store.get("retrieved_nodes")
        relevancy_results = ev.relevant_results


        relevant_texts = [
            retrieved_nodes[i].text
            for i, result in enumerate(relevancy_results)
            if result == "yes"
        ]


        result = "\n".join(relevant_texts)
        return TextExtractEvent(relevant_text=result)


    @step
    async def transform_query(
        self, ctx: Context, ev: TextExtractEvent
    ) -> QueryEvent:
        """Search the transformed query with Tavily API."""
        relevant_text = ev.relevant_text
        relevancy_results = await ctx.store.get("relevancy_results")
        query_str = await ctx.store.get("query_str")


        # If any document is found irrelevant, transform the query string for better search results.
        if "no" in relevancy_results:
            llm = await ctx.store.get("llm")
            resp = await llm.acomplete(
                DEFAULT_TRANSFORM_QUERY_TEMPLATE.format(query_str=query_str)
            )
            transformed_query_str = resp.text
            # Conduct a search with the transformed query string and collect the results.
            tavily_tool = await ctx.store.get("tavily_tool")
            search_results = tavily_tool.search(
                transformed_query_str, max_results=5
            )
            search_text = "\n".join([result.text for result in search_results])
        else:
            search_text = ""


        return QueryEvent(relevant_text=relevant_text, search_text=search_text)


    @step
    async def query_result(self, ctx: Context, ev: QueryEvent) -> StopEvent:
        """Get result with relevant text."""
        relevant_text = ev.relevant_text
        search_text = ev.search_text
        query_str = await ctx.store.get("query_str")


        documents = [Document(text=relevant_text + "\n" + search_text)]
        index = SummaryIndex.from_documents(documents)
        query_engine = index.as_query_engine()
        result = query_engine.query(query_str)
        return StopEvent(result=result)
```

## Workflow 실행

```
from llama_index.core import SimpleDirectoryReader


documents = SimpleDirectoryReader("./data").load_data()
workflow = CorrectiveRAGWorkflow()
index = await workflow.run(documents=documents)
```

```
from IPython.display import Markdown, display


response = await workflow.run(
    query_str="How was Llama2 pretrained?",
    index=index,
    tavily_ai_apikey=tavily_ai_api_key,
)
display(Markdown(str(response)))
```

Llama 2는 성능을 높이기 위해 여러 변경을 적용한 최적화된 auto-regressive transformer를 사용해 사전 학습되었습니다. 더 철저한 데이터 정제, 업데이트된 데이터 구성, 전체 학습 token 40% 추가, context 길이 2배 확장, 대형 모델의 추론 확장성을 높이는 grouped-query attention (GQA) 적용 등이 변경 사항에 포함됩니다.

```
response = await workflow.run(
    query_str="What is the functionality of latest ChatGPT memory."
)
display(Markdown(str(response)))
```

최신 ChatGPT memory 기능은 대화에서 중요하다고 판단한 정보를 자동으로 기억하는 것입니다. 이 기능은 사용자가 정보를 반복해서 말하지 않아도 되게 해 향후 대화를 더 유용하게 만드는 것을 목표로 합니다. 사용자는 챗봇의 memory를 확인하고 관리할 수 있어 memory를 제어할 수 있습니다.

원문: [Corrective RAG — LlamaIndex](https://developers.llamaindex.ai/python/examples/workflow/corrective_rag_pack/)

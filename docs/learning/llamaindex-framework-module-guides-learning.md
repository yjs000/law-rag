# LlamaIndex Python Framework Module Guides와 law-rag v2

작성일: 2026-08-25  
공식 기준: <https://developers.llamaindex.ai/python/framework/module_guides/>

## 한눈에 보기

LlamaIndex는 문서·조문을 Node로 표현하고, 임베딩·벡터 저장소로 검색하며, 필요하면 그 위에
질의·답변·에이전트·평가·관측 기능을 조합하는 프레임워크다.

law-rag v2는 현재 TextNode, NVIDIA 임베딩, PostgreSQL 벡터 저장소와 저수준 VectorStoreQuery를 사용한다.
질문 라우팅, 법령 기준일 필터, 답변 생성·검증, 감사 로그는 프로젝트 도메인 계층이 직접 담당한다.
따라서 고수준 Query Engine·Agent를 추가하는 것은 현재 추천하지 않는다.

아래 목록은 공식 Component Guides의 모든 핵심 모듈 링크를 기준으로 했다. 수백 개의 개별 공급자
integration 예제는 기능군(LLM, Embeddings, Data Connectors, Vector Stores)의 선택지이므로,
공급자별 행 대신 해당 기능군 행에 포함했다.

- **사용 중**: 현재 v2 코드가 직접 사용한다.
- **주목 대상**: 다음 설계·실험 단계에서 우선적으로 검토한다. 바로 전면 대체한다는 뜻은 아니다.
- **조건부 추천**: 독립 실험 또는 명확한 필요가 생겼을 때만 검토한다.
- **현재 비추천**: 현행 도메인 경계·검증 규칙을 흐리거나, 확인된 요구가 없다.
- **미사용**: 기능 자체는 알되 현재 도입 판단을 보류한다.

## 전체 기능 비교표

| 주요 기능 | law-rag v2의 사용·추천 판단 | 간단한 설명 |
|---|---|---|
| [Models 소개](https://developers.llamaindex.ai/python/framework/module_guides/models/) | 미사용 — 개념 참조 | LLM·임베딩·멀티모달 모델을 다루는 공통 추상화다. |
| [LLMs](https://developers.llamaindex.ai/python/framework/module_guides/models/llms/) | 미사용 — 현재 비추천 | 텍스트 생성·추론 모델 호출 인터페이스다. v2 답변 생성은 별도 NVIDIA 어댑터다. |
| [Embeddings](https://developers.llamaindex.ai/python/framework/module_guides/models/embeddings/) | **사용 중** | 텍스트를 의미 검색용 벡터로 변환한다. v2는 NVIDIA 임베딩을 사용한다. |
| [Multi Modal](https://developers.llamaindex.ai/python/framework/module_guides/models/multi_modal/) | 현재 비추천 | 이미지·음성 등 비텍스트 입력을 다룬다. 현재 법령 조문 검색 범위 밖이다. |
| [Prompts 소개](https://developers.llamaindex.ai/python/framework/module_guides/models/prompts/) | **주목 대상** | 프롬프트 템플릿을 정의하고 모델 호출에 채운다. |
| [Prompt Usage Patterns](https://developers.llamaindex.ai/python/framework/module_guides/models/prompts/usage_pattern/) | **주목 대상** | 프롬프트 변수 주입·선택·갱신 방법이다. 현재 답변 프롬프트는 자체 구현이다. |
| [Loading 소개](https://developers.llamaindex.ai/python/framework/module_guides/loading/) | 미사용 | 외부 원문을 Document/Node로 가져오는 진입점이다. |
| [Documents and Nodes](https://developers.llamaindex.ai/python/framework/module_guides/loading/documents_and_nodes/) | **사용 중** | Document는 원문 단위, Node는 검색·처리 단위다. v2는 조문 하나를 TextNode로 만든다. |
| [SimpleDirectoryReader](https://developers.llamaindex.ai/python/framework/module_guides/loading/simpledirectoryreader/) | 현재 비추천 | 로컬 디렉터리 파일을 읽는다. 법령 원문은 공용 DB·국가법령정보 API 경로를 써야 한다. |
| [Data Connectors](https://developers.llamaindex.ai/python/framework/module_guides/loading/connector/) | 현재 비추천 | 파일·SaaS·웹 등 외부 소스를 Document로 불러온다. 허용 법령 출처를 넓히지 않는다. |
| [Node Parsers / Text Splitters](https://developers.llamaindex.ai/python/framework/module_guides/loading/node_parsers/modules/) | **조건부 추천 — 청킹 A/B 실험에 한정** | Document/Node를 작은 청크로 분할한다. 운영 검색 교체가 아니라 고정 조건의 청킹 비교에만 쓴다. |
| [Ingestion Pipeline](https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/) | **주목 대상** | 변환·임베딩·캐시·벡터 기록을 조합한다. 변경 조문·출처·버전 통제와 결합하는 방식을 검토한다. |
| [Indexing 소개](https://developers.llamaindex.ai/python/framework/module_guides/indexing/) | **주목 대상** | 문서에서 검색 가능한 구조를 만드는 방식들의 개요다. |
| [Index Guide](https://developers.llamaindex.ai/python/framework/module_guides/indexing/index_guide/) | 미사용 — 개념 참조 | 벡터·요약·트리·그래프 등 인덱스의 특성과 선택 기준이다. |
| [Vector Store Index](https://developers.llamaindex.ai/python/framework/module_guides/indexing/vector_store_index/) | 미사용 — 현재 비추천 | 벡터 저장소 위에 고수준 index 객체를 만든다. v2는 필요한 벡터 조회만 직접 호출한다. |
| [Property Graph Index](https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/) | 현재 비추천 | 엔터티·관계 그래프를 추출해 그래프 기반으로 조회한다. 관계 모델링 요구가 확정되지 않았다. |
| [Storing 소개](https://developers.llamaindex.ai/python/framework/module_guides/storing/) | **주목 대상 — 공용 DB 권위 유지 조건** | 벡터·문서·인덱스 저장 계층의 역할이다. v2는 벡터 저장소만 사용한다. |
| [Vector Stores](https://developers.llamaindex.ai/python/framework/module_guides/storing/vector_stores/) | **사용 중** | 임베딩과 Node metadata를 저장하고 유사도 검색한다. v2는 PostgreSQL PGVectorStore다. |
| [Document Stores](https://developers.llamaindex.ai/python/framework/module_guides/storing/docstores/) | 현재 비추천 | Document/Node 원문을 별도 저장한다. 원문·버전의 권위 저장소는 기존 공용 DB다. |
| [Index Stores](https://developers.llamaindex.ai/python/framework/module_guides/storing/index_stores/) | 현재 비추천 | LlamaIndex index의 구조 metadata를 저장한다. 고수준 index를 쓰지 않으므로 필요 없다. |
| [Querying 소개](https://developers.llamaindex.ai/python/framework/module_guides/querying/) | 부분 사용 | 검색, 답변 합성, 대화형 질의를 조합하는 계층의 개요다. |
| [Query Engines](https://developers.llamaindex.ai/python/framework/module_guides/deploying/query_engine/) | 현재 비추천 | 검색과 답변 생성을 하나로 묶는다. v2의 라우팅·기준일·검증 경계를 직접 유지하는 편이 낫다. |
| [Chat Engines](https://developers.llamaindex.ai/python/framework/module_guides/deploying/chat_engines/) | 현재 비추천 | 대화 문맥을 유지하며 질의한다. 현재 질문 API는 단발 법률 질의 기준이다. |
| [Retrieval](https://developers.llamaindex.ai/python/framework/module_guides/querying/retriever/) | **사용 중 · 주목 대상** | 관련 Node를 찾는다. v2는 BaseRetriever가 아니라 VectorStoreQuery와 aquery를 직접 쓴다. |
| [Response Synthesis](https://developers.llamaindex.ai/python/framework/module_guides/querying/response_synthesizers/) | **주목 대상** | 검색 Node를 LLM 답변으로 합성한다. 근거 검증을 유지한 제한적 적용을 검토한다. |
| [Agents](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/) | 현재 비추천 | LLM이 도구를 선택해 여러 단계를 수행하게 한다. 법률 답변의 결정적 흐름과 충돌할 수 있다. |
| [Memory](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/memory/) | 현재 비추천 | 에이전트의 대화·장기 메모리를 관리한다. 개인정보 정책과 별도 설계가 필요하다. |
| [Tools](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/tools/) | 현재 비추천 | 함수·API·검색기를 에이전트 호출 가능 Tool로 노출한다. |
| [Workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/) | 미사용 — 보류 | 이벤트 기반 다단계 AI workflow를 구성한다. 현행 API 서비스 흐름을 대체할 필요는 확인되지 않았다. |
| [Evaluation 소개](https://developers.llamaindex.ai/python/framework/module_guides/evaluating/) | **주목 대상** | 검색·답변 품질 평가 인터페이스다. 청킹 판정은 기존 확정 10개 평가셋의 Recall@K를 유지한다. |
| [Evaluation Usage Patterns](https://developers.llamaindex.ai/python/framework/module_guides/evaluating/usage_pattern/) | **주목 대상** | faithfulness, relevance 같은 평가 패턴이다. Recall 판정과는 별도의 보조 분석으로 검토한다. |
| [LlamaDatasets](https://developers.llamaindex.ai/python/framework/module_guides/evaluating/contributing_llamadatasets/) | **주목 대상 — 병행 사용 검토** | 표준화된 RAG 평가 데이터셋 형식이다. 기존 법령 평가셋을 권위 기준으로 유지한 채 호환 형식으로 검토한다. |
| [Observability 소개](https://developers.llamaindex.ai/python/framework/module_guides/observability/) | **주목 대상 — 병행 관측 검토** | LlamaIndex 실행 이벤트·추적을 수집한다. 현재 자체 stage timing·감사 로그를 유지하며 보강한다. |
| [Instrumentation](https://developers.llamaindex.ai/python/framework/module_guides/observability/instrumentation/) | **주목 대상 — 보안 검토 후** | 이벤트 dispatcher와 span handler로 실행을 계측한다. 원문·질문·인증정보 유출 방지가 먼저다. |
| [Settings Configuration](https://developers.llamaindex.ai/python/framework/module_guides/supporting_modules/settings/) | 현재 비추천 | 전역 Settings 객체로 LLM·임베딩·callback을 기본 설정한다. v2는 명시적 Pydantic 설정과 의존성 주입을 유지한다. |

## 사용 중·조건부 추천 상세

<details>
<summary><strong>Documents and Nodes — 사용 중</strong></summary>

### 주요 함수와 역할

- TextNode(id_, text, metadata): 검색 텍스트, 안정적인 ID, 출처 추적 metadata를 함께 만든다.
- node.embedding: 계산된 임베딩을 Node에 붙여 vector store에 기록한다.

### 예시 코드

~~~python
from llama_index.core.schema import TextNode

node = TextNode(
    id_="provision-123",
    text="제1조(목적) ...",
    metadata={"document_id": "law-1", "effective_from": "2026-01-01"},
)
~~~

### 실제 사용 코드와 참조

~~~python
nodes.append(
    TextNode(
        id_=record["provision_id"],
        text=passage_text,
        metadata=build_node_metadata(record, sha256),
    )
)
~~~

실제 위치: [build_nodes](../../apps/law-rag-llamaindex/src/law_rag_llamaindex/ingest.py#L72)<br>
공식 참조: <https://developers.llamaindex.ai/python/framework/module_guides/loading/documents_and_nodes/>
</details>

<details>
<summary><strong>Embeddings / NVIDIAEmbedding — 사용 중</strong></summary>

### 주요 함수와 역할

- NVIDIAEmbedding(...): NVIDIA 임베딩 모델 클라이언트를 만든다.
- get_text_embedding_batch(texts): 적재할 조문 텍스트를 일괄 벡터화한다.
- get_query_embedding(query): 사용자 질문을 같은 벡터 공간의 query vector로 바꾼다.

### 예시 코드

~~~python
from llama_index.embeddings.nvidia import NVIDIAEmbedding

embedder = NVIDIAEmbedding(model="nvidia/llama-3.2-nv-embedqa-1b-v2")
query_vector = embedder.get_query_embedding("전기사업의 목적은?")
~~~

### 실제 사용 코드와 참조

~~~python
return NVIDIAEmbedding(
    model=settings.nvidia_embedding_model,
    api_key=settings.nvidia_api_key,
    base_url=settings.nvidia_base_url,
    truncate="END",
)
~~~

실제 위치: [build_embedder](../../apps/law-rag-llamaindex/src/law_rag_llamaindex/embedding.py#L8)<br>
공식 참조: <https://developers.llamaindex.ai/python/framework/module_guides/models/embeddings/>
</details>

<details>
<summary><strong>Vector Stores / PGVectorStore — 사용 중</strong></summary>

### 주요 함수와 역할

- PGVectorStore.from_params(...): PostgreSQL/pgvector 기반 저장소를 만든다.
- add(nodes): embedding을 가진 Node를 저장한다.
- aquery(VectorStoreQuery(...)): 비동기로 유사도 검색하고 Node·점수를 반환한다.
- MetadataFilters, MetadataFilter: 저장소에서 1차 metadata 조건을 적용한다.

### 예시 코드

~~~python
result = await vector_store.aquery(
    VectorStoreQuery(
        query_embedding=query_vector,
        similarity_top_k=10,
        filters=MetadataFilters(filters=[
            MetadataFilter(key="effective_from", value="2026-08-25",
                           operator=FilterOperator.LTE),
        ]),
    )
)
~~~

### 실제 사용 코드와 참조

~~~python
return PGVectorStore.from_params(
    host=url.host,
    database=url.database,
    table_name=settings.vector_table_name,
    embed_dim=settings.embed_dim,
    hnsw_kwargs=settings.hnsw_kwargs,
    use_jsonb=True,
    perform_setup=True,
)
~~~

실제 위치: [build_vector_store](../../apps/law-rag-llamaindex/src/law_rag_llamaindex/store.py#L9)<br>
공식 참조: <https://developers.llamaindex.ai/python/framework/module_guides/storing/vector_stores/>
</details>

<details>
<summary><strong>Retrieval / VectorStoreQuery — 사용 중</strong></summary>

### 주요 함수와 역할

- VectorStoreQuery: query embedding, top-k, metadata filter를 vector store에 전달한다.
- aquery(): 후보 Node와 유사도 점수를 가져온다.
- similarity_top_k: DB에서 가져올 후보 수다. v2는 limit × 4를 가져오되 최대 100개로 제한한다.

### 예시 코드

~~~python
query_vector = embedder.get_query_embedding(question)
result = await vector_store.aquery(
    VectorStoreQuery(query_embedding=query_vector, similarity_top_k=20)
)
~~~

### 실제 사용 코드와 참조

~~~python
result = await vector_store.aquery(
    VectorStoreQuery(
        query_embedding=query_embedding,
        similarity_top_k=over_fetch,
        filters=filters,
    )
)
~~~

조회 뒤에는 effective_to까지 애플리케이션에서 다시 검사하고, limit에 도달하면 반환한다. 결과가 비어도
v1 검색을 다시 호출하지 않는다.

실제 위치: [search](../../apps/law-rag-llamaindex/src/law_rag_llamaindex/retriever.py#L17)<br>
공식 참조: <https://developers.llamaindex.ai/python/framework/module_guides/querying/retriever/>
</details>

<details>
<summary><strong>Node Parsers / Text Splitters — 조건부 추천: 청킹 A/B 실험에만</strong></summary>

### 주요 함수와 역할

- SentenceSplitter: 문장 경계를 우선해 일정 크기의 Node로 나눈다.
- SemanticSplitterNodeParser: 임베딩상 의미 변화가 큰 지점에서 Node 경계를 찾는다.
- get_nodes_from_documents(documents): Document 목록을 분할 결과 Node 목록으로 변환한다.

### 예시 코드

~~~python
from llama_index.core.node_parser import SentenceSplitter

splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
candidate_nodes = splitter.get_nodes_from_documents(documents)
~~~

### 적용 원칙

추천 범위는 **청킹 구현 하나의 독립 A/B 실험**이다. 현재 청킹과 LlamaIndex 청킹을 교대로 바꾸고,
청킹 이후 단계는 v2 embedder·v2 vector snapshot·동일 filter·동일 top-k·동일 D-10 평가셋으로 고정한다.
판정은 Recall@K 등 검색 수치만 비교한다. LLM 답변 품질, 라우팅, 다른 fallback 판단을 섞지 않는다.

현재 실제 코드는 이 Parser를 쓰지 않는다. 조문 1개를 Node 1개로 명시 생성한다.

현재 관련 위치: [build_nodes](../../apps/law-rag-llamaindex/src/law_rag_llamaindex/ingest.py#L72)<br>
공식 참조: <https://developers.llamaindex.ai/python/framework/module_guides/loading/node_parsers/modules/>
</details>

<details>
<summary><strong>Ingestion Pipeline — 미사용, 현재 방식 유지</strong></summary>

### 주요 함수와 역할

- IngestionPipeline(transformations=[...]): 파싱·분할·임베딩 같은 변환을 순서대로 실행한다.
- run(documents=...): 문서에서 변환된 Node를 생성한다.
- cache/vector-store 옵션: 같은 입력의 재처리와 저장을 조정한다.

### 예시 코드

~~~python
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter

pipeline = IngestionPipeline(transformations=[SentenceSplitter(chunk_size=512)])
nodes = pipeline.run(documents=documents)
~~~

### 실제 사용 코드와 참조

현재 v2는 Pipeline 클래스를 직접 사용하지 않는다. 바뀐 조문만 SHA-256으로 식별하고, 기존 Node를 삭제한 뒤,
일괄 임베딩과 vector_store.add(nodes)를 명시적으로 수행한다. 이 흐름이 원문·파생 청크·인덱스 버전
추적 요구와 더 직접적으로 맞는다.

~~~python
changed_ids = changed_provision_ids(provisions, current_hashes)
await delete_nodes(engine, table_name, ids_to_delete)
embeddings = embedder.get_text_embedding_batch(texts)
vector_store.add(nodes)
~~~

실제 위치: [run_ingestion](../../apps/law-rag-llamaindex/src/law_rag_llamaindex/ingest.py#L114)<br>
공식 참조: <https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/>
</details>

<details>
<summary><strong>Evaluation — 조건부 추천: 보조 분석에만</strong></summary>

### 주요 함수와 역할

- evaluator 계열: 검색 결과 또는 답변의 관련성·근거 충실성 등을 평가한다.
- LabelledRagDataset: query와 정답 context를 가진 RAG 평가셋 표현 방식이다.

### 예시 코드

~~~python
# 개념 예시: 동일한 retrieval 결과에 대해서만 보조 평가한다.
evaluation_result = evaluator.evaluate(query=query, response=response)
~~~

### 적용 원칙

청킹 판정의 권위 기준은 기존 확정 10개 평가셋과 Recall@K다. 이 모듈은 나중에 답변 근거 충실성의
보조 분석을 추가할 때만 검토한다. 외부 형식으로 평가셋을 옮기거나 LLM 기반 점수로 Recall 판정을
대체하지 않는다.

공식 참조: <https://developers.llamaindex.ai/python/framework/module_guides/evaluating/>
</details>

<details>
<summary><strong>Instrumentation — 조건부 추천: 개인정보·원문 유출 검토 후</strong></summary>

### 주요 함수와 역할

- get_dispatcher(name): LlamaIndex 실행 이벤트 dispatcher를 얻는다.
- event/span handler: embedding·retrieval 등 내부 단계를 추적 대상으로 연결한다.

### 예시 코드

~~~python
from llama_index.core.instrumentation import get_dispatcher

dispatcher = get_dispatcher(__name__)
# 안전하게 비식별 stage·지연 시간만 별도 handler에 전송한다.
~~~

### 실제 사용 코드와 참조

현재 서비스는 LlamaIndex instrumentation 대신 요청·routing·embedding·retrieval·answer generation·validation
stage별 자체 timing 이벤트를 기록한다. 외부 관측 도구를 도입하려면 질문 전문, 법령 원문 전문, 인증정보가
전송·저장되지 않음을 먼저 확인해야 한다.

실제 위치: [emit_question_stage_timing](../../apps/api/app/observability.py#L133)<br>
공식 참조: <https://developers.llamaindex.ai/python/framework/module_guides/observability/instrumentation/>
</details>

## 이번 비교의 결론

1. v2가 실제로 의존하는 범위는 **TextNode → NVIDIAEmbedding → PGVectorStore/VectorStoreQuery**다.
2. 지금 새로 검토할 가치가 가장 큰 것은 **Node Parser/Text Splitter**이며, 운영 변경이 아니라
   고정 D-10과 Recall@K로 판정하는 청킹 A/B 실험이어야 한다.
3. Query Engine, Response Synthesis, Agent, Memory, Tools는 현재의 법률 근거·기준일·검증·로그 경계를
   하나의 범용 흐름으로 감싸므로 도입하지 않는다.
4. Evaluation과 Instrumentation은 향후 보조 분석·관측 후보지만, 기존 평가셋의 판정권이나 개인정보
   보호 규칙을 대체하지 않는다.

## 공식 문서 탐색 범위

이 문서는 다음 Component Guides 링크를 모두 확인해 분류했다: Models(4), Prompts(2), Loading(6),
Indexing(4), Storing(4), Querying(5), Agents(3), Workflows(1), Evaluation(3), Observability(2),
Settings(1). 개별 provider integration은 같은 기능군의 대체 구현이므로, 현재 사용하는 NVIDIA와
PostgreSQL 외에는 별도 도입 추천으로 표시하지 않았다.

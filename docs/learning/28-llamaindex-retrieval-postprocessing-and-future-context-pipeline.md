# LlamaIndex 검색·후처리·답변 합성의 역할 분리

확인일: 2026-08-03

상태: 개념 학습 문서. 이 문서의 `추후 검토 방향`은 현재 구현이나 채택 결정이 아니다.

## 한 문장 요약

LlamaIndex의 Query Engine은 검색된 `NodeWithScore` 목록을 하나 이상의 Node Postprocessor에 순서대로
통과시킨 뒤, 남거나 보강된 Node를 Response Synthesizer에 넘긴다. `Node Postprocessor`는 이 단계의
공통 인터페이스이고, `SimilarityPostprocessor`는 기존 검색 점수에 임계값을 적용하는 가장 단순한 구체
구현이다.

```text
질문
-> Retriever: 넓은 후보 검색
-> Node Postprocessor 1
-> Node Postprocessor 2
-> Response Synthesizer: 선택된 문맥으로 답변 생성
```

LlamaIndex의 현재 `RetrieverQueryEngine` 소스도 retriever의 결과를 받은 다음 등록된 postprocessor를
목록 순서대로 호출하고, 그 결과를 response synthesizer에 전달한다. 따라서 postprocessor의 순서는
동작에 영향을 준다.

```python
nodes = retriever.retrieve(query)
for processor in node_postprocessors:
    nodes = processor.postprocess_nodes(nodes, query)
response = response_synthesizer.synthesize(query, nodes)
```

## Node와 NodeWithScore

`Node`는 검색·답변에 사용하는 문서 조각이다. 본문뿐 아니라 ID, 원문과 위치를 나타내는 메타데이터,
부모·자식이나 이전·다음 관계를 가질 수 있다. `NodeWithScore`는 Node와 검색기가 부여한 점수를 함께
전달하는 포장 객체다.

법률 문서에서는 다음처럼 대응할 수 있다.

```text
Node
- content: "가. 태양에너지"
- law_name: "신에너지 및 재생에너지 개발·이용·보급 촉진법"
- provision_path: "제2조제2호가목"
- parent_path: "제2조제2호"

NodeWithScore
- node: 위 Node
- score: dense 검색기의 cosine 점수
```

## Node Postprocessor는 무엇인가

`Node Postprocessor`는 특정 필터 이름이 아니라 공통 추상화다. 입력으로 `NodeWithScore[]`와 선택적으로
질문을 받고, 다시 `NodeWithScore[]`를 반환한다. 구체 구현은 다음처럼 서로 다른 일을 할 수 있다.

- 필터링: 약한 후보나 금지 키워드가 있는 후보 제거
- 재순위: 질문 관련성을 다시 계산해 순서 변경
- 축소: 상위 N개만 반환하거나 불필요한 문장 제거
- 문맥 보강: 이전·다음·부모 Node 추가
- 본문 교체: 검색용 작은 Node를 답변용 문맥 창으로 교체
- 순서 조정: 긴 입력에서 중요한 근거가 가운데 묻히지 않게 배치

즉 모든 Node Postprocessor가 필터는 아니다. `SimilarityPostprocessor`, reranker, 문맥 보강기는 모두
같은 확장 지점을 사용하지만 내부 판단과 결과가 다르다.

여러 postprocessor를 연결하면 앞 단계의 출력이 다음 단계의 입력이 된다. 예를 들어 임계값 필터를 먼저
적용하면 reranker는 제거된 후보를 복구할 수 없다. 반대로 reranker를 먼저 적용한 뒤 임계값 필터를
사용하면 임계값이 어느 모델의 점수를 뜻하는지 명확히 해야 한다.

## SimilarityPostprocessor의 정확한 동작

`SimilarityPostprocessor`는 AI를 새로 호출하지 않고 임베딩도 다시 계산하지 않는다. 각 후보의 기존
`node.score`를 읽어서 점수가 `similarity_cutoff`보다 낮거나 점수가 없으면 제거하고, 나머지는 원래
순서대로 반환한다.

```text
입력                    cutoff 0.70             출력
A score 0.82      ->    유지             ->    A score 0.82
B score 0.69      ->    제거
C score 없음      ->    제거
```

`Node Postprocessor`와의 관계는 다음과 같다.

```text
Node Postprocessor                 공통 규격/부모 개념
├─ SimilarityPostprocessor         기존 점수 임계값 필터
├─ KeywordNodePostprocessor        키워드 포함·제외 필터
├─ CohereRerank                    학습된 rerank 모델로 재순위
├─ LLMRerank                       LLM으로 관련성을 판정해 재순위
└─ PrevNextNodePostprocessor       인접 Node를 추가해 문맥 보강
```

따라서 “둘 다 검색 후 단계인가?”에는 `그렇다`가 답이다. 그러나 하나는 단계 전체를 가리키는 인터페이스이고,
다른 하나는 그 단계에서 사용할 수 있는 한 가지 알고리즘이다.

## 위험한데도 SimilarityPostprocessor가 존재하는 이유

Retriever는 보통 고정된 `top_k`만큼 후보를 반환한다. 질문과 관련된 문서가 거의 없더라도 채울 수 있는
만큼 후보를 반환하면 꼬리 후보의 점수가 매우 낮을 수 있다. 이때 저렴하고 결정적인 1차 noise gate로
약한 꼬리를 제거하면 다음 효과를 기대할 수 있다.

- 답변 모델에 전달되는 토큰과 호출 비용 감소
- 명백히 약한 문맥이 답변에 끼어드는 양 감소
- 뒤의 비싼 reranker가 검사할 후보 수 감소
- 같은 입력과 점수에 대해 재현 가능한 결과

LlamaIndex 공식 질의 문서는 Node 후처리가 관련성을 높이고 LLM 호출 수·시간·비용을 줄이거나 답변
품질을 높이는 데 사용될 수 있다고 설명한다. 하지만 이는 후처리 단계의 일반적인 기대효과다.

중요하게도 공식 문서와 공식 블로그에서 `SimilarityPostprocessor` 하나만을 대상으로 법률 데이터나
일반 데이터에서 품질이 개선됐다고 증명한 벤치마크는 확인하지 못했다. 공식 구현은 단순 임계값 필터를
제공하고, 실제 cutoff 선택은 사용자 데이터의 책임으로 남긴다.

LlamaIndex 공식 블로그도 임베딩 검색에서 top-k나 similarity threshold를 너무 작게 잡으면 필요한
문맥을 놓치고, 너무 크게 잡으면 무관한 문맥과 비용·지연이 늘어난다고 설명한다. 이것은 임계값이
유용할 수 있는 이유와 동시에 고정값을 맹신하면 안 되는 이유다.

## Similarity cutoff와 insufficient_evidence는 다른 판정이다

Similarity cutoff가 대답하는 질문은 다음과 같다.

> 이 후보의 기존 검색 점수가 미리 정한 하한보다 낮은가?

`insufficient_evidence`가 대답해야 하는 질문은 다음과 같다.

> 남은 후보와 복원한 법률 계층 안에 질문의 필수 답변 요소를 직접 뒷받침하는 원문이 있는가?

코사인 점수는 정답 확률이나 법적 근거 충분성 점수가 아니다. 점수 분포는 임베딩 모델, 청크 크기,
질문 형태, 언어와 코퍼스에 따라 달라진다. 따라서 SimilarityPostprocessor는 검증된 평가셋에서 정한
noise gate로는 사용할 수 있지만, 그 결과가 비었다는 사실만으로 법률적 근거 부족을 일반화하면 안 된다.

법률 RAG에서 근거 부족 판정에는 최소한 다음 검사가 별도로 필요하다.

- 질문이 요구하는 법률과 조문 범위가 후보에 있는가
- 정의·요건·예외 등 필요한 답변 요소를 본문이 직접 포함하는가
- 조·항·호·목 부모 문맥을 복원했는가
- 단순 인용이나 관련 단어만 있는 간접 후보가 아닌가
- 인용 가능한 source ID와 정확한 위치가 있는가

## Reranker는 AI가 판단하는가

reranker의 종류에 따라 다르다.

### 학습된 rerank 모델

Cohere Rerank나 BGE reranker 같은 모델은 질문과 각 후보 문서를 함께 입력받아 관련성 점수를 새로
계산하고 순서를 바꾼다. 이것은 학습된 AI 모델의 판단이지만, 자유롭게 답변을 작성하는 생성 LLM과는
다르다. 주된 출력은 후보별 관련성 점수와 순위다.

```text
Retriever: 질문 벡터와 문서 벡터를 각각 만들어 빠르게 후보 20개 회수
Reranker: 질문+후보 1, 질문+후보 2, ... 를 더 세밀하게 비교
결과: 상위 3~5개로 재정렬
```

### LLM reranker

`LLMRerank`는 생성 LLM에게 후보들의 질문 관련성을 고르게 하거나 점수를 매기게 한다. 이것도 AI
판정이고 설명 가능한 프롬프트를 만들 수 있지만, 비용·지연·비결정성과 프롬프트 오류 위험이 더 크다.

### 규칙 기반 reranker

날짜, 권위, 법률 효력 시점, 정확한 조문 경로 같은 규칙으로 순위를 바꾸는 경우에는 AI가 필요 없다.
LlamaIndex의 Postprocessor 인터페이스는 AI 사용 여부를 강제하지 않는다.

LlamaIndex 공식 블로그의 Llama 2 논문 데이터 실험에서는 여러 임베딩에 Cohere/BGE reranker를 붙였을
때 Hit Rate와 MRR이 대체로 개선됐다. 예를 들어 블로그에 보고된 특정 조합에서는
`JinaAI-v2-base-en + CohereRerank`가 Hit Rate `0.932584`, MRR `0.873689`를 기록했다. 그러나 글 자체도
데이터, 청크 크기와 top-k에 따라 결과가 달라지므로 숫자를 일반화하지 말고 자기 데이터에서 재현하라고
경고한다. 이 결과는 reranker 도입을 검토할 근거이지, 현재 법률 코퍼스에서 자동 채택할 근거는 아니다.

## Vector, BM25, graph 후보 회수

후보 생성은 서로 다른 검색기의 장점을 합칠 수 있다.

- dense/vector: 표현이 달라도 의미가 비슷한 후보를 찾는 데 유리
- BM25/lexical: 법률명, 조문 번호와 정확한 용어 일치에 유리
- graph/관계 탐색: 조·항·호·목, 인용 조문과 부모·자식 문맥을 따라가는 데 유리

법률 문서에서 graph는 반드시 LLM이 만든 지식 그래프일 필요가 없다. 파서가 이미 아는
`법률 -> 장 -> 조 -> 항 -> 호 -> 목` 관계를 결정적으로 사용하는 편이 먼저 검토할 수 있는 단순한
방법이다.

## Join, dedup과 group

여러 검색기의 후보 목록을 합치는 것이 join이다. 같은 `chunk_id`가 여러 목록에 있으면 하나로 만드는
것이 dedup이다. dense와 BM25의 점수 척도는 서로 다르므로 점수를 직접 더하기보다 순위를 사용하는
RRF 같은 방식을 검토할 수 있다.

같은 조에 속한 서로 다른 항·호·목은 중복이 아니다. 삭제하지 않고 조 단위로 group한 뒤 문맥을
조립해야 한다.

```text
dedup 대상
- dense의 제2조제2호가목 chunk-123
- BM25의 제2조제2호가목 chunk-123

group 대상
- 제2조 본문 chunk-100
- 제2조제2호 chunk-120
- 제2조제2호가목 chunk-123
```

## 추후 검토 방향 — 현재 작업에 반영하지 않음

아래 구조는 현재 구현 설명도, LlamaIndex 도입 결정도 아니다. 진행 중인 corpus 복구, 검증, 실험 C/D
기준선과 자동 기록이 모두 끝난 뒤 별도 변경으로 평가할 후보 방향이다.

```text
실험 C: 후보 생성
  dense 기준선
  -> 후속 비교에서만 BM25/lexical 후보 추가
  -> RRF 등으로 join
  -> chunk ID dedup
  -> 조 단위 group

실험 D: 답변 문맥 구성
  후보를 넉넉하게 입력
  -> 필요성이 측정된 경우에만 reranker 비교
  -> 조·항·호·목 계층 보강
  -> 직접 근거와 필수 답변 요소 검사
  -> 근거 1~5개 또는 insufficient_evidence

후속 답변 단계
  -> 검증된 근거만 Response Synthesizer 또는 답변 모델에 전달
  -> 인용 ID 검증
```

적용 순서는 다음 게이트를 지킨다.

1. corpus 본문과 법률 계층이 정상인지 먼저 검증한다.
2. dense-only Evidence Recall, Recall@K와 MRR 기준선을 다시 고정한다.
3. lexical+dense 결합과 reranker를 각각 분리해 비교한다.
4. 검색 recall뿐 아니라 직접 근거 정확성, 지연, 비용과 재현성을 함께 측정한다.
5. 실제 법률 평가셋에서 개선될 때만 채택한다.

따라서 이 문서는 추후 작업의 설계 입력일 뿐이며, 진행 중인 실험 D 계획 파일이나 코드에는 지금
반영하지 않는다.

## 공식 자료

- [LlamaIndex Node Postprocessor 개념과 사용 위치](https://developers.llamaindex.ai/python/framework/module_guides/querying/node_postprocessors/)
- [LlamaIndex Node Postprocessor 구현 종류](https://developers.llamaindex.ai/python/framework/module_guides/querying/node_postprocessors/node_postprocessors/)
- [LlamaIndex Retriever 개념](https://developers.llamaindex.ai/python/framework/module_guides/querying/retriever/)
- [LlamaIndex Response Synthesizer 개념](https://developers.llamaindex.ai/python/framework/module_guides/querying/response_synthesizers/)
- [RetrieverQueryEngine 공식 소스](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/query_engine/retriever_query_engine.py)
- [BaseNodePostprocessor 공식 소스](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/postprocessor/types.py)
- [SimilarityPostprocessor 공식 소스](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/postprocessor/node.py)
- [공식 블로그: Advanced RAG의 retrieval과 rerank 구분](https://www.llamaindex.ai/blog/a-cheat-sheet-and-some-recipes-for-building-advanced-rag-803a9d94c41b)
- [공식 블로그: embedding·reranker 조합 평가](https://www.llamaindex.ai/blog/boosting-rag-picking-the-best-embedding-reranker-models-42d079022e83)
- [공식 블로그: top-k·similarity threshold의 상충 관계](https://www.llamaindex.ai/blog/a-new-document-summary-index-for-llm-powered-qa-systems-9a32ece2f9ec)

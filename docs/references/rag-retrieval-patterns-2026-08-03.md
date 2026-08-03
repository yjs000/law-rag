# RAG 검색·근거 선택 참고 자료

확인일: 2026-08-03

## 1차 자료

- RAGFlow 공식 저장소: <https://github.com/infiniflow/ragflow>
  - 적용: 입력 문서 품질, 문서 구조 기반 chunking, 여러 recall과 fused reranking을 분리해 판단한다.
- Microsoft GraphRAG query overview: <https://microsoft.github.io/graphrag/query/overview/>
  - 적용: local search는 그래프와 원문 청크를 결합하고 global search는 전체 데이터셋 질문용이다. 현재 조문 직접 근거 문제에는 우선 적용하지 않는다.
- Microsoft GraphRAG indexing overview: <https://microsoft.github.io/graphrag/index/overview/>
  - 적용: 그래프 구축에는 별도 indexing 비용과 산출물이 필요하므로 벡터 기준선보다 효과가 입증될 때 검토한다.
- LlamaIndex node postprocessors: <https://developers.llamaindex.ai/python/framework/module_guides/querying/node_postprocessors/>
  - 적용: 검색된 노드를 답변 합성 전에 필터링·변환하는 단계로 실험 D의 위치를 비교했다.
- Haystack DocumentJoiner: <https://docs.haystack.deepset.ai/docs/documentjoiner>
  - 적용: 여러 retriever 결과 결합과 reciprocal rank fusion 선택지를 비교했다.
- Haystack SentenceTransformersSimilarityRanker: <https://docs.haystack.deepset.ai/docs/sentencetransformerssimilarityranker>
  - 적용: retriever가 넉넉히 찾고 ranker가 더 적은 후보를 고르는 `top_k` 분리를 비교했다.
- Cormack, Clarke, Buettcher, *Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods*: <https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf>
  - 적용: RRF는 검색별 역순위 기여를 합산한다. 한 검색의 기여를 다른 검색에서 빼지 않는다.

## 프로젝트에 적용한 경계

이 자료는 외부 시스템을 그대로 도입하는 근거가 아니다. 다음 세 원칙만 현재 구현에 적용했다.

1. 잘못된 입력 문서는 검색 알고리즘으로 보상하지 않는다.
2. 넉넉한 검색 후보와 답변에 전달할 직접 근거를 분리한다.
3. hybrid·reranker·graph는 고정 평가에서 실제 개선을 보일 때만 채택한다.

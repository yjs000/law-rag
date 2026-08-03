# RAG 평가 방법 공식 자료

확인일: 2026-08-03

## NVIDIA NeMo Platform RAG metrics

- URL: https://docs.nvidia.com/nemo-platform/documentation/evaluate-models/metrics/rag-metrics
- 확인 내용: RAG 평가 입력을 `user_input`, `retrieved_contexts`, `response`, `reference`로 분리한다. 검색 품질에는 context recall/precision/relevance, 답변에는 faithfulness, groundedness, response relevancy 등을 사용한다. 대부분의 의미 평가는 judge LLM이 필요하고 실패가 NaN으로 나타날 수 있으므로 행별 오류 확인이 필요하다.
- 적용: 실험 D 데이터셋은 질문·정답·기대 근거를 독립 필드로 보존한다. judge 점수는 후속 지표이며 ID·경로 기반 결정적 검사를 대체하지 않는다.

## NVIDIA NeMo retriever/RAG evaluation

- URL: https://docs.nvidia.com/nemo/microservices/25.8.0/evaluate/evaluation-types/rag.html
- 확인 내용: retrieval은 `recall@k`, `nDCG@k`를 별도로 측정하고, 답변 평가는 faithfulness·answer relevancy·answer correctness·context precision/recall로 나눈다. BEIR·SQuAD·RAGAS 형식을 지원한다.
- 적용: qrels 기반 Recall@1/3/5/10, MRR, nDCG@k와 답변/근거 지표를 분리한다.

## NVIDIA RAG Blueprint accuracy benchmark

- URL: https://docs.nvidia.com/rag/latest/accuracy-benchmarks.html
- 확인 내용: 여러 데이터셋과 구성을 같은 ground truth answer 기준으로 비교하고, end-to-end answer accuracy를 별도로 보고한다. judge 모델과 생성 구성을 명시한다.
- 적용: 모델·검색 프로필·top-k·데이터셋 버전을 평가 실행에 기록하고, 구성 변경 전후를 같은 1,000문항으로 비교한다.

## LlamaIndex LabelledRagDataset

- URL: https://docs.llamaindex.ai/en/v0.10.17/examples/llama_dataset/labelled-rag-datasets.html
- URL: https://github.com/run-llama/llama-datasets
- 확인 내용: 원문 노드에서 질문을 생성하고 `query`, `reference_contexts`, `reference_answer`, 생성 주체를 보존하는 labelled RAG dataset을 만든다. 같은 데이터셋으로 기준 RAG 시스템의 결과를 비교한다.
- 적용: 각 문항에 생성 방식과 검토 상태를 기록하고, reference context를 provision ID·path·원문 해시로 더 엄격하게 고정한다.

## BEIR

- URL: https://github.com/beir-cellar/beir
- 확인 내용: corpus, queries, qrels를 분리하고 nDCG@k, MAP@k, Recall@k, Precision@k, MRR을 계산한다.
- 적용: 실험 D JSON과 함께 BEIR 호환 `corpus.jsonl`, `queries.jsonl`, `qrels/test.tsv`를 생성할 수 있는 내부 계약을 둔다.

## pgvector

- URL: https://github.com/pgvector/pgvector
- 확인 내용: 차원 가변 `vector` 열에는 같은 차원의 행만 expression/partial index로 인덱싱한다. HNSW는 exact search보다 빠른 근사 검색이고 recall과 교환 관계가 있으므로 exact 결과와 비교해야 한다.
- 적용: NVIDIA 프로필 전용 512차원 HNSW partial index를 사용하고 실험 D에서 exact와 indexed 결과를 비교할 수 있게 한다.

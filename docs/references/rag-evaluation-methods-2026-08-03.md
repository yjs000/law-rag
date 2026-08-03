# RAG 평가 방법 공식 자료

확인일: 2026-08-03

## NVIDIA NeMo Platform RAG metrics

- URL: https://docs.nvidia.com/nemo-platform/documentation/evaluate-models/metrics/rag-metrics
- 확인 내용: RAG 평가 입력을 `user_input`, `retrieved_contexts`, `response`, `reference`로 분리한다. 검색 품질에는 context recall/precision/relevance, 답변에는 faithfulness, groundedness, response relevancy 등을 사용한다. 대부분의 의미 평가는 judge LLM이 필요하고 실패가 NaN으로 나타날 수 있으므로 행별 오류 확인이 필요하다.
- 적용: 실험 D 데이터셋은 질문·정답·기대 근거를 독립 필드로 보존한다. judge 점수는 후속 지표이며 ID·경로 기반 결정적 검사를 대체하지 않는다.

## NVIDIA NeMo Retriever Evaluator

- URL: https://docs.nvidia.com/nemo/microservices/latest/evaluator/metrics/retriever.html
- 확인 내용: 검색 평가는 query, corpus, relevance judgment인 qrels를 분리하고 Precision, Recall, nDCG, MAP, reciprocal rank 등을 계산한다. 정답·qrels가 없는 질문 목록만으로는 검색 정확도를 계산할 수 없다.
- 적용: qrels 기반 Recall@1/3/5/10, Precision@1/3/5/10, MRR@10, graded nDCG@k와 답변/근거 지표를 분리한다. 대표 순위 지표는 nDCG@10, 누락 방지 지표는 Recall@10, 상위 문맥 순도 진단은 Precision@5로 미리 고정한다.

## NVIDIA RAG Blueprint accuracy benchmark

- URL: https://docs.nvidia.com/rag/latest/accuracy-benchmarks.html
- 확인 내용: 여러 데이터셋과 구성을 같은 ground truth answer 기준으로 비교하고, end-to-end answer accuracy를 별도로 보고한다. judge 모델과 생성 구성을 명시한다.
- 적용: 모델·검색 프로필·top-k·데이터셋 버전을 평가 실행에 기록하고, 구성 변경 전후를 같은 1,000문항으로 비교한다.

## LlamaIndex LabelledRagDataset

- URL: https://docs.llamaindex.ai/en/v0.10.17/examples/llama_dataset/labelled-rag-datasets.html
- URL: https://github.com/run-llama/llama-datasets
- 현재 retrieval metric 소스: https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/evaluation/retrieval/metrics.py
- 확인 내용: 원문 노드에서 질문을 생성하고 `query`, `reference_contexts`, `reference_answer`, 생성 주체를 보존하는 labelled RAG dataset을 만든다. 이는 데이터 구조와 예제이지 독립 이중 주석을 요구하는 gold 제작 표준은 아니다. 현재 LlamaIndex 기본 nDCG 구현은 binary relevance를 사용한다.
- 적용: 각 문항에 생성 방식과 검토 상태를 기록하고, reference context를 provision ID·path·원문 해시로 더 엄격하게 고정한다. relevance 2/1을 사용하는 graded nDCG와 독립 검토·adjudication은 BEIR/TREC 계열을 참고한 이 프로젝트의 확장이라고 명시한다.

## BEIR

- URL: https://github.com/beir-cellar/beir
- 논문: https://datasets-benchmarks-proceedings.neurips.cc/paper_files/paper/2021/file/65b9eea6e1cc6bb9f0cd2a47751a186f-Paper-round2.pdf
- 확인 내용: corpus, queries, qrels를 분리하고 nDCG@k, MAP@k, Recall@k, Precision@k, MRR을 계산한다. 새로운 검색기가 기존 pooling 방법이 보지 못한 진짜 관련 문서를 찾으면 미판정 문서를 비관련으로 취급하는 annotation hole과 pooling bias가 생길 수 있다.
- 적용: 실험 D JSON과 함께 BEIR 형식의 `corpus.jsonl`, `queries.jsonl`, `qrels/test.tsv`를 생성할 수 있는 내부 계약을 둔다. 새 BM25·reranker를 비교할 때는 새 상위 후보를 다시 판정하는 hole audit를 수행한다.

## 프로젝트 고유 표본 설계

- 질문 1,000개, 200개 scenario family, family별 5개 표현 변형, calibration 200/test 800은 NVIDIA·LlamaIndex·BEIR가 정한 표준 크기나 분할이 아니라 이 프로젝트가 누수를 줄이기 위해 선택한 설계다.
- 같은 family의 다섯 표현은 같은 split에 둔다. 질문별 macro 평균과 함께 family 안에서 먼저 평균한 family-macro 결과를 보고하고, test family를 재표집하는 고정 방식의 95% bootstrap 신뢰구간을 기록한다.
- unlabelled 질문은행은 말투·범위·중복 검토에만 사용한다. Recall·Precision·MRR·nDCG는 독립적으로 qrels와 기준 문맥을 확정한 approved gold에만 계산한다.

## NIST trec_eval

- URL: https://github.com/usnistgov/trec_eval
- 확인 내용: TREC 공동체의 표준 검색 평가 도구로, qrels와 검색 실행 결과를 입력받아 recall, reciprocal rank, nDCG 등 순위 지표를 계산한다.
- 적용: 지표 이름이 같아도 프로젝트 자체 계산식과 표준 구현의 의미가 달라지지 않도록 qrels relevance 기준, cutoff K와 query별 평균 방식을 명시한다.

## Ragas context와 answer metrics

- URL: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/
- URL: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/
- URL: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_correctness/
- 확인 내용: Context Precision은 관련 청크가 앞에 놓이는지를 순위 가중으로 평가하고, Faithfulness는 답변의 개별 주장이 검색 문맥으로 지원되는지 평가한다. Answer Correctness는 기준 답변과 생성 답변의 사실 단위 일치와 의미 유사도를 결합한다.
- 적용: 의미 기반 judge 지표는 ID·path·SHA 기반 결정적 검색·인용 지표와 분리하고 judge 모델·프롬프트·실패/NaN을 함께 기록한다.

## pgvector

- URL: https://github.com/pgvector/pgvector
- 확인 내용: 차원 가변 `vector` 열에는 같은 차원의 행만 expression/partial index로 인덱싱한다. HNSW는 exact search보다 빠른 근사 검색이고 recall과 교환 관계가 있으므로 exact 결과와 비교해야 한다.
- 당시 적용 메모: NVIDIA 프로필 전용 512차원 HNSW partial index를 만들고 exact와 indexed 결과를 비교하려 했다. 후속 결정으로 이 비교는 1,000문항 gold와 근거 찾기 전수 검증 뒤 별도 설계·사용자 승인 전까지 보류했으며, 현재 실험 D에는 포함하지 않는다.

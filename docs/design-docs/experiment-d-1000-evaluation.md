# 실험 D 1,000문항 평가 설계

상태: 데이터셋 v2 생성 완료, 검색·답변 측정 전
확정일: 2026-08-03

## 선택한 방식

NVIDIA의 검색/답변 분리와 BEIR qrels, LlamaIndex의 labelled RAG dataset을 결합해 법률 corpus에 맞게 조정했다.

- NVIDIA 방식: retrieval과 answer generation을 분리하고 Recall@k·nDCG@k, context recall/precision, faithfulness, answer correctness를 각각 측정한다.
- BEIR 방식: corpus, query, qrels를 분리해 검색기를 같은 정답 집합으로 비교한다.
- LlamaIndex 방식: query와 reference context/reference answer를 가진 라벨 데이터셋으로 RAG 기준선을 반복 비교한다.
- 법률용 보강: 모든 근거를 DB의 document/version/provision ID, path, 원문 SHA-256으로 고정하고 기준일·근거 부족 사례를 포함한다.

공식 자료와 확인 내용은 [RAG 평가 방법 공식 자료](../references/rag-evaluation-methods-2026-08-03.md)에 기록했다.

## 왜 LLM이 1,000개 정답을 쓰게 하지 않았는가

생성 모델이 자연스러운 질문을 만들 수는 있지만 원문에 없는 법률 요건을 추가하거나 정답 범위를 바꿀 수 있다. 이번 v2는 정답 신뢰성을 우선해 질문을 결정적 템플릿으로 만들고 reference는 원문 그대로 사용했다.

LlamaIndex의 “청크에서 질문과 reference를 생성해 labelled dataset으로 보존한다”는 구조는 따르되, 법률 답은 LLM 생성문이 아니라 원문 조각으로 고정했다. 의미 변형은 `하여야 한다 → 해야 하나요`, `할 수 있다 → 할 수 있나요`, `받아야 한다 → 받아야 하나요`처럼 법적 의미를 바꾸지 않는 제한된 형태만 사용했다.

장점은 재생성해도 같은 문항이 나오고 정답 환각이 없다는 것이다. 한계는 실제 사용자의 짧고 다양한 표현보다 문장이 길고 원문과 유사하다는 것이다. 이 한계는 현재 12개 수동 검토뿐 아니라 후속 human-authored holdout에서 보완해야 한다.

## 1,000문항 구성

| 범주 | 수 | 목적 |
|---|---:|---|
| exact path control | 200 | 법률명·조문 번호 직접 조회 기준선 |
| heading lexical control | 200 | 정확한 법률명·표제·조문 표현 대조군 |
| semantic paraphrase | 200 | 의무·허가·금지·가능 표현의 제한된 의미 변형 |
| hierarchy child | 150 | 조→항→호→목 경로 복원과 하위 근거 확인 |
| hard contrast | 100 | 같은 문서의 인접 규정을 distractor로 둔 구분 능력 |
| temporal before effective | 75 | 첫 수록 버전 시행 전 기준일의 근거 부족 |
| outside corpus | 75 | 존재하지 않는 조문을 억지로 답하지 않는지 |

전체 중 850개는 answerable, 150개는 unanswerable이다. 각 범주에서 20%를 calibration으로 배정해 top-k·후속 임계값 후보를 관찰하고, 나머지 800개 test는 결정 후 최종 비교에 사용한다. test 결과를 보고 calibration 규칙을 바꾸지 않는다.

## 경계값·대조·비교군

### 경계값

- `Recall@1/3/5/10`: 후보 수를 늘릴 때 직접 근거가 언제 들어오는지 본다.
- HNSW exact 대조: indexed search가 exact cosine 순위에서 얼마나 근거를 놓치는지 본다.
- 근거 부족: 시행 전 75개와 존재하지 않는 조문 75개의 false-positive rate를 본다.
- 생성 문맥: 후보 10개와 생성 최대 5개 조문의 Evidence Recall/Precision 변화를 분리한다.

고정 similarity cutoff는 아직 채택하지 않는다. calibration 200개의 positive/negative 점수 분포가 분리되는지 관찰할 뿐이며, 직접 근거 판정을 코사인 점수 하나로 대체하지 않는다.

### 대조군

- exact path/heading 400개: lexical하게 쉬운 양성 대조군
- semantic 200개: 표현 종결을 바꾼 dense 검색군
- hard contrast 100개: 인접 조문 distractor가 있는 어려운 양성군
- negative 150개: 결과가 없어야 하는 안전 대조군

### 향후 검색기 비교

현재 dense-only를 baseline으로 저장한다. BM25를 추가하면 dense와 BM25를 독립 실행해 같은 qrels로 비교한다. RRF는 두 독립 결과가 서로 다른 실패를 보완한다는 증거가 있을 때만 세 번째 구성으로 실험한다.

## 데이터 형식

권위 데이터셋은 [experiment-d-v2-1000.json](../../apps/api/evaluation/experiment-d-v2-1000.json)이다. 각 문항은 다음을 가진다.

- `user_input`, `as_of_date`, `answerable`
- 원문 기반 `reference`, `reference_contexts`
- `document_id`, `version_id`, `provision_id`, `path`, `content_sha256`
- 관련 조각과 relevance 등급인 `qrels`
- hard contrast의 `distractor_provision_ids`
- 생성 템플릿과 사람 검토 상태

BEIR 호환 `corpus.jsonl`, `queries.jsonl`, calibration/test qrels는 `.data/experiments/context/beir-v2/`에 로컬 생성한다. 전체 법률 원문 corpus는 실행 산출물이므로 Git에 넣지 않는다.

## 자동 검증과 사람 검토

자동 검사는 다음을 보장한다.

- 정확히 1,000문항
- ID와 질문 중복 없음
- 850 positive / 150 negative
- positive는 qrels와 relevance 2의 primary evidence 보유
- negative는 qrels가 비어 있음
- qrel의 provision ID와 원문 SHA-256 일치
- calibration 200 / test 800과 범주별 고정 수량

표제가 없거나 근거가 매우 짧고 교차참조 중심인 문항은 자동 통과로 숨기지 않는다. 현재 12개를 [사람이 직접 확인할 문항](../generated/experiment-d-1000-review.md)에 질문·기준 답·이유와 함께 분리했다.

## 아직 측정하지 않은 것

이 문서는 데이터셋 생성 결과이지 검색 품질 결과가 아니다. 벡터 backfill과 HNSW 검증 후 다음을 실제 실행값으로 별도 기록한다.

- Recall@1/3/5/10, MRR, nDCG@3/5/10
- answerable 범주의 Article/Evidence Recall
- unanswerable false-positive rate
- HNSW 대 exact recall과 latency
- 생성 답변의 faithfulness·answer correctness·citation correctness

LLM judge를 쓰는 지표는 모델·프롬프트·실패/NaN 수를 함께 기록하고, ID·원문 기반 결정적 지표와 분리한다.

## 결정 기록

- 2026-08-03: 1,000문항을 850 positive와 150 negative, calibration 200과 test 800으로 고정했다.
- 2026-08-03: 법률 정답은 생성 모델 문장이 아니라 원문 reference와 qrels로 고정했다.
- 2026-08-03: semantic 문항은 법적 의미를 보존하는 제한된 종결 변형만 사용했다.
- 2026-08-03: 현재 12개 모호 문항은 삭제하거나 임의 수정하지 않고 별도 사람 검토 큐로 공개했다.

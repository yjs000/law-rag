# RAG 평가 지표: 검색, 문맥, 답변과 근거 부족 판정

확인일: 2026-08-03

이 문서는 RAG 평가에서 사용하는 지표가 각각 무엇을 측정하는지, 왜 여러 지표를 함께 봐야 하는지 설명한다. 학습용 개념 문서이며 아직 실행하지 않은 실험 D의 결과를 적는 문서가 아니다.

## 가장 중요한 원칙

> **용어 요약:** `RAG`는 `Retrieval-Augmented Generation`, 즉 “검색으로 보강한 생성”이다. 먼저 외부 문서에서 근거를 검색하고, 그 근거를 생성 모델에 전달해 답변을 만드는 방식이다.

RAG는 한 번에 하나의 점수로 평가할 수 없다. 다음 단계가 서로 다른 이유로 실패하기 때문이다.

```text
원문과 정답표가 정확한가
→ 검색기가 정답 후보를 찾았는가
→ 찾은 후보 중 직접 근거만 문맥으로 골랐는가
→ 답변이 질문에 답했는가
→ 답변의 각 주장을 인용 원문이 뒷받침하는가
→ 근거가 없을 때 답변을 거부했는가
```

예를 들어 검색 Recall이 높아도 불필요한 청크가 많으면 답변 모델이 잘못된 문맥을 사용할 수 있다. Faithfulness가 높아도 검색된 문맥 자체가 틀렸다면 답변은 틀린 문맥에 충실할 뿐이다. Answer relevancy가 높아도 답변 내용이 사실과 다를 수 있다.

NVIDIA 공식 평가 문서도 문서 검색 지표와 답변 생성 지표를 분리한다. 검색에는 `Recall@k`, `nDCG@k`를 사용하고, 답변·문맥에는 faithfulness, answer relevancy, answer correctness, context precision 같은 별도 지표를 사용한다.

## 평가 데이터의 기본 구조

### Corpus

> **용어 요약:** `Corpus`(코퍼스)는 원래 “자료의 모음”이라는 뜻이다. 검색 시스템에서는 검색 대상이 되는 문서 전체 집합을 가리킨다.

`corpus`는 검색 대상 문서 전체다. 법률 RAG에서는 각 조·항·호·목의 본문과 다음 추적 정보를 함께 가져야 한다.

- 법률 문서 ID와 버전 ID
- 조문 ID와 `조/항/호/목` 경로
- 기준일과 시행일
- 원문 SHA-256

### Query

> **용어 요약:** `Query`(쿼리)는 시스템에 보내는 요청이나 검색 질문이다. 여기서는 사용자가 입력한 법률 질문 한 건을 뜻한다.

`query`는 평가 질문이다. 실제 사용자 질문과 비슷한 질문뿐 아니라 정확한 조문 조회, 의미 변형, 인접 조문과 혼동하기 쉬운 질문, corpus 범위 밖 질문을 포함해야 한다.

### Qrels

> **용어 요약:** `Qrels`는 `Query Relevance Judgments`의 줄임말로, “각 질문에 어떤 문서가 얼마나 관련 있는지 표시한 정답표”다. `binary relevance`는 관련·무관만 나누고, `graded relevance`는 직접 근거·보조 근거처럼 관련성의 정도까지 나눈다.

`qrels`는 `query relevance judgments`의 줄임말이다. 각 질문과 문서가 얼마나 관련 있는지 적은 정답표다.

```text
질문 Q1 → 제2조의 직접 근거: relevance 2
질문 Q1 → 관련 정의 보조 근거: relevance 1
질문 Q1 → 관련 없음: relevance 0
```

관련성을 `0/1`로만 기록하면 binary relevance이고, `0/1/2`처럼 중요도를 나누면 graded relevance다. Recall과 Precision은 보통 일정 등급 이상을 관련 문서로 보지만, nDCG는 등급 차이를 순위 품질에 반영할 수 있다.

### Reference contexts와 reference answer

> **용어 요약:** `Reference`는 평가할 때 비교 기준으로 삼는 정답이다. `Reference contexts`는 정답 근거 원문, `reference answer`는 그 원문을 바탕으로 만든 기준 답변을 뜻한다.

- `reference_contexts`: 질문에 답하는 기준 원문 조각
- `reference_answer`: 비교 대상이 되는 기준 답변

LlamaIndex의 `LabelledRagDataset`은 각 사례에 `query`, `reference_contexts`, `reference_answer`, 그리고 사람이 만들었는지 AI가 만들었는지를 보존한다. 이것은 지표가 아니라 같은 평가 입력으로 여러 RAG 구성을 반복 비교하기 위한 데이터 구조다.

법률 RAG에서는 문자열만 저장하는 것보다 `document_id`, `version_id`, `provision_id`, `path`, `content_sha256`까지 고정해야 원문 변경이나 잘못된 조문 연결을 찾을 수 있다.

## 예제로 보는 검색 순위

질문에 관련된 문서가 두 개라고 가정한다.

- A: 직접 답을 가진 핵심 조문, relevance `2`
- B: 보조 정의 조문, relevance `1`

검색 결과가 다음 순서로 나왔다.

| 순위 | 문서 | relevance |
|---:|---|---:|
| 1 | B | 1 |
| 2 | C | 0 |
| 3 | A | 2 |
| 4 | D | 0 |
| 5 | E | 0 |

이 하나의 결과를 서로 다른 지표가 다르게 해석한다.

## Recall@K

> **용어 요약:** `Recall`(재현율)은 “찾아야 할 정답을 얼마나 빠뜨리지 않고 찾아냈는가”를 나타낸다. `@K`는 검색 결과의 상위 K개까지만 검사한다는 뜻이다.

`Recall@K`는 전체 정답 문서 중 상위 K개 안에서 몇 개를 찾았는지 측정한다.

```text
Recall@K = top K에서 찾은 관련 문서 수 / 전체 관련 문서 수
```

예제에서는 관련 문서가 A와 B 두 개이고 둘 다 top 3에 있다.

```text
Recall@3 = 2 / 2 = 1.0
```

### 무엇을 알려주는가

- 후보를 K개 가져오면 필요한 근거를 놓치지 않는가
- `top 3`, `top 5`, `top 10` 중 어느 범위에서 정답이 회수되는가
- dense, BM25, hybrid 검색 중 어느 방식이 근거 누락을 줄이는가

### 알려주지 않는 것

- 정답이 1위인지 K위인지는 구분하지 않는다.
- 함께 가져온 오답 문서가 얼마나 많은지는 알려주지 않는다.
- 조문 ID만 찾고 실제 답변 문구가 누락된 경우를 자동으로 구분하지 않는다.

질문마다 정답 문서가 하나뿐이면 Recall@K는 “정답이 top K에 들어온 질문의 비율”인 Hit Rate@K와 같은 값이 된다. 정답이 여러 개인 평가셋에서는 둘이 다르므로 계산 계약을 명시해야 한다.

## Precision@K

> **용어 요약:** `Precision`(정밀도)은 “가져온 결과 중 실제 정답이 얼마나 되는가”를 나타낸다. Recall이 누락을 보는 지표라면 Precision은 불필요한 결과가 얼마나 섞였는지를 보는 지표다.

`Precision@K`는 상위 K개 결과 중 실제 관련 문서가 차지하는 비율이다.

```text
Precision@K = top K의 관련 문서 수 / K
```

예제에서는 top 3 중 A와 B가 관련 문서다.

```text
Precision@3 = 2 / 3 ≈ 0.667
```

Recall을 높이려고 후보를 많이 가져오면 Precision은 낮아질 수 있다. 후보 검색 단계에서는 높은 Recall이 중요하지만, 생성 모델에 전달하는 최종 문맥에서는 높은 Precision이 중요하다.

## MRR

> **용어 요약:** `MRR`은 `Mean Reciprocal Rank`의 줄임말이다. `Rank`는 순위, `Reciprocal Rank`는 첫 정답 순위의 역수, `Mean`은 여러 질문에서 낸 평균을 뜻한다.

`MRR`은 `Mean Reciprocal Rank`, 평균 역순위다. 각 질문에서 **첫 번째 관련 문서**가 몇 위인지 본다.

```text
Reciprocal Rank = 1 / 첫 관련 문서 순위
MRR = 모든 질문의 Reciprocal Rank 평균
```

```text
1위 → 1
2위 → 0.5
3위 → 0.333...
top K 안에 없음 → 0
```

예제에서는 보조 근거 B가 1위이므로 MRR은 `1.0`이다. 하지만 핵심 직접 근거 A는 3위다. 따라서 relevance 등급이 다른 법률 근거에서는 MRR만 보면 “보조 근거가 핵심 근거보다 앞선 문제”를 놓칠 수 있다.

MRR은 “첫 정답 하나를 빨리 보여주는가”에는 적합하지만, 두 번째 이후 정답의 순서는 평가하지 않는다.

## DCG와 nDCG@K

> **용어 요약:** `DCG`는 `Discounted Cumulative Gain`으로, 관련 문서의 가치를 더하되 뒤 순위일수록 할인한다. `nDCG`의 `n`은 `normalized`로, 이상적인 순위의 점수로 나누어 0~1 범위에서 비교 가능하게 만들었다는 뜻이다.

`DCG`는 `Discounted Cumulative Gain`이다. 한국어로 풀면 “순위가 뒤로 갈수록 가치를 할인해서 더한 점수”다.

대표적인 계산식은 다음과 같다.

```text
DCG@K = Σ (2^relevance_i - 1) / log2(i + 1)
```

- relevance가 높을수록 gain이 커진다.
- 같은 관련 문서라도 뒤 순위에 있으면 `log2(i + 1)`로 할인된다.

`IDCG`는 정답 문서를 가장 이상적인 순서로 배치했을 때의 DCG다. `nDCG`는 실제 DCG를 IDCG로 나눠 질문마다 정답 수가 달라도 0~1 범위에서 비교할 수 있게 한다.

```text
nDCG@K = DCG@K / IDCG@K
```

예제 순위 `B(1), C(0), A(2)`의 DCG@3은 다음과 같다.

```text
B: (2^1 - 1) / log2(2) = 1
C: 0
A: (2^2 - 1) / log2(4) = 1.5
DCG@3 = 2.5
```

이상적인 순위 `A(2), B(1), C(0)`는 다음과 같다.

```text
IDCG@3 = 3 + 1/log2(3) ≈ 3.631
nDCG@3 = 2.5 / 3.631 ≈ 0.689
```

Recall@3은 `1.0`이지만 nDCG@3은 약 `0.689`다. 필요한 문서는 모두 찾았지만 핵심 조문을 보조 조문보다 뒤에 놓았기 때문이다.

nDCG는 다음 조건에서 특히 유용하다.

- 직접 근거와 보조 근거의 중요도를 다르게 표시했을 때
- 관련 문서가 여러 개일 때
- “찾았는가”뿐 아니라 “좋은 순서로 놓았는가”를 비교할 때

모든 qrel이 `0/1`이고 질문마다 정답이 하나뿐이면 nDCG가 제공하는 추가 정보가 줄어든다.

## Article Recall과 Evidence Recall

> **용어 요약:** `Article`은 여기서 법률의 “조”를 뜻하고, `Evidence`는 질문에 직접 답하는 근거 본문을 뜻한다. 따라서 Article Recall은 조문 ID 회수, Evidence Recall은 실제 답변 문구 회수를 검사한다.

이 두 지표는 법률 RAG에 맞춘 프로젝트 지표다.

### Article Recall@K

> **용어 요약:** 상위 K개 후보 안에 기대한 조문 `provision_id`가 들어왔는지를 보는 법률용 Recall이다. 조문 본문이 온전한지는 별도로 검사한다.

기대 조문 ID가 상위 K개의 조문 후보에 포함됐는지 검사한다.

```text
기대 provision_id가 top K에 있음 → 성공
```

### Evidence Recall@K

> **용어 요약:** 상위 K개 후보와 복원된 법률 계층 안에 질문을 실제로 뒷받침하는 근거 문구가 들어왔는지를 본다. 조문 번호만 맞고 필요한 항·호·목이 빠진 경우는 실패다.

조문 ID뿐 아니라 질문에 필요한 실제 본문이 복원된 문맥에 포함됐는지 검사한다.

```text
제2조 ID는 검색됨                   → Article Recall 성공
제2조의 “태양에너지” 하위 목은 누락 → Evidence Recall 실패
```

법률 계층을 청킹할 때 조·항·호·목 일부가 빠질 수 있으므로 두 지표를 분리해야 한다. Article Recall은 검색 식별자의 정확성을 보고, Evidence Recall은 실제로 답변 가능한 본문이 도착했는지를 본다.

## Law@1

> **용어 요약:** `Law`는 법률, `@1`은 검색 결과 1위만 검사한다는 뜻이다. 가장 먼저 나온 후보가 기대한 법률에 속하는지를 빠르게 확인하는 지표다.

`Law@1`은 1위 결과가 기대 법률에 속하는지 보는 거친 진단 지표다.

태양광 질문에서 신재생에너지법이 1위인지 빠르게 확인할 수 있지만, 같은 법 안에서 틀린 조문이 1위여도 성공한다. 따라서 Article Recall, Evidence Recall과 함께 사용해야 한다.

## Context Recall

> **용어 요약:** `Context`는 답변 모델에 전달되는 검색 문맥이다. `Context Recall`은 기준 답변에 필요한 정보가 그 문맥에 얼마나 빠짐없이 들어 있는지를 뜻한다.

`Context Recall`은 기준 답변이나 기준 원문에 필요한 정보 중 검색된 문맥이 얼마나 많이 포함하는지 본다.

개념적으로는 다음 질문이다.

> 기준 답변을 구성하는 필수 주장들을 현재 검색 문맥으로 얼마나 뒷받침할 수 있는가?

NVIDIA의 현재 RAG 지표 문서는 이를 “reference의 관련 내용 중 검색된 context가 차지하는 비율”로 설명한다. 보통 LLM judge가 기준 답변을 여러 주장으로 나누고 각 주장이 검색 문맥에서 지원되는지 평가한다.

qrels 기반 Recall@K와의 차이는 다음과 같다.

- Recall@K: 정답으로 표시한 문서 ID를 찾았는가
- Context Recall: 기준 답변에 필요한 정보가 문맥 내용에 들어 있는가

법률 RAG에서는 ID·경로·원문으로 계산하는 Evidence Recall을 우선 사용하고, LLM 기반 Context Recall은 의미 보조 지표로 두는 편이 안전하다.

## Context Precision

> **용어 요약:** 검색 문맥 중 직접 도움이 되는 청크가 얼마나 앞쪽에, 불필요한 청크보다 우선해서 놓였는지를 본다. 일반 `Precision@K`와 달리 관련 청크가 등장한 순서까지 반영한다. `Average Precision`은 관련 결과가 나타난 각 순위의 Precision을 평균한 값이다.

`Context Precision`은 관련 문맥이 불필요한 문맥보다 앞에 배치되는지 본다. Ragas의 계산은 단순한 `관련 청크 수/K`보다 Average Precision에 가까운 순위 가중 방식이다.

```text
각 관련 청크가 나온 순위에서 Precision@k를 계산
→ 관련 청크 위치의 Precision@k를 평균
```

예를 들어 관련 청크가 1위와 3위에 있다면:

```text
1위 시점 Precision = 1/1 = 1
3위 시점 Precision = 2/3 ≈ 0.667
Context Precision ≈ (1 + 0.667) / 2 = 0.833
```

관련 청크 수가 같아도 1·2위에 모여 있으면 점수가 더 높다. 생성 모델 앞에 직접 근거를 먼저 배치하고 잡음을 뒤로 보내는 품질을 평가할 수 있다.

평가 구현에 따라 LLM이 각 청크의 관련성을 판단하거나, reference context ID가 있으면 결정적으로 계산할 수 있다. 두 방식을 같은 이름으로 섞지 말고 `judge-based`와 `ID-based`를 구분해 기록해야 한다.

## Context Relevance

> **용어 요약:** `Relevance`는 질문과의 관련성이다. `Context Relevance`는 검색 문맥이 질문 주제와 얼마나 가까운지를 보지만, 그 문맥이 질문의 직접 근거인지까지 보장하지는 않는다.

`Context Relevance`는 검색 문맥이 질문 주제와 얼마나 관련 있는지를 본다. reference answer가 없어도 계산할 수 있다는 장점이 있지만, “주제가 비슷하다”와 “질문에 직접 답한다”를 혼동할 수 있다.

송전·배전 조문이 태양광 질문과 전력 분야라는 점에서는 관련 있어도 태양광의 법적 분류를 직접 설명하지 않을 수 있다. 따라서 직접 근거 판정과 `insufficient_evidence`를 Context Relevance 하나로 결정하면 안 된다.

## Context Entity Recall

> **용어 요약:** `Entity`는 사람·기관·법률명·지역처럼 구별 가능한 중요 개체다. 이 지표는 기준 답변의 중요 개체가 검색 문맥에 얼마나 빠짐없이 나타났는지 본다.

`Context Entity Recall`은 기준 답변의 중요 개체가 검색 문맥에 얼마나 포함됐는지 본다. 사람, 기관, 법률명, 허가 주체 같은 고유 개체 누락을 찾는 보조 지표다.

하지만 개체가 모두 등장해도 법률 관계가 반대일 수 있다. “장관”, “허가”, “전기사업자”가 모두 포함됐다는 사실만으로 누가 누구에게 무엇을 허가하는지 검증할 수는 없다.

## Evidence Precision

> **용어 요약:** 최종 근거로 선택한 문맥 중 실제로 질문을 직접 뒷받침하는 근거가 차지하는 비율이다. 후보를 넓게 찾은 뒤 답변에 넣을 근거를 깨끗하게 줄였는지를 본다.

`Evidence Precision`은 최종 선택한 근거 중 실제 직접 근거의 비율이다.

```text
Evidence Precision = 직접 근거로 판정된 선택 문맥 수 / 전체 선택 문맥 수
```

후보 검색의 top 10은 Recall을 높이기 위한 넓은 집합이고, 답변 생성에 전달할 3~5개 근거는 Precision을 높인 좁은 집합이어야 한다. 이 지표는 실험 C의 후보 회수와 실험 D의 문맥 선택을 분리해서 평가하게 해준다.

## Faithfulness

> **용어 요약:** `Faithfulness`는 “충실성”이다. 생성 답변이 검색 문맥에 적힌 내용만 사용했는지를 뜻하며, 검색 문맥 자체가 올바른지는 별개의 문제다.

`Faithfulness`는 생성된 답변의 각 주장이 검색 문맥으로 뒷받침되는지 본다.

```text
Faithfulness = 문맥이 지원하는 답변 주장 수 / 전체 답변 주장 수
```

예를 들어 답변에 세 주장이 있고 두 주장만 인용 본문에서 추론 가능하면 faithfulness는 `2/3`이다.

Faithfulness가 높은 것은 “주어진 문맥을 벗어나 말하지 않았다”는 뜻이다. 다음을 보장하지는 않는다.

- 검색 문맥 자체가 올바른 조문인가
- 질문에 필요한 내용을 빠짐없이 답했는가
- 기준일에 유효한 법률 버전인가

따라서 Faithfulness는 검색 품질이나 답변 완전성을 대체하지 않는다.

## Response Groundedness

> **용어 요약:** `Response`는 시스템이 생성한 답변이고, `Groundedness`는 그 답변이 제공된 근거에 발을 딛고 있는 정도다. 답변이 외부 지식이나 추측을 섞지 않았는지를 검사한다.

`Response Groundedness`도 답변이 문맥에 근거하는지 평가한다. NVIDIA/Ragas 구현에서는 Faithfulness와 별도 지표로 제공되지만 두 지표의 의미 영역이 크게 겹친다.

도구마다 프롬프트, 주장 분해 방식과 점수 계산이 다를 수 있으므로 이름만 보고 같은 값이라고 간주하면 안 된다. 실제 평가에서는 하나를 주 지표로 정하고 다른 하나는 보조 또는 교차검증으로 사용하는 편이 해석하기 쉽다.

## Response Relevancy 또는 Answer Relevancy

> **용어 요약:** `Response`와 `Answer`는 모두 생성 답변을 뜻한다. `Relevancy`는 답변이 질문의 요점을 직접 다루는 정도이며, 사실이 맞는지를 뜻하는 `Correctness`와는 다르다.

답변이 사용자 질문을 직접 다루는지 평가한다. 장황하거나 질문의 일부만 답하는 응답을 낮게 평가하는 데 사용한다.

높은 relevancy는 정답이라는 뜻이 아니다.

```text
질문: 허가권자는 누구인가?
답변: 허가권자는 환경부장관이다.
```

이 답변은 질문 형식에는 정확히 대응하므로 relevant할 수 있지만, 실제 법률상 주체가 다르면 incorrect다.

## Answer Correctness

> **용어 요약:** `Correctness`는 정답성·정확성이다. `TP`(`True Positive`)는 맞게 포함한 사실, `FP`(`False Positive`)는 잘못 추가한 사실, `FN`(`False Negative`)은 빠뜨린 사실이다. `F1`은 이 세 값을 이용해 정확성과 누락을 함께 나타내는 점수다.

`Answer Correctness`는 생성 답변을 기준 답변과 비교해 정확한지를 본다. Ragas의 현재 설명은 사실 단위의 TP·FP·FN으로 계산한 factual similarity와 임베딩 기반 semantic similarity를 가중 결합한다.

- TP: 기준 답변과 생성 답변에 모두 있는 사실
- FP: 생성 답변에만 추가된 사실
- FN: 기준 답변에는 있지만 생성 답변에서 빠진 사실

사실 부분의 대표 계산은 F1 형태다.

```text
F1 = TP / (TP + 0.5 × (FP + FN))
```

법률 답변에서는 부정, 예외, 의무와 재량의 차이가 중요하다. 의미 유사도만 높고 법적 효과가 반대인 문장을 통과시키지 않도록 원문 인용과 주장별 entailment 검사를 별도로 둬야 한다.

## Answer Similarity

> **용어 요약:** `Similarity`는 두 문장의 의미적 유사성이다. 표현이 비슷한지를 보는 지표이지, 부정·예외·의무처럼 법적 효과까지 정확히 같은지를 보장하는 지표는 아니다.

생성 답변과 기준 답변의 임베딩 의미 유사도를 본다. 표현이 달라도 비슷한 뜻인지 확인하는 데 유용하지만, 다음 차이에 둔감할 수 있다.

- “해야 한다”와 “할 수 있다”
- “허가한다”와 “허가하지 않는다”
- 원칙과 단서·예외

따라서 법률 정답성의 단독 게이트로 사용하지 않는다.

## Citation Correctness와 Citation Coverage

> **용어 요약:** `Citation`은 인용이다. `Citation Correctness`는 붙인 인용이 해당 주장을 실제로 지원하는지, `Citation Coverage`는 근거가 필요한 주장에 인용이 빠짐없이 붙었는지를 본다.

### Citation Correctness

> **용어 요약:** 주장과 인용을 한 쌍으로 보았을 때 인용 원문이 그 주장을 실제로 뒷받침하는지를 검사한다.

답변에 붙인 인용이 바로 그 주장을 실제로 뒷받침하는지 검사한다.

```text
Citation Correctness = 지원되는 주장-인용 쌍 / 검사한 주장-인용 쌍
```

### Citation Coverage

> **용어 요약:** `Coverage`는 범위의 충족 정도다. 답변의 실질 주장 전체 중 유효한 인용이 붙은 주장이 얼마나 되는지를 본다.

근거가 필요한 답변 주장 중 유효한 인용을 가진 비율이다.

```text
Citation Coverage = 유효 인용이 있는 실질 주장 수 / 인용이 필요한 전체 실질 주장 수
```

정확한 인용 하나만 붙여도 correctness는 높을 수 있지만 나머지 주장에 인용이 없으면 coverage가 낮다. 둘을 함께 봐야 한다.

### Source integrity

> **용어 요약:** `Source`는 출처 원문, `integrity`는 무결성이다. 인용한 ID·경로·문구·문서 해시가 실제 원문과 변조 없이 정확히 연결되는지를 뜻한다.

법률 RAG에서는 의미 판정 전에 다음을 결정적으로 검사한다.

- 인용 ID가 실제 검색 결과에 존재하는가
- 조·항·호·목 경로가 원문과 일치하는가
- 인용문이 원문에 정확히 존재하는가
- 문서 버전과 SHA-256이 평가 기준과 일치하는가

이 검사는 LLM judge 점수로 대체하지 않는다.

## Noise Sensitivity

> **용어 요약:** `Noise`는 질문에 불필요하거나 무관한 문맥이고, `Sensitivity`는 그 잡음에 영향을 받는 정도다. 관련 없는 조문이 섞였을 때 답변이 흔들리는지를 본다.

`Noise Sensitivity`는 관련 없는 문맥이 섞였을 때 답변이 잘못된 정보에 얼마나 영향을 받는지 본다. NVIDIA의 현재 문서에서는 낮을수록 일반적으로 잡음에 덜 민감하다고 설명한다.

예를 들어 정확한 태양에너지 조문과 무관한 송전사업 조문을 함께 넣어도 답변이 직접 근거만 사용해야 한다. top 10을 넉넉히 검색한 뒤 일부만 생성 문맥으로 줄이는 이유를 검증하는 지표다.

## 근거 부족 판정 지표

평가셋에서 answerable을 양성, unanswerable을 음성으로 두면 다음 지표를 계산할 수 있다.

### Unanswerable false-positive rate

> **용어 요약:** `Unanswerable`은 현재 corpus의 근거로 답할 수 없는 질문이다. `False positive`는 실제로는 답할 수 없는데 답할 수 있다고 잘못 판정한 경우이며, `rate`는 그 비율이다.

근거가 없는 질문인데 답변 가능하다고 잘못 통과시킨 비율이다.

```text
FPR = unanswerable인데 답변한 수 / 전체 unanswerable 수
```

법률 RAG에서 가장 위험한 오류 중 하나이므로 낮을수록 좋다.

### Abstention recall

> **용어 요약:** `Abstention`은 답변을 억지로 만들지 않고 보류·거부하는 행동이다. 이 지표는 근거가 부족한 질문을 얼마나 빠짐없이 올바르게 거부했는지 본다.

근거 부족 질문을 올바르게 `insufficient_evidence`로 판정한 비율이다.

```text
Abstention Recall = 올바르게 거부한 unanswerable 수 / 전체 unanswerable 수
```

### Answerable false-negative rate

> **용어 요약:** `Answerable`은 근거가 있어 답할 수 있는 질문이다. `False negative`는 실제로 답할 수 있는데 답할 수 없다고 잘못 거부한 경우이며, 이 지표는 그 비율이다.

근거가 있는데도 근거 부족으로 잘못 거부한 비율이다.

```text
FNR = answerable인데 거부한 수 / 전체 answerable 수
```

무조건 많이 거부하면 FPR은 낮아지지만 FNR이 높아진다. 두 지표를 같이 보고 calibration 데이터에서 기준을 정한 뒤 test 데이터에는 기준을 고정해야 한다.

## HNSW exact-search 대비 recall

> **용어 요약:** `HNSW`는 `Hierarchical Navigable Small World`의 줄임말로, 모든 벡터를 전부 비교하지 않고 그래프를 따라 빠르게 이웃을 찾는 근사 검색 방식이다. `ANN`은 `Approximate Nearest Neighbor`, 근사 최근접 이웃 검색을 뜻한다. `Exact search`는 모든 후보를 정확히 비교하며, 여기의 recall은 HNSW가 exact 상위 결과를 얼마나 재현했는지를 뜻한다.

이 지표는 qrels 기반 검색 Recall과 다른 문제를 측정한다.

- qrels Recall: 법적으로 정답인 문서를 찾았는가
- ANN recall: 근사 검색이 exact vector search의 상위 결과를 얼마나 재현했는가

대표적으로 다음처럼 계산할 수 있다.

```text
ANN Recall@K = |HNSW top K ∩ exact top K| / K
```

ANN Recall이 낮으면 임베딩 모델이 아니라 HNSW 인덱스 설정 때문에 후보가 누락될 수 있다. 반대로 ANN Recall이 1.0이어도 exact 검색 자체가 법적 정답을 못 찾으면 qrels Recall은 낮다.

## 운영 지표

> **용어 요약:** `Latency`는 요청부터 결과까지 걸린 시간이다. `p50`은 절반의 요청이 이 시간 안에 끝났다는 뜻이고, `p95`는 95%의 요청이 이 시간 안에 끝났다는 뜻이다. `NaN`은 `Not a Number`로, 정상 숫자 점수를 계산하지 못한 실패 상태를 나타낼 수 있다.

품질이 같다면 더 빠르고 안정적인 구성이 낫다. 다음을 품질 지표와 함께 기록한다.

- p50, p95, 최대 latency
- 임베딩·reranker·judge·생성 단계별 시간
- API 호출 실패, timeout, 재시도 수
- judge 결과의 NaN과 행별 오류 수
- 질문당 토큰과 비용
- 동일 입력 반복 시 순위·점수·응답의 재현성

NVIDIA 문서는 일부 RAGAS 지표가 judge 호출 실패 시 예외 대신 NaN을 반환할 수 있다고 경고한다. 실패 행을 제외하고 평균만 내면 점수가 인위적으로 좋아질 수 있으므로 `count`, 오류 수와 NaN 수를 함께 보고해야 한다.

## 결정적 지표와 LLM judge 지표

> **용어 요약:** `LLM`은 `Large Language Model`, 대규모 언어 모델이다. `LLM judge`는 별도의 언어 모델이 답변·문맥의 품질을 심사하도록 하는 방식이며, 코드 공식만으로 계산하는 결정적 지표와 구분한다.

### 결정적 지표

같은 입력이면 같은 결과가 나오며 코드로 직접 계산할 수 있다.

- ID 기반 Recall@K, Precision@K, MRR, nDCG
- Article/Evidence Recall과 Evidence Precision
- ID·path·SHA-256 검증
- citation source integrity
- unanswerable FPR과 answerable FNR
- latency와 오류 수

### LLM judge 지표

> **용어 요약:** 사람 대신 LLM이 의미를 읽고 점수를 매기는 지표다. 모델·프롬프트에 따라 판정이 달라질 수 있으므로 사람 정답표와의 일치율을 먼저 검증해야 한다.

문장의 의미를 판정해야 하므로 모델과 프롬프트에 의존한다.

- Context Recall/Precision/Relevance의 의미 기반 변형
- Faithfulness와 Groundedness
- Answer Relevancy와 Answer Correctness
- 주장-인용 entailment

LLM judge 결과에는 반드시 다음을 기록한다.

- judge 모델과 정확한 버전
- 프롬프트와 temperature 등 설정
- 입력 reference와 context
- 행별 판정과 이유
- 실패·timeout·NaN 수
- 사람 라벨과의 일치율 및 오탐·미탐

## 실험 D에서 지표를 읽는 순서

1. **데이터 무결성**: ID·path·SHA-256과 기준일이 모두 맞는지 확인한다.
2. **후보 회수**: Recall@1/3/5/10과 Evidence Recall로 직접 근거가 후보 안에 들어오는지 본다.
3. **순위 품질**: MRR과 graded nDCG로 핵심 근거가 보조 근거보다 앞서는지 본다.
4. **문맥 축소**: Context/Evidence Precision과 Recall을 함께 보며 top 10에서 생성 문맥 3~5개로 줄였을 때 근거를 잃지 않는지 본다.
5. **근거 부족**: unanswerable FPR과 answerable FNR을 함께 본다.
6. **답변 생성**: Faithfulness, Answer Relevancy, Answer Correctness를 분리해 본다.
7. **인용 검증**: Citation Correctness·Coverage와 ID·path·SHA 검사를 통과하는지 본다.
8. **운영성**: latency, 비용, 오류, NaN과 반복 재현성을 확인한다.

## 한 점수만 보면 생기는 오판

| 높은 점수 | 그래도 남을 수 있는 실패 |
|---|---|
| Recall@10 | 정답이 10위이고 오답 9개가 앞에 있음 |
| MRR | 첫 보조 근거만 빠르고 핵심·예외 근거는 누락 |
| nDCG | qrels 자체가 잘못 표시됨 |
| Context Precision | 필요한 근거 일부가 완전히 누락됨 |
| Context Recall | 불필요한 문맥이 너무 많이 섞임 |
| Faithfulness | 틀린 검색 문맥에 충실하게 답함 |
| Answer Relevancy | 질문에는 맞지만 사실이 틀림 |
| Answer Correctness | 올바른 답이지만 인용이 없거나 잘못됨 |
| Citation Correctness | 일부 주장만 인용되고 나머지는 무근거 |
| ANN Recall | exact vector 검색 자체가 법적 정답을 못 찾음 |

## 최소 권장 지표 묶음

법률 RAG의 최소 평가 묶음은 다음과 같다.

```text
검색 후보:
Recall@1/3/5/10 + MRR + graded nDCG@3/5/10

실제 근거:
Article Recall + Evidence Recall + Evidence Precision

근거 부족:
unanswerable FPR + answerable FNR

생성 답변:
Faithfulness + Answer Correctness + Answer Relevancy

인용:
Citation Correctness + Citation Coverage + ID/path/SHA 검증

운영:
p50/p95 latency + 비용 + 오류/NaN + 재현성
```

## 출처

- [NVIDIA NeMo Platform RAG Evaluation Metrics](https://docs.nvidia.com/nemo-platform/documentation/evaluate-models/metrics/rag-metrics)
- [NVIDIA NeMo Microservices RAG Evaluation Type](https://docs.nvidia.com/nemo/microservices/25.8.0/evaluate/evaluation-types/rag.html)
- [NVIDIA RAG Blueprint accuracy benchmark](https://docs.nvidia.com/rag/latest/accuracy-benchmarks.html)
- [LlamaIndex LabelledRagDataset 공식 예제](https://docs.llamaindex.ai/en/v0.10.17/examples/llama_dataset/labelled-rag-datasets.html)
- [LlamaIndex llama-datasets 공식 GitHub](https://github.com/run-llama/llama-datasets)
- [BEIR 공식 GitHub](https://github.com/beir-cellar/beir)
- [NIST trec_eval 공식 GitHub](https://github.com/usnistgov/trec_eval)
- [Ragas Context Precision 공식 문서](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/)
- [Ragas Faithfulness 공식 문서](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)
- [Ragas Answer Correctness 공식 문서](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_correctness/)

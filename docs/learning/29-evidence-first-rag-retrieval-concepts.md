# 근거 우선 RAG 검색의 전체 개념

확인일: 2026-08-03

이 문서는 실험 C·D에서 사용한 영어 용어를 쉬운 말로 설명한다. 학습 로드맵이나 실행 증거가 아니라, 나중에 다시 읽기 위한 개념 자료다.

## 전체 흐름

```text
Corpus 준비
→ Chunking
→ Dense retrieval로 후보를 넉넉히 찾기
→ Article 단위로 묶기
→ Evidence를 고르기
→ 근거가 부족하면 insufficient_evidence
→ 충분할 때만 답변 생성
```

## Corpus

`Corpus`(코퍼스)는 검색 대상 문서 전체다. 이 실험에서는 선택한 저작권법, 전기사업법, 신재생에너지법의 조문과 그 하위 항·호·목이 corpus다.

검색 모델은 corpus에 없는 본문을 찾을 수 없다. 조문 번호만 있고 실제 본문이 빠졌다면 검색 점수가 아무리 좋아도 답변 근거는 만들 수 없다. 그래서 검색 알고리즘보다 corpus 정확성을 먼저 확인한다.

## Parser와 normalization

`Parser`(파서)는 Open API의 JSON·XML을 프로그램 내부의 일정한 문서 구조로 바꾸는 코드다. `Normalization`(정규화)은 서로 다른 입력 형식을 같은 필드와 규칙으로 맞추는 과정이다.

예를 들어 JSON과 XML이 다르게 생겼어도 결과는 다음처럼 같아야 한다.

```text
제2조
└─ 호2.
   └─ 목가. 태양에너지
```

## Legal hierarchy와 parent path

`Legal hierarchy`는 법률의 `장 → 절 → 조 → 항 → 호 → 목` 계층이다. `parent_path`는 각 조각의 바로 위 부모 경로다.

```text
path:        제2조/호2./목가.
parent_path: 제2조/호2.
```

부모 경로를 보존하면 `가. 태양에너지`라는 짧은 목만 검색되어도 상위 호의 “재생에너지” 정의와 조문 제목을 함께 복원할 수 있다.

## Corpus validator

`Validator`는 결과가 약속한 조건을 만족하는지 검사하는 장치다. corpus validator는 중복 경로, 장 제목으로 대체된 조문, 없는 부모 경로 같은 오류를 임베딩 전에 차단한다.

검증 실패를 무시하고 계속 검색하는 것보다 준비 단계에서 멈추는 편이 안전하다. 잘못된 corpus에서 나온 높은 점수는 품질 증거가 아니기 때문이다.

## Chunk와 chunking

`Chunk`는 검색할 수 있도록 나눈 문서 조각이고, `chunking`은 문서를 조각으로 나누는 과정이다. 이 프로젝트는 새 분할법을 만들지 않고 기존 법률 청커를 재사용한다.

항·호·목처럼 작은 단위는 특정 문장을 잘 찾게 해주지만 문맥이 부족할 수 있다. 그래서 검색은 작은 청크로 하고, 답변 직전에는 같은 조의 부모·자식 청크를 다시 묶는다.

## Embedding과 vector

`Embedding`은 문장을 여러 숫자로 바꾼 표현이고, 그 숫자 목록을 `vector`(벡터)라고 한다. 비슷한 의미의 문장은 벡터 공간에서 비슷한 방향을 갖도록 모델이 학습된다.

이 실험은 NVIDIA NIM의 `nvidia/nemotron-3-embed-1b`로 질문과 청크를 임베딩하고 코사인 유사도를 계산한다.

## Dense retrieval과 dense-only

`Dense retrieval`(밀집 검색)은 임베딩 벡터의 의미적 가까움을 이용하는 검색이다. 질문과 문서에 같은 단어가 없어도 의미가 비슷하면 찾을 수 있다.

`Dense-only`는 키워드 검색을 섞지 않고 임베딩 검색만 쓰는 기준선이다.

```text
질문 임베딩
→ 모든 청크 임베딩과 코사인 유사도 계산
→ 점수가 높은 후보부터 정렬
```

장점은 표현이 달라도 찾을 수 있다는 점이다. 단점은 정확한 법률명·조문 번호·전문용어보다 넓게 관련된 문장을 높게 올릴 수 있다는 점이다.

## Candidate와 top-k

`Candidate`는 아직 최종 근거로 확정하지 않은 후보 문서다. `top-k`는 점수가 높은 앞의 k개를 뜻한다. top 10이면 상위 후보 10개를 관찰한다.

후보 수를 넉넉히 잡는 목적은 정답을 놓치지 않는 것이다. 후보 10개를 모두 AI에 넣어야 한다는 뜻은 아니다. 실험 C는 후보를 찾고, 실험 D는 그중 직접 근거만 답변 문맥으로 만든다.

## Article grouping

`Article grouping`은 같은 조에 속한 여러 항·호·목 청크를 하나의 조 후보로 묶는 것이다. 같은 제2조의 청크 여러 개가 순위를 독점하지 않게 한다.

현재 조 점수는 해당 조의 청크 중 가장 높은 코사인 점수다. 작은 청크로 잘 찾되 최종 관찰 단위는 조로 정리하는 방식이다.

## Evidence

`Evidence`는 질문에 실제로 답할 수 있는 본문이다. 주제만 비슷한 문장은 근거가 아니다.

```text
질문: 전기사업 허가권자는 누구인가?

간접 관련: 제7조에 따라 허가받은 자
직접 근거: 산업통상자원부장관의 허가를 받아야 한다
```

첫 문장은 허가권자를 말하지 않으므로 직접 근거가 아니다.

## Evidence contract

`Evidence contract`는 고정 평가 질문이 어떤 법률·조문·필수 문구를 가져야 성공인지 적은 검사 약속이다.

```text
질문: 태양에너지는 어디에 해당하는가?
기대 조문: 신재생에너지법 제2조
필수 문구: 재생에너지, 태양에너지
```

이 계약은 평가용 정답표다. 임의의 실제 사용자 질문을 자동으로 이해하는 범용 판정기가 아니다.

## Hard gate와 insufficient_evidence

`Gate`는 다음 단계로 보내도 되는지 결정하는 문이다. `Hard gate`는 조건을 만족하지 않으면 반드시 차단하는 규칙이다.

`insufficient_evidence`는 “비슷한 문서를 찾았지만 이 corpus만으로는 안전하게 답할 직접 근거가 부족하다”는 상태다. 실패를 숨기거나 가장 비슷한 문서를 정답처럼 보여주지 않는다.

예를 들어 질문의 근거가 전기사업법 제7조인데 corpus가 제1장과 제6장만 포함하고 제7조를 제외했다면, 제2조의 “허가받은 자” 문장이 높게 검색되어도 답변 생성을 허용하지 않는다.

## Baseline

`Baseline`(기준선)은 새 방법이 좋아졌는지 비교하는 기존 결과다. 복잡한 기능을 추가한 뒤 수치가 같거나 나빠지면 개선이라고 할 수 없다.

이 실험의 수정된 dense-only 기준선은 범위 내 5개 질문에서 Law@1, Article Recall@3/5/10, Article MRR, Evidence Recall@3/5/10이 모두 1.0이다. 평가셋이 작으므로 일반 성능이 완벽하다는 뜻은 아니다.

## Recall@K

`Recall@K`는 정답이 상위 K개 안에 들어온 질문의 비율이다.

```text
5개 질문 중 4개의 정답이 top 3 안에 있음
Recall@3 = 4 / 5 = 0.8
```

1위와 3위는 모두 Recall@3 성공으로 계산된다. 순위 차이는 MRR로 본다.

## Article Recall과 Evidence Recall

`Article Recall`은 기대 조문 ID가 후보 안에 있는지를 본다. `Evidence Recall`은 질문에 필요한 실제 본문이 후보 조문의 복원된 계층 안에 있는지를 본다.

```text
제2조 ID는 찾음             → Article Recall 성공
제2조의 “태양에너지” 목 누락 → Evidence Recall 실패
```

이번 실험에서 실제로 Article Recall은 1.0인데 Evidence Recall이 0.8인 중간 상태가 있었다. 이 차이 때문에 두 지표를 분리해야 한다.

## MRR

`MRR`은 Mean Reciprocal Rank, 한국어로 평균 역순위다. 첫 정답이 얼마나 앞에 있는지를 본다.

```text
1위 → 1/1 = 1
2위 → 1/2 = 0.5
3위 → 1/3 = 0.333...
```

각 질문의 값을 평균한다. 높을수록 첫 정답이 앞에 있다.

## Evidence Precision

`Evidence Precision`은 선택한 근거 중 실제로 질문을 뒷받침하는 근거의 비율이다. 후보를 너무 많이 넣으면 Recall은 유지되어도 Precision이 낮아질 수 있다.

```text
선택한 근거 5개 중 직접 근거 2개
Evidence Precision = 2 / 5 = 0.4
```

## Citation Correctness

`Citation Correctness`는 답변에 붙인 인용이 바로 그 주장을 실제로 뒷받침하는지 보는 품질이다. 관련 법률을 인용했어도 주장에 필요한 문장이 없다면 올바른 인용이 아니다.

## Lexical retrieval과 BM25

`Lexical retrieval`은 실제 단어가 얼마나 겹치는지 보는 키워드 검색이다. `BM25`는 대표적인 키워드 순위 알고리즘이다.

법률명, 조문 번호, 고유명사, 정확한 전문용어에 강하다. 반면 질문이 “얼마나 자주”이고 본문이 “5년마다”처럼 표현이 다르면 놓칠 수 있다.

## Hybrid search

`Hybrid search`는 dense 검색과 lexical 검색을 결합한다.

```text
의미 검색 결과 + 키워드 검색 결과 → 결합 순위
```

두 방식의 약점을 보완할 수 있지만, 기능이 복잡해지는 만큼 실제 평가에서 좋아졌다는 증거가 필요하다.

## RRF

`RRF`는 Reciprocal Rank Fusion, 역순위 결합이다. dense 점수와 BM25 점수는 단위가 달라 직접 더하기 어렵기 때문에 점수 대신 각 검색의 순위를 사용한다.

```text
RRF(d) = 1/(k + dense 순위) + 1/(k + lexical 순위)
```

검색 방식이 더 있으면 각 항을 계속 더한다. 한 순위의 기여를 다른 순위에서 빼는 공식이 아니다. 두 검색에서 모두 높은 문서는 합계가 커진다.

## Reranker

`Reranker`는 1차 검색 후보를 더 정교한 모델로 다시 평가해 순서를 바꾸는 단계다. 보통 검색기는 후보를 넉넉히 찾고, reranker는 더 적은 후보를 읽는다.

정확도를 높일 수 있지만 호출 시간과 비용이 늘고 별도 평가가 필요하다. 현재 실험 D는 AI reranker 없이 고정 근거 계약으로만 동작한다.

## GraphRAG

`GraphRAG`는 문서에서 개체와 관계를 추출해 그래프를 만들고 검색에 활용하는 RAG 방식이다. 여러 문서의 관계를 따라가거나 corpus 전체 주제를 요약할 때 유용할 수 있다.

현재 문제는 이미 법률에 적힌 `조 → 항 → 호 → 목` 구조를 복원하는 것이다. 이 구조는 검색으로 새로 추론할 관계가 아니라 원문에서 보존해야 할 계층이다. 따라서 지금은 그래프보다 파서·validator·근거 게이트가 더 단순하고 직접적인 해결책이다.

## 한 문장으로 정리

정확한 문서를 먼저 만들고, 작은 청크로 후보를 넉넉히 찾고, 법률 계층을 복원해 직접 근거만 묶으며, 근거가 부족하면 답하지 않는 것이 현재 실험의 핵심이다.

## 출처

- [RAGFlow 공식 저장소](https://github.com/infiniflow/ragflow)
- [Microsoft GraphRAG query overview](https://microsoft.github.io/graphrag/query/overview/)
- [LlamaIndex node postprocessors](https://developers.llamaindex.ai/python/framework/module_guides/querying/node_postprocessors/)
- [Haystack DocumentJoiner](https://docs.haystack.deepset.ai/docs/documentjoiner)
- [Reciprocal Rank Fusion 원 논문](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)

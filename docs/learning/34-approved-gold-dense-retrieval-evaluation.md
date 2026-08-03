# 승인된 Gold만 실행하는 Dense 검색 평가

확인일: 2026-08-03

이 문서는 일반 사용자 질문은행이 어떻게 실제 검색 평가 자료가 되는지, 실험 D runner가 왜 두 번 검사하고 DB 공유 잠금을 잡는지, Recall과 HitRate가 어떻게 다른지를 한 흐름으로 설명한다. 실제 일반 사용자 1,000문항의 검색 결과를 기록한 문서가 아니다.

## 질문 1,000개만으로는 왜 평가할 수 없는가

정답 없는 질문은행으로 확인할 수 있는 것은 다음과 같다.

- 일반인다운 말투인가
- 질문 범위와 주제가 적절한가
- 중복되거나 선행 문맥이 빠진 질문이 없는가
- 특정 기술이나 상황에 지나치게 치우치지 않았는가

하지만 검색 결과가 맞는지는 확인할 수 없다. Recall, Precision, MRR과 nDCG를 계산하려면 질문마다 어떤 원문이 직접 근거인지 미리 확정한 정답표가 필요하다.

```text
질문은행 draft
→ 사용자가 질문 문구와 범위를 승인
→ 공식 원문에서 독립적으로 근거 후보 수집·판정
→ 다른 검토자가 불일치를 해결
→ 전체 dataset과 문항별 payload를 별도 adjudication manifest로 봉인
→ qrels·reference contexts·reference response가 있는 approved gold
→ 검색 평가
```

`not_annotated`는 정답이 없는 편이 더 좋은 평가라는 뜻이 아니다. 질문을 먼저 검토하고 현재 검색기의 결과를 정답으로 굳히지 않기 위한 임시 상태다.

## 검색 결과를 정답으로 저장하면 생기는 순환 평가

현재 검색기의 top 10을 그대로 qrels로 저장하면 다음 문제가 생긴다.

```text
현재 검색기가 찾은 조문
→ 그 조문을 정답으로 등록
→ 현재 검색기가 정답을 잘 찾았다고 평가
```

검색기의 누락과 오탐이 gold에 들어가므로 새 검색기와 공정하게 비교할 수 없다. 따라서 후보 수집에는 dense, lexical, 법률 경로 직접 확인 같은 여러 방법을 사용할 수 있지만, 어느 시스템이 후보를 냈는지는 주석자에게 숨기고 사람이 공식 원문을 판정한다.

## 후보 pool은 어떻게 빠진 정답을 줄이는가

한 검색기의 top 10만 판정하면 그 검색기가 놓친 조문은 qrels 후보에도 들어오지 않는다. 그래서 주석 단계에서는 여러 후보 수집 방법을 분리하고 다음 값을 고정한다.

- 방법 ID와 종류
- 방법 설정의 SHA-256
- 방법별 정확한 `top_k`
- 문항별 실제 후보 provision ID 전체와 정렬 집합 SHA-256
- 모든 방법 후보의 합집합인 문항별 판정 pool

전체 corpus 직접 검토만 `top_k`를 갖지 않는다. 그 밖의 방법은 후보 수가 `min(top_k, corpus_snapshot.searchable_provision_count)`와 정확히 같아야 한다. 각 방법의 후보 합집합은 `judged_candidate_provision_ids`와 같아야 하고, 전수 판정 뒤 qrels와 distractor의 합집합도 이 판정 pool과 같아야 한다.

`full_corpus_manual_review`를 선언한 경우에는 단지 현재 provision ID를 모두 적는 것으로 끝나지 않는다. 각 질문의 `as_of_date`에 실제로 효력이 있는 searchable provision 전체와 후보 집합이 정확히 같은지 preflight가 확인한다. qrel뿐 아니라 distractor와 pool 후보도 그 기준일에 유효해야 한다. 이 검사는 “정답이 될 법한 본문”만 남기는 생성 휴리스틱과 분리되어 장·절 표지나 짧은 조각도 검색 가능하다면 판정 대상으로 보존한다.

## Gold에 필요한 세 종류의 정답

### Qrels

`qrels`는 질문과 검색 단위의 관련성 정답표다.

- relevance `2`: 필수 답변 요소를 직접 뒷받침하는 원문
- relevance `1`: 직접 근거를 이해하는 데 필요한 보조 문맥
- relevance `0`: gold qrels에 넣지 않고 distractor로 판정한 후보

각 qrel은 `document_id`, `version_id`, `provision_id`, 조문 경로, 기준일, 본문 SHA-256과 passage SHA-256으로 고정한다.

### Reference contexts

`reference_contexts`는 qrel이 가리킨 당시 원문을 동결한 기준 문맥이다. 나중에 corpus가 바뀌어도 평가 당시 정답 문맥을 다시 확인할 수 있다.

### Reference response

`reference_response`는 검색 정답이 아니라 최종 기대 동작과 기준 답이다.

- 직접 답변
- 확인 가능한 부분만 답하고 한계를 밝히기
- 필요한 사용자 사실을 다시 묻기
- 직접 근거 부족으로 답변 보류

따라서 검색 평가는 qrels로, 후속 답변 평가는 reference contexts와 reference response로 나눈다.

## 질문이 넓으면 필수 답변 요소를 나눈다

“태양광 사업을 시작하려면 무엇을 준비해야 하나요?”처럼 넓은 질문은 조문 하나를 찾았다고 끝나지 않는다. 허가, 부지, 계통연계, 검사처럼 답에 필요한 요소를 `required_answer_facets`로 나누고 각 요소를 grade 2 qrels에 연결한다.

이렇게 하면 다음 두 경우를 구분할 수 있다.

```text
직접 근거 하나는 찾음                 → HitRate 성공
필수 요소 네 개 중 하나만 뒷받침함    → Recall과 facet recall은 1보다 작음
```

## 질문 승인과 Gold 승인은 다르다

질문 승인 manifest는 사용자가 확인한 질문 ID, 문구·범위 SHA-256과 승인 시각을 질문은행과 별도 파일로 고정한다. 이 승인은 질문을 몰래 바꾸지 않았다는 증거이며 qrels의 정확성까지 승인한다는 뜻은 아니다.

질문을 승인했다고 qrels까지 정답이 되는 것은 아니다. 공식 원문 주석, 후보 전수 판정과 독립 검토를 끝낸 뒤 별도 gold adjudication manifest가 완성 dataset과 각 문항을 다시 봉인한다. 다음 네 파일이 서로 맞아야 `approved_gold`가 된다.

1. 고정 질문은행
2. 별도 질문 승인 manifest
3. qrels·reference contexts·reference response를 가진 gold dataset
4. 전체 gold dataset canonical SHA-256과 1,000개 문항별 완성 payload canonical SHA-256을 가진 adjudication manifest

Canonical JSON은 객체 key 정렬과 고정 직렬화 규칙으로 같은 내용을 항상 같은 바이트열로 만드는 표현이다. 그러므로 adjudication 뒤 reference response 한 문장이나 qrel 하나만 바뀌어도 문항 해시와 전체 dataset 해시가 달라져 실행이 거부된다.

승인 시각도 증거의 순서를 고정한다.

```text
질문 approval manifest의 approved_at
< 문항 annotation_review.reviewed_at
< gold adjudication manifest의 approved_at
```

같은 시각은 허용하지 않는다. 먼저 완성 gold를 승인한 뒤 나중에 review 시각만 채우는 식의 사후 정당화를 막기 위한 계약이다.

## 왜 preflight를 두 번 하는가

runner의 순서는 다음과 같다.

```text
artifact 계약과 critical code provenance 확인
→ REPEATABLE READ, READ ONLY 초기 transaction에서 preflight + retrieval 상태 검사
→ 질문 임베딩
→ READ COMMITTED, READ ONLY transaction의 첫 snapshot-taking statement로 shared lock 획득
→ locked preflight + retrieval 상태 재검사
→ 기준일별 대표 exhaustive exact cosine query EXPLAIN과 SHA-256 기록
→ 모든 질문 raw exact cosine 검색
→ lock 해제
→ 지표 계산
→ 완성 결과만 원자 게시
```

초기 검사는 미승인 질문, 바뀐 qrel, 준비되지 않은 corpus나 벡터 때문에 실패할 실행이 NVIDIA 임베딩 비용을 쓰지 않게 한다.

질문 1,000개를 임베딩하는 동안 corpus가 바뀔 수 있으므로 초기 검사만으로는 부족하다. 초기 검사는 한 번의 일관된 읽기를 위해 `REPEATABLE READ, READ ONLY`를 사용한다. 임베딩 뒤에는 별도 `READ COMMITTED, READ ONLY` transaction에서 writer와 같은 corpus mutation key의 PostgreSQL shared transaction advisory lock을 첫 snapshot-taking statement로 얻고 그 잠금 안에서 다시 검사한다. 잠금 직전에 commit된 writer의 결과를 locked preflight가 보게 하면서, collector나 vector backfill처럼 같은 key의 exclusive lock을 쓰는 writer와 검색 구간이 겹치지 않게 한다. 같은 연결과 transaction을 마지막 검색까지 유지한다.

질문 임베딩을 lock 전에 하는 이유는 corpus writer를 불필요하게 오래 기다리게 하지 않기 위해서다. 그 사이 상태가 바뀌면 locked preflight가 실행을 거부한다.

## 검색 상태 지문에는 무엇이 들어가는가

같은 질문과 corpus라도 벡터나 검색 실행 방식이 바뀌면 순위가 달라질 수 있다. runner는 exhaustive exact cosine 평가에 실제로 영향을 주는 상태만 검증하고 결과에 기록한다.

- NVIDIA embedding profile의 모델, query/passage 유형, native·stored 차원, 축약·정규화와 템플릿 버전
- 검색 가능한 provision 수와 active 벡터 수
- passage 벡터의 source SHA와 전체 벡터 지문
- L2 norm 위반 벡터 수
- PostgreSQL server와 pgvector extension 버전
- transaction isolation·read-only 상태
- `enable_seqscan`, `enable_indexscan`, `enable_bitmapscan`, `random_page_cost`, `effective_cache_size`, `work_mem` 같은 planner 설정

이 값들을 canonical JSON으로 묶은 retrieval state fingerprint를 저장한다. 실행 입력에는 실제 NVIDIA embedding batch 크기도 기록한다. critical code는 clean Git commit과 평가에 영향을 주는 파일별 SHA-256으로 고정하며, 계약에 정한 핵심 파일이 하나라도 dirty하거나 해시 목록이 불완전하면 run을 시작하지 않는다.

## 실행 계획 지문은 상태 지문과 무엇이 다른가

retrieval state는 corpus·벡터·DB 설정이 같은지를 보여주고, 실행 계획 지문은 실제 exact query가 어떤 계획으로 실행됐는지를 보여준다. 실험 D primary dense baseline은 각 문항의 기준일에 유효한 전체 검색 population을 먼저 `MATERIALIZED`한 뒤 모두 비교하는 exhaustive exact cosine이다. runner는 서로 다른 기준일마다 대표 질문 하나의 `EXPLAIN (FORMAT JSON)`을 같은 잠금 안에서 수집해 다음을 기록한다.

- raw plan
- 실행 방식이 `exact_cosine`인지 여부
- 대표 질문과 query embedding SHA-256
- 전체 plan 기록의 SHA-256

성공 결과에는 raw plan, plan SHA-256과 exact 실행 방식이 기록된다. 기존 물리 HNSW 인덱스의 identity·상태·결과 비교는 runner의 입력·게이트·결과에 넣지 않는다. 질문-정답 gold와 직접 근거 찾기 자체를 모두 검증하기 전에 근사 인덱스를 함께 측정하면 어느 단계의 실패인지 분리할 수 없기 때문이다. HNSW 설계와 평가는 gold 1,000문항·근거 찾기 전수 검증 이후 별도 제안과 사용자 승인을 거친 경우에만 진행한다.

## 현재 corpus에서 허용하는 기준일

법률 버전의 효력 구간과 현재 저장소가 완전하게 보장하는 날짜 범위는 다르다. 현재 snapshot `mvp-current-corpus-2026-08-03`은 9개 open version과 3,066개 provision이 공통으로 갖춰진 다음 범위만 지원한다.

```text
2026-06-03 <= as_of_date <= 2026-08-03
```

양끝을 포함한다. 더 과거 또는 미래 문항은 일부 corpus로 검색하지 않고 질문 임베딩 전에 실패시킨다. 운영 API도 같은 범위 밖 요청을 `422 unsupported_corpus_date`로 차단하며 `/v1/corpus/status`에서 snapshot ID와 두 경계를 제공한다.

## Production 검색과 평가 검색은 왜 다른가

production은 다음 사용자 편의 동작을 가진다.

- 명시된 법률명·조문 경로 direct lookup
- 일반 질문의 dense-only 검색
- dense 결과가 0건이거나 embedding 경로가 없을 때 독립 keyword fallback
- 같은 조의 하위 조각을 조 단위로 묶는 grouping

실험 D core runner는 이 동작을 섞지 않는다.

```text
질문 query embedding
→ raw provision exact cosine search
→ raw cosine 내림차순
→ 같은 점수면 provision ID 오름차순
→ top 10을 qrels와 비교
```

그래야 조·항·호·목의 어느 `provision_id`를 실제로 찾았는지 qrels와 정확히 비교할 수 있다. keyword fallback이나 article grouping이 섞이면 dense embedding 자체의 기준 성능을 분리할 수 없다.

## 왜 10개가 아니라 11개를 검색하는가

지표 cutoff는 10이지만 runner는 11개를 요청한다. 10위와 11위의 raw cosine 점수가 같으면 어느 문서가 top 10에 들어가는지가 tie-break에 좌우될 수 있다.

```text
10위 score = 0.51234
11위 score = 0.51234
→ top 10 경계가 해결되지 않음
→ unresolved_cutoff_tie로 run 실패
```

동점이 아니면 앞의 10개만 지표에 사용한다. 중복 provision ID, NaN·무한대 점수, raw cosine 내림차순과 provision ID tie-break 위반도 실패다.

## Recall과 HitRate의 차이

질문 `q`의 grade 2 직접 qrel 집합을 `G2(q)`, 상위 K개 결과를 `TopK(q)`라고 하자.

```text
Recall@K(q) = |TopK(q) ∩ G2(q)| / |G2(q)|

HitRate@K(q) =
  TopK(q)에 grade 2 qrel이 하나라도 있으면 1
  하나도 없으면 0
```

예를 들어 직접 근거가 네 개이고 top 3에서 한 개를 찾았다면 다음과 같다.

```text
Recall@3 = 1 / 4 = 0.25
HitRate@3 = 1
```

정답이 하나인 질문에서는 두 값이 같지만 넓은 질문에서는 다르다. 그래서 둘을 같은 이름으로 기록하지 않는다.

## Precision@5와 Direct Precision@5

질문 `q`의 relevance 1 보조 qrel 집합을 `G1(q)`라고 하자. `Precision@5`는 상위 5개 중 relevance 1 보조 문맥 또는 relevance 2 직접 근거가 차지하는 비율이다. `Direct Precision@5`는 그중 relevance 2 직접 근거만 센다.

```text
Precision@5(q) = |Top5(q) ∩ (G1(q) ∪ G2(q))| / 5
Direct Precision@5(q) = |Top5(q) ∩ G2(q)| / 5
```

Recall이 필요한 근거를 놓치지 않았는지 본다면, 두 Precision은 생성 문맥으로 넘길 상위 후보에 잡음이 얼마나 섞였는지 본다. 관련 근거가 원래 한두 개뿐인 질문에서는 최대값이 1보다 작을 수 있으므로 단독 합격선이 아니라 top-context-purity 진단으로 해석한다.

## MRR@10과 nDCG

`MRR@10`은 처음 찾은 grade 2 직접 qrel의 순위를 본다.

```text
첫 grade 2 qrel이 1위  → 1
첫 grade 2 qrel이 3위  → 1/3
10위 안에 없음         → 0
```

`nDCG@K`는 직접 근거와 보조 문맥의 등급과 순서를 함께 본다.

```text
DCG@K = Σ (2^relevance_i - 1) / log2(rank_i + 1)
nDCG@K = 실제 DCG@K / 이상적 순서의 DCG@K
```

grade 2 직접 근거를 grade 1 보조 문맥보다 앞에 놓을수록 높다. cutoff는 `1, 3, 5, 10`이다.

## Facet 지표

```text
Facet Recall@K(q)
= top K의 grade 2 qrels가 덮은 supported 필수 요소 수
  / supported 필수 요소 전체 수

All Required Facets Covered@K(q)
= supported 필수 요소를 모두 덮으면 1, 아니면 0
```

질문마다 요소 수가 다르므로 질문별 값을 먼저 계산한다. 다만 현재 질문은행은 같은 상황을 다르게 말한 5개 질문이 하나의 scenario family를 이루므로 1,000개 질문을 서로 독립인 표본처럼 평균하지 않는다. primary는 각 family 안에서 먼저 평균한 뒤 family에 같은 가중치를 주는 `scenario-family macro`이며, 95% 신뢰구간도 질문이 아니라 family를 단위로 2,000회 결정적 bootstrap 재표집해 계산한다.

primary Recall·HitRate·MRR@10·nDCG·Precision과 facet 평균은 retrieval 설정 조정에 쓰지 않은 held-out `test` split의 `fully_answerable`만 포함한다. calibration fully-answerable과 calibration+test 결합값은 `diagnostic_only`로 기록하며 primary 성능처럼 해석하지 않는다. partially answerable, clarification required와 unanswerable도 같은 평균에 섞지 않고 별도 진단 모집단으로 보고한다.

## 실패하면 무엇이 기록되는가

runner는 fail-closed로 동작한다.

- 질문은행·질문 승인·gold dataset·adjudication manifest 계약, canonical hash, 승인 시간 순서 또는 critical code·initial preflight 실패: embed와 search 전에 종료
- query embedding 실패: lock과 search 전에 종료
- shared lock 획득 실패: search 전에 종료
- locked preflight·retrieval 상태 실패: search 전에 종료
- plan·search·후보·지표 계산 실패: 일부 내부 작업이 있었더라도 완성 결과를 게시하지 않음

성공한 전체 payload만 같은 output directory의 임시 파일에 쓰고 flush·fsync한 뒤 기존 run을 덮어쓰지 않는 원자적 hard-link 게시를 사용한다. 실패 시 stderr에는 `result_written=false`가 있는 오류 요약만 출력하고 완성 run JSON은 만들지 않는다.

성공 결과에는 다음을 함께 저장한다.

- 실제 질문과 query embedding 및 SHA-256
- 실제 top 10 provision ID, raw cosine 점수와 source metadata
- initial·locked preflight
- retrieval state와 query plans
- 입력 artifact·코드·corpus·vector·plan·실제 순위 지문
- embedding batch 크기와 PostgreSQL·pgvector 버전·planner 설정·exact 실행 방식
- 질문별 순위와 aggregate 지표

결과 파일 자체 SHA-256은 파일 안에 자기 자신을 포함할 수 없으므로 성공 시 터미널에 출력되는 완료 요약에 기록한다. JSON 안에는 자기 해시 필드를 넣기 직전 payload의 SHA-256인 `payload_without_self_hash_sha256`을 둔다.

## 현재 상태

approved-gold-only runner와 합성 fixture 검증은 구현됐다. 그러나 일반 사용자 질문은행 1,000개는 아직 사용자 승인과 독립 qrels·reference response 주석·adjudication을 마친 gold가 아니다. 따라서 실제 1,000개 질문의 NVIDIA query embedding, DB 검색, Recall·HitRate·Precision·MRR@10·nDCG·facet 결과는 아직 실행하거나 기록하지 않았다.

기존 물리 HNSW 인덱스는 삭제하지 않았지만 현재 runner가 읽거나 검증하지 않는 보류 자산이다. gold와 근거 찾기 검증 완료 뒤에도 사용자에게 설계 승인을 받기 전에는 HNSW 평가를 시작하지 않는다.

## 관련 문서와 구현

- [일반 사용자 질문은행과 gold 주석 경계](../design-docs/experiment-d-layperson-question-bank.md)
- [실험 D 1,000문항 평가 설계](../design-docs/experiment-d-1000-evaluation.md)
- [RAG 평가 지표](31-rag-evaluation-metrics.md)
- [NVIDIA RAG 평가 문서 읽기 안내](32-nvidia-rag-evaluation-reading-guide.md)
- `apps/api/scripts/experiment_d_gold_contract.py`
- `apps/api/scripts/preflight_experiment_d_gold.py`
- `apps/api/scripts/evaluate_experiment_d_gold.py`
- `apps/api/scripts/experiment_d_metrics.py`
- [RAG 평가 방법 공식 자료](../references/rag-evaluation-methods-2026-08-03.md)

# 실험 D-10 M3 — raw/R1 소표본 calibration 요약

> 생성 근거: `docs/generated/experiment-d-10-manual-diagnostic.md`(raw, 2026-08-05),
> `docs/generated/experiment-d-10-local-rerank.md`(R1, 2026-08-05)의 저장 artifact를 재계산 없이 읽고,
> `.data/experiments/d-gold-10/d10-gold-20260807t051714397779z/review/sealed/judgments.jsonl`(0030 sealed
> D-10 Gold, 2026-08-07)로 미판정 후보 잔여 항목만 추가 확인했다. 새 query embedding·DB 검색은
> 실행하지 않았다.
>
> 기준 시점: 2026-08-07 · 외부 호출 0회 · 같은 10문항 calibration 진단

## raw vs R1

| 지표 | raw dense | R1(로컬 재정렬) |
|---|---:|---:|
| manual hit@1 | 6/10 | 6/10 |
| manual hit@3 | 6/10 | 7/10 |
| manual hit@5 | 6/10 | 7/10 |
| manual hit@10 | 7/10 | 7/10 |
| manual reciprocal rank@10 (MRR@10) | 0.6125 | 0.65 |
| confirmed known irrelevant@5 | 28 | 18 |

MRR@10은 문항별 `1/rank`(직접 근거가 top 10 밖이거나 없으면 0)의 평균이다. 문항별 근거:

| case_id | raw rank | R1 rank | 비고 |
|---|---:|---:|---|
| lay-energy-0201 | 1 | 1 | 동일 |
| lay-energy-0251 | 1 | 1 | 동일 |
| lay-energy-0521 | 1 | 1 | 동일 |
| lay-energy-0601 | 1 | 1 | 동일 |
| lay-energy-0111 | 1 | 1 | 동일 |
| lay-energy-0561 | 1 | 1 | 동일 |
| lay-energy-0346 | 8 | 2 | R1 개선 |
| lay-energy-0605 | 없음 | 없음 | 현재 corpus에 positive qrel 없음(0030) |
| lay-energy-0836 | 없음 | 없음 | 현재 corpus에 positive qrel 없음(0030) |
| lay-energy-0943 | 없음 | 없음 | 현재 corpus에 positive qrel 없음(0030) |

**순위가 나빠진 사례는 0건이다.** R1은 모든 문항에서 raw와 같거나 더 나은 순위를 냈다.

## M3 step 5 — R1 새 top 5 미판정 후보 해소

R1 재정렬 뒤 원래 6~10위였다가 새 top 5에 들어온 후보 9개(6문항)가 있었고, 당시(2026-08-05)
`comparison.json`은 이들을 "미판정"으로 표시했다. 2026-08-07 완료된 [0030 D-10 전수 qrel
adjudication](../exec-plans/completed/0030-d-10-full-corpus-qrels-adjudication.md)이 문항당 corpus 전체
(3,066개)를 판정했으므로, 이 9개 후보는 모두 그 안에 포함되어 이미 사용자 확정 판정을 받았다.

| case_id | 후보 provision_id | 0030 확정 relevance |
|---|---|---:|
| lay-energy-0201 | 47a0677f-3050-5b28-800b-23bc319bd539 | 0 |
| lay-energy-0201 | 8bdef74d-fed3-58e2-b297-7c63289d789c | 0 |
| lay-energy-0251 | a45792e3-d026-5669-9d03-24cd7ea43fec | 0 |
| lay-energy-0521 | d75015a2-e88e-5a05-bfad-a01260a7a089 | 0 |
| lay-energy-0601 | eb7c34d5-8951-5b95-950b-9a395de854ea | 0 |
| lay-energy-0605 | 85a4a1f5-cdac-5335-8c41-aa26e5e967aa | 0 |
| lay-energy-0605 | 56315b50-e66c-5cd8-ad4f-34bae2d6e837 | 0 |
| lay-energy-0605 | 9a8438b0-0b40-5f72-8339-d43839602970 | 0 |
| lay-energy-0836 | 013e11a1-5663-53f6-99e8-136bd3b37ee5 | 0 |

9개 전부 relevance 0(무관)으로 확정됐다. R1이 새로 끌어올린 후보 중 실제로 관련 있는 것이 섞여
있었는지 우려했던 부분이 해소됐고, hit@k·MRR 결과를 바꿀 새 direct evidence는 없다.

## 2026-08-07 D-10 Gold 정정과의 관계

같은 날 0030에서 `lay-energy-0346`의 `approved_use_terms` facet 근거(`41ebaef4-4a6d-5bdc-a36d-ac54bb04a1e1`)
relevance를 1→2로 정정했다. 이 provision은 raw top 10과 R1 top 10 후보 집합 어디에도 없으므로(원래
10개 후보는 `34eb965b-...` 하나만 포함) 이 정정은 위 raw/R1 순위·hit@k·MRR@10 어느 값도 바꾸지 않는다.
정정은 Gold 계약 정합성(facet 하나가 grade-2 근거를 요구)에 대한 것이지 이 M3 소표본 비교의 입력은
아니었다.

## 문항별 결정

| case_id | 결정 |
|---|---|
| lay-energy-0201/0251/0521/0601/0111/0561 | baseline 유지(raw==R1, 차이 없음) |
| lay-energy-0346 | R1 사용 후보(8위→2위, known irrelevant@5 감소) |
| lay-energy-0605/0836/0943 | 순위 문제가 아니라 corpus 근거 부족 — 검색 순서 조정으로 해결 불가, M4.5 라우팅(TODO) 또는 근거 부족 응답 대상 |

## 해석 한계

- 이 결과는 D-10 10문항 calibration이며 held-out 성능·모집단 일반화·release gate로 사용하지 않는다
  ([plan 0025 "튜닝 데이터와 측정 데이터"](../exec-plans/active/0025-approved-questions-to-grounded-answer-roadmap.md#튜닝-데이터와-측정-데이터) 참고).
- `known irrelevant@5: 28 → 18`은 원래 확인된 무관 ID가 새 top 5에 남은 수이지 전체 무관 후보 감소가
  아니다(0027의 해석 한계와 동일).
- R1(`d10-parent-heading-directness-v1`)은 이 10문항을 보며 설계한 규칙이라 그 자체로 운영 검색
  순서를 바꾸지 않는다. M4가 raw와 R1 중 무엇으로 AI 입력 문맥을 조립할지 별도로 결정한다.

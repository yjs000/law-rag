# 실험 D-10 M3 — raw/R1 소표본 calibration 요약

> 생성 근거: `docs/generated/experiment-d-10-manual-diagnostic.md`(raw, 2026-08-05),
> `docs/generated/experiment-d-10-local-rerank.md`(R1, 2026-08-05)의 저장 artifact를 재계산 없이 읽고,
> `.data/experiments/d-gold-10/d10-gold-20260807t065254073895z/review/sealed/judgments.jsonl`(0030 v3
> sealed D-10 Gold, 2026-08-07)로 문항별 direct evidence(relevance 2)를 다시 계산했다. 새 query
> embedding·DB 검색은 실행하지 않았다.
>
> 기준 시점: 2026-08-07(v3 재계산) · 외부 호출 0회 · 같은 10문항 calibration 진단
>
> **이 문서는 v2 기준으로 처음 발행됐다가 v3 Gold 정정 이후 재계산됐다.** 최초 발행 수치(raw
> hit@1/3/5/10 `6/6/6/7`, MRR@10 `0.6125`)는 부정확했다 — 아래 "왜 숫자가 바뀌었나" 참고.

## raw vs R1 (v3 Gold 기준, 최종)

| 지표 | raw dense | R1(로컬 재정렬) |
|---|---:|---:|
| manual hit@1 | 5/10 | 5/10 |
| manual hit@3 | 5/10 | 7/10 |
| manual hit@5 | 5/10 | 7/10 |
| manual hit@10 | 7/10 | 7/10 |
| manual reciprocal rank@10 (MRR@10) | 0.525 | 0.60 |
| confirmed known irrelevant@5 | 37 | 34 |

MRR@10은 문항별 `1/rank`(직접 근거가 top 10 밖이거나 없으면 0)의 평균이다. 문항별 근거:

| case_id | raw rank | R1 rank | 비고 |
|---|---:|---:|---|
| lay-energy-0201 | 1 | 1 | 동일 |
| lay-energy-0251 | 1 | 1 | 동일 |
| lay-energy-0521 | 1 | 1 | 동일 |
| lay-energy-0601 | 1 | 1 | v3에서 새로 확인(아래 참고) |
| lay-energy-0111 | 1 | 1 | 동일 |
| lay-energy-0346 | 8 | 2 | R1 개선 |
| lay-energy-0561 | 8 | 2 | R1 개선(v3에서 순위 재확인, 아래 참고) |
| lay-energy-0605 | 없음 | 없음 | 현재 corpus에 positive qrel 없음(0030) |
| lay-energy-0836 | 없음 | 없음 | 현재 corpus에 positive qrel 없음(0030) |
| lay-energy-0943 | 없음 | 없음 | 현재 corpus에 positive qrel 없음(0030) |

**순위가 나빠진 사례는 0건이다.** R1은 모든 문항에서 raw와 같거나 더 나은 순위를 냈다.

## 왜 숫자가 바뀌었나

M3를 처음 실행했을 때는 0026(2026-08-05 사람이 raw top-10만 보고 판정)의
`direct_evidence_provision_ids`를 그대로 "직접 근거" 기준으로 썼다. 이후 사용자가 0026과 0030 v2
sealed Gold를 문항별로 전수 대조해 6문항(9건 후보)의 불일치를 찾았고, 각 후보를 원문·facet과 대조한
결과:

- **`0601`**: `9c93a34b-...`(신에너지 및 재생에너지법 제12조의13제3항, "국가 및 지방자치단체는...
  설치하려는 자에게 필요한 재정적·행정적 지원을 할 수 있다")가 `deployment_program_basis` facet을
  그대로 서술하는데, raw·R1 top 10 모두 **1위**임에도 0030 초안에서 개별 재검토 없이 일괄 무관
  처리(relevance 0)에 묻혀 있었다. 이 문항은 원래 M3에서 "직접 근거 없음(rank 없음)"으로 기록됐지만
  실제로는 raw/R1 둘 다 1위였다. 같이 발견된 `7cd6894f-...`(제28조제2항, 지원 세부사항을 부령에
  위임하는 조항)는 직접 답이 아니라 relevance 1(보조 문맥)로 정정했다 — hit@k·MRR에는 영향 없음.
- **`0561`**: 0026은 4개 조문(발전차액 보전, 차액계약 체결·의무거래 관련 조문 3개 + 정산 근거 조문
  1개)을 뭉뚱그려 "직접 근거"로 분류했지만, 실제로 `market_price_basis`·`settlement_rule_basis`·
  `settlement_and_metering_records` facet을 직접 서술하는 건 정산 근거 조문(`49c7b961-...`, 이미
  relevance 2) 하나뿐이었다. 나머지 3개는 가격 "구조"에 대한 배경 정보일 뿐 facet을 직접 답하지
  않는다 — 0030의 relevance 0 판정이 맞았다. 그런데 이 조문(`49c7b961`)의 실제 순위는 raw **8위**,
  R1 **2위**였다 — 0026 기준 계산에서는 "1위"로 잘못 집계돼 있었다.
- 나머지 5건(`0201` 1건, `0251` 1건, `0111` 2건)도 개별 대조 결과 0030의 relevance 0 판정이 맞았다.

**두 오차가 서로 반대 방향으로 작용해 부분 상쇄됐다.** `0601`은 과소평가(없음→1위)였고 `0561`은
과대평가(1위→8위)였다. 최종 raw MRR@10(`0.525`)은 최초 발행값(`0.6125`)보다 낮은데, 이는 실제 성능이
나빠졌다는 뜻이 아니라 **최초 발행값 자체가 부정확했다**는 뜻이다. 왜 v1 Gold 초안이 이런 오류를
냈는지와 다음 평가에서 고려할 점은 [design doc "회고" 절](../design-docs/experiment-d-10-gold-adjudication.md#회고--v1에서-놓친-것과-다음-평가에서-고려할-점)에
정리했다.

## M3 step 5 — R1 새 top 5 미판정 후보 해소

R1 재정렬 뒤 원래 6~10위였다가 새 top 5에 들어온 후보 9개(6문항)를 원문·facet 대조로 개별
재검토했다. 7건은 0030(v1/v2)의 relevance 0 판정이 정확했고, `0601`의 2건만 위에서 설명한 대로
정정했다(v3에 반영 완료). hit@k·MRR을 추가로 바꿀 미판정 후보는 남아 있지 않다.

## 문항별 결정

| case_id | 결정 |
|---|---|
| lay-energy-0201/0251/0521/0601/0111 | baseline 유지(raw==R1, 1위로 동일) |
| lay-energy-0346/0561 | R1 사용 후보(8위→2위, known irrelevant@5 감소) |
| lay-energy-0605/0836/0943 | 순위 문제가 아니라 corpus 근거 부족 — 검색 순서 조정으로 해결 불가, M4.5 라우팅(TODO) 또는 근거 부족 응답 대상 |

## 해석 한계

- 이 결과는 D-10 10문항 calibration이며 held-out 성능·모집단 일반화·release gate로 사용하지 않는다
  ([plan 0025 "튜닝 데이터와 측정 데이터"](../exec-plans/active/0025-approved-questions-to-grounded-answer-roadmap.md#튜닝-데이터와-측정-데이터) 참고).
- known irrelevant@5는 v3 Gold의 relevance 0 라벨을 top 5 후보에 직접 적용해 재계산한 값이다(0026의
  별도 `irrelevant_top5_provision_ids` 주석과는 다른 산출 방식) — 문항마다 다른 라운드의 기준을 섞지
  않기 위해 v3 하나로 통일했다.
- R1(`d10-parent-heading-directness-v1`)은 이 10문항을 보며 설계한 규칙이라 그 자체로 운영 검색
  순서를 바꾸지 않는다. M4가 raw와 R1 중 무엇으로 AI 입력 문맥을 조립할지 별도로 결정한다.

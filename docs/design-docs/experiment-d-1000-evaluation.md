# 실험 D 1,000문항 평가 설계

상태: 일반 사용자 질문 승인·gold 주석·검색 측정 전
최종 갱신: 2026-08-04

## 목적

일반 사용자 질문 1,000개를 검색 결과와 독립적으로 주석한 `approved_gold`로 평가한다. 검색 평가는 현재 parser v3가 만든 searchable provision만 사용하며 과거 parser ID, 과거 synthetic dataset, 자동 생성 qrels는 입력으로 허용하지 않는다.

정답 없는 질문은행만으로 Recall·MRR·nDCG를 계산하지 않는다. 질문 승인, 독립 qrels·reference contexts·reference response 주석, 별도 adjudication manifest가 모두 완료된 뒤에만 평가 runner를 실행한다. 세부 주석 절차는 [일반 사용자 질문은행과 gold 주석 경계](experiment-d-layperson-question-bank.md)를 따른다.

## 권위 입력

- 질문은행: `evaluation/experiment-d-lay-energy-query-bank-v1-draft.json`
- 승인 gold: `evaluation/experiment-d-lay-energy-gold-v1.json`
- 질문 승인 manifest와 gold adjudication manifest
- 현재 parser v3 searchable corpus와 현재 NVIDIA passage 벡터
- 실행 가능한 계약: `scripts.experiment_d_gold_contract`

과거 parser로 생성한 dataset·qrels·검토 산출물은 삭제했으며 재주석하거나 대조군으로 재사용하지 않는다.

## 현재 parser ID 게이트

평가 파일에 연결된 모든 단일 `provision_id`와 `*_provision_ids` 목록은 다른 gold 검사보다 먼저 현재 searchable corpus ID 집합과 대조한다. 하나라도 현재 집합에 없으면 `non_current_parser_provision_ids` 예외를 즉시 발생시키며 corpus fingerprint, 본문 SHA, 승인 상태 등 뒤의 검사를 계속하지 않는다.

이 검사는 UUID 문자열만 보고 parser 버전을 추측하지 않는다. 현재 parser가 만든 ID의 권위 있는 집합은 현재 searchable corpus이므로 다음 한 번의 집합 차이만 계산한다.

```text
evaluation에 연결된 provision ID 집합 - 현재 searchable provision ID 집합
```

차집합이 비어 있지 않으면 과거 parser ID 또는 현재 corpus에 없는 잘못된 ID로 취급한다. 오류에는 현재 parser 계약 버전, 불일치 개수와 최대 10개 표본을 담는다. runner는 이 검사를 초기 preflight와 corpus 공유 잠금 안의 locked preflight에서 모두 수행하므로 질문 임베딩과 검색 전에 실패한다.

## gold 불변조건

- `evaluation_status=approved_gold`만 허용한다.
- 질문 ID·문구·범위 해시는 승인된 질문은행과 일치해야 한다.
- gold adjudication manifest는 전체 dataset과 문항별 완성 payload의 canonical SHA-256을 봉인한다.
- 시간 순서는 모든 문항에서 `질문 승인 < 문항 review < gold adjudication`이어야 한다.
- `fully_answerable`의 supported facet마다 relevance 2 직접 qrel이 있어야 한다.
- `unanswerable`은 qrels가 비어 있고 근거 부족 사유를 가져야 한다.
- 모든 qrel·distractor·pool 후보는 문항 기준일에 유효한 searchable provision이어야 한다.
- 전체 corpus 검토 방법을 선언했다면 해당 기준일의 전체 유효 population과 정확히 일치해야 한다.
- 현재 지원 기준일 `2026-06-03..2026-08-03` 밖의 문항은 거부한다.

## 실행 경계

독립 읽기 전용 점검:

```powershell
uv run --directory apps/api python -m scripts.preflight_experiment_d_gold `
  --dataset evaluation/experiment-d-lay-energy-gold-v1.json
```

독립 preflight는 검색이나 임베딩을 호출하지 않는다. 실제 `scripts.evaluate_experiment_d_gold` runner는 clean code provenance와 초기 preflight를 통과한 뒤에만 질문을 임베딩한다. 이어 corpus mutation 공유 advisory lock 안에서 locked preflight와 retrieval 상태를 다시 검사하고 마지막 raw provision 검색까지 같은 corpus를 유지한다.

primary dense 검색은 물리 HNSW 상태와 무관한 exhaustive exact cosine이다. 각 질문은 raw 후보 11개를 받아 10위와 11위의 동점을 검사하고 동점이면 실패한다. 성공한 전체 run만 새 JSON으로 원자 게시하며 실패 시 부분 결과나 기존 run을 덮어쓰지 않는다.

## 지표

- Recall@1/3/5/10과 HitRate@1/3/5/10
- grade 1·2 Precision과 grade 2 Direct Precision
- grade 2 직접 qrel 기준 MRR@10
- grade 2/1 graded nDCG@1/3/5/10
- facet recall과 모든 필수 facet 충족률
- partial·clarification·unanswerable 별도 진단

primary 모집단은 held-out test의 `fully_answerable` 문항이다. 같은 scenario family의 다섯 표현을 먼저 평균한 뒤 family별 동일 가중치로 집계하고, family 단위 결정적 bootstrap 2,000회로 95% 신뢰구간을 기록한다. calibration과 calibration+test 결합값은 진단용이며 primary 성능으로 보고하지 않는다.

## 결정 기록

- 2026-08-03: 질문 승인과 gold 주석·adjudication을 분리하고 approved-gold-only runner를 채택했다.
- 2026-08-03: primary 검색을 exhaustive exact cosine으로 고정하고 HNSW 상태·게이트·결과를 제외했다.
- 2026-08-03: 질문 approval manifest와 gold adjudication manifest를 분리했다.
- 2026-08-04: 과거 parser 기반 synthetic dataset·qrels·생성·검토 경로를 삭제하고 재사용하지 않기로 결정했다.
- 2026-08-04: 평가에 연결된 ID가 현재 parser corpus에 없으면 다른 검사보다 먼저 `non_current_parser_provision_ids`로 실패하도록 고정했다.

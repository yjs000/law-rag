# 실험 D 1,000문항 평가 설계

상태: 질문 문구·범위 승인 완료 · gold 주석·검색 측정 전
최종 갱신: 2026-08-04

## 목적

일반 사용자 질문 1,000개를 검색 결과와 독립적으로 주석한 `approved_gold`로 평가한다. 검색 평가는 현재 parser v3가 만든 searchable provision만 사용하며 과거 parser ID, 과거 synthetic dataset, 자동 생성 qrels는 입력으로 허용하지 않는다.

정답 없는 질문은행만으로 Recall·MRR·nDCG를 계산하지 않는다. 질문 승인, 독립 qrels·reference contexts·reference response 주석, 별도 adjudication manifest가 모두 완료된 뒤에만 평가 runner를 실행한다. 세부 주석 절차는 [일반 사용자 질문은행과 gold 주석 경계](experiment-d-layperson-question-bank.md)를 따른다.

## 권위 입력

- 질문은행: `evaluation/experiment-d-lay-energy-query-bank-v1-draft.json`
- 승인 gold: `evaluation/experiment-d-lay-energy-gold-v1.json`
- 질문 승인 manifest와 gold adjudication manifest
- 현재 parser v3 searchable corpus와 현재 NVIDIA passage 벡터. corpus 내용 식별과 임베딩 프로필은 서로 다른 계약으로 검증한다.
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
- gold의 서로 다른 모든 `case.as_of_date`에는 해당 날짜의 유효 provision 수와 콘텐츠 지문이 정확히 하나씩 있어야 하며, 사용하지 않는 날짜의 population을 추가할 수 없다.
- qrel이 가리키는 실제 corpus 원문은 문항 기준일에 유효해야 한다. 높은 검색 점수나 gold에 기록된 과거 메타데이터만으로 효력을 대신하지 않는다.

## gold의 날짜와 콘텐츠 스냅샷

gold는 저장된 역사 버전 전체를 하나의 전역 해시로 묶지 않는다. 각 문항의 `as_of_date`에 먼저 다음
반개구간 조건을 적용한 뒤, 그 날짜에 검색 가능한 provision의 수와 콘텐츠 지문을
`corpus_snapshot.as_of_populations`에 고정한다.

```text
effective_from <= as_of_date
그리고
effective_to IS NULL 또는 as_of_date < effective_to
```

`snapshot_id`는 날짜 문자열이 아니라 위에서 얻은 고유한 콘텐츠 population identity로 계산한다. 따라서
2026-08-03과 2026-08-04의 유효 provision ID와 검색 콘텐츠가 같으면 두 날짜의 content snapshot ID도
같다. 그렇다고 날짜가 사라지는 것은 아니다. 날짜와 날짜별 count·fingerprint 대응은
`as_of_populations`에 남고, 전체 gold dataset과 adjudication manifest의 canonical SHA-256이 이를 다시
봉인한다. 날짜만 바꿔도 dataset·adjudication 해시는 달라진다.

아직 시행되지 않은 미래 버전이 저장되거나, 그 수집 때문에 기존 버전의 `effective_to`가 `NULL`에서
미래 날짜로 닫혀도 과거 기준일의 유효 ID와 검색 콘텐츠가 같으면 과거 snapshot을 무효화하지 않는다.
반대로 새 버전의 시행일을 지나 유효 집합이 바뀌거나 provision의 ID·본문·검색 경로 등 콘텐츠 identity가
바뀌면 해당 날짜의 count 또는 fingerprint와 snapshot ID가 달라져 preflight가 실패한다.

NVIDIA 모델, query/passage 입력 유형, 512차원 축약·정규화와 본문 템플릿은 retrieval contract다. 이 값은
실행 입력과 결과에 별도로 기록하지만 corpus content snapshot ID 계산에는 넣지 않는다. 같은 원문을 다른
임베딩 프로필로 평가하는 일은 corpus 변경이 아니라 retrieval 설정 변경이기 때문이다. 물리 HNSW는 이
retrieval contract에도 포함하지 않는다.

운영 API는 별도로 한국 날짜의 오늘을 종료일로 하고, 오늘 이하인 수집·현재 parser·검색 가능 버전의
`effective_from` 전역 최솟값을 시작일로 하는 동적 runtime 범위를 계산한다. 운영 status의 snapshot ID는
오늘 population 하나를 식별한다. 반면 실험 D gold는 문항에 실제 사용한 서로 다른 모든 기준일의
population을 `as_of_populations`로 고정하고, 그 고유 population identity 집합을 하나의 gold snapshot ID로
봉인한다. 두 계약은 같은 content identity 함수를 재사용하지만 용도가 다르며, runtime의 오늘 snapshot을
과거 평가 문항의 gold population 대신 사용하지 않는다. 어느 쪽도 이 계산만으로 법률별 과거 timeline의
gap·overlap 완전성이 검증됐다고 주장하지 않는다.

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
- 2026-08-04: HNSW는 향후 비교·설계·도입 후보에서도 제외했다. 실험 D는 계속 exhaustive exact cosine만 평가하며 기존 물리 인덱스의 존재를 입력·상태·게이트·결과로 사용하지 않는다.
- 2026-08-03: 질문 approval manifest와 gold adjudication manifest를 분리했다.
- 2026-08-04: 일반 사용자 질문 1,000개의 문구·범위 승인을 완료했다. 이는 gold 주석·adjudication이나 검색 실행 승인이 아니다.
- 2026-08-04: 과거 parser 기반 synthetic dataset·qrels·생성·검토 경로를 삭제하고 재사용하지 않기로 결정했다.
- 2026-08-04: 평가에 연결된 ID가 현재 parser corpus에 없으면 다른 검사보다 먼저 `non_current_parser_provision_ids`로 실패하도록 고정했다.
- 2026-08-04: gold를 문항별 `as_of_date`의 유효 provision count·content fingerprint에 결박하고, `snapshot_id`에서는 날짜와 임베딩 프로필을 분리했다. 같은 콘텐츠 population은 날짜가 달라도 같은 ID를 가지며 날짜 대응은 dataset·adjudication 해시에 별도로 봉인한다.
- 2026-08-04: 운영 API의 한국 날짜 오늘 population identity와 실험 D의 문항 기준일별 population 집합 계약을 분리했다. 같은 canonical content identity 함수를 쓰되 운영 status 값으로 과거 gold를 대신하지 않는다.

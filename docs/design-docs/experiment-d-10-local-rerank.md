# 실험 D-10-R1 부모 표제·직접성 로컬 재정렬

상태: 구현 중
작성일: 2026-08-05

## 목적

사용자 확인이 끝난 D-10의 저장된 raw top 10 후보 집합을 바꾸지 않고, 부모 조문 표제와 질문·후보의
일반 직접성 개념 일치를 사용해 로컬에서만 순서를 다시 매긴다. `lay-energy-0346`의 직접 근거가 raw
8위에서 top 3으로 이동하는지와 사용자 확인 top 5 무관 후보가 줄어드는지를 비교한다.

이 실험은 같은 10문항의 확인 라벨을 평가에 다시 사용하는 calibration 진단이다. 독립 test, gold,
일반화된 MRR·nDCG, 운영 승인을 주장하지 않는다.

## 입력과 불변조건

- 입력 result와 confirmed manual review의 run ID·result SHA·corpus snapshot·embedding profile 결박을
  다시 검증한다.
- 각 문항의 candidate ID 집합과 raw cosine, raw rank는 그대로 보존한다.
- DB, NVIDIA, Open API, query/passage embedding을 호출하지 않는다.
- direct evidence와 irrelevant 라벨은 점수 계산에 넣지 않고 재정렬 뒤 진단에만 사용한다.
- 원본 `result.json`, `review.md`, `manual-review.json`, `confirmed-diagnostics.json`을 덮어쓰지 않는다.
- HNSW, keyword, hybrid, RRF와 모델 reranker를 사용하지 않는다.

## 직접성 규칙 v1

질문과 후보 문자열은 소문자 영숫자·한글만 남겨 비교한다. 고정된 에너지 법률 개념군은 허가, 신고,
용량·사용, 공급인증서, 발급, 지원, 대상·조건, 입지, 설치, 전력망, 비용, 정산, 계량, 충전시설, 장애,
빛 반사, 민원이다. 질문에 실제로 나타난 개념군만 활성화한다.

후보별 입력은 다음 세 부분이다.

```text
법령명 + 복원된 부모 조문 표제 + raw provision 본문
```

점수 구성은 문항 내부 raw cosine min-max 위치, 전체 후보 문자열의 활성 개념 coverage, 부모 표제의
활성 개념 coverage, 둘 이상의 활성 개념을 모두 충족한 관계 completion이다. 동점은 원래 raw rank와
provision ID로 결정한다. 정확한 가중치와 개념어는 코드의 versioned profile에 고정하고 출력에 해시를
남긴다. 질문 ID나 direct/irrelevant provision ID에 따른 예외 규칙은 금지한다.

## 비교값

- 문항별 첫 직접 근거 raw rank와 reranked rank
- hit@1/3/5/10 전후 변화
- 원래 확인된 irrelevant ID 중 reranked top 5에 남은 수
- reranked top 5에 새로 진입한 미판정 후보 목록
- `lay-energy-0346`의 순서·점수 구성과 top 3 달성 여부
- candidate 집합·raw cosine·원순위 보존 여부

원래 수동 검토는 raw top 5의 무관 후보만 의무 판정했으므로, 6~10위에서 새 top 5로 진입한 후보를
자동으로 관련 또는 무관으로 간주하지 않는다. 따라서 전체 무관 후보 감소는 `confirmed known irrelevant`
하한과 새 진입 후보 목록을 함께 보고한다. `lay-energy-0346`은 기존 top 5가 전부 무관이고 유일한 직접
근거가 8위이므로 그 근거가 top 5에 들면 최소 한 개의 무관 후보가 확실히 밀려난다.

## 성공 판정

- 모든 입력·불변조건과 원자 출력 계약이 통과한다.
- 결과를 목표에 맞춰 사후 수정하지 않고 고정 v1 규칙의 실제 비교값을 기록한다.
- `lay-energy-0346` 직접 근거 top 3 여부와 confirmed known irrelevant@5 감소 여부를 명시한다.
- 결과가 좋아도 운영에 바로 반영하지 않고 별도 held-out 평가 필요성을 남긴다.

## 결정 기록

- 2026-08-05: 사용자 승인 D-10을 기준선으로 고정하고 재정렬을 별도 `D-10-R1` artifact로 분리했다.
- 2026-08-05: 외부 호출이 없는 부모 표제·직접성 규칙을 먼저 검증하고 passage 재임베딩과 모델
  reranker는 범위에서 제외했다.

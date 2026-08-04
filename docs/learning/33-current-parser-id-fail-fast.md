# 현재 parser ID를 가장 싸게 차단하는 방법

## 문제

parser가 바뀌면 같은 법령 조문도 canonical `provision_id`가 달라질 수 있다. 과거 ID가 qrels나 후보 pool에 남으면 검색기가 절대로 반환할 수 없는 정답을 기준으로 평가하게 된다. 이 상태에서 corpus fingerprint, 본문 해시, 메타데이터를 자세히 검사하는 것은 비용만 쓰고 핵심 오류를 늦게 보여 준다.

## 선택한 방법

평가 JSON에서 `provision_id`와 이름이 `*_provision_ids`인 모든 연결을 모은다. 현재 searchable corpus에서 provision ID 집합을 만들고 다음 차집합을 한 번 계산한다.

```text
linked_ids - current_searchable_ids
```

차집합이 있으면 즉시 `NonCurrentParserIdError`를 발생시킨다. 오류 코드는 `non_current_parser_provision_ids`이고 현재 parser 계약 버전, 전체 불일치 개수, 최대 10개 표본을 제공한다.

UUID 자체에서 parser 버전을 역추론하지 않는다. UUID5는 namespace와 입력으로부터 생성되지만 결과 UUID만으로 어느 과거 namespace를 사용했는지 안정적으로 복원할 수 없다. 현재 searchable corpus ID 집합이 평가 시점의 권위 원본이다.

## 데이터 흐름

```text
gold JSON의 연결 ID 수집
        +
현재 searchable provision ID 집합
        ↓
집합 차이 검사
  ├─ 차이 있음 → 즉시 오류, 후속 검사·임베딩·검색 없음
  └─ 차이 없음 → 승인·해시·메타데이터·검색 상태 검사
```

독립 preflight, runner의 초기 preflight, corpus 공유 잠금 안의 locked preflight가 같은 함수를 사용한다. 따라서 별도 우회 경로가 없고 구현도 하나만 유지한다.

## 직접 검증

```powershell
$env:PYTHONPATH = 'apps/api'
uv run --project apps/api pytest apps/api/tests/test_experiment_d_gold_preflight.py -q
```

현재 corpus ID만 있는 fixture는 기존 검사를 계속하고, 하나의 과거/비현재 ID가 섞인 fixture는 나머지 gold 검사를 수행하기 전에 예외를 낸다.

## 다음 학습 주제

- corpus snapshot 교체 시 승인 gold를 새 snapshot으로 이관하는 절차
- ID 집합 검사와 corpus mutation lock의 관계

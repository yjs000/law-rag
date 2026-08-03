# 시간 효력 모델

## 날짜 구간

질문 `as_of_date`는 공포일이 아니라 시행 효력에 적용한다. 버전은 다음 반개구간 조건을 만족할 때 해당 날짜에 유효하다.

```text
effective_from <= as_of_date
그리고
effective_to IS NULL 또는 as_of_date < effective_to
```

`effective_from`은 필수다. 시행일을 알 수 없는 원문은 공포일이나 수집일로 채우지 않고 활성 코퍼스 승격을 중단한다. `effective_to`가 있으면 `effective_from`보다 반드시 뒤여야 한다. `effective_to IS NULL`인 행을 open version이라 하며 한 문서에는 하나만 존재할 수 있다.

`eflaw`는 시행일 기준 현행 검색에 사용한다. `target=law`는 공포일 기준 진단과 과거 MST 본문 확인에만 쓴다. 시행일, 공포일, 수집일을 서로 대체하지 않는다.

## 법적 효력 구간과 corpus 지원 범위는 다르다

위 날짜 식은 저장된 버전이 특정 날짜에 법적으로 유효한지를 판정한다. 그러나 유효성 식이 참이라고 해서 현재 저장소가 그 날짜의 9개 법령을 모두 갖췄다는 뜻은 아니다. 현행 버전 중심으로 수집한 지금 corpus를 과거 전체 연혁처럼 검색하면 일부 문서만 남은 결과를 “직접 근거 없음”으로 잘못 해석할 수 있다.

2026-08-03 운영 DB 읽기 전용 감사에서 다음 상태를 확인했다.

- 허용 목록 9개 문서마다 open version 1개
- 검색 가능한 provision 3,066개
- 9개 open version 중 가장 늦은 `effective_from`: `2026-06-03`
- 현재 snapshot 검증 기준일: `2026-08-03`

따라서 현재 snapshot ID와 지원 범위를 코드에 명시적으로 고정한다.

```text
corpus_snapshot_id = mvp-current-corpus-2026-08-03
supported_as_of_from = 2026-06-03
supported_as_of_through = 2026-08-03

2026-06-03 <= as_of_date <= 2026-08-03
```

양끝 날짜를 포함한다. 범위 밖 `as_of_date`는 유효 조문을 일부만 검색하지 않고 API 경계에서 HTTP `422`, 코드 `unsupported_corpus_date`로 거부한다. 이 검사는 quota, 질문 임베딩과 repository 호출보다 먼저 실행한다. `POST /v1/search`, `POST /v1/questions`, `GET /v1/provisions/{id}`에 같은 계약을 적용하며 `/v1/corpus/status`는 `corpus_snapshot_id`, `supported_as_of_from`, `supported_as_of_through`를 반환한다.

이 범위는 법 자체의 효력 범위가 아니라 **현재 수집 snapshot의 검색 보장 범위**다. 과거 연혁을 충분히 수집·검증하거나 새 현행 snapshot으로 교체하면, 실제 공통 coverage를 다시 읽기 전용으로 감사한 뒤 상수·테스트·문서를 함께 갱신한다. 단지 현재 날짜가 지났다는 이유로 `supported_as_of_through`를 자동 연장하지 않는다.

## 버전 식별자

`document_versions`의 자연키는 `(document_id, mst, effective_from)`이다. 같은 MST가 단계별 시행일에 다시 노출되더라도 서로 다른 원문 스냅샷으로 보존하기 위해 시행일을 키에 포함한다.

동일 문서에 서로 다른 MST가 같은 시행일로 들어오는 경우는 애플리케이션의 연혁 검증에서 거부한다. 이 규칙은 수집 응답을 함께 확인해야 하므로 데이터베이스 exclusion constraint로 중복 구현하지 않는다.

## 서로 다른 세 가지 상태

| 필드 | 값 | 뜻 |
|---|---|---|
| `lifecycle_state` | `active`, `scheduled`, `abolished` | 법적 생명주기 상태. 현행·시행예정·폐지를 서로 구분한다. |
| `source_record_state` | `available`, `deleted` | 공동활용 Open API에서 해당 레코드를 다시 확인할 수 있는지 나타낸다. |
| `source_deleted_on` | 날짜 또는 `NULL` | 공식 삭제 목록에서 확인한 출처 레코드 삭제일이다. |
| `has_supplementary_provisions` | `true`, `false` | 파싱한 원문에 부칙 구조가 있었는지 나타낸다. |

법적 폐지와 출처 레코드 삭제는 같은 사건이 아니다. `delHst`에서 발견한 레코드는 `source_record_state=deleted`와 `source_deleted_on`만 갱신한다. 이를 근거로 `lifecycle_state=abolished`나 `effective_to`를 추론하지 않는다. 삭제된 출처 레코드의 원문은 감사용으로 보존하되 검색 근거에서는 격리한다.

`lifecycle_state`도 효력 날짜 구간을 대신하지 않는다. 예를 들어 `scheduled`는 미래 `effective_from`을 설명하는 상태이고, 과거 기준일 판정은 언제나 날짜 구간을 사용한다.

## 마이그레이션과 검증

`0009_temporal_document_versions.py`는 기존 행을 `lifecycle_state=active`, `source_record_state=available`, `has_supplementary_provisions=false`로 이관한다. 이 값들을 새 행의 DB 기본값으로 두지는 않는다. 이후 쓰기 경로가 세 상태를 검증하고 명시해야 하므로 누락된 입력은 실패한다. 시행일 누락, 길이가 0 이하인 효력 구간, 문서별 복수 open version이 있으면 값을 추정하거나 일부만 적용하지 않고 마이그레이션을 중단한다.

법적 효력의 경계일, 과거, 현재, 시행예정, 폐지, 출처 삭제 fixture와 corpus coverage의 지원 시작일·종료일·양쪽 범위 밖 fixture를 각각 테스트해야 한다. 현재 운영 수집은 현행 버전을 저장하며 과거 버전 전체 수집은 아직 활성화하지 않았다.

## 결정 기록

- 2026-07-13: 모든 사용자 질문에 명시적 기준일을 요구하고 기본값만 오늘로 설정.
- 2026-08-03: 버전 자연키를 `문서 + MST + 시행일`로 확장하고 시행일·효력 구간·문서별 open version을 DB 불변조건으로 고정.
- 2026-08-03: 법적 생명주기와 Open API 레코드 가용성을 별도 상태로 저장하고 출처 삭제에서 폐지를 추론하지 않음.
- 2026-08-03: 현재 corpus의 공통 지원 범위를 `2026-06-03..2026-08-03` 양끝 포함으로 고정하고 범위 밖은 부분 검색 대신 `422 unsupported_corpus_date`로 차단.

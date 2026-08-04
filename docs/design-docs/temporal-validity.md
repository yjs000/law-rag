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

위 날짜 식은 저장된 버전이 특정 날짜에 법적으로 유효한지를 판정한다. 그러나 유효성 식이 참이라고 해서 현재 저장소가 그 날짜의 허용 법령 전체 연혁을 빠짐없이 갖췄다는 뜻은 아니다. 현행 버전 중심으로 수집한 corpus를 과거 전체 연혁처럼 검색하면 일부 문서만 남은 결과를 “직접 근거 없음”으로 잘못 해석할 수 있다.

2026-08-03 운영 DB 읽기 전용 감사에서는 당시 다음 상태를 확인했다.

- 허용 목록 9개 문서마다 open version 1개
- 검색 가능한 provision 3,066개
- 9개 open version 중 가장 늦은 `effective_from`: `2026-06-03`
- 당시 snapshot 검증 기준일: `2026-08-03`

이 관측으로 도입했던 다음 고정 계약은 역사 기록이며 2026-08-04 동적 계약으로 대체됐다.

```text
corpus_snapshot_id = mvp-current-corpus-2026-08-03
supported_as_of_from = 2026-06-03
supported_as_of_through = 2026-08-03

2026-06-03 <= as_of_date <= 2026-08-03
```

현재 runtime은 요청마다 UTC+9 한국 날짜의 오늘을 기준으로 다음 상태를 읽기 전용으로 계산한다.

```text
supported_as_of_through = korea_today(UTC+9)

collected = 수집된 parser-current searchable version의 provision
            단, effective_from <= supported_as_of_through

supported_as_of_from = MIN(collected.effective_from)

today_eligible = collected 중
                 effective_from <= supported_as_of_through
                 그리고
                 effective_to IS NULL 또는 supported_as_of_through < effective_to

지원 범위: supported_as_of_from <= as_of_date <= supported_as_of_through
```

여기서 searchable version은 출처 레코드가 `available`이고 parser schema가 현재 버전이며, lifecycle이 `active`·`scheduled`이거나 공식 `effective_to`가 있는 `abolished` 버전이다. 지원 시작일은 이 집합의 **전역 최솟값**이다. 법률마다 처음 시행된 날을 모두 복원하거나 문서별 timeline의 gap·overlap을 검사해 공통 완전 coverage를 증명하는 계산은 아니다. 따라서 이 범위는 법 자체의 전체 효력 범위가 아니라 **현재 수집·검색 가능 corpus에 적용하는 runtime 안전 경계**다.

runtime snapshot ID는 오늘 유효한 provision의 개수와 검색 콘텐츠 fingerprint로 계산한다. fingerprint는 parser 버전, 문서·버전·조문 ID, 법령명·출처 종류, `effective_from`, 조문 경로·부모 경로·표제와 본문 SHA-256을 정렬해 만든다. 달력 날짜, `effective_to`, embedding profile은 content ID 입력에 넣지 않는다. `effective_to`는 오늘 population에 들어오는지를 결정하지만 그 값 자체로 content ID를 바꾸지 않는다. 따라서 오늘과 내일 사이에 시행·개정·폐지 경계나 검색 콘텐츠 변화가 없으면 같은 ID를 유지한다.

전체 corpus 검색 게이트가 닫혔거나 오늘 유효한 provision이 0개이거나 지원 시작일·fingerprint를 완성할 수 없으면 temporal state는 준비되지 않은 상태다. 검색 엔드포인트는 이를 빈 결과나 근거 부족으로 바꾸지 않고 HTTP `503`, 코드 `corpus_unready`로 반환한다. 이때 `/v1/corpus/status`의 `supported_as_of_from`과 `corpus_snapshot_id`는 `null`일 수 있고, `supported_as_of_through`는 한국 날짜의 오늘을 계속 보여 준다.

준비된 범위 밖 `as_of_date`는 API 경계에서 HTTP `422`, 코드 `unsupported_corpus_date`로 거부한다. 이 검사는 quota, 질문 임베딩과 repository 검색보다 먼저 실행한다. `POST /v1/search`, `POST /v1/questions`, `GET /v1/provisions/{id}`에 같은 계약을 적용한다. 날짜를 생략한 요청도 서버 로컬 날짜가 아니라 한국 날짜의 오늘을 사용한다. `/v1/corpus/status`는 계산된 snapshot ID, 양쪽 경계와 준비 상태·사유를 반환한다.

초기 API 검사와 실제 검색 사이에는 인증·quota·질문 임베딩 시간이 있을 수 있다. 코퍼스 변경이 있으면 publisher는 `corpus.search_ready=false`를 먼저 커밋하고 65초 동안 기존 요청을 drain한 뒤 변경분을 단일 transaction으로 반영·검증한다. 새 요청과 실제 PostgreSQL 검색 직전 재검사는 advisory lock을 잡거나 기다리지 않고 닫힌 게이트에서 즉시 `503 corpus_unready`를 반환한다. 재검사 직후 게이트가 닫혀도 검색 SQL 자체의 준비 조건이 결과를 차단하고, 빈 결과를 반환하기 전에 게이트를 다시 확인하므로 이를 근거 부족으로 오인하지 않는다. publisher가 성공하면 반영 transaction 끝에서 게이트를 열고, 실패하면 변경분 전체를 rollback한 채 게이트를 닫아 둔다.

2026-08-04 KST 운영 Supabase 읽기 전용 검증에서는 `ready=true`, 동적 범위 `2024-07-01..2026-08-04`, 오늘 유효 provision 3,066개와 content-derived `corpus-sha256:*` ID 반환을 확인했다. 이는 그날의 관측값이며 코드에 하드코딩하는 계약이 아니다.

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

법적 효력의 경계일, 과거, 현재, 시행예정, 폐지, 출처 삭제 fixture를 테스트한다. runtime 시간 계약은 주입한 한국 날짜를 기준으로 동적 시작일·종료일, 양쪽 범위 밖, 게이트 닫힘, 오늘 eligible 0개, identity 불완전과 날짜가 달라도 같은 population이면 같은 ID인 사례를 검사한다. 현재 계산은 문서별 과거 timeline의 gap·overlap 완전성을 검증하지 않는다.

## 결정 기록

- 2026-07-13: 모든 사용자 질문에 명시적 기준일을 요구하고 기본값만 오늘로 설정.
- 2026-08-03: 버전 자연키를 `문서 + MST + 시행일`로 확장하고 시행일·효력 구간·문서별 open version을 DB 불변조건으로 고정.
- 2026-08-03: 법적 생명주기와 Open API 레코드 가용성을 별도 상태로 저장하고 출처 삭제에서 폐지를 추론하지 않음.
- 2026-08-03: [대체됨] 당시 감사한 corpus의 지원 범위를 `2026-06-03..2026-08-03` 양끝 포함으로 고정하고 범위 밖은 부분 검색 대신 `422 unsupported_corpus_date`로 차단.
- 2026-08-04: 지원 시작일은 오늘 이하인 수집·현재 parser·검색 가능 버전의 `effective_from` 전역 최솟값, 종료일은 한국 날짜의 오늘로 동적 계산한다. 오늘 유효 population의 content identity를 사용하고, 준비 불완전은 `503 corpus_unready`, 준비된 범위 밖은 검색 전 `422 unsupported_corpus_date`로 구분한다. 이 계산만으로 법률별 timeline gap·overlap이 검증됐다고 주장하지 않는다.
- 2026-08-04: 드문 corpus 갱신을 위해 모든 운영 reader가 공유 lock을 부담하지 않도록 reader lock을 제거한다. publisher가 검색 게이트를 먼저 닫고 65초 drain한 뒤 단일 transaction으로 반영하며, writer와 실험 D의 기존 lock은 유지한다.

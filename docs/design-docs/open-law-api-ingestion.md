# 국가법령정보 Open API 수집 계약

상태: 현행 구현과 미활성 계약을 구분해 기록
최종 확인: 2026-08-03

## 범위

법률 근거는 `open.law.go.kr`이 제공하는 공동활용 Open API만 허용한다. `OC`는 `LAW_OPEN_API_OC` 비밀값이다. 화면 HTML 크롤링, PDF 청킹, 검색엔진과 다른 법률 사이트는 금지한다.

JSON을 우선 요청하지만 채택 기준은 파싱 성공이 아니라 도메인 정규화 성공이다. 정확 명칭, 출처 ID, MST, 시행일, 검색 가능한 조문 구조가 없으면 같은 요청을 XML로 한 번 폴백한다. 두 포맷 fixture는 같은 조문 경로와 parser v3 조문 ID를 만들어야 한다.

일시적 5xx, timeout, 네트워크 오류는 같은 포맷을 최대 3회 재시도한다. 재시도 소진은 수집 실패이며 포맷 폴백 조건이 아니다. 관측 URL에서는 `OC`를 `[redacted]`로 치환한다.

## 현재 Supabase 수집 순서

현재 운영 가능한 명령은 `preview-current`, `sync-current`, `status`다. Supabase의 `sync-history`는 전체 과거 버전 수집이 아직 비활성이라 명시적으로 종료 코드 2를 반환한다. 공식 삭제 목록 동기화는 이 명령과 분리되어 `sync-current`의 끝에서 실행된다.

1. 법령은 `lawSearch.do?target=eflaw&search=1&nw=3`, 행정규칙은 `target=admrul&search=1&nw=1`로 현재 목록을 찾는다.
2. 허용 목록의 현재 정확 명칭과 일치하는 결과가 정확히 한 건인지 검사한다.
3. 법령은 `lawService.do?target=eflaw&ID`, 행정규칙은 `target=admrul&ID`로 본문을 조회한다.
4. JSON 우선·XML 폴백 파서가 조·항·호·목과 부모 경로를 정규화한다.
5. 활성화 검증기가 parser schema, UUID, 원문 SHA-256, 시행일, 조문 계층과 실제 본문을 검사한다.
6. 검증된 원문은 SHA-256이 포함된 불변 Storage 경로에 보존하고, 문서·버전·조문은 문서 하나의 DB 트랜잭션으로 반영한다.
7. 임베딩 입력이나 검색 가능 상태가 바뀌면 같은 트랜잭션에서 embedding profile을 비활성화한다. 임베딩 생성과 활성화는 collector 안에서 하지 않고 별도 backfill로 수행한다.

같은 `(document_id, mst, effective_from)`과 같은 원문을 다시 수집하면 멱등적으로 `unchanged`가 된다. 새 시행 버전이 들어오면 이전 open version의 `effective_to`를 새 버전의 `effective_from`으로 닫는다.

## Parser schema v3와 조문 식별자

parser schema v3의 조문 UUID는 다음 다섯 값을 정렬된 JSON으로 직렬화한 뒤, v3 전용 UUID5 namespace에 넣어 결정한다.

```text
source_kind + source_id + mst + effective_from + path
```

- JSON과 XML이 같은 원문 구조를 나타내면 같은 UUID와 부모 경로를 만든다.
- 같은 MST와 조문 경로라도 시행일이 다르면 다른 버전의 조문이므로 UUID가 다르다.
- 연혁 목록의 시행일이 본문 안의 날짜보다 권위 있을 때 parser의 `effective_from_override`가 레코드 날짜와 UUID를 함께 결정한다.
- 활성화 검증기는 모든 조문 UUID를 다시 계산하며 하나라도 다르면 DB 승격을 거부한다.
- 검색·backfill은 `parser_schema_version='3'`인 버전만 대상으로 한다.

parser schema를 바꾸면 UUID namespace도 바뀐다. 따라서 schema v2 조문 ID를 그대로 재사용하지 않으며, v3 재수집과 파생 데이터 재생성이 rollout의 일부다.

## 버전 식별과 효력 기간

DB 버전 자연키는 `(document_id, mst, effective_from)`이다. 같은 MST가 단계별 시행일에 나타날 수 있으므로 MST만으로 버전을 식별하지 않는다.

효력 기간은 시행일 오름차순으로 다음 반개구간을 사용한다.

```text
[effective_from, effective_to)
effective_from <= as_of_date < effective_to
```

마지막 비교식은 `effective_to`가 있을 때만 적용한다. 한 문서에는 `effective_to IS NULL`인 open version이 하나만 있을 수 있다. 같은 문서의 다른 MST가 같은 시행일을 가지면 수집기가 거부한다.

`lifecycle_state=abolished`만으로 효력 종료일을 추정하지 않는다. 공식 연혁으로 검증된 `effective_to`가 있는 폐지 버전만 그 종료일 이전의 과거 질문에서 검색할 수 있다. 폐지 표식은 있지만 종료일이 없는 버전은 현행·과거 검색 모두에서 격리한다.

## 연혁 수집의 현재 제한

연혁 클라이언트와 파일 mock에는 다음 계약이 구현되어 있다.

- 법령 `eflaw&nw=1`, 행정규칙 `admrul&nw=2` 목록에서 `(MST, 시행일)`을 수집한다.
- 법령 과거 본문은 `target=eflaw&MST&efYd`로 조회한다.
- 서로 다른 시행일을 정렬해 `effective_to=다음 시행일`을 계산한다.
- `lsHstInf`, `lsJoHstInf`는 변경 진단에만 사용하며 응답 계약이 검증되지 않은 기능은 활성화하지 않는다.

그러나 Supabase repository의 연혁·삭제 반영 메서드는 아직 비활성화되어 있다. 따라서 현재 운영 DB가 “최초 시행부터 모든 연혁을 완전하게 보존한다”고 주장해서는 안 된다. 반복된 `sync-current`로 관측한 현재 버전들은 누적될 수 있지만, 이는 공식 전체 연혁 backfill과 동등하지 않다.

## 현재 법령명만 보존하는 제한

`legal_documents`에는 안정 출처 ID당 `exact_title` 하나만 있고, `document_versions`에는 버전별 법령명 필드가 없다. collector도 허용 목록의 현재 정확 명칭으로 과거 목록과 본문을 검증하며, upsert 시 그 현재 명칭을 `exact_title`에 저장한다.

따라서 현재 모델은 개정 전 명칭, 제명 이력, 버전별 별칭을 보존하거나 검색하지 않는다. 과거 버전의 본문을 저장하더라도 인용·임베딩에는 현재 법령명이 사용된다. 공식 명칭 이력을 별도 테이블과 출처 계약으로 구현하기 전에는 역사적 법령명을 복원했다고 표시하지 않는다.

## 삭제 이력 동기화 계약

삭제 목록은 법적 폐지 목록이 아니라 공동활용 데이터 레코드 가용성 목록이다. 목표 계약은 다음과 같다.

1. `lawSearch.do?target=delHst`를 법령 `knd=1`, 행정규칙 `knd=2`로 모두 조회한다.
2. 최초 실행은 오늘 포함 최근 8일, 이후에는 마지막 성공일 하루 전부터 오늘까지 겹쳐 조회한다.
3. `display=100` 페이지를 끝까지 읽고 `(source_kind, MST, 삭제일)` 중복을 제거한다.
4. 두 종류의 조회가 모두 성공한 뒤에만 허용 corpus의 MST와 대조한다.
5. 일치 버전은 `source_record_state=deleted`, `source_deleted_on=가장 이른 삭제일`만 변경한다. `lifecycle_state`와 `effective_to`는 변경하지 않는다.
6. 한 `(source_kind, MST)`의 상태 변경은 mutation lock이 있는 개별 transaction으로 반영한다. 실제 변경이 있으면 같은 transaction에서 `corpus.search_ready=false`와 active embedding profile 비활성화를 반영한다.
7. 모든 레코드 처리가 성공한 뒤에만 `runtime_flags['collector.deletion_sync']` 체크포인트를 전진시킨다. 더 오래된 동시 실행이 최신 체크포인트를 뒤로 덮어쓰지 못하게 단조 증가 조건을 적용한다.

출처 삭제 원문은 감사용으로 보존하지만 `source_record_state='available'` 검색 조건에서 제외한다. 이 계약은 파일 mock과 Supabase repository에 구현되어 있고, 운영 경로에서는 collector run lock을 보유한 `sync-current`가 현재 문서 동기화 뒤 실행한다. Supabase `sync-history`가 종료 코드 2인 이유는 삭제 목록 때문이 아니라 전체 과거 본문 수집이 아직 비활성화됐기 때문이다.

삭제 상태 전체와 체크포인트가 하나의 거대한 transaction인 것은 아니다. 중간 실패 전에 반영된 source 삭제는 남을 수 있지만 체크포인트는 전진하지 않는다. 다음 실행이 하루 overlap 구간을 다시 읽고, 가장 이른 삭제일을 보존하는 멱등 update를 반복해 수렴한다. 따라서 보장하는 것은 “부분 성공을 되돌림”이 아니라 “부분 성공을 완료로 표시하지 않고 안전하게 재실행”하는 것이다.

## 수집 잠금과 벡터 활성화 경계

Supabase `sync-current`는 session advisory run lock을 Open API 조회 전부터 마지막 문서 처리까지 보유한다. 이 잠금은 두 collector 실행의 중복과, 수집 중 embedding profile 승격을 막는다. 전체 9개 문서를 하나의 DB 트랜잭션으로 만드는 잠금은 아니다.

각 문서 upsert는 별도의 transaction advisory mutation lock 안에서 수행된다. 원문·버전·조문·파생 데이터 무효화와 profile 비활성화는 문서 단위로 함께 commit되거나 rollback된다. 다른 조문 버전의 UUID를 가로채지 않으며, 제거할 조문은 새 ID 삽입 전에 정리한다.

벡터 backfill은 별도 session lock으로 중복 실행을 막는다. DB batch마다 mutation lock 아래 현재 `legal-provision-v1` SHA를 다시 검사한다. 마지막 승격은 collector run lock, mutation lock 순서로 잡고 다음 조건이 모두 맞을 때만 `active=true`로 바꾼다.

- 검색 가능한 parser v3 조문 전체에 현재 SHA의 벡터가 있다.
- 프로필·차원·query/passage 입력 유형·축약·정규화 계약이 같다.
- 벡터 L2 norm과 profile 전용 HNSW index가 유효하다.

어느 단계에서든 실패하면 profile은 inactive, `corpus.search_ready`는 false로 남는다. direct path와 keyword 검색도 전체 준비 게이트, parser v3, 출처 가용성, 법적 상태와 효력 기간 조건을 적용한다.

run lock 자체는 reader snapshot이 아니며 각 문서는 별도 transaction으로 commit된다. 대신 첫 검색 가시성 변경과 같은 transaction에서 `corpus.search_ready=false`가 되므로 multi-document sync의 중간 상태는 direct·keyword·dense 모두에서 보이지 않는다. 마지막 전체 검증 transaction이 embedding profile과 전체 준비 게이트를 함께 활성화한다. 이 방식은 갱신 중 잠시 검색을 닫는 fail-closed 전환이며, 무중단으로 구세대와 신세대를 동시에 유지해야 할 때만 별도 generation pointer가 필요하다.

## 로컬 cache의 SHA 재사용

벡터 JSONL은 원문 대신 `provision_id`, profile, `source_text_sha256`, 512차원 벡터를 저장한다. 현재 ID에 cache 행이 없어도 동일 profile 안에서 SHA가 같은 과거 행이 있으면 벡터를 새 ID에 재사용한다. parser v2에서 v3로 UUID가 바뀌었지만 법령명·경로·표제·본문으로 만든 실제 임베딩 입력이 같을 때 외부 API를 다시 호출하지 않기 위한 동작이다.

본문 입력이 한 글자라도 달라 SHA가 달라지므로 재사용하지 않는다. DB 적재 직전에는 cache 행의 ID와 SHA를 현재 corpus와 다시 대조하며, stale이면 batch 전체를 rollback한다. cache append는 batch마다 flush와 `fsync`를 하고, 중단된 마지막 JSONL 행은 다음 append 전에 복구한다.

## 안전한 rollout 순서

1. 운영 DB 백업과 session-mode `DIRECT_URL`을 확인하고 collector 실행을 정지한다.
2. gate-aware API를 먼저 배포하고 production이 새 revision으로 완전히 전환됐는지 확인한다. marker가 아직 없으므로 이 구간 검색은 `503 corpus_unready`다.
3. migration 0009와 0010을 적용한다. 기존 버전에 명시적 상태를 채우고 embedding profile과 전체 검색 준비 게이트를 닫으며, 0010 capability marker를 설치한다.
4. `preview-current`로 v3 ID, 변경 버전 필드, 새·변경·삭제 조문과 임베딩 재검증 범위를 읽기 전용 확인한다.
5. run lock 아래 `sync-current`를 실행한다. 중간 실패 시 dense profile이나 runtime flag를 수동 활성화하지 않는다.
6. `generate-cache`로 현재 parser v3 corpus의 cache를 완성한다. 같은 SHA 벡터는 재사용한다.
7. `DIRECT_URL`로 `load-cache`를 실행해 DB의 missing/stale 행만 적재하고 profile과 corpus 게이트를 자동 승격한다.
8. capability·coverage·SHA·norm·HNSW 검증 뒤 `status`와 실제 query `verify`를 확인한다.
9. 삭제 목록은 `sync-current`에 포함되어 있으므로 별도 `sync-history` 없이 실행된다. 전체 과거 본문 수집이 구현·검증되기 전까지 `sync-history`는 활성화하지 않는다.

구버전 API가 남아 있는 동안 collector를 재개하지 않는다. 구버전 reader는 `corpus.search_ready`를 검사하지 않으므로 migration만 먼저 적용해서는 부분 corpus 노출을 막을 수 없다.

## 결정 기록

- 2026-07-13: XML 전용 초안을 JSON 우선·XML 폴백으로 변경했다.
- 2026-07-13: 수집기를 API와 분리하고 고정 공인 IP 서버의 OS scheduler가 실행하도록 정했다.
- 2026-07-14: `delHst`를 법적 폐지가 아닌 Open API 레코드 가용성으로 분리했다.
- 2026-08-03: 버전 자연키를 `(문서, MST, 시행일)`로 확장하고 효력 기간을 `[from, to)`로 고정했다.
- 2026-08-03: parser schema v3 UUID에 시행일을 포함하고 JSON/XML 식별자를 통일했다.
- 2026-08-03: collector run lock과 문서 mutation lock을 분리하고, 완전한 벡터 검증 뒤에만 profile을 fail-closed 방식으로 활성화하도록 했다.
- 2026-08-03: Supabase 삭제 목록 동기화는 `sync-current`에 포함하고, 전체 과거 본문 동기화와 역사적 법령명 보존은 구현 전까지 명시적 제한으로 유지한다.

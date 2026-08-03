# 법령 코퍼스 원자 동기화와 벡터 안전 활성화

확인일: 2026-08-03

## 한 문장 결론

법령 원문과 벡터는 한 번에 만들어지지 않으므로, 원문 변경 시 모델 독립 게이트 `runtime_flags['corpus.search_ready']`로 모든 검색을 먼저 닫고 현재 원문 전체에 맞는 벡터와 인덱스가 준비됐다는 검증을 통과한 뒤 다시 연다.

## 왜 단순 upsert만으로 부족한가

RAG corpus에는 원본과 파생 데이터가 함께 있다.

```text
공식 Open API 원문
  └─ 정규화된 문서 버전
      └─ 조·항·호·목
          ├─ 임베딩 벡터
          ├─ 조문 관계
          └─ 추출 의무
```

본문 한 글자가 바뀌면 조문 행만 고쳐서는 안 된다. 예전 본문으로 만든 벡터나 관계가 남으면 검색 결과는 새 원문처럼 보이지만 실제로는 오래된 파생 데이터를 사용한다.

반대로 수천 개 벡터를 만드는 동안 DB를 완전히 잠그면 수집과 검색을 오래 막는다. 그래서 시스템은 다음 두 원칙을 결합한다.

1. 문서 하나의 원문 변경은 짧은 DB transaction으로 원자 반영하며, 실제 검색 상태가 바뀌면 같은 transaction에서 corpus 검색 게이트를 닫는다. 임베딩 입력이나 검색 자격도 바뀐 경우에는 profile까지 비활성화한다.
2. 여러 batch가 필요한 벡터 재생성을 시작할 때에는 corpus 게이트와 embedding profile을 모두 inactive로 두고, 전체 검증 뒤 같은 승격 transaction에서 함께 활성화한다.

## 세 단계 식별자

### 문서

문서는 `(source_kind, source_id)`로 식별한다. 법령과 행정규칙에서 같은 문자열 ID가 우연히 겹쳐도 source kind가 다르면 다른 문서다.

### 문서 버전

버전 자연키는 다음과 같다.

```text
(document_id, mst, effective_from)
```

MST만으로는 부족하다. 같은 MST가 단계별 시행일에 다시 나타날 수 있기 때문이다.

### 조문

parser schema v3는 다음 값을 정렬된 JSON으로 만든 뒤 UUID5를 계산한다.

```text
source_kind + source_id + mst + effective_from + path
```

이 방식의 결과는 다음과 같다.

- JSON과 XML parser가 같은 구조를 읽으면 같은 UUID가 나온다.
- 같은 제1조라도 MST나 시행일이 다르면 다른 UUID가 나온다.
- 시행일을 나중에 UUID 밖의 메타데이터로만 붙이지 않는다.
- path가 바뀌면 원문 위치가 바뀐 것이므로 새 조문 ID가 된다.

활성화 검증기는 parser가 준 ID를 같은 함수로 다시 계산한다. schema version이 3이 아니거나 ID가 다르면 수집 결과를 DB에 넣지 않는다.

## 효력 기간은 `[from, to)`다

버전의 시간 조건은 시작일을 포함하고 종료일은 포함하지 않는 반개구간이다.

```text
effective_from <= 질문 기준일
질문 기준일 < effective_to
```

`effective_to`가 없으면 두 번째 조건은 적용하지 않는다. 예를 들어 새 버전이 2026년 3월 1일 시행이면 앞 버전의 종료일은 2026년 3월 1일이다.

```text
앞 버전: [2025-01-01, 2026-03-01)
새 버전: [2026-03-01, ...)
```

그러므로 2026년 3월 1일에는 새 버전만 유효하다. 양쪽 구간이 같은 날을 포함해 중복되는 문제를 피한다.

## 폐지와 출처 삭제는 다르다

`lifecycle_state=abolished`는 법적 상태이고, `source_record_state=deleted`는 Open API에서 그 데이터 레코드를 다시 확인할 수 있는지 나타내는 출처 상태다.

폐지 표식만으로 폐지 효력일을 추정하면 안 된다. 현재 검색 계약은 다음처럼 보수적으로 동작한다.

- `active`, `scheduled`: 날짜 구간이 맞으면 검색 가능
- `abolished`와 검증된 `effective_to` 있음: 종료일 이전의 과거 질문에서만 검색 가능
- `abolished`이지만 `effective_to` 없음: 검색 불가
- `source_record_state=deleted`: 법적 상태와 관계없이 검색 불가

즉 “폐지됐다”는 사실과 “언제까지 효력이 있었는가”는 별도의 증거가 필요하다.

## Atomic의 정확한 범위

Atomic은 여러 변경이 전부 성공하거나 전부 취소된다는 뜻이다. 이 시스템에는 atomic 범위가 둘 있다.

### 문서 하나의 transaction

한 문서의 version·provision 변경, 파생 데이터 무효화와 corpus 게이트 비활성화는 하나의 DB transaction에 들어간다. 임베딩 입력이나 검색 자격이 바뀌면 profile 비활성화도 여기에 포함된다. 중간 SQL이 실패하면 모두 rollback된다.

### 전체 collector run

여러 법률을 차례로 수집하는 전체 실행은 하나의 거대한 transaction이 아니다. session advisory run lock으로 다른 collector 실행과 profile 승격을 막지만, 각 문서는 따로 commit한다.

run lock 자체는 상호 배제이지 전체 reader snapshot이 아니다. 대신 실제 corpus 변경을 commit하는 첫 transaction이 `corpus.search_ready=false`도 함께 commit한다. API의 direct lookup, keyword 검색, dense 검색은 모두 이 모델 독립 게이트를 검사하므로 그 뒤에는 부분 갱신 corpus를 반환하지 않는다. 수집이나 backfill이 중간에 실패해도 게이트는 false로 남는다.

현재 방식은 갱신 중 검색을 닫는 fail-closed 전환이며 무중단 전환은 아니다. 미래에 갱신 중에도 검증된 이전 corpus를 계속 서비스해야 한다면, 새 generation을 옆에서 완성한 뒤 active generation pointer 하나만 바꾸는 구조를 별도 선택지로 도입할 수 있다. 이는 현재 `corpus.search_ready` 계약의 필수 조건이 아니다.

## 모델 독립 corpus 검색 게이트

`runtime_flags`의 `corpus.search_ready` 행은 특정 임베딩 모델이나 검색 알고리즘에 속하지 않는다. runtime은 이 값 하나만 믿지 않고, 게이트 계약을 설치한 schema capability marker도 함께 검사한다.

```json
{
  "schema.corpus_search_ready_v1": {"enabled": true, "migration": "0010"},
  "corpus.search_ready": {"ready": false, "reason": "collector_corpus_change"}
}
```

`schema.corpus_search_ready_v1`은 DB가 이 fail-closed 계약을 지원한다는 표시다. runtime reader는 capability의 `enabled`와 corpus gate의 `ready`가 모두 문자열 값 `true`일 때만 검색한다. 둘 중 하나가 없거나 false이거나 형식이 다르면 검색 결과를 열지 않는다. writer도 capability가 확인되지 않으면 corpus 상태나 벡터를 변경하지 않고 migration 0010 적용을 요구한다.

현재 같은 SQL 게이트를 사용하는 경로는 다음과 같다.

- 조문 경로를 이용한 direct lookup
- provision ID 단건 조회
- PGroonga keyword 검색
- embedding dense 검색

따라서 embedding profile만 비활성화했을 때처럼 keyword/direct 경로가 갱신 중 corpus를 우회해서 읽는 문제가 없다. embedding profile의 `active`는 해당 벡터 profile의 준비 상태이고, `corpus.search_ready`는 어떤 검색 방식도 현재 corpus를 노출해도 되는지를 나타내는 상위 게이트다.

### 닫힌 corpus와 근거 부족은 다른 상태다

게이트가 열린 상태에서 검색했지만 질문에 답할 조문이 없으면 `insufficient_evidence`, 즉 “검색 가능한 corpus 안에 충분한 근거가 없음”이다. 반대로 게이트가 닫혀 있으면 corpus를 검사할 수 없으므로 무근거로 판정하지 않는다.

현재 API는 검색·질문·조문 조회에서 닫힌 게이트를 감지하면 HTTP 503과 다음 오류 코드를 반환한다.

```json
{
  "detail": {
    "code": "corpus_unready",
    "message": "법령 corpus를 갱신·검증하는 동안 검색이 일시 중지되었습니다."
  }
}
```

운영 상태는 `GET /v1/corpus/status`에서 확인한다. 응답의 `corpus_search_ready`는 검색 허용 여부이고, `corpus_search_unavailable_reason`은 닫힌 이유다. 예를 들어 capability marker가 없으면 `schema_capability_missing`, 0010 직후에는 `migration_0010`, backfill을 시작하면 `embedding_backfill_started`가 될 수 있다. 상태 endpoint는 검색 실패를 정답 없음과 구분해 운영자와 UI가 재시도·점검 상태로 표시하게 한다.

게이트 상태 전이는 다음과 같다.

```text
검증된 corpus: corpus.search_ready=true
  → collector가 검색 상태 변경을 감지
  → 같은 문서 변경 transaction: corpus.search_ready=false
     + 임베딩 입력·검색 자격 변경이면 profile active=false
  → 전체 수집 및 embedding backfill: false 유지
  → run lock + mutation lock 아래 전체 벡터·SHA·index 검증
  → 같은 승격 transaction: profile active=true + corpus.search_ready=true
```

변경 없는 collector 실행은 게이트를 불필요하게 닫지 않는다. 본문·제목·조문 집합·검색 자격이 바뀌거나 공식 출처 삭제가 실제 반영될 때 닫는다. embedding backfill도 여러 batch 쓰기를 시작하기 전에 mutation lock 아래 profile과 corpus 게이트를 함께 비활성화한다.

## Advisory lock 세 가지

Advisory lock은 PostgreSQL이 업무 의미를 스스로 알지는 못하지만, 애플리케이션끼리 같은 숫자 key를 사용해 작업 순서를 맞추는 잠금이다.

| 잠금 | 범위 | 역할 |
|---|---|---|
| corpus sync run lock | session | Open API 조회부터 마지막 문서 처리까지 collector 중복 실행 방지 |
| corpus mutation lock | transaction | 문서 변경과 embedding batch 쓰기가 동시에 일어나지 않게 함 |
| embedding backfill lock | session | 두 `run`/`load-cache` 프로세스가 같은 profile을 동시에 채우지 않게 함 |

profile 승격은 `sync run lock → mutation lock` 순서로 잡는다. collector가 이미 run lock을 보유하고 있으면 승격은 수집이 끝날 때까지 기다린다. 모든 코드가 같은 잠금 순서를 지켜야 교착 상태를 피할 수 있다.

session lock을 쓰는 DB writer는 transaction pooler가 아니라 session-mode `DIRECT_URL`을 사용해야 한다. 다른 물리 연결로 바뀌면 lock을 잡은 session과 해제하는 session이 달라질 수 있기 때문이다.

## 문서 동기화가 실제로 하는 일

검증된 한 문서를 반영하는 순서는 다음과 같다.

1. parser v3 구조와 UUID, 시행일, 원문 SHA를 검증한다.
2. SHA가 들어간 content-addressed 경로에 원문을 불변 저장한다.
3. mutation lock을 획득한다.
4. 문서와 기존 버전 행을 잠그고 `(document, MST, 시행일)` 충돌을 검사한다.
5. 새 시행일이 들어오면 이전 open version을 그 날짜로 닫는다.
6. 다른 버전에 이미 속한 조문 UUID가 있는지 검사한다.
7. 검색에 보이는 상태가 바뀌면 같은 transaction에서 `corpus.search_ready=false`를 반영한다. 본문·경로·표제처럼 임베딩 입력이 바뀌거나 검색 자격이 달라지면 embedding profile도 inactive로 만든다.
8. 오래된 벡터·관계·추출 의무를 제거한다.
9. 제거될 조문을 먼저 삭제하고 새·변경 조문을 upsert한다.
10. 저장 결과를 입력과 다시 비교한 뒤 commit한다.

원문 Storage 쓰기는 DB transaction보다 먼저 일어난다. DB가 실패하면 참조되지 않은 SHA 객체가 남을 수 있지만, 활성 corpus에 연결되지는 않는다. 이 객체는 임의로 즉시 삭제하지 않고 별도의 보존·정리 정책으로 다뤄야 한다.

## 왜 corpus 게이트와 profile을 모두 inactive로 만드는가

profile이 active인 상태에서 3,000개 중 500개만 새 벡터로 바뀌면 검색 공간에 두 세대가 섞인다. 코사인 점수는 같은 변환 계약과 같은 corpus snapshot을 전제로 비교해야 하므로 이런 부분 상태를 정상 검색으로 보여주면 안 된다.

Fail-closed는 준비 상태를 확신할 수 없으면 기능을 닫아 두는 방식이다. profile만 닫으면 dense 검색은 막을 수 있지만 direct/keyword 검색은 막지 못하므로 corpus 전체 게이트가 추가로 필요하다.

```text
corpus 변경 감지
  → 같은 transaction에서 corpus.search_ready=false
     + 임베딩 재검증이 필요하면 profile inactive
  → missing/stale vector 생성·적재
  → 전체 검증
  → 성공: 같은 transaction에서 profile active + corpus.search_ready=true
  → 실패: corpus.search_ready=false 유지
```

모든 runtime 검색 SQL은 먼저 `corpus.search_ready`를 검사한다. dense SQL은 여기에 더해 다음 조건을 행마다 다시 확인한다.

- profile이 active인가
- profile과 차원이 맞는가
- parser schema가 v3인가
- `legal-provision-v1` 현재 입력 SHA와 저장 SHA가 같은가
- 출처가 available인가
- lifecycle과 `[from, to)`가 질문 기준일에 맞는가

corpus gate, profile flag와 행 단위 SHA 검사를 함께 두면 collector가 title을 바꾼 직후 예전 벡터가 남아 있어도 어떤 runtime 검색 경로에서도 노출되지 않는다.

## Cache SHA 재사용은 왜 안전한가

로컬 JSONL cache에는 원문을 넣지 않고 다음만 저장한다.

```text
profile_key
dimensions
provision_id
source_text_sha256
embedding
```

`source_text_sha256`는 다음 임베딩 입력 전체의 지문이다.

```text
현재 법령명
조문 경로
표제
본문
```

parser v2에서 v3로 바뀌면 provision ID가 달라져도 이 입력 문자열이 같을 수 있다. cache는 같은 profile 안에서 SHA가 같은 기존 벡터를 새 ID에 복사해 NVIDIA API 호출을 생략한다.

이는 ID만 보고 재사용하는 것이 아니다. 법령명·경로·표제·본문 중 하나라도 달라지면 SHA가 달라져 새 벡터가 필요하다. DB batch 쓰기 직전에도 현재 SHA를 다시 계산해 하나라도 stale이면 INSERT 전에 batch 전체를 취소한다.

JSONL은 append 후 flush와 `fsync`를 수행한다. 프로세스가 마지막 행 중간에서 중단되면 다음 append 전에 불완전한 tail만 잘라내므로 이미 완료된 batch는 재사용할 수 있다.

## Profile 활성화 검증

`run`과 `load-cache`는 DB를 쓰기 전에 mutation lock 아래 profile inactive와 `corpus.search_ready=false`를 같은 transaction으로 commit한다. `load-cache`는 DB에서 missing 또는 stale인 조문만 upsert한다.

마지막 승격 transaction은 collector run lock과 mutation lock을 잡고 다음을 검사한다.

1. 검색 가능한 모든 parser v3 조문에 벡터가 있는가
2. 모든 저장 SHA가 현재 `legal-provision-v1` 입력과 같은가
3. provider, model, 원본·저장 차원, query/passage 유형, 축약, 정규화와 profile version이 같은가
4. 벡터가 유한하고 L2 norm이 1인가
5. profile 전용 HNSW index가 valid·ready이며 정의도 기대 계약과 같은가
6. eligible corpus가 비어 있지 않은가

하나라도 실패하면 `active=true`나 `corpus.search_ready=true`를 쓰지 않는다. 모두 성공하면 collector run lock과 mutation lock을 보유한 같은 승격 transaction에서 profile을 활성화하고 corpus 게이트를 true로 바꾼다. 운영자가 profile이나 runtime flag를 수동으로 켜면 이 안전 게이트를 우회하므로 금지한다.

## 현재 법률명만 저장하는 명시적 한계

현재 `legal_documents`는 안정 ID마다 `exact_title` 하나만 저장한다. 버전 테이블에는 역사적 법령명이나 별칭이 없다. collector도 허용 목록의 현재 명칭과 정확히 같은 결과만 받아들인다.

그래서 과거 version을 저장해도 검색·인용·임베딩에는 현재 명칭이 들어간다. 제명 전 이름으로 질문하는 검색, 이름이 바뀐 날짜의 복원, 과거 별칭 인용은 아직 지원하지 않는다.

이 문제는 현재 title을 덮어쓰지 않는 것만으로 해결되지 않는다. 공식 출처가 확인되는 title history와 유효 기간을 별도 모델로 추가해야 한다.

## 삭제 이력 동기화 계약과 현재 상태

공식 `delHst` 삭제 목록은 다음 계약으로 설계됐다.

- 법령 `knd=1`과 행정규칙 `knd=2`를 같은 기간에 모두 조회
- 첫 실행 8일, 이후 마지막 성공일 하루 전부터 겹쳐 조회
- 전체 페이지를 읽고 `(종류, MST, 삭제일)` 중복 제거
- 두 조회가 모두 성공한 뒤에만 corpus와 대조
- `source_record_state`와 가장 이른 `source_deleted_on`만 변경
- 한 `(종류, MST)`의 변경마다 mutation lock을 잡고, 실제 변경 시 같은 transaction에서 corpus 게이트와 embedding profile 비활성화
- 모든 레코드를 처리한 뒤에만 `runtime_flags['collector.deletion_sync']` 성공 체크포인트 전진

어느 한 목록이 실패하면 다른 목록도 성공으로 처리하지 않고 체크포인트를 전진시키지 않는다. 그래야 다음 실행이 같은 기간을 다시 안전하게 읽는다.

현재 이 계약은 파일 mock과 Supabase repository에 구현되어 있다. 운영 경로에서는 run lock을 보유한 `sync-current`가 현재 본문 처리 뒤 법령·행정규칙 삭제 목록을 모두 조회한다. Supabase `sync-history`가 종료 코드 2로 거부되는 것은 전체 과거 본문 수집이 아직 비활성화됐기 때문이며, 삭제 목록 동기화까지 비활성이라는 뜻은 아니다.

삭제 상태 전체와 체크포인트가 하나의 transaction에 들어가는 것은 아니다. 한 source key의 변경은 원자적이지만, 여러 key를 처리하다 실패하면 앞서 commit한 삭제 상태는 남고 체크포인트만 전진하지 않는다. 다음 실행은 overlap 기간을 다시 읽는다. update는 같은 삭제를 반복 적용해도 상태가 중복되지 않고 가장 이른 삭제일을 보존하므로 안전하게 수렴한다. 이것은 “실패하면 앞선 변경을 모두 rollback”하는 원자성이 아니라 “실패한 실행을 완료로 표시하지 않는 재실행 계약”이다.

## 안전한 rollout 읽기

parser v3와 시간 모델, 벡터 gate를 운영에 넣는 순서는 다음과 같다.

1. collector와 embedding writer를 정지하고 실행 중인 run이 없음을 확인한다.
2. capability와 gate를 모두 검사하고 `corpus_unready`를 503으로 구분하는 새 API를 모든 instance에 완전히 배포한다. marker가 아직 없으므로 이 API는 fail-closed 상태여야 한다.
3. 배포 상태와 `GET /v1/corpus/status`로 구버전 reader가 하나도 남지 않았음을 확인한다. 이때 `corpus_search_ready=false`여야 하며, 일반적인 pre-0010 DB의 사유는 `schema_capability_missing`이다. legacy gate 행이 이미 있으면 그 행에 저장된 사유가 보일 수 있지만 준비 상태는 계속 false여야 한다.
4. 백업과 session-mode `DIRECT_URL`을 확인한 뒤 migration 0010까지 적용한다. 0009가 아직 적용되지 않았다면 같은 정비 구간에서 0009를 먼저 적용하되, 그 사이 collector를 시작하지 않는다.
5. migration 0010은 한 migration transaction 안에서 `schema.corpus_search_ready_v1` capability marker와 `corpus.search_ready=false`를 함께 설치한다. capability를 먼저 disabled로 쓰고 gate를 false로 만든 다음 capability를 enabled로 바꾸며, 전체가 commit돼야 runtime이 계약을 인정한다.
6. `preview-current`로 v3 ID와 변경 범위를 확인한다.
7. run lock 아래 `sync-current`로 현재 허용 corpus를 v3로 재수집한다. 변경이 있으면 게이트는 false로 유지한다.
8. `generate-cache`로 동일 SHA 벡터를 재사용하고 나머지만 생성한다.
9. `load-cache`로 DB missing/stale 벡터만 적재한다.
10. 전체 coverage·SHA·norm·HNSW 검증을 통과한 승격 transaction이 profile과 corpus 게이트를 함께 활성화한 뒤 `status`와 실제 query `verify`를 확인한다.
11. collector 운영을 재개한다. 삭제 목록은 `sync-current`에 포함해 계속 동기화하되, 전체 과거 본문 수집이 별도로 구현·검증될 때까지 `sync-history`는 켜지 않는다.

순서의 핵심은 “collector 정지 → gate-aware API 완전 배포 확인 → 0010 → sync/backfill”이다. 구버전 reader는 capability와 gate를 모르므로, 그것이 살아 있는 동안 corpus를 변경하면 새 API는 닫혀 있어도 구버전 API가 부분 corpus를 읽을 수 있다. 따라서 혼합 버전 배포 중에는 migration 0010 이후의 corpus 변경을 시작하지 않는다.

검색이 닫힌 시간은 의도된 안전 상태이며 이 기간의 요청은 무근거 응답이 아니라 503 `corpus_unready`다. 0010 직후에는 이전 profile이 존재해도 direct, keyword, dense 모두 결과를 내지 않는다. 완전한 검증 없이 flag를 수동으로 true로 바꾸지 않는다. 무중단이 제품 요구사항이 되면 현재 테이블을 부분 갱신하는 대신 generation pointer 방식을 별도 설계한다.

배포 완료 표시는 충분한 증거가 아니다. 이 작업 중 Vercel은 빌드를 성공 처리했지만 기존 catch-all rewrite가 원래 요청 경로를 `/app/main.py`로 바꾸어 모든 FastAPI route가 404를 반환했다. FastAPI 프로젝트는 `pyproject.toml`의 명시적 ASGI entrypoint를 사용하고, 운영 별칭에서 `/health`와 corpus 상태 응답을 직접 확인한 뒤에만 DB 전환을 시작한다.

## 용어 정리

- **Atomic**: 여러 변경이 전부 반영되거나 전부 취소되는 성질
- **Transaction**: DB가 atomic commit/rollback을 제공하는 작업 단위
- **Advisory lock**: 애플리케이션이 공통 key로 작업 순서를 맞추는 PostgreSQL 잠금
- **Idempotent**: 같은 입력을 다시 적용해도 결과가 중복되지 않는 성질
- **Fail-closed**: 불확실하거나 실패하면 기능을 닫힌 상태로 유지하는 정책
- **Capability marker**: DB schema가 특정 runtime 계약을 완전히 지원한다고 알리는 버전 표식. 현재 값은 `schema.corpus_search_ready_v1`
- **Corpus search readiness gate**: 현재 corpus 전체를 모든 검색 방식에 노출해도 되는지 나타내는 모델 독립 runtime flag
- **corpus_unready**: corpus gate가 닫혔을 때 정답 없음과 구분해 반환하는 HTTP 503 오류 코드
- **Derived data**: 원문에서 계산한 벡터·관계·추출 의무 같은 파생 데이터
- **Content-addressed path**: 내용 SHA를 경로에 넣어 같은 원문을 같은 불변 객체로 가리키는 방식
- **Half-open interval**: 시작은 포함하고 끝은 제외하는 `[from, to)` 구간
- **Activation gate**: 전체 준비 조건을 통과했을 때만 embedding profile과 corpus 검색 게이트를 같은 transaction에서 활성화하는 검증 단계
- **Generation pointer**: 새 corpus 세대를 별도로 완성한 뒤 서비스가 읽을 세대 ID만 원자적으로 전환하는 무중단 방식의 선택지

상세 구현 계약은 [국가법령정보 Open API 수집 계약](../design-docs/open-law-api-ingestion.md), [시간 효력 모델](../design-docs/temporal-validity.md), [검색 인덱스와 임베딩 계보 설계](../design-docs/retrieval-index-storage.md)에 있다.

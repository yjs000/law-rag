# 2. 법령 코퍼스의 생애주기

## 코퍼스는 파일 모음이 아니라 검증된 세대다

코퍼스는 검색 대상 원문 전체다. 이 프로젝트에서는 “법령 JSON을 받았다”만으로 코퍼스가 준비됐다고
보지 않는다. 어떤 출처·버전·파서에서 만들어졌는지 추적되고, 검색 가능한 모든 조문과 파생 벡터가
같은 세대임을 검증해야 한다.

현재 법률 코퍼스 출처는 국가법령정보 공동활용 Open API 하나뿐이다. MVP는 정확 명칭 허용 목록 9개만
수집하며 HTML·PDF·다른 법률 사이트로 실패를 우회하지 않는다. 외부 자료를 섞지 않는 이유는 정보가
적어서가 아니라, 답변에서 원문·버전·위치를 끝까지 역추적하기 위해서다.

```text
Open API 원문
→ 형식·도메인 검증
→ 불변 raw 객체
→ 문서·버전·조문
→ 임베딩·검색 자산
→ 전체 준비 검증
→ 검색 가능 세대
```

## JSON 우선, XML은 스키마 폴백

collector는 같은 요청을 먼저 JSON으로 호출한다. JSON 문법만 읽히는지 보지 않고 법령명, 출처 ID,
MST, 시행일, 조문 구조가 도메인 객체로 정규화되는지 검사한다. 지원하지 않는 형식이나 도메인 스키마
검증 실패 때만 XML로 다시 요청한다.

timeout, 5xx, 인증 실패와 다른 4xx는 XML로 숨기지 않는다. 일시 장애에는 같은 형식으로 제한된
재시도를 하고, 자격정보·권한 문제는 실패로 드러낸다. JSON과 XML이 같은 원문을 표현한다면 최종
`LegalDocumentRecord`도 같아야 한다.

정규화가 하는 일은 전송 형식의 차이를 없애되 법률 구조는 보존하는 것이다.

- 문서: `source_kind + source_id`로 식별한다.
- 버전: `document_id + MST + effective_from`을 자연키로 사용한다.
- 조문: 문서·MST·시행일·조/항/호/목 경로를 포함해 결정적 ID를 만든다.
- parser v3는 JSON/XML이 같은 구조를 읽으면 같은 조문 ID를 내야 한다.

MST만으로 버전을 식별하지 않는 이유는 같은 MST가 여러 시행일에 나타날 수 있기 때문이다. 조문 ID에
시행일과 경로를 넣는 이유는 같은 제7조라도 서로 다른 법령 버전의 원문 위치를 섞지 않기 위해서다.

## 파싱과 청킹은 같은 말이 아니다

파싱은 JSON/XML의 표현 차이를 없애고 법률 구조를 도메인 객체로 바꾸는 단계다. 그 결과의 핵심 모양은
다음과 같다. 아래는 이해를 위한 주요 필드이며 실제 타입에는 공포일·소관 부처·파서 버전 같은 계보
필드도 더 있다.

```text
LegalDocumentRecord
├─ source_id       # Open API가 부여한 법령·행정규칙 식별자
├─ mst             # 해당 원문 버전의 일련번호
├─ title           # 공식 법령명
├─ effective_from  # 이 버전이 효력을 시작하는 날
├─ source_url      # 원문을 다시 추적할 공식 출처
├─ raw_format      # 실제로 파싱한 JSON 또는 XML
├─ raw_sha256      # 받은 원문 바이트의 SHA-256 지문
└─ provisions[]    # 검색 가능한 조·항·호·목 목록
   └─ ProvisionRecord
      ├─ id          # 출처·버전·시행일·경로로 만든 결정적 ID
      ├─ path        # 제7조/항①/호1. 같은 법률 계층 위치
      ├─ heading     # 조문 표제
      ├─ content     # 이 단위의 원문 본문
      ├─ parent_path # 바로 위 조·항·호의 경로
      └─ ordinal     # 원문에서의 결정적 순서
```

청킹은 파싱된 구조에서 검색 단위를 정하는 단계다. 현재 parser v3는 Open API가 제공한 조·항·호·목
계층을 보존해 각 본문 단위를 `ProvisionRecord`로 만든다. 임의 글자 수나 토큰 수로 다시 자르지 않는다.
따라서 조문 전체만 들어온 실험 A 입력은 조마다 하나의 청크가 되고, 항·호·목이 구조화된 운영 원문은
그 하위 단위도 각각 검색 가능한 청크가 된다.

실험 A의 일반 텍스트 어댑터는 별도 파서를 복제한 것이 아니다. 텍스트의 `제N조` 경계를 최소 Open API
JSON 모양으로 옮긴 뒤 기존 `parse_legal_document()`를 그대로 호출한다. 자세한 입력·출력·실패 계약은
[실험 A 완료 계획](../exec-plans/completed/0016-experiment-a-plain-text-chunking.md)에 있다.

## 시간은 `[from, to)`로 읽는다

법령 버전은 시작일을 포함하고 종료일은 제외하는 반개구간으로 모델링한다.

```text
effective_from <= as_of_date < effective_to
```

종료일이 없으면 오른쪽 조건은 없다. 새 버전이 2026-03-01에 시행되면 앞 버전은
`[이전 시작일, 2026-03-01)`, 새 버전은 `[2026-03-01, ...)`이다. 같은 날 두 버전이 유효해지는
중복을 피한다.

법적 폐지와 Open API 레코드 삭제도 다르다.

- `lifecycle_state=abolished`: 법률의 상태다. 정확한 종료일이 있어야 과거 효력을 계산할 수 있다.
- `source_record_state=deleted`: 출처에서 레코드를 다시 확인할 수 있는지의 상태다.

삭제 목록 `delHst`에는 법적 폐지 사유나 효력 종료일이 없으므로 삭제 사실로 폐지일을 추론하지 않는다.
원문은 감사와 복구 판단을 위해 보존하되 출처 삭제 상태인 버전은 검색에서 제외한다.

또한 저장된 전체 역사 코퍼스와 한 기준일에 실제 검색되는 집합은 다르다. 기준일 검색 집합은
`effective_from <= as_of_date < effective_to`를 만족하는 버전의 조문만 포함한다. 운영 지원 범위 밖
날짜는 일부 법령만 검색하지 않고 검색 전에 `422 unsupported_corpus_date`로 거부한다. 정확한 범위는
날짜를 이름에 박은 snapshot 문자열이 아니라 `/v1/corpus/status`와 시간 계약에서 확인한다.

평가 재현성은 질문의 `as_of_date`와 그 날짜에 유효한 조문 집합의 내용 지문을 함께 고정해야 한다.
오늘과 내일 사이에 시행·개정·폐지 경계가 없고 유효 조문 집합도 같다면 같은 검색 population이다.
반대로 미리 저장된 예정 버전이 시행되는 날에는 저장 파일이 새로 늘지 않아도 유효 집합과 지문이
바뀐다. 그래서 “저장된 모든 버전의 해시”와 “특정 날짜에 검색할 조문의 해시”를 구분한다.

## raw Storage와 PostgreSQL을 둘 다 쓰는 이유

collector는 한 번 받은 응답에서 두 종류의 결과를 만든다.

```text
원문 바이트 ── SHA-256 ── private Storage의 content-addressed 객체
     └─ 검증·파싱 ── legal_documents / document_versions / provisions
```

Storage에는 당시 받은 JSON/XML을 손실 없이 보존한다. DB에는 검색·기준일 필터·인용에 적합한 문서,
버전과 조문 행을 저장한다. `document_versions`가 raw 경로, 포맷, SHA-256, parser version과 폴백 사유를
연결한다.

SHA-256은 암호화가 아니라 바이트 지문이다. 같은 바이트는 같은 해시를 내고, 바이트가 달라지면 다른
해시를 낸다. 원문 파일명에 해시를 넣고 덮어쓰지 않으면 DB transaction이 실패해도 이미 활성인
manifest가 바뀐 원문을 가리키지 않는다. 참조되지 않은 객체는 남을 수 있으므로 별도 보존 정책 없이
즉시 삭제하지 않는다.

문서 하나의 DB 반영은 transaction으로 묶는다. 문서·버전·조문 upsert, 제거된 조문의 파생 데이터
무효화와 검색 준비 게이트 변경 중 하나라도 실패하면 전부 rollback한다. 하지만 여러 법령을 처리하는
collector 전체 실행은 하나의 거대한 transaction이 아니다. 성공한 문서는 commit하고, 전체 세대가
완성될 때까지 검색을 닫아 부분 코퍼스 노출을 막는다.

## 왜 검색 준비 게이트가 두 개인가

원문과 벡터는 한 번에 바뀌지 않는다. 본문이 변경된 직후 예전 벡터가 남아 있으면 서로 다른 세대가
같은 검색 공간에 섞인다. 그래서 두 준비 상태를 구분한다.

- `corpus.search_ready`: direct path, keyword, dense, 단건 조문 조회를 모두 막는 모델 독립 상위 게이트
- `embedding_profiles.active`: 특정 임베딩 변환 계약의 전체 벡터가 준비됐다는 하위 게이트

검색 결과를 바꾸는 원문 변경을 commit하는 transaction은 `corpus.search_ready=false`도 함께 쓴다.
임베딩 입력이나 검색 자격이 바뀌면 해당 profile도 inactive로 만든다. 이후 현재 조문 전체에 맞는
벡터·입력 SHA·차원·norm을 검증한 마지막 승격 transaction에서 두 상태를 함께 연다.

```text
검증된 세대
→ 원문 변경 commit + corpus gate 닫기
→ 조문·벡터 batch 갱신
→ 전체 coverage·SHA·profile·norm 검사
→ profile 활성 + corpus gate 열기
```

게이트가 닫힌 상태는 근거 부족이 아니다. 검색 가능한 코퍼스를 검사하지 못했으므로 API는 빈 결과 대신
`503 corpus_unready`를 반환한다. `/v1/corpus/status`가 준비 여부와 닫힌 이유를 노출한다.

## 잠금은 원자성과 역할이 다르다

PostgreSQL advisory lock은 애플리케이션 작업끼리 순서를 맞춘다.

| 잠금 | 범위 | 목적 |
|---|---|---|
| corpus sync run lock | session | collector 두 개가 동시에 실행되지 않게 함 |
| corpus mutation lock | transaction | 원문 변경과 벡터 batch 쓰기가 겹치지 않게 함 |
| embedding backfill lock | session | 같은 profile을 두 프로세스가 채우지 않게 함 |

lock은 상호 배제이고 transaction은 원자성이다. run lock을 잡았다고 여러 문서 commit이 하나로
rollback되는 것은 아니다. 반대로 한 문서 transaction이 원자적이어도 다른 backfill과 동시에 실행하면
세대가 섞일 수 있으므로 공용 mutation lock이 필요하다.

## 계보와 세대 이름

결과를 비교하려면 “dense 검색” 같은 알고리즘 이름만 저장해서는 부족하다.

```text
corpus snapshot: 검색 원문의 고정된 집합
retrieval profile: 검색기 하나의 계산 계약
index build: snapshot + profile로 만든 물리 산출물
configuration: profile의 실행 순서와 primary/fallback 역할
release: snapshot + configuration + 필요한 build의 배포 후보
active pointer: 현재 선택한 ready release
```

현재 DB에는 이 계보를 기록할 catalog가 있지만, catalog 행이 있다는 사실만으로 검색기가 구현·승인·활성
상태라는 뜻은 아니다. 현재 runtime은 아직 catalog pointer로 검색 방식을 동적으로 선택하지 않는다.
과거 HNSW 물리 인덱스도 보존되어 있지만 현재와 미래의 운영·실험 검색에는 사용하지 않는다. 새 HNSW
설계·인덱스·재구축·튜닝·평가·release도 만들지 않으며, 물리 잔여물 제거는 별도 cleanup 작업이다.

## 직접 확인

```powershell
uv run --project apps/collector law-rag-collector status
uv run --directory apps/api python -m scripts.backfill_embeddings status
```

실제 수집·migration·벡터 적재는 운영 DB와 외부 API를 변경할 수 있다. 실행 전
[Open API 수집 계약](../design-docs/open-law-api-ingestion.md)과
[검색 인덱스와 임베딩 계보](../design-docs/retrieval-index-storage.md)의 rollout 순서를 확인한다.

## 핵심 확인

1. raw Storage와 파싱된 DB 조문을 둘 다 보존하는 이유는 무엇인가?
2. `abolished`와 `source_record_state=deleted`를 합치면 왜 안 되는가?
3. `corpus_unready`와 `insufficient_evidence`는 어떻게 다른가?

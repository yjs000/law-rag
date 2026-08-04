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
`effective_from <= as_of_date < effective_to`를 만족하는 버전의 조문만 포함한다.

운영 API는 UTC+9 한국 날짜의 오늘을 종료일로 사용한다. 지원 시작일은 오늘 이하인 수집 완료·현재
parser·검색 가능 버전의 `effective_from` 가운데 전역 최솟값이다. 이 값은 법률별 최초 시행일을 모두
복원한 결과도, 각 법률 timeline의 gap·overlap을 검사한 결과도 아니다. 현재 저장된 검색 가능 corpus에
적용하는 안전 경계다.

```text
지원 시작일 = MIN(검색 가능한 수집 버전.effective_from), 단 effective_from <= 한국 오늘
지원 종료일 = 한국 오늘

지원 시작일 <= as_of_date <= 지원 종료일
```

범위 밖 날짜는 일부 법령만 검색하지 않고 quota·임베딩·검색 전에 `422 unsupported_corpus_date`로
거부한다. 전체 검색 준비 게이트가 닫혔거나 오늘 유효한 조문이 0개이거나 시작일·content fingerprint를
완성할 수 없으면 `503 corpus_unready`다. 준비되지 않은 상태 API에서는 시작일과 snapshot ID가 `null`일
수 있다. 날짜를 생략한 요청은 서버 지역과 관계없이 한국 날짜의 오늘을 사용한다. 운영 검색은 API
경계에서 이 상태를 먼저 검사하고 실제 repository 검색 직전에 준비 상태를 다시 검사한다. 검색 SQL도
준비 gate를 요구한다. 코퍼스 반영 중에는 gate가 닫혀 있으므로 부분 결과 대신 `503 corpus_unready`로
재시도하게 한다.

runtime은 오늘 유효한 provision population의 count와 content fingerprint로 현재 snapshot ID를 만든다.
실험 D 평가 재현성은 이 오늘 값과 별도로, 질문의 서로 다른 모든 `as_of_date`와 각 날짜에 유효한 조문
집합의 count·content fingerprint를 함께 고정한다.

```text
저장된 전체 역사 버전
→ 기준일 효력 필터
→ 그 날짜의 eligible provision population
→ eligible count + content fingerprint
→ 고유 content population으로 snapshot ID 계산
```

content snapshot ID에는 달력 날짜를 넣지 않는다. 오늘과 내일 사이에 시행·개정·폐지 경계가 없고 유효
provision ID와 검색 콘텐츠가 같다면 같은 population이고 같은 ID다. 날짜를 버리는 것은 아니다. runtime
status는 그날의 동적 경계를 함께 반환하고, 실험 D gold는 `as_of_populations`에 날짜와
count·fingerprint 대응을 남긴다. gold dataset과 adjudication manifest의 canonical SHA-256도 그 대응을
다시 봉인하므로 같은 content snapshot ID를 쓰더라도 8월 3일 문항을 8월 4일 문항으로 몰래 바꾸면 gold
해시가 달라진다.

아직 시행되지 않은 미래 버전은 과거 날짜의 eligible population에 들어오지 않는다. 미래 버전을 수집하며
기존 버전의 `effective_to`가 `NULL`에서 미래 날짜로 바뀌어도, 그 종료일보다 앞선 기준일의 ID와 검색
콘텐츠는 그대로다. content fingerprint는 `effective_to` 자체를 내용 변경처럼 해시하지 않으므로 과거
snapshot도 유지된다. 반대로 예정 버전의 시행일을 지나거나 ID·본문·경로 등 검색 콘텐츠가 바뀌면
eligible population 지문이 바뀐다.

임베딩 모델·query/passage 유형·차원 축약·정규화·본문 템플릿은 retrieval contract다. 어느 벡터 공간에서
비교했는지를 재현하려면 반드시 따로 기록해야 하지만 원문 content snapshot ID에는 넣지 않는다. 같은
원문을 다른 임베딩 프로필로 평가한 것은 corpus 변경이 아니라 검색 설정 변경이다. 그래서 “저장된 모든
버전의 해시”, “특정 날짜의 eligible content fingerprint”, “embedding profile”을 서로 구분한다.

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

정기 갱신은 바로 DB에 쓰지 않는다. 스케줄러가 전체 허용 법률과 삭제 목록을 수집·파싱하고, 현재 DB와
비교한 결과를 먼저 로컬 bundle로 만든다.

```text
.data/corpus-updates/<update-id>/
├─ manifest.json      # 기준 snapshot, 계약 버전, 개수, 파일 SHA-256
├─ documents.jsonl    # 정규화한 문서·버전·ProvisionRecord
├─ deletions.json     # 출처 삭제 반영 목록
├─ raw/               # 공식 API 원문 바이트
└─ embeddings.jsonl   # 재사용했거나 새로 만든 512차원 벡터
```

manifest를 마지막에 만들기 때문에 중간에 멈춘 폴더를 완성 bundle로 오인하지 않는다. 준비 중에는 DB를
읽기만 하고 advisory lock, Storage write, DB write를 하지 않는다. 원문·삭제·벡터 변화가 없고 coverage도
정상이면 NIM 호출과 점검 중단 없이 그대로 끝난다.

여기서 게시 전용 기준 snapshot과 사용자가 보는 runtime content snapshot은 목적이 다르다. 게시 전용
snapshot은 오래된 bundle이 최신 DB를 덮어쓰지 못하게 `effective_to`, 법적·출처 상태, raw SHA와 조문
ordinal까지 writer 변경 조건을 넓게 묶는다. runtime content snapshot은 같은 검색 본문 집합을 식별하므로
날짜 자체를 넣지 않는다.

로컬 `embeddings.jsonl`은 새 벡터를 DB까지 옮기는 준비물이다. 웹/API는 이 파일을 검색하지 않고 DB의
활성 `provision_embeddings`만 읽는다. 기존 DB 벡터로 서비스하다가 gate를 닫고, transaction B에서 새
벡터를 DB에 넣고 검증·commit한 뒤에만 새 벡터가 사용자 검색에 사용된다.

## 왜 검색 준비 게이트가 두 개인가

원문과 벡터는 한 번에 바뀌지 않는다. 본문이 변경된 직후 예전 벡터가 남아 있으면 서로 다른 세대가
같은 검색 공간에 섞인다. 그래서 두 준비 상태를 구분한다.

- `corpus.search_ready`: direct path, keyword, dense, 단건 조문 조회를 모두 막는 모델 독립 상위 게이트
- `embedding_profiles.active`: 특정 임베딩 변환 계약의 전체 벡터가 준비됐다는 하위 게이트

변경이 있을 때 반영기는 먼저 작은 transaction A에서 `corpus.search_ready=false`를 commit한다. 새 검색은
즉시 닫히지만 이미 시작한 요청이 남을 수 있어 65초 기다린다. 그 뒤 transaction B 하나에서 모든 corpus
변경과 벡터를 적용하고 전체 coverage·입력 SHA·차원·norm을 검증한다. 마지막에 두 상태를 함께 열고 한
번만 commit한다.

```text
로컬에서 원문·조문·벡터 bundle 완성
→ transaction A: corpus gate 닫기
→ 65초 drain
→ transaction B: 조문·삭제·벡터 갱신
→ 전체 coverage·SHA·profile·norm 검사
→ profile 활성 + corpus gate 열기 + commit 1회
```

게이트가 닫힌 상태는 근거 부족이 아니다. 오늘 유효한 조문이 0개이거나 시작일·content identity를
완성하지 못한 상태도 마찬가지다. 검색 가능한 코퍼스를 검사하지 못했으므로 API는 빈 결과 대신
`503 corpus_unready`를 반환한다. `/v1/corpus/status`가 준비 여부와 닫힌 이유를 노출하며, 준비되지 않은
상태의 지원 시작일과 snapshot ID는 `null`일 수 있다.

## 잠금은 원자성과 역할이 다르다

PostgreSQL advisory lock은 writer끼리 순서를 맞춘다.

| 잠금 | 범위 | 목적 |
|---|---|---|
| embedding backfill lock | session | embedding writer가 겹치지 않게 함 |
| corpus sync run lock | session | corpus writer가 겹치지 않게 함 |
| corpus mutation lock | transaction | gate·corpus·vector 변경 순서를 보호함 |

lock은 상호 배제이고 transaction은 원자성이다. writer lock은 다른 writer가 끼어드는 일을 막지만 실패한
DB 변경을 되돌리지는 않는다. transaction B가 문서·삭제·벡터 전체를 하나로 묶기 때문에 중간 실패 시 B
전체가 rollback된다. 다만 transaction A에서 이미 닫은 gate는 남는다. 자동으로 옛 상태를 복구해 검색을
여는 기능은 추가하지 않고 원인을 고친 뒤 bundle을 다시 준비·반영한다.

운영 reader에는 shared advisory lock을 쓰지 않는다. gate를 닫고 최대 요청시간보다 긴 65초를 기다리는
점검 모드가 reader와 writer의 겹침을 피한다. 이 방식은 잠깐 서비스를 닫는 대신 구·신세대 테이블이나
active generation pointer를 만들지 않아 가벼운 프로젝트에 더 싸고 단순하다. 반면 실험 D는 한 평가 실행
내내 같은 corpus를 증명해야 하므로 그 평가 경로의 shared lock은 유지한다.

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

## 게시 전 검사는 왜 읽기 전용이어야 하는가

운영 코퍼스를 바꾸기 전에 알고 싶은 것은 “지금 게시해도 되는가”이지 “검사하면서 상태를 고치는가”가
아니다. 사전검사가 데이터를 고치면 검사 실패 자체가 운영 상태를 바꾸므로 원인과 결과를 분리하기
어렵다. 그래서 `preflight-current`는 다음 경계를 갖는다.

```text
DIRECT_URL session 연결
→ REPEATABLE READ, READ ONLY transaction
→ migration·gate·profile·vector coverage·snapshot SELECT
→ 결과 출력 후 종료
```

`REPEATABLE READ`는 한 번의 검사 안에서 서로 다른 SELECT가 같은 DB 시점을 보게 한다. `READ ONLY`는 그
transaction의 write를 PostgreSQL이 거부하게 한다. 짧은 statement·lock timeout은 막힌 검사가 운영 연결을
오래 점유하지 않게 한다. 이 검사는 advisory lock, NIM, Open API와 Storage를 사용하지 않는다.

성공의 뜻도 좁게 읽어야 한다. bundle 없이 통과했다면 현재 DB의 migration, ready gate, 활성 profile과
vector coverage가 그 검사 시점에 일치했다는 뜻이다. 새 bundle의 checksum이나 게시·rollback·검색 재개를
검증한 것이 아니며, lock을 잡지 않으므로 검사 직후 DB가 바뀌는 것까지 막지 않는다. 따라서 운영 증거에는
실행 시각, publisher snapshot, runtime snapshot과 bundle 유무를 함께 남긴다.

## 직접 확인

```powershell
uv run --project apps/collector law-rag-collector status
uv run --project apps/collector law-rag-collector preflight-current
uv run --directory apps/api python -m scripts.backfill_embeddings status
```

실제 수집·migration·벡터 적재는 운영 DB와 외부 API를 변경할 수 있다. 실행 전
[Open API 수집 계약](../design-docs/open-law-api-ingestion.md)과
[검색 인덱스와 임베딩 계보](../design-docs/retrieval-index-storage.md)의 rollout 순서를 확인한다.

## 핵심 확인

1. raw Storage와 파싱된 DB 조문을 둘 다 보존하는 이유는 무엇인가?
2. `abolished`와 `source_record_state=deleted`를 합치면 왜 안 되는가?
3. `corpus_unready`와 `insufficient_evidence`는 어떻게 다른가?

# Law RAG Collector

웹/API와 분리된 국가법령정보 공동활용 Open API 수집기다. JSON을 먼저 도메인 스키마까지 검증하고,
스키마가 맞지 않을 때만 같은 요청을 XML로 폴백한다. HTML·PDF·다른 법률 출처는 사용하지 않는다.

## 정기 운영 경로

저장소 루트에서 다음 세 명령을 같은 bundle 경로로 순서대로 실행한다.

```powershell
uv sync --all-packages
uv run --project apps/collector law-rag-collector prepare-current `
  --output .data/corpus-updates/20260804T030000Z
uv run --directory apps/api python -m scripts.backfill_embeddings generate-cache `
  --bundle .data/corpus-updates/20260804T030000Z
uv run --project apps/collector law-rag-collector apply-prepared `
  --bundle .data/corpus-updates/20260804T030000Z
```

`prepare-current`는 전체 고정 catalog와 공식 삭제 목록을 수집하고 기존 파서가 만든 조·항·호·목
`ProvisionRecord`를 그대로 사용한다. 검색 가능한 과거·현재·시행예정 버전 전체의 snapshot과 현재
PostgreSQL vector coverage를 읽기 전용으로 비교한다. 이 단계에서는 advisory lock, DB write와 Storage
upload를 하지 않는다. 준비 중 기준 corpus나 vector 상태가 바뀌면 manifest를 게시하지 않고 실패한다.

bundle은 다음 파일을 가진다.

```text
.data/corpus-updates/<update-id>/
├─ manifest.json
├─ documents.jsonl
├─ deletions.json
├─ raw/
└─ embeddings.jsonl  # generate-cache가 마지막에 추가
```

manifest에는 전체 검색 가능 corpus의 게시 전용 `base_snapshot_id`, parser·embedding profile, 문서·삭제·
필요 vector 변경 목록과 개수, 각 파일 SHA-256과 bundle SHA-256이 있다. 게시 전용 snapshot은 조문 본문뿐
아니라 `effective_to`, lifecycle·source 상태, raw SHA처럼 writer가 바꿀 수 있는 저장 필드도 포함한다.
다른 파일을 먼저 원자 기록하고 manifest를 마지막에 교체하므로 파일 누락·부분 기록·변조는 loader가
거부한다.

문서·삭제 변화가 없고 vector coverage도 정상이면 상태는 `unchanged`다. 이 경우 뒤 명령도 NIM·Storage·
writer lock·DB write 없이 종료한다. 변화가 있으면 상태는 `needs_embeddings`이고, `generate-cache --bundle`이
동일 ID·본문 SHA 또는 동일 본문 SHA의 기존 512차원 벡터를 재사용한다. 새 본문만 NVIDIA NIM에 보내며
완성된 `embeddings.jsonl`과 manifest 상태 `ready_to_publish`를 게시한다.

`apply-prepared`는 checksum과 고정 parser/NVIDIA profile을 검사하고 변경 raw를 SHA 기반 불변 Storage
경로에 올린다. 이어 기존 writer lock을 `EMBEDDING_BACKFILL → CORPUS_SYNC_RUN` 순서로 얻고 기준
snapshot과 prospective 전체 vector coverage를 다시 확인한다. 충돌·불일치·불완전 cache는 검색 gate를
닫기 전에 실패한다.

변경이 있으면 transaction A에서 `corpus.search_ready=false`를 commit하고 65초 drain한다. transaction B는
문서·버전·조문·삭제·벡터를 최대 100행씩 처리하되 전체를 한 번만 commit한다. 전체 parser·시간 범위·
본문 SHA·512차원·L2 norm·coverage를 검증한 마지막에만 profile과 gate를 함께 활성화한다. B가 실패하면
전체 DB 변경은 rollback되고 A의 gate=false는 남는다.

로컬 `embeddings.jsonl`은 점검 반영 전의 운반 파일일 뿐 검색 저장소가 아니다. 운영 웹/API는 이 파일이나
로컬 cache를 열지 않고 활성 profile의 PostgreSQL `provision_embeddings`만 검색한다. 기존 DB 벡터는 gate를
닫기 전까지 계속 서비스되고, 새 로컬 벡터는 transaction B가 DB에 복사·검증·commit한 뒤에만 검색된다.

## 환경변수

- `LAW_OPEN_API_OC`: `prepare-current`의 국가법령정보 API 인증값
- `DIRECT_URL`: PostgreSQL session 연결 URL; transaction pooler URL을 사용하지 않음
- `SUPABASE_URL`, `SUPABASE_SECRET_KEY`: private raw Storage 접근
- `NVIDIA_API_KEY`: `generate-cache`가 실제 새 본문을 임베딩할 때만 사용

비밀값은 OS·GitHub Actions secret 또는 로컬 `.env.local`에만 둔다. 명령행, Git, 로그에 기록하지 않는다.
`SUPABASE_SECRET_KEY`는 `sb_secret_` 형식이어야 한다.

## 예약 실행

`.github/workflows/sync-corpus.yml`은 self-hosted Windows runner에서 매일 03:00 KST와 수동 실행을 지원한다.
기존 `legal-corpus-sync` concurrency group이 workflow 중복을 막고 다음 순서를 고정한다.

1. `prepare-current --output <run 전용 bundle>`
2. `generate-cache --bundle <같은 bundle>`
3. `apply-prepared --bundle <같은 bundle>`

Open API에 등록한 고정 공인 출구 IP를 사용하는 runner에서만 실행한다. 외부 API·NIM·Storage 호출과 65초
대기는 transaction B 밖에서 실행된다.

## 실패 복구

1. 준비·NIM·Storage·writer lock·기준 snapshot 실패는 gate 변경 전이므로 기존 검색이 계속된다.
2. gate를 닫은 뒤 실패하면 Tx B는 전부 rollback되고 `reason=corpus_publish`인 gate=false가 남는다.
3. update ID와 실패 단계만 확인하고 원문 전문이나 비밀값을 로그에 남기지 않는다.
4. 원인을 수정한 뒤 새 bundle을 준비하거나 아직 유효한 ready bundle을 다시 적용한다. gate=false에서도
   복구 bundle 준비와 적용이 가능하다.
5. gate나 profile을 수동 활성화하지 않는다. 전체 검증에 성공한 publisher만 검색을 연다.

DB transaction 전에 업로드된 불변 raw가 고아 객체로 남을 수 있으나 즉시 삭제하지 않는다.

## 기존 명령

`preview-current`, `sync-current`, `sync-history`, `status`와 embedding의 기존 `run`, `load-cache`는 호환성과
진단을 위해 당장 삭제하지 않는다. 정기 workflow에서는 사용하지 않으며 운영 반영 진입점은
`apply-prepared` 하나다. Supabase 전체 과거 본문 수집은 아직 활성화하지 않아 Supabase에서
`sync-history`는 종료 코드 2를 반환한다. 공식 삭제 목록은 prepared bundle과 레거시 `sync-current`에
포함된다.

```powershell
uv run --project apps/collector law-rag-collector preview-current
uv run --project apps/collector law-rag-collector sync-current
uv run --project apps/collector law-rag-collector status
```

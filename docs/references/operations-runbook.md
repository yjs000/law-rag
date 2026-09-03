# 코퍼스 운영·롤백 런북

최종 갱신: 2026-09-03

## 에이전트 빠른 명령 색인

법률 수집, 임베딩, migration, `corpus_unready`, `v2_search_not_ready` 또는 active generation을 다루는
에이전트는 소스 코드를 다시 검색하기 전에 이 절을 먼저 사용한다. 모든 명령은 **저장소 루트**에서
실행한다.

아래에서 `DB write` 또는 `외부 호출`로 표시한 명령은 운영 데이터와 외부 API 비용에 영향을 줄 수
있으므로 사용자 승인을 받은 뒤 실행한다. 비밀값은 `.env.local` 또는 프로세스 환경에서 읽고 명령줄,
로그와 문서에 출력하지 않는다.

| 목적 | 명령 | 영향 |
|---|---|---|
| 전체 로컬 검증 | `pnpm.cmd verify` | 로컬 읽기·테스트 산출물 |
| DB migration 상태 확인 | `uv run --directory apps/api alembic current` | DB read |
| 누락 migration 적용 | `uv run --directory apps/api alembic upgrade head` | DB write |
| 법률 수집과 기존 corpus 임베딩 갱신 | `powershell -ExecutionPolicy Bypass -File apps/collector/ops/Sync-Corpus.ps1` | 외부 법령 API·NVIDIA 호출, DB·Storage write |
| V2 LlamaIndex generation 생성·검증·활성화 | `uv run --directory apps/law-rag-llamaindex python -m law_rag_llamaindex.ingest` | NVIDIA 호출, DB write |
| 공개 corpus 상태 확인 | `Invoke-RestMethod https://law-rag-api-opal.vercel.app/v1/corpus/status` | 운영 API read |

### 전체 법령·검색 갱신 순서

최신 법률 원문부터 V2 검색 활성화까지 갱신할 때는 다음 두 명령을 순서대로 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File apps/collector/ops/Sync-Corpus.ps1
uv run --directory apps/law-rag-llamaindex python -m law_rag_llamaindex.ingest
```

첫 번째 명령은 `prepare-current → generate-cache --bundle → apply-prepared`를 묶어 공식 원문과 기존
corpus 임베딩을 갱신한다. 두 번째 명령은 그 결과로 새 V2 immutable generation을 만들고 전체 검증을
통과한 뒤 active pointer를 전환한다. `Sync-Corpus.ps1`만 실행하면 V2 active generation은 생성되지
않는다.

필수 설정은 다음과 같다. 값 자체는 이 문서에 기록하지 않는다.

- corpus 갱신: `LAW_OPEN_API_OC`, `DIRECT_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
  `NVIDIA_API_KEY`
- V2 generation: `DATABASE_URL` 또는 fallback `DIRECT_URL`, `NVIDIA_API_KEY`와 해당 embedding 설정.
  저장소 루트의 `.env`와 `.env.local`은 실행 위치와 무관하게 자동으로 읽는다.
- 국가법령정보 호출: 등록된 고정 공인 출구 IP 머신에서 실행

## 정상 실행

1. 저장소 루트에서 `pnpm.cmd verify`를 실행한다.
2. `LAW_OPEN_API_OC`는 OS 비밀 저장소나 현재 프로세스 환경변수로만 주입한다.
3. 자동 예약 실행은 없다. `law-rag-ingestion` self-hosted GitHub Actions runner로 자동화하려던 초기
   계획은 2026-07-13에 폐기됐고(등록 러너가 존재한 적 없음), 대체안이었던 Windows Task Scheduler도
   등록된 적이 없다 - [기술 스택 결정 기록](../design-docs/technology-stack.md) 참고. 지금까지의 모든
   반영은 등록된 고정 공인 출구 IP 머신에서 사람 또는 에이전트가 아래 순서를 그 자리에서 수동 실행해
   왔다.
4. `/v1/corpus/status`에서 9개 대상, 현재 snapshot, 지원 날짜와 `corpus_search_ready`를 확인한다.
5. DB schema가 저장소 head인지 확인하고 누락 migration이 있으면 API 코드보다 먼저 적용한다. Preview와
   Production에는 `NVIDIA_API_KEY`와 현재 embedding 설정을 환경별로 등록한다.

## 수동 준비와 점검 반영

- `prepare-current`가 JSON 우선/XML 폴백 정규화, 정확 명칭, 버전 키, 조문과 삭제 목록을 로컬 bundle로
  준비한다. 이 단계는 DB lock·DB write·Storage write를 하지 않는다.
- 변화가 없고 vector coverage가 정상이면 NIM과 반영 단계를 생략하고 서비스도 닫지 않는다.
- 변화가 있으면 `generate-cache --bundle`이 기존 SHA 벡터를 재사용하고 변경 본문만 임베딩한다.
- `apply-prepared`는 원문 업로드와 gate 변경 전 검사를 마친 뒤 gate를 닫고 65초 기다린다. 이후
  `DIRECT_URL` session 연결의 단일 transaction으로 변경과 검증을 반영하고 성공할 때만 검색을 연다.
- 실패하면 반영 transaction은 rollback되며 검색은 닫힌 상태로 남는다. gate를 수동으로 열지 말고 원인을
  고친 뒤 새 bundle을 준비·반영한다.

## 장애 대응

| 증상 | 확인 | 대응 |
|---|---|---|
| 401/403 또는 사용자 검증 실패 | 등록된 고정 공인 출구 IP와 OC | 재시도 반복 금지, 등록 정보 수정 후 한 문서 smoke |
| 429/5xx/timeout | 준비 단계의 실행 상태와 재시도 소진 | gate가 열려 있으면 기존 코퍼스 유지, 다음 예약 또는 수동 재실행 |
| 정규화 실패 | 포맷·폴백 사유·대상 MST | HTML로 우회하지 않고 fixture와 파서를 먼저 갱신 |
| AI quota/모델 오류 | execution issue와 단계별 reason code | 다른 모델이나 검색 경로로 임의 전환하지 않고 현재 fail-closed 계약 유지 |
| NVIDIA 임베딩 오류 | bundle 상태와 profile·key·quota | gate를 닫기 전 실패하므로 기존 검색 유지, 원인 수정 후 재준비 |
| `corpus_unready` + `corpus_publish` | update ID와 workflow 실패 단계 | 원인 수정 후 bundle을 다시 준비·반영; gate 수동 활성화 금지 |
| 기준 snapshot 불일치·writer lock 충돌 | prepare/apply 실행 ID | gate를 닫지 않고 종료되므로 충돌 writer 종료 뒤 새 bundle 준비 |
| API 재시작 | 목업 로그인·질문 이력 | 목업 데이터 소실을 허용하며 운영 전 Supabase로 교체 |

## 롤백

- 코드: 직전 검증 커밋으로 새 배포를 만들며 원격 DB 파괴 명령은 실행하지 않는다.
- 코퍼스: 준비 실패는 DB를 바꾸지 않는다. 반영 실패는 transaction B 전체를 rollback하고 gate=false를
  유지한다. 자동 rollback이나 구세대 전환 대신 원인을 수정한 새 bundle을 다시 적용한다.
- AI: 다른 provider로 임의 전환하지 않는다. 검증 전 생성 내용은 공개하지 않고 단계별 실패 원인을
  확인한 뒤 같은 계약으로 복구한다.
- 인증: Production은 Supabase Google OAuth를 사용한다. 장애 시 mock 인증을 Production에 활성화하지
  않고 OAuth 설정과 callback allowlist를 복구한다.

## 비밀과 로그

- `.env`, OC, NVIDIA/OpenAI 키, Supabase secret key를 이슈·로그·Git에 남기지 않는다.
- 질문 원문, 이메일, IP 원문, 법령 원문 전문을 관측 이벤트에 남기지 않는다.
- 문제 보고에는 요청 ID, 실행 ID, 대상의 비민감 안정 ID, 오류 분류만 포함한다.

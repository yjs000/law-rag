# 코퍼스 운영·롤백 런북

최종 갱신: 2026-08-04

## 정상 실행

1. 저장소 루트에서 `pnpm.cmd verify`를 실행한다.
2. `LAW_OPEN_API_OC`는 OS 비밀 저장소나 현재 프로세스 환경변수로만 주입한다.
3. `sync-corpus` workflow는 일 1회 03:00 KST와 수동 실행만 허용하고 기존 concurrency group으로 겹친
   예약 실행을 직렬화한다.
4. `/v1/corpus/status`에서 9개 대상, 현재 snapshot, 지원 날짜와 `corpus_search_ready`를 확인한다.
5. NVIDIA 임베딩 검색을 배포할 때는 API 코드보다 먼저 migration `0007`을 적용하고, Preview와
   Production에 `NVIDIA_API_KEY`, `NVIDIA_EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`,
   `EMBEDDING_TIMEOUT_SECONDS`를 환경별로 등록한다.

## 일일 준비와 점검 반영

- 기본 일정은 매일 03:00 KST다.
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
| AI quota/모델 오류 | 응답 mode와 관측 이벤트 | 다른 모델로 전환하지 않고 검색 전용 유지 |
| NVIDIA 임베딩 오류 | bundle 상태와 profile·key·quota | gate를 닫기 전 실패하므로 기존 검색 유지, 원인 수정 후 재준비 |
| `corpus_unready` + `corpus_publish` | update ID와 workflow 실패 단계 | 원인 수정 후 bundle을 다시 준비·반영; gate 수동 활성화 금지 |
| 기준 snapshot 불일치·writer lock 충돌 | prepare/apply 실행 ID | gate를 닫지 않고 종료되므로 충돌 writer 종료 뒤 새 bundle 준비 |
| API 재시작 | 목업 로그인·질문 이력 | 목업 데이터 소실을 허용하며 운영 전 Supabase로 교체 |

## 롤백

- 코드: 직전 검증 커밋으로 새 배포를 만들며 원격 DB 파괴 명령은 실행하지 않는다.
- 코퍼스: 준비 실패는 DB를 바꾸지 않는다. 반영 실패는 transaction B 전체를 rollback하고 gate=false를
  유지한다. 자동 rollback이나 구세대 전환 대신 원인을 수정한 새 bundle을 다시 적용한다.
- AI: `AI_MODE=off`로 검색 전용 모드로 전환한다.
- 인증: 목업 인증은 production 환경에서 404이며 실제 OAuth 연결 전 공개 로그인 기능을 열지 않는다.

## 비밀과 로그

- `.env`, OC, NVIDIA/OpenAI 키, Supabase secret key를 이슈·로그·Git에 남기지 않는다.
- 질문 원문, 이메일, IP 원문, 법령 원문 전문을 관측 이벤트에 남기지 않는다.
- 문제 보고에는 요청 ID, 실행 ID, 대상의 비민감 안정 ID, 오류 분류만 포함한다.

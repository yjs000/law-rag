# 에너지 법령 RAG 아키텍처

상태: `MVP 구현 중`
최종 갱신: 2026-08-04

## 목적

일반 사용자가 에너지 사업 규제를 질문하면 국가법령정보 공동활용 Open API 원문만으로 기준일에 유효한 의무·예외·인허가를 설명한다. 답변의 실질 주장은 조·항·호·목 인용으로 검증되며, 검증 실패나 AI 쿼터 소진 시 원문 검색만 제공한다.

## 배포와 데이터 흐름

```text
고정 공인 IP Windows PC의 collector ── JSON 우선/XML 폴백 ──> 국가법령정보 Open API
       │                         │
       │                         └─ HTML·PDF·외부 법률 사이트 금지
       └─ OS 스케줄러 ──> 정규화/해시/버전 ──> Supabase DB + private Storage
                                                  │ PGroonga + pgvector
                                                  v
Browser ──> Vercel Next.js ── 동일 출처 /api 프록시 ──> Vercel FastAPI
                                                        ├─ Supabase 검색·Auth·Storage
                                                        └─ NVIDIA hosted NIM 또는 OpenAI + Structured Outputs
```

Web과 stateless FastAPI는 Vercel, 영속 상태는 Supabase에 배치한다. collector는 국가법령정보 Open API에 등록된 고정 공인 IPv4 Windows PC에서 실행하고 검증된 현재 버전을 Supabase private Storage와 PostgreSQL에 반영한다. 로컬 파일 저장소는 외부 자격정보가 없는 개발·테스트 fallback이다. 집 PC는 공개 인바운드 요청을 받지 않는다. API는 Python 3.14 런타임, 웹은 Node 24/pnpm 11을 사용한다. Supabase DB 연결 시에는 Supavisor transaction pooler를 전제로 prepared statement cache를 끈다.

Python 실행 단위는 같은 저장소 안에서 두 프로젝트로 분리한다.

- `apps/api`: 질문·검색·인증·내보내기 API를 제공하며 운영에서는 stateless Vercel Function으로 실행
- `apps/collector`: 국가법령정보 수집 전용 CLI/배치 프로젝트. API와 독립적으로 고정 공인 IP Windows PC의 OS 스케줄러가 실행

공유 도메인 타입과 파서는 인프라 실행 단위에 종속되지 않는 공용 패키지로 추출한다. `apps/web`은 기존 프런트엔드 프로젝트이며 위의 두 Python 실행 단위 구분에 포함하지 않는다.

## 모듈 경계

의존성은 `domain -> application -> ports <- adapters -> delivery` 방향이다.

- `domain`: 법령 버전, 조문, 공개 API 계약과 순수 검증 규칙
- `application`: 수집, 검색, 답변 조립, 인용 검증 유스케이스
- `ports`: 법령 저장소·임베딩·답변 모델·원문 저장소 계약
- `adapters`: 국가법령 API, Supabase/PostgreSQL/Storage, NVIDIA NIM 등 외부 생성·임베딩 provider 구현
- `delivery`: FastAPI 엔드포인트, collector CLI·OS 스케줄러, Next.js 워크벤치

도메인 계층은 FastAPI, SQLAlchemy, OpenAI SDK를 import하지 않는다. 브라우저는 OpenAI와 Supabase service role에 직접 접근하지 않는다.

## 수집 계약

MVP는 정확 명칭 허용 목록 9개만 수집한다. 법령은 `eflaw`, 행정규칙은 `admrul&nw=1`을 사용한다.

1. 같은 요청을 `type=JSON`으로 호출한다.
2. JSON 문법뿐 아니라 법령명, ID/MST, 조문 구조를 도메인 객체까지 정규화한다.
3. 지원되지 않는 형식 또는 스키마 검증 실패 때만 `type=XML`로 재호출한다.
4. timeout/5xx는 같은 포맷으로 지수 백오프 재시도한 뒤 실패시킨다. 일시 장애를 XML 폴백으로 감추지 않는다.
5. JSON/XML은 같은 `LegalDocumentRecord`가 되어야 하며 포맷, SHA-256, 파서 버전, 폴백 사유를 기록한다.
6. 원문은 Supabase Storage에 보존한다. HTML과 PDF로 우회하지 않는다.

## 저장과 검색

- `legal_documents`: 안정적인 출처 ID와 정확 명칭
- `document_versions`: `안정 ID + MST + 시행일` 버전 키, 공포/시행/종료일, 원문 포맷·해시·경로
- `provisions`: 조·항·호·목 경로와 원문
- `embedding_profiles`, `provision_embeddings`: 제공자·모델·입력 유형·축약·정규화·본문 템플릿 계약과 그 프로필로 만든 차원 가변 벡터
- `corpus_snapshots`, `retrieval_profiles`, `retrieval_index_builds`: 코퍼스 세대와 dense·lexical 등 독립 검색기의 설정·구축 계보
- `retrieval_configurations`, `retrieval_releases`: 검색기 구성과 특정 snapshot/build 조합을 고정한 배포 단위 및 활성 포인터
- `legal_relationships`: 상하위법·위임·인용 관계
- `derived_obligations`: 행위자·조건·의무 유형과 검증 상태
- `ingestion_runs`, `evaluation_runs`, `runtime_flags`: 운영·평가 상태와 dataset·code·corpus·retrieval release 계보

검색은 먼저 corpus 전체 준비 게이트와 동적으로 계산한 기준일 지원 범위를 검사한 뒤 기준일 유효 버전을 제한한다. 지원 시작일은 오늘 이하인 수집 완료·현재 parser·검색 가능 버전의 `effective_from` 전역 최솟값이고, 지원 종료일은 UTC+9 한국 날짜의 오늘이며 양끝을 포함한다. 이는 저장된 버전 전체의 법률별 연속성·중복 여부를 검증한 공통 timeline이라는 뜻이 아니다. 오늘 유효한 provision population의 개수와 검색 콘텐츠 지문으로 `corpus-sha256:*` ID를 계산하며, 달력 날짜·`effective_to`·임베딩 프로필은 content ID 입력에 넣지 않는다. 따라서 시행·개정·폐지 경계와 검색 콘텐츠 변경이 없으면 날짜가 지나도 같은 ID를 유지한다.

전체 검색 준비 게이트가 닫혔거나 오늘 유효한 provision이 0개이거나 시간 identity를 완성할 수 없으면 검색 엔드포인트는 HTTP `503`, 코드 `corpus_unready`로 닫힌다. 준비되지 않은 `/v1/corpus/status`에서는 지원 시작일과 snapshot ID가 `null`일 수 있다. 준비된 범위 밖 날짜는 일부 문서만 남은 결과를 근거 부족처럼 반환하지 않고 quota·임베딩·저장소 검색 전에 HTTP `422`, 코드 `unsupported_corpus_date`로 거부한다. PostgreSQL 실제 검색은 새 연결의 첫 문장으로 corpus mutation 공유 advisory transaction lock을 얻은 뒤 현재 범위를 다시 계산한다. 최초 검사 뒤 corpus 세대가 교체돼 요청일이 새 범위를 벗어나면 검색하지 않고 `503 corpus_unready` 재시도로 닫으며, 같은 잠금이 검색 종료까지 writer와 세대 전환을 막는다. `/v1/corpus/status`는 이때 계산된 `corpus_snapshot_id`, `supported_as_of_from`, `supported_as_of_through`, 준비 상태와 사유를 노출한다. 요청에서 날짜를 생략하면 API는 서버 시간대가 아니라 한국 날짜의 오늘을 사용한다.

법률명·조문 경로를 명시한 질문은 direct-path로 조회한다. 일반 질문은 query embedding이 준비됐을 때 pgvector dense-only 검색을 실행하고, 후보가 있으면 그 dense 순위만 반환한다. 운영 dense와 실험 D는 기준일 유효 population을 먼저 `MATERIALIZED`한 exhaustive exact cosine을 사용한다. HNSW는 현재와 미래의 검색·평가 경로에서 사용하지 않으며 새 인덱스·build·release도 만들지 않는다. dense 결과가 0건이거나 embedding 경로가 없을 때에만 PGroonga 4단계 keyword 검색을 독립 fallback으로 실행한다. dense와 keyword 점수는 합치지 않으며 hybrid와 RRF는 현재 검색 경로에 없다.

의미 검색은 질의와 저장 벡터의 profile key가 같을 때만 실행한다. 현재 임베딩 provider는 NVIDIA hosted NIM의 `nvidia/nemotron-3-embed-1b`이며 native 2048차원의 첫 512개를 L2 재정규화해 저장한다. production 응답은 같은 조의 하위 조각을 조 단위로 묶을 수 있지만, 실험 D의 검색 평가는 qrels와 같은 raw `provision_id` 단위를 사용하고 direct-path, keyword fallback, 조 단위 grouping을 우회한다.

## 답변 안전 게이트

1. 질문의 기준일이 현재 corpus 지원 범위 안인지와 사업 단계를 검증한다.
2. direct-path 또는 dense-only 검색으로 근거 후보를 구성하고, dense가 0건일 때만 독립 keyword fallback을 사용한다.
3. provider adapter의 JSON schema 출력으로 답변·체크리스트·인용 ID를 받는다.
4. 모든 실질 주장과 체크리스트에 존재하는 인용 ID가 있는지 검사한다.
5. 선택된 생성 provider 실패, quota 402/429, 권한 오류, AI 비활성 시 다른 생성 모델로 자동 전환하지 않고 검색 전용 응답으로 전환한다.

현재 인용 게이트는 인용 ID 존재와 원문 반환을 보장한다. 주장-원문 의미 일치 자동평가와 법령 관계 확장은 다음 품질 게이트다.

## 실험 D 검색 평가 게이트

정답이 없는 일반 사용자 질문은행은 질문 문구·범위 검토용 중간 산출물이다. 실제 검색 지표는 사용자가 질문을 승인한 뒤 공식 원문을 독립 검토해 qrels, reference contexts와 reference response를 붙이고 `approved_gold`로 확정한 자료에서만 계산한다. 질문 승인은 질문 문구·범위만 고정하며, 별도 gold adjudication manifest가 전체 dataset과 문항별 완성 payload의 canonical SHA-256을 다시 봉인한다. 시간 순서는 모든 문항에서 `질문 승인 < 독립 annotation review < gold adjudication`이어야 한다. 2026-08-04 일반 사용자 질문 1,000개의 문구·범위 승인은 완료했지만 독립 gold 주석과 실제 검색 평가는 아직 실행하지 않았다.

승인된 gold runner는 다음 순서를 강제한다.

1. dataset, 질문은행, 질문 승인 manifest, gold adjudication manifest와 critical code provenance를 검증한다.
2. 초기 `REPEATABLE READ, READ ONLY` transaction에서 지원 기준일·corpus·벡터 상태와 gold preflight를 통과하기 전에는 질문을 임베딩하지 않는다.
3. 질문 임베딩 뒤 별도 `READ COMMITTED, READ ONLY` transaction의 첫 snapshot-taking statement로 PostgreSQL corpus mutation 공유 advisory lock을 얻는다.
4. 같은 연결과 잠금 transaction 안에서 전체 검색 가능 corpus와 문항별 기준일 유효 population, qrels·distractor·후보 pool, 벡터 profile·coverage·L2 norm과 transaction·planner 설정을 다시 검증한다.
5. 기준일별 대표 query의 `EXPLAIN` plan과 plan SHA-256을 검색 전에 기록한다. 실험 D primary dense baseline은 기준일 유효 population 전체를 `MATERIALIZED`한 뒤 모두 비교하는 exhaustive exact cosine만 사용한다. 통과한 경우에만 모든 질문을 raw provision exact cosine 검색으로 11개까지 조회하며, 10위와 11위의 raw cosine 점수가 같으면 top 10 경계를 임의로 자르지 않고 실행을 실패시킨다. HNSW identity·상태·결과 비교는 이 runner의 입력이나 결과에 포함하지 않는다.
6. 같은 공유 lock을 마지막 검색까지 유지한 뒤에만 지표를 계산한다. 결과에는 입력·질문·corpus·벡터·query plan·임베딩 batch 크기·PostgreSQL/pgvector 버전과 검색 설정·critical code commit 및 파일 해시를 기록한다.
7. 전체 실행이 성공한 경우에만 새 run JSON을 임시 파일에서 원자적으로 게시한다. 기존 run을 덮어쓰지 않으며 실패 시 완성 결과 파일을 만들지 않는다.

annotation pool은 방법별 설정 해시와 정확한 `top_k`, 실제 후보 ID와 후보 집합 해시를 보존한다. 비전체검사 방법은 후보 수가 `min(top_k, 기준 corpus 크기)`와 정확히 같아야 하고, 방법별 후보의 합집합은 문항별 판정 pool과 정확히 같아야 한다. `full_corpus_manual_review` 방법을 선언하면 그 후보 집합은 해당 문항 기준일에 유효한 전체 검색 가능 provision 집합과 정확히 같아야 한다.

핵심 검색 평균의 primary 모집단은 조정에 쓰지 않은 `test` split의 `fully_answerable` 문항이다. grade 2 직접 qrels를 기준으로 Recall@1/3/5/10, HitRate@1/3/5/10, Direct Precision@5와 MRR@10을 계산하고, Precision@5는 grade 1 보조 문맥과 grade 2 직접 근거를 모두 센다. nDCG@1/3/5/10은 두 등급의 차이를 반영한다. 넓은 질문에는 supported 필수 요소의 `facet_recall`과 `all_required_facets_covered`를 함께 계산한다. primary 집계는 scenario-family macro이며 family를 단위로 결정적 bootstrap 2,000회의 95% 신뢰구간을 계산한다. calibration과 calibration+test 결합값은 diagnostic-only이고 partial·clarification·unanswerable도 core 평균과 분리한다.

## 공개 API

- `POST /v1/questions`
- `POST /v1/search`
- `GET /v1/provisions/{id}`
- `GET /v1/documents/{id}/changes`
- `GET /v1/corpus/status`
- `GET /health`

연혁 본문 경로가 XML/JSON 계약 테스트를 통과하기 전 변경 API는 `supported=false`를 반환한다. HTML로 기능을 가장하지 않는다.

`POST /v1/questions`, `POST /v1/search`, `GET /v1/provisions/{id}`는 현재 corpus가 준비되지 않았으면 `503 corpus_unready`로 닫고, 동적 지원 범위 밖 `as_of_date`는 quota·provider·실제 검색 호출 전에 같은 `422 unsupported_corpus_date` 계약으로 차단한다. 날짜 기본값은 UTC+9 한국 날짜의 오늘이다.

## 운영 원칙

- 키는 저장소에 커밋하지 않고 Vercel·Supabase 환경 설정 또는 collector PC의 OS 비밀 저장소에 둔다.
- 질문 원문, IP, 원문 전문을 로그에 남기지 않는다.
- AI 장애와 검색 장애를 분리한다.
- 법제처에 등록한 고정 공인 IPv4 Windows PC에서 `apps/collector`를 별도 프로세스로 실행한다. Vercel, 공용 runner와 브라우저에서 법령 API를 직접 호출하지 않으며 collector PC에 포트포워딩이나 공개 API를 열지 않는다.
- 현재 버전 collector와 Vercel API, Google 인증과 사용자 질문 이력은 Supabase에 연결되어 있다. 연혁·삭제 격리와 영속 운영 플래그는 후속 단계다.
- 익명 질문은 저장하지 않는다. 운영 로그인은 Supabase Google OAuth만 지원하며 질문 이력은 PostgreSQL에 생성일부터 1년 보존 후 삭제한다. 계정 삭제 시 질문·이력·세션·내보내기·동의 등 해당 사용자와 연결된 데이터를 삭제한다. 개발·테스트의 목업 인증은 production에서 비활성화한다.
- 공개 서비스의 rate limit HMAC 저장과 승인 gold 기반 Recall·HitRate·Precision·MRR@10·nDCG·facet 회귀 게이트는 배포 전 필수 잔여 작업이다. 임계값은 calibration 결과를 보기 전에 임의로 확정하지 않는다.

## 결정 기록

| 날짜 | 결정 | 이유 |
|---|---|---|
| 2026-07-13 | 국가법령정보 Open API만 법률 코퍼스로 사용 | 출처와 버전 추적을 단순하고 검증 가능하게 유지 |
| 2026-07-13 | JSON 우선, 정규화 실패 시 XML 폴백 | 전송 효율과 개발 편의성을 얻되 XML 호환성을 보존 |
| 2026-07-13 | 초기안: Next.js/FastAPI/Supabase/Vercel/GitHub Actions(단일 클라우드 서버 결정으로 배포안 대체) | 무료 우선 공개 MVP와 학습 목적에 적합 |
| 2026-07-13 | OpenAI를 포트 뒤에 배치하고 검색 전용 폴백 제공 | AI 비용·장애가 원문 조회를 중단하지 않게 함 |
| 2026-07-13 | 초기안: 법령 수집에 고정 출구 IP의 self-hosted runner 사용(아래 OS 스케줄러 결정으로 대체) | Open API가 등록 IP/도메인을 검증하며 공용 runner 출구 IP는 고정되지 않음 |
| 2026-07-13 | Terra 오류 시 대체 생성 모델 없이 검색 전용 모드 사용 | 모델 변경으로 검증되지 않은 품질 차이가 숨겨지는 것을 방지 |
| 2026-07-13 | Python 실행 단위를 API와 collector 두 프로젝트로 분리 | 웹 요청과 장시간·예약 수집의 장애 및 배포 수명주기를 분리 |
| 2026-07-13 | Supabase·Vercel·로그인은 목업 우선 | 외부 자격정보 없이 제품 흐름과 계약을 먼저 검증 |
| 2026-07-15 | Google OAuth는 Supabase Auth PKCE, API 인증은 Supabase 사용자 검증 | 브라우저에 secret을 노출하지 않고 실제 질문 이력을 사용자별로 저장 |
| 2026-07-13 | 실제 로그인은 Google만 지원 | 초기 인증 선택지와 계정 연결 복잡도를 최소화 |
| 2026-07-13 | 질문 이력 1년 보존, 계정 삭제 시 사용자 관련 데이터 전부 삭제 | 사용자 통제권과 개인정보 최소 보존 원칙 적용 |
| 2026-07-13 | 웹·API·collector를 같은 클라우드 서버의 독립 프로세스로 배치 | 고정 공인 IP와 초기 운영 단순성을 함께 확보 |
| 2026-07-14 | 주 1회 수집하고 검증된 문서 변경을 즉시 활성 코퍼스에 반영 | 최신성 지연을 줄이면서 문서 단위 실패 격리와 원자 승격을 유지 |
| 2026-07-14 | Open API `delHst`를 법적 폐지가 아닌 출처 레코드 가용성으로 관리 | 삭제 응답에 폐지 여부·삭제 사유가 없으므로 법적 효력 종료를 추론하지 않기 위함 |
| 2026-07-14 | collector 로컬 설정은 `.env` 후 `.env.local`을 읽고 프로세스 환경변수를 최우선 적용 | 개발 비밀값을 커밋하지 않으면서 실행 시 명시적으로 재사용 |
| 2026-07-14 | 위 단일 서버 배치를 Vercel Web/FastAPI + Supabase + 고정 공인 IP Windows collector로 대체 | 공개 서버 운영 부담과 Open API 고정 IP 제약을 분리하고 API를 stateless하게 운영 |
| 2026-07-14 | Preview Web은 Next.js 상대 `/api/*` 동일 출처 프록시 사용 | 가변 Preview origin을 FastAPI CORS wildcard로 허용하지 않고 환경 경계를 유지 |
| 2026-07-14 | 질문 요청에서 Terra 또는 검색 전용을 명시적으로 선택 | 사용자가 생성 모델 호출 여부를 통제하면서 Terra 단일 모델·안전 폴백 계약을 유지 |
| 2026-07-15 | collector `sync-current`는 검증된 원문을 content-addressed private Storage에 먼저 보존하고 DB 문서·버전·조문을 트랜잭션 반영 | 원문 계보와 재실행 멱등성을 유지하면서 Vercel API가 같은 Supabase 코퍼스를 읽게 함 |
| 2026-07-19 | 생성 기본 후보를 NVIDIA hosted Nemotron 3 Ultra로 변경하고 기존 `terra` wire 값은 호환용으로 유지 | 로컬 PC 공개 없이 Vercel outbound 호출이 가능하며 provider 변경 중 기존 클라이언트 호환을 보존 |
| 2026-07-23 | 임베딩 provider를 NVIDIA hosted Nemotron 3 Embed 1B로 교체하고 검색 시 모델 ID를 필터링 | 한국어 hosted 실험과 기존 512차원 계약을 유지하면서 OpenAI·NVIDIA 벡터 공간 혼합을 방지 |
| 2026-08-03 | 실험 D primary dense baseline을 exhaustive exact cosine으로 고정 | 근사화 변수를 현재와 미래의 품질 판정에서 영구 배제하고 근거 찾기 자체의 재현성을 유지 |
| 2026-08-03 | [대체됨] HNSW 설계·평가를 gold 1,000문항과 근거 찾기 전수 검증 이후의 별도 승인 단계로 보류 | 당시에는 근거 찾기와 근사 인덱스 중 무엇을 측정했는지 구분하기 위해 보류했으나, 2026-08-04 영구 제외 결정으로 대체됨 |
| 2026-08-04 | HNSW를 현재와 미래의 제품·실험 경로에서 영구 제외하고 exhaustive exact cosine을 유지 | 근사 인덱스 도입으로 품질 판정과 운영 복잡도를 다시 늘리지 않기로 한 사용자 결정. 2026-08-03의 “검증 후 재검토” 결정을 대체하며, 기존 물리 인덱스는 사용·재구축·튜닝·평가·release 연결하지 않는 역사적 잔여물로만 남김 |
| 2026-08-03 | [대체됨] 당시 감사한 corpus 지원 기준일을 `2026-06-03..2026-08-03` 양끝 포함으로 고정하고 범위 밖 요청을 `422`로 거부 | 당시 9개 open version과 3,066개 조문을 기준으로 한 안전 경계였으나, 2026-08-04 동적 시간 계약으로 대체됨 |
| 2026-08-04 | 지원 시작일은 오늘 이하인 수집·현재 parser·검색 가능 버전의 `effective_from` 전역 최솟값, 종료일은 한국 날짜의 오늘로 계산하고 오늘 유효 population의 content identity를 상태로 노출 | 날짜 상수를 매일 고치지 않으면서 현재 수집 corpus만 검색하고, 준비 불완전은 `503`, 범위 밖은 검색 전 `422`로 분리하기 위함. 이 계산은 법률별 timeline 연속성을 검증했다는 주장이 아님 |

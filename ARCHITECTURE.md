# 에너지 법령 RAG 아키텍처

상태: `MVP 구현 중`
최종 갱신: 2026-07-14

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
                                                        └─ OpenAI Responses + Structured Outputs
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
- `adapters`: 국가법령 API, Supabase/PostgreSQL/Storage, OpenAI 구현
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
- `provision_embeddings`: 모델·차원·색인 버전별 512차원 벡터
- `legal_relationships`: 상하위법·위임·인용 관계
- `derived_obligations`: 행위자·조건·의무 유형과 검증 상태
- `ingestion_runs`, `evaluation_runs`, `runtime_flags`: 운영·평가 상태

검색은 기준일 유효 버전을 먼저 제한하고 PGroonga 한국어 전문 검색과 pgvector 의미 검색을 병렬 수행한다. 두 순위를 RRF로 결합한다. 임베딩 API를 사용할 수 없으면 PGroonga 검색만 유지한다.

## 답변 안전 게이트

1. 질문의 기준일과 사업 단계를 검증한다.
2. 하이브리드 검색으로 근거 후보를 구성한다.
3. Responses API Structured Outputs로 답변·체크리스트·인용 ID를 받는다.
4. 모든 실질 주장과 체크리스트에 존재하는 인용 ID가 있는지 검사한다.
5. `gpt-5.6-terra` 실패, quota 402/429, 권한 오류, AI 비활성 시 다른 생성 모델로 전환하지 않고 검색 전용 응답으로 전환한다.

현재 인용 게이트는 인용 ID 존재와 원문 반환을 보장한다. 주장-원문 의미 일치 자동평가와 법령 관계 확장은 다음 품질 게이트다.

## 공개 API

- `POST /v1/questions`
- `POST /v1/search`
- `GET /v1/provisions/{id}`
- `GET /v1/documents/{id}/changes`
- `GET /v1/corpus/status`
- `GET /health`

연혁 본문 경로가 XML/JSON 계약 테스트를 통과하기 전 변경 API는 `supported=false`를 반환한다. HTML로 기능을 가장하지 않는다.

## 운영 원칙

- 키는 저장소에 커밋하지 않고 Vercel·Supabase 환경 설정 또는 collector PC의 OS 비밀 저장소에 둔다.
- 질문 원문, IP, 원문 전문을 로그에 남기지 않는다.
- AI 장애와 검색 장애를 분리한다.
- 법제처에 등록한 고정 공인 IPv4 Windows PC에서 `apps/collector`를 별도 프로세스로 실행한다. Vercel, 공용 runner와 브라우저에서 법령 API를 직접 호출하지 않으며 collector PC에 포트포워딩이나 공개 API를 열지 않는다.
- 현재 버전 collector와 Vercel API, Google 인증과 사용자 질문 이력은 Supabase에 연결되어 있다. 연혁·삭제 격리와 영속 운영 플래그는 후속 단계다.
- 익명 질문은 저장하지 않는다. 운영 로그인은 Supabase Google OAuth만 지원하며 질문 이력은 PostgreSQL에 생성일부터 1년 보존 후 삭제한다. 계정 삭제 시 질문·이력·세션·내보내기·동의 등 해당 사용자와 연결된 데이터를 삭제한다. 개발·테스트의 목업 인증은 production에서 비활성화한다.
- 공개 서비스의 rate limit HMAC 저장과 평가셋 Recall@10 게이트는 배포 전 필수 잔여 작업이다.

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

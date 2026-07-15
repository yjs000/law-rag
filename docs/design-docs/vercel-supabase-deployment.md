# Vercel·Supabase 운영 전환 설계

상태: 승인
최종 갱신: 2026-07-14

## 목적

공개 Web과 FastAPI는 Vercel에 배포하고 영속 상태는 Supabase로 이전한다. 국가법령정보 공동활용 Open API를 호출하는 collector만 등록된 고정 공인 IPv4의 Windows PC에서 실행한다. 집 PC는 공개 서버가 아니며 Vercel의 인바운드 요청을 받지 않는다.

```text
Browser -> Vercel Next.js -- same-origin /api proxy -> Vercel FastAPI
                                                     |-> Supabase PostgreSQL/Auth/Storage
                                                     `-> OpenAI

Windows Task Scheduler -> collector -> 국가법령정보 Open API
                                   `-> Supabase PostgreSQL/Storage
```

Vercel이 자동 발급하는 `*.vercel.app` Production 주소를 사용한다. 커스텀 도메인은 출시 선행조건이 아니다.

## 배포 단위

- `apps/web`: 별도 Vercel Project의 Next.js Production·Preview 배포
- `apps/api`: 별도 Vercel Project의 Python 3.14 FastAPI Function
- `apps/collector`: 등록된 고정 공인 IPv4 Windows PC의 OS 스케줄러 작업
- Supabase: PostgreSQL, Auth, Storage와 모든 영속 운영 상태
- OpenAI: FastAPI 서버 계층에서만 호출

## 환경변수와 Git 브랜치

실제 비밀값은 Git의 `.env*` 파일에 커밋하지 않고 Vercel Project Settings에 직접 등록한다. 로컬 개발은 각 프로젝트의 `.env.local`을 사용한다. FastAPI 설정은 `.env`를 먼저 읽고 `.env.local`로 덮어쓰며, 프로세스 환경변수가 최우선이다.

현재 저장소의 Vercel Production Branch는 `main`으로 유지한다. 별도 `prod` 브랜치는 만들지 않는다. `develop` 브랜치도 필수는 아니다. 지속적으로 유지되는 staging URL과 staging Supabase 프로젝트가 필요해질 때만 `develop`을 만들고 Vercel Preview의 branch-specific 환경변수를 연결한다. 그 전에는 기능 브랜치별 Preview를 목업 또는 격리된 Preview 자원에 연결한다.

### API Vercel Project

| 변수 | Local | Preview | Production | 비고 |
|---|---:|---:|---:|---|
| `ENVIRONMENT` | `development` | `test` | `production` | Production에서 mock auth 경로 차단 |
| `DATABASE_URL` | 선택 | staging/격리 DB | 운영 DB | Vercel은 Supavisor transaction URL 사용 |
| `OPENAI_API_KEY` | 선택 | 별도 제한 키 또는 미설정 | 운영 서버 키 | 미설정 시 검색 전용 |
| `AI_MODE` | `auto`/`off` | 기본 `off` | `auto` | Preview 비용·오용 방지 |
| `RATE_LIMIT_SECRET` | 개발용 난수 | Preview 전용 난수 | 운영 전용 난수 | 환경마다 다른 16자 이상 값 |
| `WEB_ORIGIN` | `http://localhost:3000` | 정확한 Preview Web origin | 정확한 Production Web origin | wildcard 금지 |
| `SUPABASE_URL` | 선택 | 구현 후 staging 값 | 구현 후 운영 값 | 현재 API에서 미사용 |
| `SUPABASE_SECRET_KEY` | 선택 | staging 서버 키 | 운영 서버 키 | `sb_secret_...`; RLS 우회 권한; 브라우저 노출 금지 |
| 모델·차원·quota 변수 | 선택 | 필요 시 설정 | 필요 시 설정 | `.env.example` 기본값 참조 |

`DATABASE_URL`은 SQLAlchemy가 직접 PostgreSQL에 연결하는 비밀이고, `SUPABASE_SECRET_KEY`와는 용도가 다르다. 현재 구현은 DB 연결에 `DATABASE_URL`만 사용한다. `SUPABASE_SECRET_KEY`는 Auth 관리자 API나 Storage 서버 어댑터에서만 사용하며 `sb_secret_...` 형식의 서버 전용 키를 등록한다.

### Web Vercel Project

| 변수 | Local | Preview | Production | 비고 |
|---|---:|---:|---:|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Preview API URL | Production API URL | 브라우저에 공개되는 값; 비밀 금지 |

현재 코드에는 설계된 Next.js 상대 `/api/*` 프록시가 아직 구현되지 않았다. 구현 전에는 Web이 API URL을 직접 호출하므로 API의 `WEB_ORIGIN`을 해당 Web 배포 URL과 정확히 맞춰야 한다. 가변 기능 브랜치 Preview를 운영 API에 연결하지 않는다.

Vercel의 기본 출구 IP를 국가법령정보 Open API 등록 IP로 사용하지 않는다. Vercel Static IP도 현재 구성에는 필요하지 않다.

## FastAPI Vercel 배포 준비 조건

아래 조건을 모두 만족하기 전에는 FastAPI를 Production에 연결하지 않는다.

### 상태와 저장소

- 메모리 저장소와 프로세스 전역 사용자·세션·quota 상태를 운영 경로에서 제거한다.
- API 시작 시 로컬 collector manifest를 읽지 않는다.
- 법령, 버전, 조문, 임베딩, 질문 이력, rate limit, `runtime_flags`, 수집·평가 실행 상태를 Supabase에 영속화한다.
- 원문과 내보내기 산출물은 Supabase Storage에 두며 Vercel 함수 로컬 파일을 영속 저장소로 사용하지 않는다.
- 함수 시작 시 스키마 변경이나 데이터 이관을 실행하지 않는다. Alembic migration은 별도 검증·배포 단계에서 실행한다.
- 인스턴스 재시작, 동시 인스턴스, scale-to-zero 후에도 동일한 사용자 결과가 나오는지 테스트한다.

### 데이터베이스 연결

- Vercel 런타임 연결은 Supavisor transaction pooler를 사용한다.
- transaction mode에서 prepared statement cache를 끄고 SQLAlchemy/driver 설정을 회귀 테스트한다.
- migration, `pg_dump`, 복구 작업은 runtime pooler와 분리한 관리용 연결을 사용한다.
- Supabase에서 `pgroonga`와 `vector` 확장을 활성화하고 실제 한국어 검색·512차원 벡터 쿼리를 검증한다.
- Vercel Function은 Supabase 데이터베이스와 같거나 가장 가까운 리전에 둔다.

공식 참고: [Supabase 연결 방식](https://supabase.com/docs/guides/database/connecting-to-postgres), [prepared statement 비활성화](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL), [Postgres 확장 목록](https://supabase.com/docs/guides/database/extensions), [Vercel 리전](https://vercel.com/docs/regions)

### 인증과 사용자 경계

- 실제 인증은 Supabase Auth의 Google 공급자만 노출한다.
- Google OAuth의 Authorized redirect URI에는 Supabase 프로젝트가 표시하는 callback URL을 정확히 등록한다.
- Supabase의 Site URL과 허용 redirect URL에는 확정된 Vercel Production URL을 등록한다.
- Preview 로그인은 운영 OAuth·운영 사용자 데이터와 분리한다. 필요할 때 별도 OAuth client 또는 명시적으로 허용한 Preview URL만 사용한다.
- FastAPI는 bearer JWT의 서명, issuer, audience, 만료를 서버에서 검증하고 공급자 ID와 내부 사용자 ID를 분리한다.
- 사용자 소유 데이터는 FastAPI 인가와 Supabase RLS를 모두 적용하고 교차 사용자 접근을 실패시킨다.

공식 참고: [Supabase Google 로그인](https://supabase.com/docs/guides/auth/social-login/auth-google)

### Web·API 연결과 Preview CORS

Preview에서는 선택지 2인 **동일 출처 프록시**를 사용한다.

- 브라우저는 현재 Next.js 배포의 상대 경로 `/api/*`만 호출한다.
- Next.js 서버 계층이 해당 환경과 연결된 FastAPI 주소로 요청을 전달한다.
- 브라우저가 FastAPI의 가변 Preview 도메인을 직접 호출하지 않게 한다.
- FastAPI CORS는 임의의 `*.vercel.app` wildcard를 허용하지 않는다. 직접 접근이 필요한 Production origin만 정확히 허용한다.
- Web Preview와 API Preview를 연결할 때는 Vercel의 환경별 변수 또는 Related Projects 값을 사용하고 운영 API를 기본값으로 두지 않는다.
- 인증 헤더와 요청 ID만 전달하며 service role·OpenAI 키는 브라우저나 프록시 응답에 노출하지 않는다.

### 함수와 배포 계약

- `apps/api/vercel.json`의 함수 경로, Python 버전, 번들 제외 목록을 실제 모노레포 Root Directory에서 검증한다.
- 응답 시간과 OpenAI 스트리밍을 측정해 `maxDuration`을 정한다. 현재 60초 값은 운영 확정값이 아니다.
- 함수 번들 크기와 cold start를 측정하고 collector 데이터·테스트 fixture를 번들에 포함하지 않는다.
- startup은 짧고 멱등적으로 유지한다. shutdown 완료에 의존해 데이터 무결성을 보장하지 않는다.
- Preview에는 목업 또는 격리된 staging 자원만 연결하고 Production 비밀을 복사하지 않는다.
- 환경변수 변경 뒤에는 새 배포가 필요함을 운영 절차에 포함한다.

## 사용자가 준비해야 하는 선행 입력

### 반드시 필요

- Vercel 계정과 Git 저장소 연결 권한
- `apps/web`, `apps/api`용 Vercel Project와 자동 발급된 Production URL
- Supabase 프로젝트, 프로젝트 리전, DB 비밀번호, Project URL, anon key, service role key
- Supabase Storage bucket과 백업·복구에 사용할 요금제/보존 선택
- Google Cloud OAuth 동의 화면, Web client ID/secret, Supabase callback URL 등록
- OpenAI API key와 `gpt-5.6-terra`, embedding 모델 사용 권한·예산
- collector PC가 사용하는 **고정 공인 IPv4**, 국가법령정보 Open API 등록 정보와 OC
- Windows 예약 실행 시 PC·네트워크·Docker 또는 Python 런타임이 사용 가능하도록 하는 운영 조건
- Vercel·Supabase·OpenAI의 비용 한도와 알림을 설정할 계정 권한

비밀값은 채팅이나 Git으로 전달하지 않고 각 서비스 Dashboard 또는 OS 비밀 저장소에 사용자가 직접 등록한다.

### 프로젝트 생성 뒤 기록할 값

- Web Production URL과 API Production URL
- Vercel Project ID·환경별 API 대상·Function 리전
- Supabase project ref·리전·Auth callback URL·runtime pooler URL·관리용 migration 연결 방식
- Google OAuth client ID와 허용 callback/redirect 목록
- Storage bucket 이름과 공개/비공개 정책
- collector 실행 ID, 마지막 성공 시각, 등록 공인 IP 확인 절차

### 필요하지 않음

- 커스텀 도메인
- Vercel Static IP 또는 Secure Compute
- 집 공유기 포트포워딩
- Vercel에서 집 PC로 연결하는 터널이나 공개 webhook
- 집 PC에 공개 FastAPI 서버 운영

고정 공인 IPv4는 Windows의 `192.168.x.x` 고정 LAN 주소와 다르다. ISP 공인 IPv4가 유동이거나 CGNAT이면 ISP 고정 IP 상품 또는 고정 IP 서버가 별도로 필요하다.

## 애플리케이션 팀의 보안·운영 책임

Vercel과 Supabase가 관리형 인프라를 제공해도 아래 책임은 이 저장소와 운영자에게 남는다.

| 영역 | 필수 책임 |
|---|---|
| 인증·인가 | JWT 검증, 서버 자원 단위 소유권 검사, RLS, 관리자 경로 최소 권한 |
| 비밀 | 환경별 최소 권한 키, service role 브라우저 노출 금지, 회전·폐기 절차 |
| 네트워크 | 동일 출처 프록시, 정확한 CORS, 허용 URL, 요청 크기·시간 제한 |
| 남용 방지 | 사용자·익명 경계별 영속 rate limit, OpenAI 비용 상한, WAF 규칙과 우회 테스트 |
| 입력·출력 | Pydantic 검증, XSS·SSRF·프롬프트 주입 방어, 허용 출처 URL만 반환 |
| 법률 안전 | 출처·버전 추적, 주장별 인용 검증, 근거 부족·AI 장애 시 검색 전용 전환 |
| 개인정보 | 익명 질문 미저장, 로그인 이력 1년 삭제, 계정 삭제 전파, 최소 로그 |
| 데이터 | migration 검토, 원자적 코퍼스 승격, 백업·복구, Storage 객체 수명주기 |
| 공급망 | 의존성 고정·스캔, Preview 비밀 분리, 검증된 커밋만 Production 승격 |
| 관측 | 요청 ID, 오류·지연·비용·최신성 메트릭, 질문·IP·원문 전문 로그 금지 |
| 사고 대응 | 키 폐기, AI 차단, 쓰기 경로 차단, 이전 배포·색인 롤백과 사용자 공지 |

플랫폼의 HTTPS, DDoS 완화, 배포 격리와 자동 확장은 위 애플리케이션 통제를 대체하지 않는다.

## 실행 순서

1. 사용자 선행 입력과 비용·리전 결정을 준비한다.
2. Supabase schema, 확장, RLS, Storage, 백업을 먼저 구성한다.
3. collector가 Supabase에 원자적으로 쓰고 로컬 manifest 없이 재실행 가능하게 한다.
4. FastAPI의 저장소·인증·rate limit을 영속 구현으로 교체하고 stateless 회귀 테스트를 통과시킨다.
5. API Preview를 배포하고 Supabase staging 자원으로 종단 검증한다.
6. Next.js `/api/*` 동일 출처 프록시와 Web Preview를 연결한다.
7. Production URL, Google OAuth, CORS, 환경변수와 보호 규칙을 확정한다.
8. migration 후 Production을 단계적으로 열고 검색 전용 모드에서 AI 모드 순으로 승격한다.

## 완료 조건

- 재배포·동시 함수 인스턴스 후에도 인증·질문·quota·코퍼스 상태가 일치한다.
- Preview 브라우저 요청은 상대 `/api/*`만 사용하며 운영 API나 wildcard CORS에 의존하지 않는다.
- 다른 사용자의 질문·내보내기·이력을 API와 직접 DB 접근 모두에서 읽을 수 없다.
- 질문 원문, 이메일, IP 원문, 법령 원문 전문, 비밀 패턴이 로그에 없다.
- collector PC에는 인바운드 공개 포트가 없고 Open API와 Supabase로만 outbound 연결한다.
- 공개 URL에서 질문→검색/답변→인용 원문→이력→삭제→내보내기 종단 흐름이 통과한다.
- AI, DB, Storage, collector 장애별 폴백·알림·롤백과 백업 복구를 훈련한다.

## 롤백

- AI 장애는 `AI_MODE=off`로 검색 전용 전환한다.
- 인증·RLS 이상은 로그인 쓰기 경로를 닫고 목업 인증을 Production에서 열지 않는다.
- DB migration은 사전 백업과 호환 배포 순서를 사용하며 원격 파괴 명령을 자동 실행하지 않는다.
- 코퍼스는 검증된 버전만 원자 승격하고 직전 활성 버전을 보존한다.
- 코드 장애는 직전 검증 Vercel 배포로 되돌리되 DB 롤백과 동일한 작업으로 간주하지 않는다.

## 결정 기록

- 2026-07-14: Web과 stateless FastAPI는 Vercel, 영속 상태는 Supabase, collector는 등록된 고정 공인 IPv4 Windows PC에 배치한다. 공개 앱 서버 운영 부담과 Open API IP 제한을 분리하기 위함이다.
- 2026-07-14: Preview 브라우저는 Next.js의 상대 `/api/*` 동일 출처 프록시를 사용한다. 가변 Preview origin을 FastAPI CORS wildcard로 허용하지 않기 위함이다.
- 2026-07-14: 커스텀 도메인과 Vercel 고정 출구 IP는 출시 선행조건에서 제외한다. Vercel 발급 Production URL을 사용하고 Open API 호출은 collector만 수행한다.
- 2026-07-14: `main`을 유일한 Production Branch로 유지하고 별도 `prod` 브랜치는 만들지 않는다. `develop`은 고정 staging 환경이 필요할 때만 branch-specific Preview로 도입한다. 환경 이름과 Git 브랜치 이름을 중복 운영해 설정 드리프트가 생기는 것을 피하기 위함이다.
- 2026-07-14: legacy `SUPABASE_SERVICE_ROLE_KEY` 대신 `sb_secret_...` 형식의 `SUPABASE_SECRET_KEY`를 서버 전용으로 사용한다. 현재 FastAPI의 DB 연결에는 `DATABASE_URL`만 사용하고, secret key는 Auth/Storage 서버 어댑터에서만 사용한다.

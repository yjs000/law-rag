# 실행 계획 0002: 실제 서비스 연결

상태: 1차 Vercel·Supabase 연결 검증 중
작성일: 2026-07-14
소유자: 사용자와 Codex

## 목적

목업 경계로 검증한 에너지 법령 RAG를 실제 Supabase, Google OAuth, OpenAI, Vercel Web/FastAPI에 연결한다. collector는 등록된 고정 공인 IP Windows PC에서 독립 실행한다.

사용자 결과는 Vercel 발급 공개 URL에서 로그인, 기준일 검색, 근거 기반 답변, 인용 원문, 이력과 내보내기를 사용할 수 있고 collector 장애 중에도 마지막 검증 코퍼스로 질문을 계속 처리하는 것이다.

## 범위와 비범위

범위에는 Supabase 영속화·RLS·Storage, Google OAuth, OpenAI 실제 호출, stateless FastAPI, Vercel Web/API 배포, Preview 동일 출처 프록시, Windows collector의 Supabase 반영과 출시 보안·복구 검증이 포함된다.

다음은 이 계획의 비범위다.

- 커스텀 도메인 구매와 DNS 이전
- Vercel Static IP·Secure Compute 도입
- 집 PC의 포트포워딩, 공개 API 또는 Vercel 인바운드 터널
- 국가법령정보 Open API 외 코퍼스 추가
- 검증되지 않은 대체 생성 모델 도입

## 선행 입력

- `gpt-5.6-terra` 권한이 있는 OpenAI API 키
- Supabase 프로젝트 URL·리전, runtime pooler와 관리용 DB 연결 방식, service role과 Storage 설정
- Google OAuth client와 Supabase callback·Vercel Production redirect URL
- `apps/web`, `apps/api` Vercel Project와 자동 발급된 `*.vercel.app` Production URL
- collector PC의 고정 공인 IPv4, 국가법령정보 Open API 등록과 OC
- Vercel·Supabase·OpenAI 비용 한도·알림과 `gpt-5.6-terra` 권한이 있는 OpenAI API 키

비밀값은 채팅·Git에 전달하지 않고 서버 또는 CI Secret에 직접 등록한다.

## 현재 집중 범위와 역할

이번 대화에서는 다음 세 항목만 우선 완료한다.

1. 로컬과 Vercel의 DB 연결 구성을 확정한다.
2. Web에서 Production API를 호출할 수 있는 공개 경로와 환경변수를 검증한다.
3. 현재 로컬 변경을 검증하고 승인 후 Production에 배포한다.

### 사용자가 해야 할 일

- [x] 루트 `.env.local`과 `apps/api/.env.local`에 `DATABASE_URL` transaction pooler(6543) URL과 `DIRECT_URL` session pooler(5432) URL을 등록한다.
- [x] 아래 에이전트 검증 결과를 확인한 뒤 `main` 커밋·푸시와 Production 자동 배포를 승인한다.
- [ ] 비밀번호, API 키, bypass secret은 채팅이나 Git에 올리지 않는다.

현재 Production API 주소는 일반 인터넷 요청의 `/health`에서 `200 OK`이므로 Deployment Protection 변경은 사용자 작업이 아니다.

### 에이전트별 TODO

#### DB·마이그레이션 에이전트

- [x] Supavisor transaction mode(6543)와 session mode(5432) 연결을 각각 검증한다.
- [x] 초기 Alembic migration을 session pooler로 적용하고 revision `0001`을 확인한다.
- [x] SQLAlchemy runtime에 transaction pooler 제약을 반영한다.
- [x] 사용자가 추가한 `DATABASE_URL`의 호스트·포트만 비밀 노출 없이 재확인한다.
- [x] API 전체 테스트, 린트와 migration contract 테스트를 실행한다.

#### Vercel·배포 에이전트

- [x] `apps/web`과 `apps/api`를 각각 별도 Vercel Project로 연결한다.
- [x] API Production `/health`를 bypass token 없는 일반 HTTP 요청으로 확인한다.
- [x] Web Production의 `NEXT_PUBLIC_API_URL`을 안정적인 API Production domain으로 확정한다.
- [ ] 사용자 승인 후 변경을 커밋·푸시하고 Web/API Production을 재배포한다.
- [ ] 재배포 후 API health, corpus status, Web 화면의 실제 요청을 순서대로 검증한다.

#### Web 통합 에이전트

- [x] 현재 Production의 별도 도메인 REST 호출과 정확한 `WEB_ORIGIN` CORS preflight 구성을 확인한다.
- [ ] Preview에서 운영 API를 실수로 호출하지 않도록 상대 `/api/*` 프록시 도입 범위를 후속 작업으로 분리한다.
- [ ] 브라우저 클릭 검증은 로컬·API 단독 검증이 끝난 뒤 최종 사용자 경로 확인에만 사용한다.

## 단계

### Supabase와 데이터 수명주기

- [x] PostgreSQL·pgvector·PGroonga·Supavisor 연결과 초기 스키마 적용
- [ ] Storage bucket과 원문 저장 수명주기 검증
- [x] Vercel runtime은 Supavisor transaction mode와 prepared statement cache 비활성화, migration은 session mode 연결로 검증
- [ ] 목업 manifest 235개 버전을 트랜잭션과 불변 원문 객체로 이관
- [ ] 질문 이력 1년 자동 삭제와 계정 삭제의 DB·Storage·백업 전파 검증
- [ ] `runtime_flags`, rate limit, 수집 실행, 평가 실행 상태 영속화하고 API의 로컬 manifest·프로세스 상태 의존 제거

### Google OAuth와 사용자 경계

- [ ] Google 공급자만 노출하고 ID 토큰·redirect·세션 회전 검증
- [ ] 내부 사용자 ID 분리와 질문 이력 RLS·교차 사용자 접근 차단
- [ ] Preview와 Production OAuth client·redirect·비밀·사용자 데이터 경계 검증
- [ ] 개인정보 처리방침, 국외 이전, 보유·삭제 정책 검토

### OpenAI와 품질 게이트

- [ ] 실제 Terra 구조화 출력에 결정적 인용 게이트 적용
- [ ] quota·권한·모델 오류의 검색 전용 폴백과 영속 상태 검증
- [ ] 사람 검토 평가셋으로 의미 게이트 오탐·미탐 측정
- [ ] 실제 서비스 연결과 반복 가능한 검색 평가 실행 기반을 완성한 뒤, 같은 한국어 법령 조문·질의·모델·검색 설정으로 256·512·1024차원을 비교하고 Recall@10·nDCG@10·HNSW exact-search 대비 recall·지연시간·DB/인덱스 크기·인용 게이트 통과율을 기록하여 512차원을 유지하거나 migration·재임베딩 계획과 함께 변경
  - 참고: [검색·원문 계보·답변 검증 기초](../../learning/07-retrieval-storage-and-grounding-foundations.md), [OpenAI embedding model 발표](https://openai.com/index/new-embedding-models-and-api-updates/), [Matryoshka Representation Learning](https://arxiv.org/abs/2205.13147), [pgvector 공식 문서](https://github.com/pgvector/pgvector)

### Vercel Web/FastAPI 배포와 운영

- [ ] `apps/web`, `apps/api` 별도 Vercel Project 연결과 Production API 공개 health 검증 완료; Function 리전·최종 환경변수·재배포 검증 잔여
- [ ] Preview 브라우저는 Next.js 상대 `/api/*` 동일 출처 프록시만 사용하고 FastAPI wildcard CORS와 운영 API 기본 연결이 없음을 검증
- [ ] FastAPI 함수의 stateless 재시작·동시 인스턴스·streaming·번들 크기·`maxDuration` 검증
- [ ] collector PC의 고정 공인 IP를 법제처에 등록하고 인바운드 포트 없이 주 1회 작업·Supabase 원자 반영 검증
- [ ] 중앙 로그·메트릭·알림, 백업·복구, 롤백, 삭제 전파 훈련
- [ ] 공개 URL에서 질문→답변/검색 전용→인용 원문→이력→내보내기 종단 검증
- [ ] 구현 마일스톤별 `docs/learning/` 기술 브리핑 갱신

## 완료 조건과 검증

- 전체 포맷·린트·타입·단위·통합 테스트와 고정 검색/인용 평가셋이 통과한다.
- FastAPI 재배포·동시 인스턴스·scale-to-zero 후에도 사용자·quota·코퍼스 상태가 일치한다.
- Preview 브라우저는 상대 `/api/*`만 호출하고 운영 API·운영 비밀·wildcard CORS에 의존하지 않는다.
- 교차 사용자 접근, JWT 변조, XSS, SSRF, 프롬프트 주입, 허위 인용, 과도 사용 회귀 테스트가 통과한다.
- migration 적용·복구, DB 백업, Storage 수명주기와 계정 삭제 전파를 staging에서 검증한다.
- collector PC에는 공개 인바운드 포트가 없고 Open API와 Supabase로의 outbound만 필요하다.
- 공개 Vercel URL에서 질문→검색/답변→인용 원문→이력→삭제→내보내기 종단 흐름이 통과한다.
- 검증 명령과 외부 smoke test의 기준 URL·시각·결과를 이 계획의 진행 기록에 남긴다.

## 롤백

- AI 장애는 `AI_MODE=off` 검색 전용으로 전환한다.
- 새 코퍼스는 검증 완료 후 원자 승격하며 직전 색인 버전을 보존한다.
- 인증·DB 전환 실패 시 공개 쓰기 경로를 닫고 목업 인증을 production에서 활성화하지 않는다.

## 차단 요소

로컬 DB 입력 차단 요소는 해소되었다. 루트와 API의 `.env.local` 모두 transaction pooler용 `DATABASE_URL`(6543)과 migration용 `DIRECT_URL`(5432)을 갖는다. Production API도 공개되어 있으므로 Deployment Protection은 현재 차단 요소가 아니다. 다음 승인 지점은 검증된 로컬 변경의 `main` 커밋·푸시와 Production 자동 배포다.

세부 준비 목록, 플랫폼과 애플리케이션 책임, 완료 조건은 [Vercel·Supabase 운영 전환 설계](../../design-docs/vercel-supabase-deployment.md)를 따른다. 커스텀 도메인, Vercel Static IP, 집 PC 포트포워딩은 선행 입력이 아니다.

## 결정 로그

- 2026-07-14: 단일 고정 IP 클라우드 서버 계획을 Vercel Web/FastAPI + Supabase + 고정 공인 IP Windows collector로 대체했다.
- 2026-07-14: Preview Web은 Next.js의 상대 `/api/*` 동일 출처 프록시를 사용한다.

## 진행 기록

- 2026-07-14: FastAPI Vercel 배포 조건, 사용자 선행 입력, 보안·운영 책임과 완료 조건을 설계 문서로 확정했다. 외부 프로젝트 생성과 구현은 시작하지 않았다.
- 2026-07-15: Web/API Vercel Project를 연결하고 API 빌드와 `/health`를 확인했다. API Production domain은 bypass token 없는 일반 HTTP 요청에서도 `200 OK`를 반환했다.
- 2026-07-15: Supavisor session pooler로 초기 migration `0001`을 적용했다. runtime은 transaction pooler, migration은 session pooler를 사용하도록 분리했다.
- 2026-07-15: `vercel curl`은 보호된 배포 진단에는 유효하지만 공개 사용자 경로 증명으로 사용하지 않기로 했다. 공개 경로는 일반 HTTP 요청과 최종 Web 동작으로 검증한다.
- 2026-07-15: 사용자 작업과 에이전트별 TODO를 분리하고 현재 집중 범위를 DB 구성, Web→API 경로, 검증·재배포 세 항목으로 제한했다.
- 2026-07-15: `https://law-rag-web.vercel.app` origin의 일반 CORS preflight가 API에서 정확한 `Access-Control-Allow-Origin`과 허용 메서드를 반환함을 확인했다.
- 2026-07-15: 두 `.env.local`의 값을 노출하지 않고 다시 파싱해 `DATABASE_URL` 6543과 `DIRECT_URL` 5432가 모두 설정되었음을 확인했다. 최초 키 누락 보고는 PowerShell 자동 변수 `$Matches`와 검사 변수 이름의 충돌로 발생한 오판이어서 정정했다.

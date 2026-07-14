# 실행 계획 0002: 실제 서비스 연결

상태: 사용자 자격정보 준비 대기
작성일: 2026-07-14
소유자: 미지정

## 목적

목업 경계로 검증한 분산에너지 법령 RAG를 실제 Supabase, Google OAuth, OpenAI, Vercel Web/FastAPI에 연결한다. collector는 등록된 고정 공인 IP Windows PC에서 독립 실행한다.

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

## 단계

### Supabase와 데이터 수명주기

- [ ] PostgreSQL·pgvector·PGroonga·Storage·Supavisor 연결
- [ ] Vercel runtime은 Supavisor transaction mode와 prepared statement cache 비활성화, migration은 별도 관리용 연결로 검증
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

- [ ] `apps/web`, `apps/api`를 별도 Vercel Project로 연결하고 Supabase와 가장 가까운 Function 리전·환경변수·배포 보호 구성
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

현재 코드는 외부 자격정보 없이 계속 테스트할 수 있지만, 위 단계의 실제 연결과 공개 배포는 선행 입력이 준비될 때 시작한다.

세부 준비 목록, 플랫폼과 애플리케이션 책임, 완료 조건은 [Vercel·Supabase 운영 전환 설계](../../design-docs/vercel-supabase-deployment.md)를 따른다. 커스텀 도메인, Vercel Static IP, 집 PC 포트포워딩은 선행 입력이 아니다.

## 결정 로그

- 2026-07-14: 단일 고정 IP 클라우드 서버 계획을 Vercel Web/FastAPI + Supabase + 고정 공인 IP Windows collector로 대체했다.
- 2026-07-14: Preview Web은 Next.js의 상대 `/api/*` 동일 출처 프록시를 사용한다.

## 진행 기록

- 2026-07-14: FastAPI Vercel 배포 조건, 사용자 선행 입력, 보안·운영 책임과 완료 조건을 설계 문서로 확정했다. 외부 프로젝트 생성과 구현은 시작하지 않았다.

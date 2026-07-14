# 기술 스택 ADR

## 선택

- Web: Next.js 16.2, React 19, TypeScript 5, Tailwind CSS 4
- API: Python 3.14.6, FastAPI, Pydantic, SQLAlchemy 2, Alembic
- Package: Node 24.18.0, pnpm 11.12.0, uv 0.11.28
- Data: Supabase PostgreSQL, PGroonga, pgvector, Storage
- AI: OpenAI Responses API, Structured Outputs, `gpt-5.6-terra`; `text-embedding-3-large` 512차원
- Runtime units: `apps/api`와 `apps/collector`를 독립 Python 프로젝트로 운영하고 `apps/web`을 프런트엔드로 유지
- Batch/Deploy: 현재 고정 공인 IP Windows PC의 OS 스케줄러에서 collector 실행, 배포는 목업; 후속으로 Web과 stateless FastAPI는 Vercel, 영속 상태는 Supabase에 배치하고 collector는 등록된 고정 공인 IP PC에 유지
- Auth: 목업 단계는 Google 로그인을 모사한 개발용 세션, 실제 서비스는 Google OAuth만 지원

pnpm 11의 설치 스크립트는 `sharp`, `unrs-resolver`만 `pnpm-workspace.yaml`에서 허용한다. 전체 허용은 사용하지 않는다.

## 하지 않는 선택

LangChain 같은 대형 프레임워크로 핵심 검색·인용 계약을 감추지 않는다. PDF 청킹, HTML 크롤링, 파인튜닝은 MVP에 넣지 않는다. 브라우저 SDK로 OpenAI와 service role을 호출하지 않는다.

## 결정 기록

- 2026-07-13: 사용자가 설치한 최신 런타임을 정확히 고정. CI와 로컬의 재현성을 확보하기 위함.
- 2026-07-13: 초기에는 등록 IP 수집 job을 `law-rag-ingestion` self-hosted runner로 계획했으나, 아래의 독립 collector·OS 스케줄러 결정으로 대체했다. 일반 CI는 공용 runner를 유지한다.
- 2026-07-13: 운영 수집은 GitHub Actions에 결합하지 않고 같은 서버의 별도 `apps/collector` 프로세스와 OS 스케줄러로 실행하기로 변경.
- 2026-07-13: Supabase와 Vercel은 목업 구현을 먼저 완료한다. 실제 배포는 Vercel 대신 고정 IP 단일 클라우드 서버를 사용하고 Supabase 연결은 후속 진행한다.
- 2026-07-13: 답변 모델은 `gpt-5.6-terra`만 사용하고 실패 시 대체 생성 모델 없이 검색 전용 모드로 전환한다.
- 2026-07-13: 실제 인증 제공자는 Google만 사용한다.
- 2026-07-13: Web/API/collector를 같은 클라우드 서버에 두되 프로세스와 장애 경계는 분리한다.
- 2026-07-14: 위 단일 서버 배포 결정을 [Vercel·Supabase 운영 전환 설계](vercel-supabase-deployment.md)로 대체한다. Web과 stateless FastAPI는 Vercel, 영속 상태는 Supabase, collector는 등록된 고정 공인 IP Windows PC에 둔다.
- 2026-07-14: Preview 브라우저는 Next.js 상대 `/api/*` 동일 출처 프록시로 FastAPI에 접근한다. FastAPI에 가변 `*.vercel.app` CORS wildcard를 허용하지 않는다.

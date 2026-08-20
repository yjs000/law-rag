# 기술 스택 ADR

## 목적과 기준

이 문서는 현재 저장소에서 사용하는 기술과 역할을 한눈에 확인하는 기준 문서다. 제품의 동작과
도메인 계약은 [아키텍처](../../ARCHITECTURE.md), 기술 선택의 상세한 이유는 연결된 설계 문서를
따른다. 버전은 각 `package.json`과 `pyproject.toml`의 선언 범위를 기준으로 하며, 배포 여부는
운영 환경 변수와 인프라 설정에 따라 달라질 수 있다.

## 현재 기술 스택

| 영역 | 기술 | 역할 | 상태 |
|---|---|---|---|
| 웹 | Next.js 16.2, React 19, TypeScript 5, Tailwind CSS 4 | 법령 검색·답변 워크벤치 UI와 동일 출처 `/api/*` 프록시 | v1 현재 구현 |
| 웹 품질 | ESLint 9, Vitest 4 | 프런트엔드 린트와 단위 테스트 | 현재 사용 |
| API | Python 3.14, FastAPI, Uvicorn | 질문, 검색, 인증, 내보내기 HTTP API | v1 현재 구현 |
| API 모델·검증 | Pydantic Settings, SQLAlchemy 2 asyncio, Alembic, asyncpg | 경계 입력 검증, 비동기 PostgreSQL 접근, 스키마 마이그레이션 | 현재 사용 |
| 수집기 | Python 3.14, HTTPX, Pydantic Settings, SQLAlchemy 2 asyncio, asyncpg | 국가법령정보 공동활용 Open API 원문 수집·정규화·버전 반영 | 현재 사용 |
| 영속 데이터 | Supabase PostgreSQL, Supabase private Storage | 법령 메타데이터·조문·계보·질문 이력과 원문 보관 | 운영 아키텍처 |
| 검색 | pgvector, PGroonga | 기준일 유효 조문 dense 검색과 dense 0건/미준비 시 키워드 fallback | v1 현재 구현 |
| 언어 처리 | Kiwi (`kiwipiepy`) | 검색 전 tier1 결정적 키워드·정규식 라우팅 | v1 현재 구현 |
| 생성·임베딩 | NVIDIA NIM, `nvidia/nemotron-3-ultra-550b-a55b`, `nvidia/nemotron-3-embed-1b` | 근거 기반 답변/라우팅 판단과 임베딩 생성 | 현재 기본 provider |
| 인증 | Supabase Auth, Google OAuth/OIDC | 운영 Google 로그인과 API 사용자 검증 | 운영 계약; 개발에서는 목업 가능 |
| 배포·스케줄링 | Vercel, Windows 작업 스케줄러 | Web·stateless FastAPI 배포, 고정 공인 IP PC의 collector 정기 실행 | 운영 아키텍처 |
| 개발 도구 | Node.js 24.18, pnpm 11.12, uv | JavaScript 의존성/워크스페이스와 Python 가상환경·의존성 관리 | 현재 사용 |

## 구성과 데이터 흐름

```text
브라우저
  -> Next.js Web
  -> 동일 출처 /api 프록시
  -> FastAPI
       -> Supabase PostgreSQL / private Storage
       -> NVIDIA NIM

고정 공인 IP Windows PC
  -> Windows 작업 스케줄러
  -> collector
  -> 국가법령정보 공동활용 Open API
  -> Supabase PostgreSQL / private Storage
```

Web과 API는 상태를 보유하지 않고, 영속 데이터는 Supabase에 둔다. collector는 Open API의 등록
고정 IP 조건 때문에 별도 Windows PC에서 실행한다. 브라우저는 NVIDIA NIM이나 Supabase service
role에 직접 접근하지 않는다.

## 검색·AI 사용 원칙

- v1 검색은 pgvector의 **exhaustive exact cosine**을 기본으로 한다. HNSW는 v1 운영과 실험 D에서
  사용하지 않는다.
- dense 검색 결과가 없거나 임베딩 경로가 준비되지 않았을 때만 PGroonga 키워드 검색으로 fallback한다.
  현재는 dense와 keyword 점수를 섞거나 RRF를 적용하지 않는다.
- 임베딩은 NVIDIA NIM의 2,048차원 출력 중 앞 512차원을 L2 재정규화해 저장하며, 모델·차원·입력
  유형을 profile로 추적한다.
- 답변과 tier2 라우팅은 NVIDIA NIM을 사용한다. provider 오류·시간 초과·quota 상태에서는 다른
  생성 모델로 자동 전환하지 않고, 검증된 검색 전용 결과로 안전하게 fallback한다.
- 법령 원문은 국가법령정보 공동활용 Open API만 사용한다. HTML 크롤링, PDF 기반 청킹, 다른 법률
  사이트를 근거로 쓰지 않는다.

## 버전별 프레임워크 경계

| 버전 | 기술 | 적용 범위 | 상태 |
|---|---|---|---|
| v1 | FastAPI, SQLAlchemy, pgvector, PGroonga, 자체 도메인 계층 | 현재 법령 수집·검색·답변 API | 현재 구현 |
| v2 | LlamaIndex Core, NVIDIA 임베딩 연동, PostgreSQL vector store | v1과 독립된 `law-rag-llamaindex` 검색 파이프라인과 `/v2` 경로 | 구현 중 |
| v3 | LangGraph, LangGraph PostgreSQL checkpointer, LangChain NVIDIA endpoint 연동 | v1/v2를 재사용하지 않는 에이전트 라우팅·생성·검증 골격 | 제안됨 |

따라서 LlamaIndex와 LangGraph는 저장소 의존성에 포함돼 있어도 v1의 기본 검색·답변 경로를 대체하지
않는다. v1의 핵심 검색·인용 계약은 대형 프레임워크 뒤에 숨기지 않는다.

## 의도적으로 하지 않는 선택

- v1에서 LangChain 같은 대형 프레임워크로 검색·인용 계약을 추상화하지 않는다.
- PDF 청킹, HTML 크롤링, 파인튜닝을 MVP 범위에 넣지 않는다.
- 브라우저에서 NVIDIA NIM 또는 Supabase service role을 직접 호출하지 않는다.
- v1과 실험 D에 HNSW, hybrid 점수 결합, RRF를 추가하지 않는다.

## 근거 파일

- Web 의존성: [`apps/web/package.json`](../../apps/web/package.json)
- API 의존성·런타임: [`apps/api/pyproject.toml`](../../apps/api/pyproject.toml)
- collector 의존성: [`apps/collector/pyproject.toml`](../../apps/collector/pyproject.toml)
- v2·v3 의존성: [`apps/law-rag-llamaindex/pyproject.toml`](../../apps/law-rag-llamaindex/pyproject.toml), [`apps/law-rag-agent/pyproject.toml`](../../apps/law-rag-agent/pyproject.toml)
- 시스템 경계와 검색 계약: [`ARCHITECTURE.md`](../../ARCHITECTURE.md)

## 결정 기록

- 2026-07-13: 초기에는 등록 IP 수집 job을 `law-rag-ingestion` self-hosted runner로 계획했으나,
  독립 collector·OS 스케줄러로 대체했다. 일반 CI는 공용 runner를 유지한다.
- 2026-07-13: 실제 인증 제공자는 Google만 사용하기로 했다.
- 2026-07-14: Web과 stateless FastAPI는 Vercel, 영속 상태는 Supabase, collector는 등록된 고정
  공인 IP Windows PC에 두기로 했다.
- 2026-07-14: Preview Web은 Next.js 상대 `/api/*` 동일 출처 프록시로 FastAPI에 접근한다. FastAPI에
  가변 `*.vercel.app` CORS wildcard를 허용하지 않는다.
- 2026-07-15: 개발·CI·Vercel의 Python 런타임 계약을 3.14 계열로 통일했다.
- 2026-08-03: 임베딩 provider를 NVIDIA NIM으로 고정하고 모델·입력 유형·차원 축약·정규화·본문
  템플릿을 하나의 DB profile로 추적한다.
- 2026-08-09: 답변 생성 provider를 NVIDIA NIM 하나로 고정하고 OpenAI 설정·실행 분기를 제거했다.
- 2026-08-20: 이 문서를 구현 기준의 기술 스택 참조로 재구성하고, 더 이상 사용하지 않는 OpenAI
  답변 provider 표기를 제거했다.

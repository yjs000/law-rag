# 기술 스택 ADR

## 선택

- Web: Next.js 16.2, React 19, TypeScript 5, Tailwind CSS 4
- API: Python 3.14.6, FastAPI, Pydantic, SQLAlchemy 2, Alembic
- Package: Node 24.18.0, pnpm 11.12.0, uv 0.11.28
- Data: Supabase PostgreSQL, PGroonga, pgvector, Storage
- AI: OpenAI Responses API, Structured Outputs, `gpt-5.6-terra`; `text-embedding-3-large` 512차원
- Batch/Deploy: 고정 공인 IP의 GitHub self-hosted Actions 수집, Vercel 별도 Web/API 프로젝트

pnpm 11의 설치 스크립트는 `sharp`, `unrs-resolver`만 `pnpm-workspace.yaml`에서 허용한다. 전체 허용은 사용하지 않는다.

## 하지 않는 선택

LangChain 같은 대형 프레임워크로 핵심 검색·인용 계약을 감추지 않는다. PDF 청킹, HTML 크롤링, 파인튜닝은 MVP에 넣지 않는다. 브라우저 SDK로 OpenAI와 service role을 호출하지 않는다.

## 결정 기록

- 2026-07-13: 사용자가 설치한 최신 런타임을 정확히 고정. CI와 로컬의 재현성을 확보하기 위함.
- 2026-07-13: 법령 API 실계약에서 등록 IP 검증을 확인해 수집 job만 `law-rag-ingestion` self-hosted runner로 전환. 일반 CI는 공용 runner를 유지한다.

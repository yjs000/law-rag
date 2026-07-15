# Supavisor 런타임과 마이그레이션 연결

## 문제

Supabase의 direct PostgreSQL endpoint는 IPv6 전용일 수 있다. 현재 로컬 Windows 네트워크에서는 direct endpoint의 IPv6 주소에 연결할 수 없었지만 Supavisor의 IPv4 호환 pooler에는 연결할 수 있었다.

## 선택

- FastAPI runtime의 `DATABASE_URL`은 transaction mode pooler의 6543 포트를 사용한다.
- Alembic의 `DIRECT_URL`은 session mode pooler의 5432 포트를 사용한다.
- Prisma는 도입하지 않는다. 현재 도메인과 repository 경계는 SQLAlchemy/asyncpg로 구현되어 있고 ORM 교체가 연결 문제를 해결하지 않기 때문이다.
- Vercel runtime에는 migration 전용 `DIRECT_URL`을 등록하지 않는다. migration은 배포 요청 처리와 분리해 실행한다.

## 왜 연결을 분리하는가

transaction mode는 요청 단위의 짧은 DB 작업에 적합하지만 연결 단위 상태와 prepared statement 재사용에 제약이 있다. runtime engine은 `NullPool`과 asyncpg의 `statement_cache_size=0`을 사용해 애플리케이션 프로세스가 pooler 바깥에 별도 장기 연결 풀이나 prepared statement cache를 유지하지 않게 한다.

마이그레이션은 여러 DDL을 순서대로 수행하고 한 세션의 연속성이 중요하므로 session mode 5432를 사용한다. 이는 IPv6 direct endpoint를 요구하지 않으면서 transaction mode보다 migration에 적합하다.

## 초기 migration 수정 이유

초기 migration은 여러 `CREATE TABLE`과 index/function 생성을 하나의 `op.execute()`에 담고 있었다. asyncpg는 이 SQL 묶음을 하나의 prepared statement로 처리할 수 없어 migration이 실패했다. 각 DDL을 별도의 `op.execute()`로 분리했으며 스키마 내용 자체는 바꾸지 않았다. 실패한 첫 시도는 트랜잭션으로 롤백되었고, 분리 후 revision `0001` 적용을 확인했다.

## 환경변수

```dotenv
DATABASE_URL=postgresql://...@...pooler.supabase.com:6543/postgres
DIRECT_URL=postgresql://...@...pooler.supabase.com:5432/postgres
```

비밀번호는 URL 인코딩하고 `.env.local` 또는 배포 환경 Secret에만 둔다. 저장소와 문서에는 실제 값을 기록하지 않는다.

## 다음 검증

1. 두 로컬 `.env.local`에 `DATABASE_URL`과 `DIRECT_URL`이 모두 있는지 값 노출 없이 확인한다.
2. API 전체 테스트와 lint를 통과시킨다.
3. Production 재배포 뒤 `/health`와 `/v1/corpus/status`를 일반 HTTP 경로로 확인한다.

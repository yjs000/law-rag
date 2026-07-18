# 검색 성능과 관측 공식 자료

기준일: 2026-07-18

## PGroonga

- [PGroonga `&@~` query operator](https://pgroonga.github.io/reference/operators/query-v2.html): 공백은 AND, `OR`는 OR 검색이다. `column &@~ (query, weights, index_name)` 형식으로 제목·표제·본문 같은 값에 가중치를 줄 수 있다.
- [PGroonga `CREATE INDEX USING pgroonga`](https://pgroonga.github.io/reference/create-index-using-pgroonga.html): text 전문 검색 인덱스, 기본 TokenBigram, Unicode NFKC 계열 정규화와 커스텀 tokenizer/normalizer 계약을 설명한다.
- [PGroonga reference manual](https://pgroonga.github.io/reference/): v2 operator class와 전문 검색 연산자 목록이다.

## PostgreSQL

- [PostgreSQL `EXPLAIN`](https://www.postgresql.org/docs/current/using-explain.html): `EXPLAIN ANALYZE`는 질의를 실제 실행하며 실제 행 수·시간을 보여준다. Production에서는 읽기 검색문에만 사용하고 `BUFFERS`, JSON 형식과 함께 기록한다.
- [PostgreSQL client connection defaults](https://www.postgresql.org/docs/current/runtime-config-client.html): `statement_timeout`은 서버가 명령을 받은 때부터 완료까지를 제한한다. 전역 설정은 모든 세션에 영향을 주므로 검색 호출 범위에만 적용한다.
- [PostgreSQL query planning](https://www.postgresql.org/docs/current/runtime-config-query.html): prepared statement의 generic plan은 planning 비용을 줄일 수 있지만 파라미터별 최적 plan이 달라지면 비효율적일 수 있다. 기본 `plan_cache_mode=auto`를 측정 없이 바꾸지 않는다.

## Supabase와 Vercel

- [Supabase database connections](https://supabase.com/docs/guides/database/connecting-to-postgres): serverless/edge에는 Supavisor transaction mode가 적합하며 연결 재사용으로 확장성을 높인다. transaction mode는 prepared statements를 지원하지 않는다.
- [Supabase prepared statements 비활성화](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL): asyncpg는 `statement_cache_size=0`이고 명시적 `Connection.prepare()`를 피해야 한다.
- [Supabase `pg_stat_statements`](https://supabase.com/docs/guides/database/extensions/pg_stat_statements): calls, planning/execute time과 normalized query를 통해 느리고 빈번한 SQL을 식별한다.
- [Supabase connection management](https://supabase.com/docs/guides/database/connection-management): pool 크기는 DB 최대 연결과 Auth/PostgREST 등 다른 서비스의 여유를 고려해 실제 사용량을 보고 정한다.
- [Vercel Functions](https://vercel.com/docs/functions): DB 왕복을 줄이려면 Function을 데이터 원본 가까운 region에 배치한다. cold start와 재사용된 instance의 지연은 별도로 측정한다.

## 이 프로젝트에 적용하는 결론

1. 검색 의미는 4단계 순차 완화로 유지하되 성공 즉시 종료한다.
2. 최대 세 번의 원격 DB 왕복이 1초 목표의 병목이면 단일 PostgreSQL 함수 내부 순차 분기로 합친다.
3. 후보 수 제한, PGroonga/B-tree 인덱스, 실행계획 확인을 먼저 하고 전역 planner 옵션은 바꾸지 않는다.
4. Vercel에서는 Supavisor transaction mode와 prepared statement cache 0을 유지한다.
5. `retrieval_total_ms`, 단계별 DB 시간, 연결 획득, 상위 후보 ID/점수를 구조화해 정확도와 지연을 함께 회귀 검증한다.

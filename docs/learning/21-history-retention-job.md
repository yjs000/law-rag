# 21 질문 이력 보존 정리와 감사 가능한 DB 작업

## 배운 개념

개인정보 보존 정책은 조회 시 만료 행을 숨기는 것만으로 충족되지 않는다. 실제 행을 주기적으로 삭제하고, 종속 데이터와 집계 행까지 일관되게 정리하며, 원문 없이 실행 결과를 증명할 수 있어야 한다.

## 선택 이유

질문 생성 시 `expires_at=now()+interval '1 year'`가 저장되므로 정리 함수는 정책 기간을 다시 계산하지 않고 `expires_at <= cutoff`만 판단한다. 테스트나 장애 재현에서는 명시적 cutoff를 넘길 수 있어 같은 데이터 집합을 결정적으로 검증할 수 있다.

정리 로직은 PostgreSQL 함수 한 transaction에 둔다. 만료 질문 삭제, FK cascade, 대화 재집계, 빈 대화 삭제가 분리된 serverless 요청으로 실행되면 중간 실패 때 요약이 실제 턴과 달라질 수 있기 때문이다.

## 데이터 흐름

```text
승인된 scheduler 또는 수동 운영 호출
  -> advisory transaction lock
  -> history_retention_runs(running)
  -> 만료 질문에 연결된 export 수 사전 집계
  -> question_history 삭제
       -> checklist_exports ON DELETE CASCADE
  -> 영향받은 conversations 재집계
  -> 남은 턴이 없는 conversations 삭제
  -> history_retention_runs(succeeded 또는 failed)
```

실패 처리는 중첩 PL/pgSQL block을 사용한다. 데이터 변경은 block 단위로 rollback하고 바깥의 감사 행에는 `failed`와 SQLSTATE만 기록한다. `SQLERRM`이나 질문·사용자 식별자는 저장하지 않는다.

`SECURITY DEFINER` 함수는 호출자의 search path를 신뢰하지 않는다. `pg_catalog, public, pg_temp`로 고정하고 테이블·함수 참조를 `public.`으로 명시해 동일 이름 객체로 권한 실행 경계를 바꾸기 어렵게 한다. 함수 실행과 감사 테이블 조회는 `service_role`에만 열고 `PUBLIC`, `anon`, `authenticated`에는 부여하지 않는다.

## 멱등성과 동시성

같은 cutoff로 다시 실행하면 이미 삭제된 질문이 없으므로 삭제 수가 0인 성공 실행이 된다. 이는 멱등적 최종 상태와 실행 감사 이력을 동시에 제공한다. `pg_advisory_xact_lock`은 schedule 중복 등록이나 수동 실행이 겹쳐도 정리를 직렬화한다. 또한 export 수를 집계하기 전에 만료 질문 행을 `FOR UPDATE`로 잠가, 집계와 질문 삭제 사이에 새 FK 참조가 추가되어 cascade 수가 감사 값과 달라지는 경합을 막는다.

## scheduler를 migration에서 만들지 않는 이유

`pg_cron`은 PostgreSQL/Supabase 환경마다 가용성, extension 설치 상태, schema, 승인 정책이 다르다. migration이 이를 무조건 설치하거나 schedule을 등록하면 로컬·Preview migration을 깨뜨리거나 승인 없는 운영 side effect를 만들 수 있다. 따라서 migration은 호출 가능한 함수만 제공하고 Production 예약은 승인 후 extension 확인을 거치는 별도 운영 단계로 둔다.

## 직접 실행 명령

로컬 정적 계약만 검증하며 외부 DB credential은 필요하지 않다.

```bash
cd apps/api
uv run pytest tests/test_history_retention_migration.py -q
uv run ruff check migrations/versions/0006_history_retention_job.py tests/test_history_retention_migration.py
```

## 다음 학습 주제

- 임시 PostgreSQL에서 실제 cascade·실패 rollback·동시 실행 검증
- Supabase `pg_cron` 승인·권한·중복 schedule 운영 패턴
- 감사 행 자체의 보존기간과 정리 작업 실패 경보
- DB 백업의 개인정보 보존·삭제 수명주기

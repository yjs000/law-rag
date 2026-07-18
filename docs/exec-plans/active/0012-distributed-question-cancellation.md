# 분산 질문 취소 실행 계획

## 목적과 사용자 결과

sticky routing 없이 어느 Vercel API 인스턴스에 취소 요청이 도착해도 중지 신호가 접수되고, 실제 질문 인스턴스의 검색·모델 태스크가 이를 감지해 종료된다. 정상 scale-out은 404가 되지 않는다.

상세 설계는 [분산 질문 취소 설계](../../design-docs/distributed-question-cancellation.md)를 따른다.

## 사용자 병목과 선행 결정

구현·목업 테스트는 사용자 입력 없이 진행할 수 있다. 실제 Production 검증 전에만 다음이 필요하다.

1. Supabase migration 적용 권한과 실행 창
2. 취소 상태 보존 기간 선택. 기본 가정은 24시간 후 삭제
3. Supabase 부하 측정 권한. 기본 watcher 간격은 500ms
4. 실제 Qwen/Ollama adapter가 provider-side 취소 API를 제공하는지 확정

비밀값 제공이나 Production migration 승인 전에는 로컬/목업 구현까지만 완료하고 운영 DB를 변경하지 않는다.

## 범위와 비범위

범위:

- 실행 상태 migration/RLS/TTL 계약
- PostgreSQL 및 memory coordinator adapter
- process-local registry와 coordinator를 결합한 watcher
- 멱등 취소 API 상태 계약
- Web의 `중지 요청됨`/`확인 중`/`완료됨` 상태
- 정상·등록 경합·다른 인스턴스·DB 장애·소유자 격리 테스트

비범위:

- sticky routing
- Redis 도입
- 질문·답변 본문을 취소 테이블에 저장
- upstream provider가 제공하지 않는 계산 환불 보장

## Agent별 실행 TODO

### Agent DB/coordinator

- [ ] `question_executions` migration, RLS, TTL index 추가
- [ ] memory/PostgreSQL coordinator 포트와 adapter 구현
- [ ] 조건부 상태 전이·등록 전 tombstone 테스트
- [ ] DB schema 생성 문서 갱신

### Agent API/runtime

- [ ] 질문 등록→watcher→종결 상태 흐름 구현
- [ ] 로컬 취소와 DB 신호 취소를 결합
- [ ] `202 cancel_requested/pending_registration`, `200 already_finished/cancelled`, `404 not_owned`, `503 unavailable` 계약 구현
- [ ] 검색 및 모델 await 취소 전파, watcher 정리 테스트

### Agent Web/UX

- [ ] 브라우저 abort와 독립적인 취소 요청 유지
- [ ] 접수와 최종 취소를 구분해 표시
- [ ] 503 재시도와 늦은 완료 결과 정책 구현
- [ ] 새 질문·로그아웃 시 상태 정리 테스트

### Agent 운영 검증

- [ ] 서로 다른 두 API 프로세스로 질문과 취소를 보내는 통합 테스트
- [ ] Production Preview에서 scale-out/재시작 경합 확인
- [ ] cancel 감지 p50/p95 및 DB read/s 기록
- [ ] orphan/TTL 정리 작업 검증

## 완료 조건

1. 다른 프로세스에서 보낸 취소가 404 없이 접수되고 원래 프로세스의 blocking search/model mock을 취소한다.
2. 질문 등록 전 취소도 검색을 시작하지 않는다.
3. 다른 사용자 요청은 취소하거나 존재를 확인할 수 없다.
4. DB 장애 시 UI가 완료를 거짓 표시하지 않고 503과 재시도를 제공한다.
5. API 단위·통합 테스트, Web 테스트, lint/type/build가 통과한다.
6. migration과 `docs/generated/db-schema.md`, 운영 런북, learning 문서가 함께 갱신된다.

## 검증 명령

```powershell
Set-Location apps/api
uv run pytest tests/test_question_cancellation.py tests/test_distributed_question_cancellation.py
uv run ruff check app tests

Set-Location ../web
pnpm test
pnpm lint
pnpm typecheck
pnpm build
```

## 롤백

분산 coordinator feature flag를 끄면 기존 process-local 취소로 되돌린다. 새 테이블은 롤백 직후 삭제하지 않고 TTL이 지난 뒤 별도 migration으로 제거해 진행 중 상태와 관측 증거를 보존한다.

## 진행 기록

- 2026-07-18: 현재 process-local registry와 Vercel/Supabase 배치를 조사했다.
- 2026-07-18: sticky routing 배제, 영속 상태+polling watcher, 404 대체 상태 계약을 확정했다.

## 미결정·차단 요소

- 실제 Production migration은 사용자 승인 및 Supabase 접근이 필요하다.
- provider-side 계산 취소는 Qwen/Ollama adapter와 배포 방식을 확정한 뒤 검증한다.

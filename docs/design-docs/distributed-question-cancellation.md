# 분산 질문 취소 설계

## 목적

Vercel의 stateless FastAPI가 여러 인스턴스로 실행되어도 사용자가 누른 중지가 검색과 모델 생성을 수행 중인 인스턴스에 전달되게 한다. sticky routing은 사용하지 않는다. 취소 요청이 원래 질문을 처리하는 인스턴스와 다른 인스턴스에 도착하는 것을 정상 조건으로 취급한다.

## 현재 상태와 문제

현재 `QuestionTaskRegistry`는 `(owner, client_request_id)`에 대응하는 `asyncio.Task`를 프로세스 메모리에 보관한다. 같은 인스턴스에 도착한 취소는 검색·모델 await에 `CancelledError`를 전파하지만 다른 인스턴스에는 그 태스크가 없어 404가 된다. Vercel 재시작과 scale-out에서도 같은 문제가 생긴다.

다른 프로세스가 Python `Task` 객체를 직접 취소할 수는 없다. **분산 취소 신호**란 모든 인스턴스가 접근하는 Supabase PostgreSQL에 요청 상태와 `cancel_requested_at`을 기록하고, 작업 인스턴스가 이를 감지해 자기 로컬 태스크를 취소하는 간접 신호다.

DB 기록만 추가해서는 실행 중인 HTTP 모델 호출을 즉시 끊지 못한다. 작업 인스턴스에 신호 watcher가 함께 있어야 한다.

## 결정

### 영속 상태

`question_executions` 테이블을 둔다.

| 열 | 의미 |
|---|---|
| `request_id uuid` | 브라우저가 생성한 멱등 키 |
| `owner_hash text` | 사용자 ID 또는 익명 일일 주체의 서버 HMAC. 원문 IP는 저장하지 않음 |
| `status text` | `accepted`, `running`, `cancel_requested`, `cancelled`, `completed`, `failed` |
| `created_at`, `updated_at` | 상태 시각 |
| `cancel_requested_at`, `finished_at` | 취소 및 종결 시각 |
| `expires_at` | 자동 삭제 기준. 질문 본문·법률 원문·모델 출력은 저장하지 않음 |

기본 키는 `(owner_hash, request_id)`다. 상태 전이는 조건부 `UPDATE`로 수행한다. `completed`, `failed`, `cancelled`는 종결 상태이며 다시 `running`으로 돌아가지 않는다. 정리 작업은 짧은 보존 기간이 지난 행을 삭제한다.

### 질문 인스턴스

1. 질문 처리 전에 `accepted`를 upsert한다. 이미 종결된 같은 키는 재실행하지 않는다.
2. 로컬 레지스트리에 태스크를 등록하고 상태를 `running`으로 바꾼다.
3. 별도 watcher는 요청 실행 중에만 request 전용 private Supabase Realtime Broadcast를 기다린다. 구독 전후에 권위 DB 행을 한 번씩 확인해 구독 경계의 신호 유실을 막으며 주기적 polling은 하지 않는다.
4. 신호를 발견하면 현재 태스크에 `cancel()`을 호출한다. asyncpg/httpx/모델 SDK await에 취소가 전파된다.
5. `finally`에서 watcher를 종료하고 `cancelled`, `completed` 또는 `failed`를 조건부 기록한다.

watcher의 DB 오류는 질문을 임의 취소하지 않는다. 로컬 HTTP disconnect 취소와 프로세스 로컬 레지스트리는 계속 동작시키고, 분산 취소 감지 실패를 구조화 메트릭으로 남긴다.

### 취소 인스턴스와 API 상태

취소 endpoint는 먼저 로컬 레지스트리를 취소하고, 성공 여부와 관계없이 DB의 미종결 상태를 `cancel_requested`로 원자 전환한다. 정상적인 다른 인스턴스 전달을 404로 취급하지 않는다.

`POST /v1/questions/{request_id}/cancel`의 응답 계약:

| HTTP | 상태 | 의미와 UI |
|---|---|---|
| 202 | `cancel_requested` | 실행 위치와 무관하게 신호가 기록됨. UI는 즉시 “중지 요청됨” 표시 |
| 200 | `cancelled` | 이미 취소 완료 |
| 200 | `already_finished` | 완료·실패 후 늦은 중지. UI는 기존 결과가 있으면 유지 |
| 202 | `pending_registration` | 질문 등록과 취소가 경합함. tombstone을 먼저 기록해 질문 시작 즉시 취소 |
| 404 | `not_owned` | 다른 사용자 키이거나 노출하면 안 되는 요청. “찾을 수 없음”으로 동일 처리 |
| 503 | `cancel_signal_unavailable` | DB에 신호를 기록하지 못함. UI가 “서버 중지는 확인되지 않음”과 재시도 제공 |

없는 UUID를 곧바로 404로 만들면 등록 경합과 다른 인스턴스를 구분할 수 없다. 인증된 owner의 유효한 UUID에는 만료 시간이 있는 `pending_registration` tombstone을 upsert한다. 이후 질문 등록은 tombstone을 확인하고 검색 전에 취소된다. 익명도 서버가 계산한 동일 일일 owner HMAC 범위에서만 이 동작을 허용한다.

웹은 취소 API를 브라우저 질문 요청의 abort와 독립적으로 전송한다. `202`는 “태스크가 이미 멈췄다”가 아니라 “중지 신호가 안전하게 접수됐다”는 뜻이다. 짧은 상태 조회 또는 질문 응답 종료로 최종 `cancelled`를 확인한다. 확인 시간 제한을 넘으면 완료를 거짓 표시하지 않고 “중지 확인 중”을 유지한다.

## 왜 LISTEN/NOTIFY만 사용하지 않는가

Supavisor transaction mode와 serverless 연결 수명에서는 장기 고정 연결이 필요한 PostgreSQL `LISTEN`을 신뢰할 수 없다. `NOTIFY`도 구독자가 재시작한 동안 발생한 이벤트를 보존하지 않는다. 영속 행을 권위 상태로 두고 짧은 polling을 사용한다. 향후 큐나 realtime을 붙여도 DB 상태는 유실 복구 기준으로 남긴다.

## 제한과 관측

- Python 태스크 취소는 애플리케이션 await를 즉시 중단하지만, upstream 모델 서버가 이미 받은 계산을 과금 전에 항상 회수한다고 보장할 수는 없다. provider가 명시적 generation cancel ID를 제공하면 함께 호출한다.
- Vercel 인스턴스가 강제 종료되면 태스크는 사라진다. TTL 정리기가 오래된 `running`을 `failed` 또는 `expired`로 정리한다.
- watcher는 활성 질문 동안에만 존재하므로 24시간 idle 배포의 조회 수는 0이다. 30초 질문은 500ms에서 약 60회, 기본 2초에서 약 15회 조회한다. 동시 100건이면 약 50 read/s다. Supabase Free는 API 요청 수를 제한하지 않고 uncached egress 5GB를 포함하지만 shared DB CPU에 대한 쿼리 성능 SLA는 없으므로 “무료 보장”으로 해석하지 않는다. cancel 감지 p95와 DB 부하를 측정해 1~5초 범위에서 조정한다.
- 메트릭: cancel 접수→감지 지연, 접수→종결 지연, watcher DB 오류, pending registration, late cancel, orphan execution 수.

## 보안

- 질문 원문, 답변, 인용 원문, IP 원문을 취소 테이블에 저장하지 않는다.
- 모든 조회·갱신은 `owner_hash`와 `request_id`를 함께 사용한다.
- 로그인 사용자의 애플리케이션 인가와 RLS를 모두 검증한다.
- 상태 조회는 다른 사용자의 요청 존재 여부를 드러내지 않는다.

## 결정 기록

| 날짜 | 결정 | 이유 |
|---|---|---|
| 2026-07-18 | sticky routing 없이 Supabase 영속 상태와 작업 인스턴스 watcher를 사용 | Vercel 다중 인스턴스·재시작에서도 취소 의도를 유실하지 않고 기존 Supabase를 공유 조정 저장소로 재사용 |
| 2026-07-18 | 일반적인 다른 인스턴스/등록 경합을 404가 아닌 202로 처리 | 접수 여부를 정확히 표현하고 사용자에게 거짓 실패를 보이지 않기 위해 |
| 2026-07-18 | LISTEN/NOTIFY 단독 사용을 배제 | transaction pooler와 serverless 연결 수명에서 지속 구독 및 이벤트 보존을 보장하지 못함 |
| 2026-07-19 | 분산 watcher 기본 간격을 2초로 완화 | 24시간 서비스의 shared DB 부하를 줄이면서 같은 인스턴스 취소는 기존 로컬 레지스트리로 즉시 유지 |

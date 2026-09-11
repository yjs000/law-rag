# 실험 P: 질문 API 성능 병목 진단·개선

상태: 승인 전 초안 · 방향 승인
작성일: 2026-09-11

## 목적

로컬 통제 환경에서 부하가 증가할 때 가장 먼저 포화되는 프로젝트 구성요소를 찾고, 그 원인을 한 가지씩
개선한 뒤 같은 조건으로 재측정하여 개선 효과와 한계를 증거로 서술한다. 최대 사용자 수 하나를 만드는
것보다 `가설 → 승인 → 실험 → 증거 → 원인 판정 → 개선 → 동일 조건 재측정`의 재현 가능한 기록을 남기는
것이 주목적이다.

Vercel, Supabase hosted project와 NVIDIA hosted NIM에는 어떤 성능 테스트 요청도 보내지 않는다. 외부
무료 tier의 변동과 정책 한계를 프로젝트 코드의 병목으로 오인하지 않도록 API, provider와 저장소를 모두
로컬 통제 대상으로 구성한다. 이 결과는 로컬 병목과 개선 효과를 증명하지만 실제 hosted 환경의 용량이나
사용자 체감 latency를 보장하지 않는다.

## 현재 시스템 경계

- V2 provider phase 전체 timeout은 57초, provider lease 예산은 55초다.
- V2 provider 동시 슬롯 기본값은 3이다.
- 슬롯 admission 실패는 HTTP `503`과 내부 코드 `system_busy`로 응답한다.
- 현재 SSE presentation은 phase 완료를 기다린 뒤 저장된 event를 `StreamingResponse`로 보낸다. 따라서
  현재 구조의 첫 event 시간은 점진적 token streaming 시간이 아니라 phase 완료시간에 가깝다.
- 한 사용자 질문은 routing, embedding, generation 등 복수 provider 호출을 만들 수 있다. 사용자 수와
  provider 호출 수를 같은 값으로 취급하지 않는다.

권위 구현 위치:

- `apps/api/app/settings.py` L41-L50
- `apps/api/app/api/v2/sse.py` L31-L68, L71-L102
- `apps/api/app/observability.py` L131-L153

## 로컬 통제 환경

| 구성요소 | 실험 구성 | 통제 목적 |
|---|---|---|
| API | local FastAPI process | Vercel cold start·함수 제한 제외 |
| provider | 고정 정상 schema를 반환하는 fake adapter | NVIDIA queue·429·503·timeout 제외 |
| provider latency | 가설에 명시한 고정값 또는 seed가 고정된 분포 | latency 조건 재현 |
| 저장소 | in-memory fixture 또는 승인된 일회성 local PostgreSQL | Supabase shared CPU·network 제외 |
| 부하 발생기 | 같은 PC의 k6와 SSE 측정 client | 외부 network jitter 제외 |

기본 실행은 외부 network egress가 없는 in-memory 저장소로 시작한다. PostgreSQL 고유 병목을 검증하는
가설이 승인된 경우에만 일회성 local PostgreSQL을 사용한다. 저장소 정책에 따라 상주형 Docker·DB 기동은
가설 승인과 별도로 명시적 실행 승인을 받아야 한다.

## 가설 승인 계약

가설은 에이전트가 제안할 수 있지만 사용자 승인 전에는 구현, 부하 실행 또는 결과 판정을 시작하지 않는다.
한 번 승인된 가설도 독립변수, 부하 상한, 지속시간, 저장소 종류나 완료조건이 바뀌면 다시 승인받는다.

각 가설은 다음 형식으로 먼저 제안한다.

| 필드 | 기록 내용 |
|---|---|
| hypothesis_id | `P-H01`처럼 변경되지 않는 ID |
| 가설 | 원인과 관측 가능한 결과를 포함한 한 문장 |
| 근거 | 코드 위치 또는 이전 측정값 |
| 독립변수 | 이번에 바꾸는 한 가지 조건 |
| 통제변수 | 동일하게 유지할 조건 |
| workload ceiling | 최대 VU/RPS, 지속시간과 총 요청 수 |
| 예상 증거 | 가설을 지지·기각할 지표와 방향 |
| 중단 조건 | 오류, CPU, memory, 시간 등 안전 상한 |
| 승인 | `Pending` 또는 사용자 승인 문구·날짜 |

가설 승인 뒤에도 결과를 가설에 맞춰 해석하지 않는다. 예상 방향과 반대 결과도 그대로 보존하고 가설을
`Supported`, `Rejected`, `Inconclusive` 중 하나로 판정한다.

## 실험 기록 순서

1. **관찰**: 아직 원인을 단정하지 않고 baseline 증상과 측정 조건을 기록한다.
2. **가설 제안**: 병목 후보 한 개와 반증 가능한 예상 결과를 쓴다.
3. **사용자 승인**: 가설, 부하 상한, 중단 조건을 사용자가 승인한다.
4. **통제 실험**: 한 번에 독립변수 하나만 바꾸고 raw 결과를 원자적으로 저장한다.
5. **증거**: client latency, stage timing, 자원 사용량과 오류 분류를 같은 run ID로 결박한다.
6. **원인 판정**: 가설을 지지·기각·미결정으로 판정하고 대안 설명을 남긴다.
7. **개선**: 증거가 가리키는 최소 변경을 별도 구현 절차로 수행한다.
8. **동일 조건 재측정**: 변경 전과 같은 workload·fixture·seed·환경에서 다시 실행한다.
9. **결론**: 효과 크기, 회귀, 비용과 hosted 환경으로 일반화할 수 없는 한계를 함께 쓴다.

## 측정 대상 사용자 여정

### 시나리오 S0: 비모델 기준선

- `GET /health`
- 준비된 local corpus에서 `POST /v2/search`
- 목적: API와 저장소 기준선을 provider latency와 분리한다.

### 시나리오 S1: V2 질문 전체 여정

1. `POST /v2/question-executions`
2. `POST /v2/question-executions/{execution_id}/core`
3. 필요 시 `POST /v2/question-executions/{execution_id}/finalize`
4. 필수 SSE event와 최종 실행 상태 검증

모든 요청은 고정된 합성 `scenario_id`를 사용하고 실제 개인 사건자료를 보내지 않는다. 같은 execution ID를
여러 VU가 재사용하지 않는다.

## 공통 지표와 결과 분류

### 입력 부하

- configured VU, active VU, 목표·실제 RPS/RPM
- 최대 동시 HTTP 요청과 최대 동시 provider phase
- 시작하지 못한 iteration 수
- 단계별 지속시간과 think time

### 응답시간

- prepare, core, finalize와 전체 journey의 p50/p95/p99/max/count
- HTTP TTFB, 첫 SSE event, 전체 body/phase 완료시간
- 서버 stage timing: routing, embedding, retrieval, answer generation, validation
- fake provider 설정 latency와 애플리케이션 추가 overhead

### 결과

- `journey_success`: 필수 event와 최종 정상 상태를 모두 만족
- `expected_busy`: 정확한 `503 system_busy`
- `unexpected_failure`: 5xx, 연결 중단, invalid SSE/schema, 서버 timeout

`expected_busy`를 애플리케이션 결함률에 섞지 않되 전체 요청 중 거절된 비율은 별도로 기록한다.

### 생존과 회복

- local API process 종료·재시작·OOM 수
- CPU·메모리·event loop 사용량
- local 저장소의 connection pool·lock 사용량과 대기 또는 in-memory queue 깊이
- provider lease used/free slot
- 부하 종료 뒤 health 성공시간
- 부하 종료 뒤 단일 S1 latency가 baseline 허용 범위로 돌아오는 시간

## 후보 부하 단계

모든 단계는 승인된 가설 하나에 종속된다. 아래 값은 후보 기본값이며 실제 실행값이 아니다. 사용자는 실행
전에 가설과 함께 최대 VU/RPS, 지속시간, 총 요청 수와 중단 조건을 승인한다.

| 단계 | 후보 부하 | 후보 지속시간 | 목적 |
|---|---:|---:|---|
| Smoke | 1 VU, 1 journey | 1회 | harness와 성공 판정 검증 |
| Baseline | 1 VU | 5분 | 단일 요청 분포 |
| Slot boundary | active provider phase 1→2→3 | 각 10분 | 설계 용량 안의 안정성 |
| Admission boundary | 4→6→10 | 각 10분 | busy 경계와 보호 동작 |
| Open-model load | baseline에서 단계적 RPS 증가 | 각 10분 | coordinated omission 없는 포화점 |
| Spike | 0→6 active phase | 2분 | 급증과 거절 동작 |
| Soak | 2 active phase | 1~2시간 | 누수와 점진적 저하 |
| Recovery | 부하 제거 뒤 S0/S1 단건 | 회복까지 | 정상화 시간 |

## 공통 안전·판정 기준

- active provider phase 1~3에서 `expected_busy=0`
- `unexpected_failure_rate < 1%`, timeout·process 종료·OOM `= 0`
- phase p95가 55초 provider 예산을 넘지 않음
- active provider phase 4 이상에서는 `expected_busy`를 허용하되 이미 승인된 작업의 실패율과 latency가
  1~3단계 기준을 유지
- 부하 종료 뒤 health와 단일 journey가 합의된 회복시간 안에 baseline 범위로 복귀

이 기준은 harness의 기본 안전 계약일 뿐 개별 가설의 성공 기준을 대신하지 않는다. 각 가설은 변경 전후에
기대하는 효과 크기와 허용 회귀를 별도로 승인받는다.

## 결과 서술 형식

각 가설은 하나의 결과 문서에서 다음 순서로 서술한다.

```text
1. 관찰한 문제와 baseline
2. 사용자 승인 가설과 승인 시각
3. 통제변수·독립변수·부하·중단 조건
4. 실행 명령, Git SHA, runtime과 fixture fingerprint
5. raw evidence와 요약 지표
6. Supported / Rejected / Inconclusive 판정과 대안 설명
7. 증거가 가리킨 최소 개선
8. 동일 조건 before/after와 효과 크기
9. 회귀·비용·로컬 결과의 일반화 한계
```

좋은 결론은 `빨라졌다`가 아니라 다음 구조를 갖는다.

```text
승인된 P-Hxx 조건에서 병목 지표 A가 X에서 Y로 변했고 전체 p95가 M에서 N으로 변했다.
다른 공통 지표의 허용 회귀는 없었다. 이 결과는 로컬 통제 환경에 한정되며 hosted 환경 용량을 보장하지 않는다.
```

## 도구와 결과 저장

- k6: closed/open workload, HTTP 지표, threshold, JSON/CSV 출력
- 작은 SSE 측정 client: 첫 event·event 순서·종료 event 검증
- 기존 stage timing log: 닫힌 stage/outcome과 정수 latency만 집계
- local process metric: CPU, memory, restart, local DB/queue와 provider lease

작은 요약은 `docs/generated/experiment-p-performance-<run-id>.md`에 생성 명령과 기준 시점을 머리에 적어
보관한다. 큰 원시 시계열은 `.data/experiments/p-performance/<run-id>/`에 두고 Git에 커밋하지 않는다.
요약에는 raw artifact path와 SHA-256을 남긴다.

최소 run metadata:

```text
run_id, hypothesis_id, hypothesis_approval, started_at, git_sha
operating_system, runtime_versions, provider_fake_profile, provider_slots, repository_mode
scenario, workload_model, target_vus, target_rate, duration, think_time
request_count, admitted_count, success_count, busy_count, unexpected_failure_count
latency_count, p50, p95, p99, max, resource_peaks, recovery_seconds
hypothesis_verdict, before_run_id, after_run_id, effect_size, limitations
```

질문 원문, 법률 근거 원문, 인증정보, 사용자 식별자와 raw exception은 log와 artifact에서 제외한다.

## 권한·외부 경계

사용자는 2026-09-11에 로컬 전용 방향과 가설별 사전 승인 원칙을 승인했다. 이는 특정 가설, 부하 상한,
Docker·상주형 DB 실행이나 구현 변경을 승인한 것은 아니다.

| Boundary | Destination or resource | Operation | Data/credential involved | Mutation/retention | Purpose | Status and date | Runtime gate |
|---|---|---|---|---|---|---|---|
| 로컬 문서 | 이 저장소 `docs/` | 문서 생성·수정 | 없음 | Git working tree에 보존 | 개념·전략 기록 | Approved — 사용자 요청, 2026-09-11 | 없음 |
| 로컬 가설 설계 | 저장소 코드·기존 로컬 결과 read-only | 가설·부하·중단 조건 제안 | 비밀·개인자료 없음 | 가설 문서에 보존 | 승인 가능한 실험 정의 | Approved — 방향 승인, 2026-09-11 | 가설마다 사용자 승인 필요 |
| 로컬 통제 부하 | local API, in-memory fixture, fake provider | process 실행·합성 요청 | 합성 scenario ID | `.data/experiments/` raw와 생성 요약 | 승인된 가설 검증 | Pending | 가설·VU/RPS·시간·총량·중단 조건 승인 |
| 로컬 일회성 DB | 명시할 local PostgreSQL test DB | schema 생성·합성 row 쓰기·정리 | 로컬 test credential | 실험 뒤 승인된 범위 정리 | PostgreSQL 병목 검증 | Pending | 가설 승인과 Docker/DB 기동 승인 |
| Vercel | Preview·Production 전체 | 모든 자동 성능 요청 | 없음 | 없음 | 범위 제외 | Denied — 로컬 전용 요청, 2026-09-11 | 새 사용자 승인 없이는 금지 |
| Supabase hosted | 모든 remote project | 성능 목적 요청·DB 쓰기·조회 | 없음 | 없음 | 범위 제외 | Denied — 로컬 전용 요청, 2026-09-11 | 새 사용자 승인 없이는 금지 |
| NVIDIA hosted NIM | `https://integrate.api.nvidia.com/v1` | inference 요청 | 없음 | 없음 | fake provider로 대체 | Denied — 로컬 전용 요청, 2026-09-11 | 새 사용자 승인 없이는 금지 |
| 외부 관측 저장소 | 모든 remote metric/log backend | metric·log 전송 | 없음 | 없음 | local artifact로 대체 | Denied — 로컬 전용 요청, 2026-09-11 | 새 사용자 승인 없이는 금지 |

## 결정 기록

- 2026-09-11: 재사용 가능한 성능 개념은 `docs/learning/07-performance-testing.md`, 이 서비스의 구체적
  실험 전략은 이 문서, 실행 수치는 `docs/generated/` 요약과 local raw artifact로 분리한다.
- 2026-09-11: provider 슬롯 3의 경계와 provider 호출률은 별도다. 사용자 수를 바로 호출률로 바꾸지 않고
  journey당 실제 provider 호출 수와 latency를 측정한다.
- 2026-09-11: 사용자가 방향 수정을 승인했다. 모든 성능 실험은 로컬 API·fake provider·로컬 저장소에서만
  수행하고 Vercel, Supabase hosted와 NVIDIA hosted NIM에는 성능 요청을 보내지 않는다.
- 2026-09-11: 실험의 주목적을 최대 사용자 수 하나의 산출에서 프로젝트 병목의 가설·증거·개선·재측정
  과정 기록으로 바꿨다. 에이전트가 제안한 모든 가설은 구체적 부하 상한과 함께 사용자 승인을 받은 뒤에만
  실행한다.

## 참고 자료

- [Grafana k6: 결과 출력](https://grafana.com/docs/k6/latest/get-started/results-output/)
- [Prometheus: histograms and summaries](https://prometheus.io/docs/practices/histograms/)

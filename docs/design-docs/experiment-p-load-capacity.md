# 실험 P: 질문 API 부하·용량·회복 성능

상태: 승인 전 초안
작성일: 2026-09-11

## 목적

동시 사용자와 요청 유입률이 증가할 때 질문 API가 어느 범위까지 응답시간과 정상 완료율을 유지하고,
용량을 넘으면 서버가 죽지 않은 채 설명 가능한 방식으로 거절하며, 부하가 줄어든 뒤 정상 상태로
회복하는지 측정한다.

이 실험은 다음 두 질문을 분리한다.

1. **애플리케이션 자체 용량**: NVIDIA가 정상 응답한다고 통제했을 때 Web/API/DB/SSE/동시성 제한이
   얼마나 처리하는가?
2. **실제 사용자 체감**: 무료 NVIDIA hosted NIM의 queue·공유 worker·rate limit·timeout 변동까지
   포함했을 때 사용자가 실제로 얼마나 기다리고 실패하는가?

두 결과를 하나의 latency 분포로 합치지 않는다.

## 현재 시스템 경계

- V2 provider phase 전체 timeout은 57초, provider lease 예산은 55초다.
- V2 provider 동시 슬롯 기본값은 3이다.
- 슬롯 admission 실패는 HTTP `503`과 내부 코드 `system_busy`로 응답한다.
- 현재 SSE presentation은 phase 완료를 기다린 뒤 저장된 event를 `StreamingResponse`로 보낸다. 따라서
  현재 구조의 첫 event 시간은 점진적 token streaming 시간이 아니라 phase 완료시간에 가깝다.
- 한 사용자 질문은 routing, embedding, generation 등 복수 NVIDIA 호출을 만들 수 있다. provider RPM은
  사용자 수가 아니라 실제 provider 호출 수를 기준으로 해석한다.

권위 구현 위치:

- `apps/api/app/settings.py` L41-L50
- `apps/api/app/api/v2/sse.py` L31-L68, L71-L102
- `apps/api/app/observability.py` L131-L153

## NVIDIA NIM 가정 검토

### 확인된 것

- NVIDIA Developer Program은 API Catalog의 hosted NIM을 무료로 사용할 수 있다고 안내한다.
- 40 RPM은 NVIDIA 포럼과 이 저장소의 과거 조사에서 반복 관측된 무료 tier 계정 제한이지만, 모든 모델과
  시점에 적용되는 고정 SLA로 공식 문서화된 값은 아니다.
- 이 저장소는 `429` 외에도 `503 ResourceExhausted: Worker local total request limit reached`와 timeout을
  실제 관측했다. 이는 계정 RPM과 별개로 무료 hosted endpoint의 공유 worker 용량이 결과에 영향을 줄 수
  있음을 보여준다.

### 확인되지 않은 것

- NVIDIA가 모든 요청을 단일 FIFO queue에 넣어 반드시 하나씩 처리한다는 계약
- 40 RPM 이하의 요청은 반드시 정상 완료한다는 보장
- 무료 endpoint의 고정 latency, 가용성 SLA와 queue 최대 대기시간
- 현재 계정·현재 모델에 항상 동일하게 적용되는 정확한 RPM

따라서 `NVIDIA는 정상 응답한다`는 문장은 **통제 실험의 가정**으로는 사용하지만, live end-to-end 실험의
사실이나 서비스 보장으로 사용하지 않는다. `40 RPM`도 초당 처리량이나 동시 처리량으로 환산하지 않는다.

### 실험에서의 처리

| 트랙 | NVIDIA 처리 | 답하는 질문 | latency 판정 |
|---|---|---|---|
| P-A 통제 provider | 고정된 정상 schema를 반환하는 fake adapter; 지연 profile도 고정 | 애플리케이션과 DB의 고유 용량 | 자동 Pass/Fail 가능 |
| P-B live provider | 실제 `https://integrate.api.nvidia.com/v1` 호출 | 실제 무료 tier 사용자 경험 | provider 결과별 층화 후 판정 |

P-B에서는 각 실행에 `provider_status`, 안전한 `provider_outcome`, 호출 횟수, 재시도 횟수, 시작 시각,
응답 header에 실제 존재할 때만 rate-limit/retry-after 값을 기록한다. 질문·근거 원문, API key와 raw
exception은 기록하지 않는다.

## 측정 대상 사용자 여정

### 시나리오 S0: 비모델 기준선

- `GET /health`
- 준비된 corpus에서 `POST /v2/search`
- 목적: 네트워크/API/DB 기준선을 provider latency와 분리한다.

### 시나리오 S1: V2 질문 전체 여정

1. `POST /v2/question-executions`
2. `POST /v2/question-executions/{execution_id}/core`
3. 필요 시 `POST /v2/question-executions/{execution_id}/finalize`
4. 필수 SSE event와 최종 실행 상태 검증

모든 요청은 고정된 합성 `scenario_id`를 사용하고 실제 개인 사건자료를 보내지 않는다. 같은 execution ID를
여러 VU가 재사용하지 않는다.

## 지표와 결과 분류

### 입력 부하

- configured VU, active VU, 목표·실제 RPS/RPM
- 최대 동시 HTTP 요청과 최대 동시 provider phase
- 시작하지 못한 iteration 수
- 단계별 지속시간과 think time

### 응답시간

- prepare, core, finalize와 전체 journey의 p50/p95/p99/max/count
- HTTP TTFB, 첫 SSE event, 전체 body/phase 완료시간
- 서버 stage timing: routing, embedding, retrieval, answer generation, validation
- provider 호출별 latency와 전체 provider 대기 비중

### 결과

- `journey_success`: 필수 event와 최종 정상 상태를 모두 만족
- `expected_busy`: 정확한 `503 system_busy`
- `provider_limited`: provider `429`, `503 ResourceExhausted`, provider timeout
- `unexpected_failure`: 그 밖의 5xx, 연결 중단, invalid SSE/schema, 서버 timeout

`expected_busy`와 `provider_limited`를 애플리케이션 결함률에 섞지 않는다. 실제 사용자 성공률에는 둘 다
영향을 주므로 별도 합계인 `user_visible_non_success_rate`도 기록한다.

### 생존과 회복

- 서버 instance restart·OOM 수
- CPU·메모리·event loop·DB pool 사용량과 대기
- provider lease used/free slot
- 부하 종료 뒤 health 성공시간
- 부하 종료 뒤 단일 S1 latency가 baseline 허용 범위로 돌아오는 시간

## 부하 단계

P-A와 P-B 모두 먼저 smoke를 통과해야 다음 단계로 간다. P-B는 무료 외부 용량과 비용·egress 승인을
보호하기 위해 아래 전체 stress를 그대로 실행하지 않고 별도 제한 범위를 승인받는다.

| 단계 | 기본 부하 | 지속시간 | 목적 |
|---|---:|---:|---|
| Smoke | 1 VU, 1 journey | 1회 | 스크립트·성공 판정 검증 |
| Baseline | 1 VU | 5분 | 단일 요청 분포 |
| Slot boundary | active provider phase 1→2→3 | 각 10분 | 설계 용량 안의 안정성 |
| Admission boundary | 4→6→10 | 각 10분 | busy 경계와 보호 동작 |
| Open-model load | 측정한 baseline에서 단계적 RPS 증가 | 각 10분 | coordinated omission 없는 최대 처리량 |
| Spike | 0→6 active phase | 2분 | 급증과 거절 동작 |
| Soak | 2 active phase | 1~2시간 | 누수와 점진적 저하 |
| Recovery | 부하 제거 뒤 S0/S1 단건 | 회복까지 | 정상화 시간 |

P-B live provider의 최초 범위는 smoke와 active provider phase 1·2·3·4의 짧은 표본으로 제한한다. 실제
호출 수는 `사용자 journey 수 × journey당 provider 호출 수`이므로 실행 전 최대 호출 수를 계산한다.

## 최초 판정 기준

실측 전 임시 기준이며 baseline 뒤 날짜를 붙여 확정한다.

### P-A 통제 provider

- active provider phase 1~3에서 `expected_busy=0`
- `unexpected_failure_rate < 1%`, timeout·restart·OOM `= 0`
- phase p95가 55초 provider 예산을 넘지 않음
- active provider phase 4 이상에서는 `expected_busy`를 허용하되 이미 승인된 작업의 실패율과 latency가
  1~3단계 기준을 유지
- 부하 종료 뒤 health와 단일 journey가 합의된 회복시간 안에 baseline 범위로 복귀

### P-B live provider

- 애플리케이션 자체 `unexpected_failure`는 P-A 기준을 적용
- provider latency는 1회 실행 절대값으로 Pass/Fail하지 않고 시간대·provider outcome별 표본 수와
  p50/p95/p99를 기록
- `429`, provider `503`, timeout이 있으면 정상 성공 표본에 섞지 않고 비율과 발생 구간을 보고
- 실제 사용자 관점의 `journey_success_rate`와 provider를 제외한 애플리케이션 성공률을 함께 보고

무료 provider의 변동이 큰 상태에서 P-B latency만으로 local slot 수를 조정하지 않는다. 먼저 P-A에서
애플리케이션 용량을 확정하고 P-B는 외부 의존성 포함 사용자 경험으로 해석한다.

## 도구와 결과 저장

- k6: closed/open workload, HTTP 지표, threshold, JSON/CSV 출력
- 작은 SSE 측정 client: 첫 event·event 순서·종료 event 검증
- 기존 stage timing log: 닫힌 stage/outcome과 정수 latency만 집계
- 배포 환경 metric: CPU, memory, restart, DB pool과 provider lease

작은 요약은 `docs/generated/experiment-p-performance-<run-id>.md`에 생성 명령과 기준 시점을 머리에 적어
보관한다. 큰 원시 시계열과 dashboard export는 `.data/experiments/p-performance/<run-id>/` 또는 CI
artifact에 두고 Git에 커밋하지 않는다. 요약에는 원시 artifact URI/path와 SHA-256을 남긴다.

최소 run metadata:

```text
run_id, started_at, git_sha, environment, server_region, load_generator_region
provider_track, provider_endpoint, provider_model, provider_slots
scenario, workload_model, target_vus, target_rate, duration, think_time
request_count, provider_call_count, admitted_count, success_count
busy_count, provider_limited_count, unexpected_failure_count
latency_count, p50, p95, p99, max, recovery_seconds, verdict
```

## 권한·외부 경계

이 문서 작성은 로컬 문서만 바꾼다. 실제 실험 실행 전 아래 `Pending` 항목을 한 번에 승인받아야 한다.

| Boundary | Destination or resource | Operation | Data/credential involved | Mutation/retention | Purpose | Status and date | Runtime gate |
|---|---|---|---|---|---|---|---|
| 로컬 문서 | 이 저장소 `docs/` | 문서 생성·수정 | 없음 | Git working tree에 보존 | 개념·전략 기록 | Approved — 사용자 요청, 2026-09-11 | 없음 |
| 로컬 통제 부하 | local API와 fake NVIDIA adapter | process 실행·합성 요청 | 합성 scenario ID | 로컬 임시 실행·artifact | P-A 용량 측정 | Pending | 테스트 실행 전 승인 |
| Preview API | 미정 Vercel Preview URL | 부하 요청 | 합성 질문·테스트 auth | Vercel log와 compute 사용 | 배포 경로 측정 | Pending | 정확한 URL·상한 승인 |
| 개발 DB | 미정 Supabase 개발 project | execution/event/history 쓰기·조회 | 합성 실행 데이터, DB credential | 테스트 row 보존·후속 정리 | DB 포함 성능 측정 | Pending | project·table·정리 범위 승인 |
| NVIDIA hosted NIM | `https://integrate.api.nvidia.com/v1`, configured model | inference 요청 | NVIDIA API key, 합성 질문과 검색 근거 | NVIDIA 측 처리·로그 정책 적용 | P-B 실제 사용자 경험 | Pending | 최대 호출 수·데이터 범위 승인 |
| 관측 저장소 | 미정 metric/log backend | metric·안전한 분류 log 쓰기 | request ID, stage/outcome/latency | backend 정책에 따라 보존 | 병목 상관분석 | Pending | 목적지·보존기간 승인 |
| Production | 운영 URL·운영 DB | 부하·쓰기 | 운영 credential·합성 실행 | 실제 사용자·비용에 영향 가능 | 운영 검증 | Pending | 별도 명시 승인 필수 |

## 결정 기록

- 2026-09-11: 재사용 가능한 성능 개념은 `docs/learning/07-performance-testing.md`, 이 서비스의 구체적
  부하 전략은 이 실험 문서, 실행 수치는 `docs/generated/` 요약과 외부 raw artifact로 분리한다.
- 2026-09-11: NVIDIA 정상 응답은 P-A 통제 실험에서만 가정한다. P-B에서는 무료 hosted endpoint의
  queue·공유 worker·429·503·timeout을 사용자 체감의 일부로 별도 층화한다.
- 2026-09-11: 40 RPM은 보편적 공식 SLA나 단일 FIFO 처리 보장으로 취급하지 않고, 실제 계정·모델의
  응답과 header를 실행마다 기록한다.
- 2026-09-11: provider 슬롯 3의 경계와 provider 호출률은 별도다. 사용자 수를 바로 RPM으로 바꾸지 않고
  journey당 실제 provider 호출 수와 호출 latency를 측정한다.

## 근거

- [NVIDIA NIM VLM 문서: Developer Program과 API Catalog 접근](https://docs.nvidia.com/nim/vision-language-models/latest/examples/kimi-k2.5/api.html)
- [NVIDIA 포럼: 무료 tier 40 RPM 상향 요청 사례](https://forums.developer.nvidia.com/t/request-to-increase-nim-rate-limit-from-40-rpm-to-200-rpm/373499)
- [NVIDIA 포럼: worker local total request limit 관측](https://forums.developer.nvidia.com/t/resourceexhausted-worker-local-total-request-limit-reached-33-32/375518)
- `docs/exec-plans/completed/0028-pre-retrieval-question-routing.md` L450-L500 — 이 저장소의 실제
  `503 ResourceExhausted`, timeout과 재시도 관측
- [Grafana k6: 결과 출력](https://grafana.com/docs/k6/latest/get-started/results-output/)
- [Prometheus: histograms and summaries](https://prometheus.io/docs/practices/histograms/)

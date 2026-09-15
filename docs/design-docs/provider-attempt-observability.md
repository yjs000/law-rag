# NVIDIA provider 시도별 관측과 실패 분류

## 상태

승인 — 2026-09-15. 사용자는 모든 NVIDIA 호출의 제한된 재시도에서 발생한 실패를 Vercel 구조화
로그에 시도별로 모두 남기고, 상세 실패 이력은 운영자에게만 공개하는 설계를 승인했다. DB 영속화와
외부 telemetry 도입은 제외한다.

## 문제

`NvidiaNimAnswerer`는 하나의 전체 timeout 안에서 최대 횟수만큼 provider 호출을 재시도한다. 하지만
현재 HTTP client 로그만으로는 다음 사실을 execution 단위로 확정할 수 없다.

- 실제로 몇 번 시도했는가
- 각 시도가 HTTP 오류, timeout, 연결 실패, 응답 검증 실패 중 무엇으로 끝났는가
- 실패 뒤 재시도가 예정됐는가
- 최초 503 뒤 남은 예산에서 재시도가 timeout됐는가

또한 V2 core coordinator의 catch-all은 provider 호출 실패와 생성된 draft의 grounding 실패를 모두
`core_repair_required`로 바꾼다. 이 때문에 provider가 draft를 반환하지 못한 장애도 최종적으로
`grounding_failed`처럼 보일 수 있다.

## 목표

1. 재시도 제한이 적용되는 모든 NVIDIA 호출의 각 시도 결과를 Vercel JSON 로그 한 줄로 남긴다.
2. 실패 뒤 성공한 경우에도 앞선 모든 실패 기록을 보존한다.
3. provider 소진 실패와 draft grounding 실패를 실행 상태와 사용자 안내에서 구분한다.
4. 질문, prompt, 검색 근거, 인증정보, 예외 메시지를 로그에 남기지 않는다.

## 비목표

- 시도 이력을 `question_execution_issues` 또는 다른 DB 테이블에 저장하지 않는다.
- migration을 추가하지 않는다.
- 재시도 횟수, timeout, provider 또는 모델을 이번 변경에서 조정하지 않는다.
- 자동으로 새 execution을 만들어 adapter 내부 재시도와 중첩하지 않는다.
- 외부 observability 서비스나 비용이 드는 telemetry backend를 도입하지 않는다.
- 배포, 운영 smoke test, NVIDIA 실호출은 이 설계의 로컬 구현 범위에 포함하지 않는다.

## 공통 관측 계약

API observability 경계에 닫힌 schema의 `ProviderAttemptEvent`와 전용
`law_rag.provider_attempt` logger를 둔다. adapter는 시도가 끝나는 즉시 이벤트를 출력한다. phase가
나중에 성공, fallback 또는 terminal error로 끝나는지와 무관하게 이미 출력한 실패 로그는 유지된다.

| 필드 | 계약 |
| --- | --- |
| `correlation` | client request ID 또는 execution ID를 SHA-256으로 해시한 앞 16자리 |
| `provider` | 현재는 닫힌 값 `nvidia` |
| `operation` | `route`, `query_embedding`, `answer_core`, `answer_detail`, `clarification` |
| `attempt` | 1부터 시작하는 현재 시도 번호 |
| `max_attempts` | 해당 adapter 호출의 전체 허용 시도 수 |
| `outcome` | `succeeded` 또는 `failed` |
| `failure_kind` | 성공이면 `null`, 실패면 아래 닫힌 분류 중 하나 |
| `upstream_status` | HTTP 상태 코드가 있을 때만 정수, 그 외 `null` |
| `elapsed_ms` | 현재 시도가 소비한 단조 시계 기준 밀리초 |
| `remaining_ms` | adapter 전체 deadline에서 남은 밀리초, 0 이상으로 고정 |
| `retry_scheduled` | 현재 실패 뒤 같은 adapter 호출 안에서 다음 시도를 시작할지 여부 |

성공 이벤트도 남겨 `attempt` 값으로 실제 총 시도 횟수를 확정한다. 모든 adapter는 호출별
`max_attempts`가 1인 경우에도 성공 또는 실패 이벤트 하나를 남긴다.

## 실패 분류

`failure_kind`는 예외 문자열이 아니라 예외 타입과 정수 `status_code`만으로 결정한다.

| 분류 | 조건 |
| --- | --- |
| `provider_http` | provider가 HTTP 오류 응답을 반환함 |
| `timeout` | application 또는 HTTP client timeout |
| `connection` | provider 연결·전송 실패 |
| `invalid_response` | choices/content 등 provider 응답 구조가 비어 있거나 잘못됨 |
| `schema_validation` | guided JSON 결과가 닫힌 schema를 만족하지 못함 |
| `cancelled` | 상위 요청 취소로 시도가 중단됨 |
| `unknown` | 위 분류에 속하지 않는 마지막 방어 경계 |

402와 429는 현재 계약대로 재시도하지 않으며 `provider_http`, 해당 상태 코드,
`retry_scheduled=false`를 기록한다. 5xx는 현재 adapter의 횟수와 전체 deadline 안에서만 재시도한다.
timeout이나 연결 실패도 같은 기존 정책을 유지한다.

## 호출 범위와 correlation

다음 NVIDIA 경계를 모두 같은 이벤트 schema로 계측한다.

- 질문 route 분류
- query embedding
- core 답변 생성
- detail 답변 생성
- clarification 해석 또는 생성

V2 prepare처럼 execution ID가 아직 만들어지지 않은 단계도 있으므로 client request ID를 공통 correlation
원본으로 사용한다. application 계층이 async-safe 호출 context에 원본 ID를 설정하고 logger는 해시만
출력한다. 공유 adapter나 동시 요청 사이에 correlation이 섞이지 않도록 전역 가변 문자열을 사용하지
않고 명시적 호출 context 또는 `ContextVar` 기반 scope를 사용한다.

## V2 실패 상태 계약

provider가 모든 시도를 소진해 draft를 만들지 못한 경우와 draft를 만든 뒤 grounding 검증에 실패한
경우를 분리한다.

1. provider HTTP, timeout 또는 connection 소진은 `provider_unavailable` terminal error다.
2. core provider 소진은 `core_repair_required`로 전환하지 않는다. 검증하거나 repair할 draft가 없기
   때문이다.
3. Web은 상세 실패를 표시하지 않고 "AI 제공자를 일시적으로 사용할 수 없습니다. 다시 시도해 주세요."
   라는 안전 안내만 제공한다.
4. schema·citation·문장 grounding처럼 draft가 존재한 뒤의 검증 실패만 기존
   `core_repair_required → repair_core` 경로를 사용한다.
5. coordinator catch-all은 `unknown` terminal 로그를 남기는 마지막 방어선으로 유지한다.
6. Web은 새 execution을 자동 생성하지 않는다. 사용자가 다시 시도할 때만 기존 제출 흐름으로 새
   execution을 만든다.

라우터, embedding, clarification의 기존 안전 fallback 정책은 바꾸지 않는다. 다만 각 adapter의 실제
provider 시도와 소진 원인은 동일한 로그로 관측할 수 있어야 한다.

## 개인정보와 보안

이 이벤트 schema는 extra field를 거부한다. 다음 값은 필드로 받을 수 없고 logger 호출부에서도
전달하지 않는다.

- 질문과 대화 내용
- system/user prompt
- 검색 hit, 법령 원문, citation quote
- 이메일, 사용자 ID, IP
- API key, Authorization header, cookie
- provider 응답 본문
- 예외 메시지와 traceback

Vercel 로그 보존기간이 지나면 이 시도 이력은 복구할 수 없다. 이는 DB에 영속화하지 않기로 한
사용자 선택의 명시적 trade-off다.

## 구현 경계

예상 변경 범위는 다음과 같다. 세부 줄 범위와 태스크는 후속 실행계획 `0072`에서 확정한다.

- `apps/api/app/observability.py` 또는 작은 전용 모듈: 닫힌 이벤트 모델, 분류기, logger
- `apps/api/app/adapters/nvidia_nim_*.py`: 시도별 계측
- `apps/api/app/application/v2/phase_service.py`: provider 소진과 grounding 실패 분리
- `apps/api/app/application/question_phase_coordinator.py`: typed failure와 catch-all terminal 관측
- `apps/web/lib/v2-execution.ts`, `apps/web/app/page.tsx`: 안전한 provider 불가 안내
- 관련 API/Web 단위·통합 테스트와 운영 문서

## 검증

- `503 → timeout → 성공`: 실패 두 건과 성공 한 건의 순서·필드 검증
- 최대 시도 전부 실패: 각 실패와 terminal 소진 로그 검증
- 402/429: 한 번만 기록하고 재시도하지 않음
- provider 실패가 `grounding_failed` 또는 `repair_core`로 바뀌지 않음
- 실제 draft grounding 실패만 `repair_core`로 진행됨
- route, query embedding, core, detail, clarification operation별 로그 검증
- 금지 필드와 임의 extra field 거부 검증
- API 관련 회귀, Web 관련 회귀, `scripts/verify.ps1`, 독립 whole-branch review

## 승인된 작업 경계

| Boundary | Destination or resource | Operation | Data/credential involved | Mutation/retention | Purpose | Status and date | Runtime gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Harness and local tools | 설치된 execution harness와 저장소 검증 스크립트 | 로컬 task/evidence 기록과 테스트 실행 | 목표·테스트 결과; credential 없음 | 로컬 harness 상태와 테스트 산출물 | 작은 검증 창과 완료 증거 유지 | Approved — 2026-09-15, 사용자가 Superpowers와 roadmap-operator 사용을 승인 | 실행 시 사용 가능한 MCP 또는 direct script를 확인 |
| Repository | `C:\development\git\law-rag` | 설계, 실행계획, 코드, 테스트, 문서 편집 및 로컬 커밋 | 저장소 소스와 공개 테스트 fixture | Git 추적 파일과 로컬 commit | 승인 설계 구현 | Approved — 2026-09-15 | push/PR은 별도 승인 필요 |
| Vercel runtime logging | 배포 후 `law_rag.provider_attempt` 표준 출력 | 애플리케이션 실행 중 구조화 로그 출력 | 해시 correlation과 닫힌 시도 metadata만 | Vercel이 현재 프로젝트 정책에 따라 보존; DB 영속화 없음 | provider 재시도 추적 | Approved design — 2026-09-15 | 이번 로컬 구현에서는 배포·운영 로그 조회를 실행하지 않음 |
| External provider | NVIDIA `https://integrate.api.nvidia.com/v1` | 로컬 구현·단위 테스트에서는 호출하지 않음 | 없음 | 없음 | 외부 호출 없는 결정적 검증 | Not required | 운영 smoke가 필요해지면 별도 승인 |
| Database | Supabase 및 `question_execution_issues` | 읽기·쓰기·migration 모두 실행하지 않음 | 없음 | 없음 | 로그 전용 설계 유지 | Not required | DB persistence 요구가 생기면 재설계·재승인 |
| Release | Vercel 배포, Git push, PR | 실행하지 않음 | 없음 | 원격 변경 없음 | 로컬 구현 범위 제한 | Not required | 별도 사용자 승인 필요 |
| Graphify | 기존 `graphify-out/` dirty 산출물 | 갱신·커밋하지 않음 | 기존 사용자 변경 | 변경 없음 | 다른 작업 산출물과 혼합 방지 | Not required | 통합 대상 브랜치 소유자가 별도 갱신 |

## 결정 기록

- 2026-09-15: 사용자는 제한된 재시도의 모든 실패를 추적해야 한다고 확인했다.
- 2026-09-15: 처음 제안한 Vercel 로그와 `question_execution_issues` 병행 저장 대신 Vercel 로그만
  사용하기로 결정했다. DB schema와 migration은 변경하지 않는다.
- 2026-09-15: 상세 실패 이력은 운영자 내부에만 두고 사용자에게는 안전한 provider 불가 안내만
  표시한다.
- 2026-09-15: answer core/detail뿐 아니라 route, query embedding, clarification을 포함한 모든 NVIDIA
  호출을 동일한 관측 계약에 포함한다.
- 2026-09-15: provider 소진과 grounding 실패를 분리하고, 실제 draft가 없는 provider 실패에는
  `repair_core`를 사용하지 않는다.

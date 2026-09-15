# V2 질문 응답 표시 계약

- 상태: 승인
- 승인일: 2026-09-15
- 적용 API: V2 question executions
- 적용 화면: Web 질문 실행 화면

## 목적

질문 실행 화면에서 사용자에게 보이는 답변 내용은 백엔드 응답을 유일한 정본으로 사용한다. Web은
백엔드가 보낸 구조를 안전하게 배치하고 진행 상태를 표현하되, `result_status`, `route`, `action`, 오류
코드를 근거로 답변 의미나 사용자 문구를 다시 만들지 않는다.

이번 변경은 인증, 이력, 계정, 내보내기 화면에는 적용하지 않는다.

## 확인된 운영 증거

2026-09-15 Vercel 프로덕션 로그에서 실행
`74c09c88-ab8d-465a-862f-8d89b2de68d1`, 요청
`68a5f023-3d5a-4241-8d77-4b5bb14ef411`의 finalize가 16:30:21 KST에 HTTP 200,
`mode=ai`, `result=served`, `fallback_reason=null`로 종료된 것을 확인했다. 로그 정책상 응답 본문은
기록되지 않았다. 사용자가 제공한 실제 SSE 본문에는
`route=clarification_required`, `result_status=no_results`와 함께 다음 summary가 있었다.

> 정확한 절차를 확인하려면 추가 정보가 필요합니다.

현재 Web은 `result_status=no_results`를 자체 해석해 이 summary를 숨기고 “검색 결과가 없습니다” 문구를
생성한다. 반대로 실제 검색 무결과 경로는 백엔드 `search_only_answer()`가 summary 자체를 “검색 결과가
없습니다…”로 시작한다. 따라서 `result_status`는 표시 문구 선택 명령이 아니라 결과 메타데이터다.

## 선택한 접근

구조화된 백엔드 응답을 그대로 전달·표시한다.

- 정상 및 안전 fallback은 `QuestionResponse` 필드를 그대로 사용한다.
- HTTP 오류는 백엔드 `message`, 문자열 `detail`, 코드 순서로 이미 받은 값을 표시한다.
- SSE 오류는 백엔드 `message` 또는 `reason_code`를 그대로 표시한다.
- 표시 가능한 백엔드 값이 전혀 없는 transport/protocol 위반은 사용자 문구를 만들지 않고 내부 실패
  상태와 진단만 남긴다.
- 사용자가 명시적으로 허용한 `system_busy`와 모드 전환 안내는 기존 Web 문구 생성을 유지한다.
- 진행 중 `…`, 로딩 표시, 버튼·접근성 레이블은 답변 의미가 아닌 UI 표현이므로 Web이 소유한다.

백엔드 완성 HTML/Markdown 반환은 채택하지 않는다. 인용·체크리스트 구조와 안전한 렌더링 경계를
유지해야 하기 때문이다.

## 응답 계약

### Prepare

`POST /v2/question-executions`는 기존 `execution_id`, `status`, `next_action`, 선택적 capability 계약을
유지한다. HTTP 실패의 사용자 표시 값은 다음 우선순위로 해석 없이 전달한다.

1. `detail.message`
2. 문자열 `detail`
3. `detail.code`

값이 없으면 Web은 대체 문구를 만들지 않는다.

### Core

`POST /v2/question-executions/{execution_id}/core`의 `summary` 이벤트를 하위 호환 방식으로 확장해
다음 표시 필드를 백엔드가 소유한다.

- `summary`
- `citations`
- `scope`
- `limitations`

Web은 한 답변 영역에 `summary → citations → scope → limitations → …` 순서로 배치한다. 기존처럼
Web이 임시 `QuestionResponse`에 scope와 limitations 문구를 작성하지 않는다. 백엔드가 필드를 보내지
않는 구버전 이벤트에서는 받은 필드만 표시한다.

### Finalize

`POST /v2/question-executions/{execution_id}/finalize`의 `complete.response`가 최종 정본이다. Web은 Core
영역을 이 응답의 동명 필드로 조정하고 중복 표시 없이 상세 `sections`와 `checklist`를 이어 붙인다.
표시 순서는 다음과 같다.

1. `summary`
2. `citations`
3. `scope`
4. `limitations`
5. `sections`
6. `checklist`

`result_status=no_results`를 포함한 모든 상태에서 백엔드 summary를 그대로 표시한다. `route`,
`action`, `result_status`는 상태 보존과 스타일 선택에 사용할 수 있지만 사용자 문구를 선택하거나
합성하는 데 사용하지 않는다.

### HTTP·SSE 실패

- HTTP: 백엔드가 보낸 `message`, 문자열 `detail`, 코드 중 존재하는 값을 그대로 알림에 표시한다.
- SSE `error`: `message`가 있으면 그대로, 없으면 `reason_code`를 그대로 표시한다.
- SSE `cancelled`: 백엔드 payload에 표시 값이 있으면 그대로 표시한다. 사용자 측 abort만 발생한 경우
  답변 오류 문구를 생성하지 않는다.
- `system_busy`: 현재 Web의 “시스템이 바쁩니다…” 변환을 허용한다.
- 모드 전환: 현재 Web의 모드 안내 생성을 허용한다.

## Web 변경 경계

- `getEmptyResultMessage()`와 질문 형식 기반 빈 결과 문구 생성을 제거한다.
- `AnswerView`는 `response.summary`를 항상 표시한다.
- Core 이벤트에서 받은 필드만 보존하는 partial response/view model을 사용한다.
- HTTP/SSE 오류 파서는 받은 표시 값을 보존하고 generic 한국어 fallback을 만들지 않는다.
- retry, idempotency, cancellation, capability, citation 필터링, `SafeText` escaping은 유지한다.
- 기존 55초 Web attempt, 170초 overall retry, 57초 phase wait, 최대 3회 reconnect와 백엔드 55초
  provider/57초 phase 예산은 변경하지 않는다.

## 안전과 관측 가능성

- 검색 원문, 질문, 응답 전문, 사용자 식별자, capability, 인증정보를 로그에 추가하지 않는다.
- 오류 코드의 사용자 노출은 백엔드가 이미 공개 payload로 보낸 값에 한정한다.
- 공급자 오류 원문과 traceback을 SSE에 노출하지 않는 현재 경계를 유지한다.
- Vercel 로그는 요청 상관관계와 결과 메타데이터 확인에만 사용하며 응답 본문을 추가 로깅하지 않는다.

## 검증

1. 제공된 `clarification_required + no_results` fixture에서 백엔드 summary가 그대로 보이고 Web 생성
   “검색 결과가 없습니다”가 나타나지 않는다.
2. 실제 검색 무결과 fixture에서는 백엔드 summary의 “검색 결과가 없습니다…”가 그대로 보인다.
3. Core 이벤트의 `summary`, `citations`, `scope`, `limitations`가 순서대로 표시되고 `…` 뒤에 finalize
   상세가 이어진다.
4. HTTP `message`, 문자열 `detail`, 코드-only 응답이 변형 없이 표시된다.
5. SSE `message`와 `reason_code`가 변형 없이 표시된다.
6. `system_busy`와 모드 전환의 기존 Web 문구는 유지된다.
7. 질문 실행 경로에서 허용된 예외 외 generic 사용자 문구가 남지 않았음을 테스트와 문자열 검색으로
   확인한다.
8. Web 단위 테스트·빌드와 API 단위·통합 테스트, 저장소 전체 검증을 통과한다.

## 권한 및 실행 경계

| Boundary | Destination or resource | Operation | Data/credential involved | Mutation/retention | Purpose | Status and date | Runtime gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 저장소 | `C:\development\git\law-rag` | 문서·코드·테스트 수정 | 소스와 비밀 아닌 fixture | 로컬 Git 변경 | 계약 구현 | Approved, 2026-09-15 사용자 구현 요청 | workspace sandbox |
| 실행 harness | 설치된 `agent-operating-harness` 직접 스크립트 | 로컬 실행 증거 기록 | 테스트 명령·결과 요약 | 로컬 harness 상태 | bounded 구현과 완료 확인 | Approved, 2026-09-15 사용자 구현 요청 | CLI alias 없음; 직접 script 사용 |
| 로컬 검증 | `scripts/verify.ps1` 및 Web 테스트/빌드 | 테스트 프로세스 실행 | 로컬 소스·fixture | 테스트 임시 산출물 | 회귀 검증 | Approved, 2026-09-15 사용자 구현 요청 | 필요 시 platform runtime 승인 |
| Vercel 로그 | `vercel.com`, project `law-rag-api`, production logs | 읽기 전용 조회 | 로그인 세션, 실행·요청 ID | 외부 변경 없음 | 운영 증거 확인 | Approved, 2026-09-15 “외부 vercel접근 허용” | 플랫폼 UI 세션 필요 |
| 로컬 커밋 | 현재 Git 브랜치 | 기능 단위 commit | 검증된 소스·문서, 비밀 제외 | 로컬 이력 추가 | durable milestone | Approved, repository commit policy | commit 전 diff·비밀 확인 |
| 원격 Git·배포 | GitHub, Vercel deployment | push, PR, deployment | 해당 없음 | 외부 변경 | 이번 설계에 불필요 | Not required, 2026-09-15 | 별도 사용자 승인 필요 |
| 외부 데이터·DB | Supabase, NVIDIA, 운영 DB | 읽기·쓰기·평가 호출 | 해당 없음 | 외부 변경 없음 | 로컬 fixture 검증으로 대체 | Not required, 2026-09-15 | 범위 확대 시 재승인 |

모든 구현·검증 단계는 위 표의 Approved 또는 Not required 경계 안에 있다. Pending 항목은 없다.

## 결정 기록

| 날짜 | 결정 | 이유 |
| --- | --- | --- |
| 2026-09-15 | 질문 실행의 사용자 표시 답변은 백엔드 응답을 정본으로 한다. | `no_results` 메타데이터를 Web이 검색 실패 문구로 재해석해 올바른 clarification summary를 숨긴 운영 결함을 제거한다. |
| 2026-09-15 | Core SSE에 scope와 limitations를 추가하고 Web은 받은 필드만 표시한다. | 점진 표시 중에도 Web이 법률 답변 관련 문구를 생성하지 않게 한다. |
| 2026-09-15 | HTTP/SSE 오류는 백엔드 문구 또는 공개 코드를 그대로 표시한다. | 오류 의미와 문구의 소유권을 백엔드에 둔다. |
| 2026-09-15 | busy, 모드 전환, 진행 `…`는 Web 표현 예외로 유지한다. | 사용자가 명시적으로 허용했고 답변의 법률적 의미를 바꾸지 않는다. |

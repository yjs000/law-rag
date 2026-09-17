# 런타임 오류 관측과 환경 스코프 분리

- 상태: 승인
- 승인일: 2026-09-17
- 범위: FastAPI 로컬·Vercel 런타임 로그, NVIDIA 모델 설정, Vercel 환경 변수 스코프

## 배경

현재 NVIDIA provider 시도 로그는 HTTP 상태와 분류를 남기지만, 실제 실패 단계·모델·timeout·예외
종류와 stack trace가 없어 원인을 단정하기 어렵다. 로컬 Uvicorn에서는 애플리케이션 INFO 로그가 root
logger의 `WARNING` 수준에 막혀 B-006 이벤트가 보이지 않는 구성도 확인됐다.

환경 변수는 역할별 NVIDIA 모델 이름과 폐기된 OpenAI 설정이 남아 있고, Vercel Preview와 Production이
운영 Supabase 자격 증명을 공유한다. 로컬 파일도 루트와 `apps/api/`에 중복돼 설정 drift 위험이 있다.

## 목표

1. 요청 실패 시 어느 pipeline 단계에서 어떤 예외와 cause로 실패했는지 correlation id로 추적한다.
2. 로컬에서는 원본 예외·cause chain·stack trace를 터미널에서 확인한다.
3. Vercel에서는 진단 가능한 stack trace를 남기되 비밀값, 사용자 질문, 법률 원문, SQL parameter를
   제거한다.
4. NVIDIA 생성 모델은 hosted `nvidia/nemotron-3.5-lightning-30b-a3b`, embedding 모델은 hosted
   `nvidia/nemotron-3-embed-1b`라는 단일 설정으로 주입한다.
5. Git branch가 아니라 Vercel Production·Preview scope로 배포 설정을 분리한다.
6. 기존 Supabase 프로젝트 하나만 유지한다.

## 비목표

- 새 Supabase 프로젝트 생성 또는 DB schema·데이터 변경
- 로컬 LLM 도입
- 사용자 HTTP 응답에 raw exception 또는 stack trace 노출
- 별도 로그 저장소·파일 logger·APM 서비스 도입
- Preview에서 운영 데이터 접근 허용

## 결정

### 1. 환경 토폴로지

코드는 `main` 한 브랜치에서 운영한다. 배포 환경 차이는 브랜치 정책이 아니라 Vercel 환경 변수 scope와
런타임 `ENVIRONMENT` 값으로 표현한다.

| 실행 위치 | 설정 원천 | 용도 |
|---|---|---|
| 로컬 API | `apps/api/.env.local` | 개발 실행, raw 터미널 진단 |
| 운영 동기화 | `apps/api/.env.prod` | Vercel Production 변수의 로컬 관리 원천 |
| Vercel Production | Production-scoped process env | 실제 운영 |
| Vercel Preview | Preview-scoped process env | 운영 DB가 없는 fail-closed 검증 |

두 `.env` 파일은 Git과 Vercel deployment bundle에 포함하지 않는다. `Settings`는 지금처럼 로컬에서
`.env.local`만 자동 로드한다. `.env.prod`는 애플리케이션이 자동으로 읽지 않으며, 명시적인 Vercel
동기화 작업에서만 사용한다. 따라서 운영 프로세스는 파일이 아니라 Vercel process env를 사용한다.

루트 `.env.local`은 수집·검색 등 루트 도구에서 실제로 쓰는 값만 유지한다. API provider와 generation
설정은 `apps/api/.env.local`을 정본으로 삼아 루트에서 제거한다. 이 분리는 동일 비밀값의 불필요한
복제를 줄인다.

### 2. NVIDIA 모델 주입

역할별 `NVIDIA_ROUTE_CLASSIFIER_MODEL`, `NVIDIA_ANSWER_MODEL`을 제거하고 다음 두 설정만 유지한다.

- `NVIDIA_GENERATION_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b`
- `NVIDIA_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b`

라우터와 답변 생성기는 같은 generation model 설정을 주입받는다. 구현 객체나 endpoint가 모델명을
하드코딩하지 않아 모델 교체는 환경 변수 한 곳의 변경으로 끝나야 한다. NVIDIA 호출은 모두 hosted
endpoint를 사용하며 로컬 추론 fallback은 두지 않는다.

### 3. Supabase와 Preview

Supabase 프로젝트는 현재 Production 하나만 유지한다. 로컬 개발은 사용자의 명시적 선택에 따라 이
프로젝트를 사용할 수 있지만, 테스트·초기화·파괴적 쓰기의 대상으로 삼지 않는다.

Vercel Preview에는 Production의 `DATABASE_URL`, `DIRECT_URL`, `SUPABASE_URL`,
`SUPABASE_SECRET_KEY` 및 운영 bucket 자격 증명을 두지 않는다. 별도 개발 DB가 생기기 전까지 Preview는
`AI_MODE=off`로 두고 DB·AI 의존 경로는 fail closed한다. 정적 빌드와 DB 비의존 동작만 검증한다.

Production에는 기존 Supabase 자격 증명을 유지한다. 이 변경은 Supabase platform 자체를 수정하지
않으며 Vercel 변수의 scope만 정리한다.

### 4. 오류 로그 모드

`ERROR_LOG_MODE`은 `raw`와 `redacted` 두 값만 허용한다. 안전 기본값은 `redacted`다.

- 로컬 `.env.local`: `ENVIRONMENT=development`, `ERROR_LOG_MODE=raw`
- Vercel Production: `ENVIRONMENT=production`, `ERROR_LOG_MODE=redacted`
- Vercel Preview: `ENVIRONMENT=test`, `ERROR_LOG_MODE=redacted`

Production 설정에서 `raw`를 선택하면 시작 단계에서 validation error로 거부한다. 로그 모드는 HTTP
응답 형식을 바꾸지 않는다.

#### 로컬 raw 로그

원본 exception type/message, nested `__cause__`/`__context__`, 전체 Python stack trace, provider 응답
오류 본문, SQLAlchemy/DBAPI 원본 예외를 stdout/stderr에 남긴다. 별도 파일은 자동 생성하지 않는다.
Uvicorn의 기존 handler chain을 재사용하되 애플리케이션 logger가 실제로 출력되지 않는 경우에만
fallback handler를 붙여 중복 출력을 막는다.

#### Vercel redacted 로그

Vercel Runtime Logs에는 exception type, redacted message, cause chain, stack trace의 코드 위치를
남긴다. 다음 값은 모든 메시지와 구조화 필드에서 제거한다.

- API key, bearer token, cookie, authorization header
- DB URL의 사용자명·비밀번호
- 사용자 질문, prompt, 답변, 검색 청크와 법률 원문
- SQL parameter와 bind value
- request/response body의 내용 필드

Provider 오류 본문은 redaction을 적용한 뒤 최대 4 KiB만 남긴다. SQL 오류는 SQLSTATE, exception type,
operation, table/constraint 등 비민감 metadata는 유지하되 statement parameter는 남기지 않는다.
`AttributeError`, `TypeError` 같은 애플리케이션 예외는 redacted message와 stack/cause chain을 유지한다.

### 5. 단계 식별과 이벤트 계약

요청 lifecycle에 `pipeline_stage` context를 두고 각 외부·핵심 경계에서 다음처럼 갱신한다.

- `request_validation`
- `routing`
- `retrieval`
- `answer_generation`
- `grounding_validation`
- `persistence`
- `response_serialization`

최상위 exception boundary는 현재 stage를 포함한 `runtime_exception` 이벤트를 정확히 한 번 남긴다.
하위 provider 시도는 기존 `provider_attempt` 이벤트를 유지하며 다음 필드를 추가한다.

- `model`
- `timeout_ms`
- `exception_type`
- `error_detail` (`raw` 또는 redacted)
- `pipeline_stage`

모든 이벤트는 기존 `correlation_id`, `provider`, `operation`, `attempt`, `outcome`, `elapsed_ms`,
`remaining_ms`와 연결된다. Python logger 이름이 Vercel message에 보존된다고 가정하지 않고,
`event_type`, `correlation_id`, `provider`, `pipeline_stage`를 검색 기준으로 삼는다.

### 6. Vercel 변수 정리

Production에는 `.env.prod`와 일치하도록 generation/embedding model, `ENVIRONMENT=production`,
`ERROR_LOG_MODE=redacted`, `AI_MODE=auto`를 설정한다. Preview에는 `ENVIRONMENT=test`,
`ERROR_LOG_MODE=redacted`, `AI_MODE=off`를 설정한다.

코드에서 더 이상 쓰지 않는 다음 변수는 Vercel scope와 로컬 파일에서 제거한다.

- `NVIDIA_ANSWER_MODEL`
- `NVIDIA_ROUTE_CLASSIFIER_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_ANSWER_MODEL`
- `OPENAI_EMBEDDING_MODEL`

변수 변경은 다음 deployment부터 적용된다. `main` push가 Git integration을 통해 Production deployment를
시작하면 새 scope를 사용한다.

## 안전한 오류 응답

로그 상세도가 높아져도 클라이언트에는 기존 public error code와 안전한 message만 보낸다. stack trace,
provider body, SQL 문장과 내부 경로는 HTTP 응답에 포함하지 않는다.

## 검증 전략

1. 설정 validation: 허용된 로그 모드, 안전 기본값, Production raw 거부
2. redaction 단위 테스트: authorization, key, DB URL, prompt/question/content, SQL parameter, nested cause
3. exception 이벤트 테스트: stage, exception type, stack, cause chain, correlation id
4. provider 이벤트 테스트: model, timeout, error detail과 기존 B-006 필드 회귀
5. logging wiring 테스트: 로컬에서 한 번 출력, Vercel/root handler 환경에서 중복 없음
6. env 계약 검사: 폐기 변수 부재, required 변수와 scope 문서 일치
7. 전체 `scripts/verify.ps1`
8. 배포 후 안전한 smoke request와 Vercel Runtime Logs에서 동일 correlation의 단계·오류 확인

## 외부 작업·권한 매트릭스

| 작업 | 대상/credential | 변경 또는 전송 | 승인과 runtime gate |
|---|---|---|---|
| 로컬 env 정리 | gitignored `.env.local`, `.env.prod` | 로컬 비밀값 복사·정리, 채팅/로그 출력 금지 | 사용자 승인 2026-09-17; 파일 존재·ignore 확인 후 실행 |
| Vercel env 조회 | 연결된 Vercel 프로젝트 | scope와 이름 조회 | 사용자 승인 2026-09-17; 값은 출력하지 않음 |
| Vercel env 수정 | Vercel CLI 인증 | Production/Preview add/update/remove | 사용자 승인 2026-09-17; 대상 프로젝트·scope 재확인 |
| Supabase | 기존 Production credential | Vercel scope 매핑만 변경; DB/platform mutation 없음 | 새 프로젝트·migration·데이터 쓰기 금지 |
| NVIDIA smoke | 기존 NVIDIA API key | 일반 테스트 질문을 hosted endpoint에 전송 | 사용자 승인 2026-09-17; 개인·사건정보 금지 |
| Git commit/push | 현재 `main`, origin | 코드·문서 commit과 push | 사용자 승인 2026-09-17; `.env*` stage 금지 |
| Production deploy | Vercel Git integration | `main` push로 새 deployment 가능 | 사용자 승인 범위; 배포 후 health/log 확인 |

## Rollback

코드 rollback은 관련 commit revert로 수행한다. Vercel 변수는 변경 전 이름·scope 목록을 값 없이 기록해
복원 가능하게 한다. Production 배포 실패 시 이전 deployment로 되돌리되, 폐기 변수 재도입보다 현재
코드가 요구하는 generation/embedding 설정을 우선 복원한다. `.env.prod`는 Git에 없으므로 운영 정본은
항상 Vercel scope이며, 동기화 뒤 이름·scope drift를 다시 검사한다.

## 결정 기록

- 2026-09-17: branch 분리 대신 Vercel scope 분리를 채택했다. 동일 코드의 환경 차이를 줄이고 기존
  `main` Production 흐름을 유지하기 위해서다.
- 2026-09-17: 로컬 raw·운영 redacted 이중 모드를 채택했다. 원인 규명에 필요한 stack/cause를
  보존하면서 저장소 보안·개인정보 불변조건을 지키기 위해서다.
- 2026-09-17: Supabase는 하나만 유지하되 Preview에서 운영 credential을 제거한다. 별도 프로젝트 생성은
  현재 비용과 범위를 넓히므로 보류한다.
- 2026-09-17: 사용자 지시에 따라 일반 선택은 권고안으로 확정하고, 추가 크리티컬 질문이 없으므로 본
  문서를 승인 상태로 기록한다.

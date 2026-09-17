> 작업 ID: `O-001`
> 상태: `Picked Up`
> 유형: `Operations`
> 보조 라벨: `Reliability`, `Security`
> 선행 조건: `B-007` 완료와 전체 로컬 검증 성공
> 다음 행동: 값 없이 Vercel Production·Preview 변수 이름과 scope snapshot을 기록한다.
> 참고 범위:
> - `docs/design-docs/runtime-error-observability-and-environment-scopes.md` L32-L185 — 환경 토폴로지, Supabase Preview 격리, Vercel 변수와 rollback 계약
> - `apps/api/.env.example` L1-L60 — API required 변수와 안전한 예시
> - `docs/design-docs/vercel-supabase-deployment.md` L1-L220 — 기존 Vercel·Supabase 배포 책임과 scope 기준

# Vercel Environment Scope Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** B-007의 안전한 로그·모델 설정을 Vercel Production에 반영하고, Preview에서 운영 Supabase와 AI 자격 증명을 제거한 뒤 실제 배포와 Runtime Logs로 검증한다.

**Architecture:** Git에 포함되지 않는 `apps/api/.env.prod`는 Production 변수 동기화 입력으로만 사용하고, Vercel의 Production·Preview scope가 실제 정본이다. Production은 기존 Supabase와 hosted NVIDIA를 유지하고 Preview는 `AI_MODE=off`와 운영 credential 부재로 fail closed한다. scope 변경 전후 이름 목록을 값 없이 비교해 rollback 가능성을 보존한다.

**Tech Stack:** Vercel CLI, PowerShell, FastAPI health/smoke endpoints, Vercel Runtime Logs, Git

**Spec:** `docs/design-docs/runtime-error-observability-and-environment-scopes.md`

## 전역 제약

- Vercel 변수 값과 `.env.prod` 내용을 터미널 transcript·문서·채팅에 출력하지 않는다.
- Supabase platform·schema·데이터는 변경하지 않는다.
- Preview에는 Production DB·Supabase·NVIDIA 자격 증명을 두지 않는다.
- 변수 변경은 다음 deployment에만 적용되므로 변경 후 Production deployment를 반드시 검증한다.
- smoke 질문에는 개인·사건정보를 사용하지 않는다.

---

### Task 1: scope snapshot과 Production/Preview 변수 정리

**결과:** Production은 hosted Nemotron 3.5·redacted logs·기존 Supabase를 사용하고 Preview는 AI off이며 운영 자격 증명이 없다.

**대상:**
- 외부 수정: Vercel Production environment — required 변수 update/add와 폐기 변수 제거
- 외부 수정: Vercel Preview environment — fail-closed 변수 add/update와 운영 credential 제거
- 검증: `apps/api/.env.prod` — Git ignored 동기화 원천, 값 출력 금지
- 기록: 이 계획의 결과 기록 — 값 없는 변수 이름·scope·명령 결과 요약(약 +25줄)
- 태스크 합계: 외부 변수 scope 변경과 문서 약 +25줄

**실행 절차:**

- [x] 대상 Vercel project·team·Git branch가 Production 프로젝트와 일치하는지 확인한다.
- [x] `vercel env ls` 결과에서 변수 이름·scope만 추출해 변경 전 snapshot을 계획 결과에 기록한다.
- [x] Production에 `ENVIRONMENT=production`, `ERROR_LOG_MODE=redacted`, `AI_MODE=auto`, `NVIDIA_GENERATION_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b`, `NVIDIA_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b`와 기존 required secret을 `.env.prod` 기준으로 add/update한다.
- [x] Preview에 `ENVIRONMENT=test`, `ERROR_LOG_MODE=redacted`, `AI_MODE=off`를 설정하고 Production DB·Supabase·NVIDIA credential을 제거한다.
- [x] 두 scope에서 폐기된 NVIDIA 역할별 변수와 OpenAI 변수를 제거한다.
- [x] `vercel env ls`를 다시 실행해 이름·scope만 비교하고 Production required/Preview forbidden 집합을 검증한다.
- [x] 실패 시 변경 전 snapshot을 기준으로 scope를 복원하고 원인을 결과 기록에 남긴다.

**완료 증거:** 값 없는 scope 목록이 Production required 집합과 Preview forbidden 집합을 만족한다.

**의존성:** B-007 Settings와 example 계약.

### Task 2: main push, Production deployment와 안전 smoke

**결과:** `main` push가 새 Production deployment를 만들고 health 및 일반 NVIDIA 질문이 성공하거나, 실패 시 정확한 runtime stage·raw upstream reason이 redacted 정책 안에서 확인된다.

**대상:**
- 원격 변경: `origin/main` push
- 외부 변경: Vercel Production deployment
- 외부 검증: Production health/question endpoint와 Runtime Logs
- 기록: 이 계획 결과와 최종 scope/deployment/log 증거(약 +30줄)
- 태스크 합계: 외부 배포와 문서 약 +30줄

**실행 절차:**

- [ ] push 직전 `git status --short --branch`, `git log -5 --oneline`, `git diff --check HEAD`를 확인하고 `.env*`가 commit되지 않았는지 검사한다.
- [ ] `git push origin main`을 실행한다.
- [ ] Vercel deployment가 Ready 또는 Error terminal 상태가 될 때까지 확인한다.
- [ ] Production health endpoint를 호출하고 hosted NVIDIA 일반 질문 한 건을 correlation 가능한 request ID로 호출한다.
- [ ] Vercel Runtime Logs에서 `event_type`, `correlation`, `provider`, `pipeline_stage`로 해당 요청을 확인한다. 성공이면 model·timeout·stage 필드를, 실패면 exception type·redacted detail·stack/cause를 확인한다.
- [ ] 로그에 질문·prompt·법률 원문·secret·DB credential·SQL parameter가 없는지 확인한다.
- [ ] 배포 실패면 이전 deployment rollback 또는 변수 snapshot 복원을 수행하고 원인과 복구 결과를 기록한다.
- [ ] 계획 상태를 Done으로 바꾸고 `completed/`로 이동한 뒤 roadmap renderer/checker와 docs check를 실행한다.
- [ ] 운영 결과 문서를 `ops: roll out vercel environment scopes`로 커밋하고 필요하면 이 기록 커밋도 `main`에 push한다.

**완료 증거:** Production deployment terminal 성공, health 성공, NVIDIA smoke와 동일 correlation의 안전 로그, Preview 운영 credential 부재가 모두 확인된다.

**의존성:** Task 1, B-007 전체 검증과 로컬 commits.

## 결과 기록

- 변경 전 scope snapshot: `law-rag-api`가 `origin/main`에 연결됨. Production·Preview에 DB/Supabase와
  OpenAI 설정이 함께 있었고, 역할별 `NVIDIA_ANSWER_MODEL`/`NVIDIA_ROUTE_CLASSIFIER_MODEL`과 구 quota
  변수가 남아 있었다. 값은 조회·기록하지 않았다.
- 변경 후 scope snapshot: Production required 10개 존재, Preview forbidden credential 8개 부재,
  폐기 변수 8개 양 scope 부재를 이름·scope만으로 검증했다. Production은 `.env.prod` 29개 키를
  동기화했고 Preview는 `ENVIRONMENT=test`, `ERROR_LOG_MODE=redacted`, `AI_MODE=off`다.
- deployment: 진행 전
- smoke와 Runtime Logs: 진행 전
- rollback: 필요 시 기록

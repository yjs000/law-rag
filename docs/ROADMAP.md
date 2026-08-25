# Discord 작업 보드

이 문서는 Discord thread `1528216345924337805`에서 시작한 작업의 순서와 상태를 관리하는 단일 진입점이다. 다른 환경에서는 적용하지 않는다. 상세 범위와 결정은 연결된 실행 계획이 권위 문서다.

## 상태 계약

- `Todo`: 선행 조건이 충족됐지만 아직 착수하지 않음
- `Picked Up`: 현재 주 에이전트가 수행 중인 유일한 milestone
- `Blocked`: 사용자 승인, credential, 운영환경 등 외부 입력 대기
- `Done`: 구현·검증·상태 문서 갱신까지 완료

작업 진행 중에는 정확히 하나의 milestone만 `Picked Up`으로 두고, 대기·완료 상태에서는 0개일 수 있다.

## 현재 순서

| ID | 상태 | 작업 | 담당 | 수정 가능 범위 | 완료 조건 | 검증 |
|---|---|---|---|---|---|---|
| D-001 | Done | Discord 전용 agent overlay와 오류 ledger 도입 | 주 에이전트 | `AGENTS.md`, `discord-agents.md`, `docs/ROADMAP.md`, `docs/operations/discord-error-ledger.md` | 지정 thread에서만 적용되고 TODO·위임·보고·오류·검증 계약이 연결됨 | 문서 검사, `git diff --check`, parent diff 검토 |
| D-002 | Blocked | 4단계 검색의 Production 실행계획과 병목 확인 | 주 에이전트 | `docs/exec-plans/active/0008-*`, 진단 산출물·관련 테스트(필요 시) | 읽기 전용 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`으로 단계별 인덱스·병목을 확인하고 다음 최적화를 증거로 결정 | 계획의 고정 질문·문서 검사·관련 테스트 |
| D-003 | Done | 완료·중복 active 계획 정리 | 주 에이전트 | `docs/exec-plans/active/`, `completed/`, active index, 기술 부채 추적기 | `0013` 완료 상태와 `0012`/`0014` 역할이 실제 구현·외부 병목과 일치 | 문서 검사, 링크 검사, diff 검토 |
| D-004 | Blocked | Supabase 분산 취소와 Realtime Broadcast 운영 연결 | DB/API/Web 에이전트(순차) | `0012`와 완료 계획 `0014`가 정한 migration/API/Web 범위 | 운영 migration 승인 후 2인스턴스 취소·소유자 격리·UX·부하 검증 통과 | API/Web 통합 테스트, schema 문서, Preview 검증 |
| D-005 | Blocked | NVIDIA hosted NIM 실연결·법률 평가 | 주 에이전트 | provider 설정, 평가 산출물, 운영 문서 | API key와 정책 승인 후 hosted smoke·고정 평가셋·운영 계약 확인 | smoke, 고정 평가셋, fallback 회귀 |
| D-006 | Done | 1년 만료 질문 이력 정리 함수와 감사 메트릭의 로컬 계약 | 주 에이전트 + 독립 검토 에이전트 | 신규 migration·계약 테스트·DB schema·운영/학습 문서 | 정리 함수가 만료 이력·종속 export·빈 conversation을 안전하게 정리하고 삭제 수·실행 상태를 감사 가능하게 기록 | migration 계약 테스트, PostgreSQL 17 실행, API 회귀, 문서 검사, parent diff 검토 |
| D-007 | Done | `main` Python CI 수집 실패 복구 | 주 에이전트 | `.github/workflows/ci.yml`, 오류 ledger | API import 경로와 pytest async 설정을 CI에 명시해 기존 suite가 수집·통과 | CI 동일 명령 207 passed, workflow diff 검토 |
| D-008 | Done | 통합 검토·PR·원격 CI 확인 | 주 에이전트 + 독립 reviewer | 현재 branch 전체 diff, GitHub PR | 독립 review finding 처리, commit/push/PR 후 CI green | immutable diff review, GitHub checks |
| D-009 | Blocked | Production 질문 이력 scheduler 적용 | 운영 승인자 + 주 에이전트 | `0006` migration, 승인된 scheduler 설정 | 대상 Supabase 승인·extension 확인 후 일 1회 예약, 최초 실행 감사·경보 확인 | Production migration/schedule/감사 증거 |
| D-010 | Active | [0057: 단일 단계 라우터와 라우터 불가 AI 응답](exec-plans/active/0057-single-stage-router-and-failure-response.md) | 주 에이전트 | API 라우팅·응답·관측·테스트 | `legal_search`와 라우터 장애 AI 안내를 분리 | 라우팅 회귀·전체 Ruff·문서 검사·전체 로컬 pytest |

## 현재 Active: D-010

- D-008은 독립 review 승인, PR #1 생성, GitHub Python/Web와 Vercel API/Web checks 통과로 완료됐다.
- D-010의 Task 1~2 구현과 focused safety regression은 완료됐다. 단일 NVIDIA `QuestionRouter`, 정상 grounded sequence, `routing_unavailable` no-search AI fallback, 명명된 generation/validation stage와 `search_only_enabled=False` 불변조건을 유지한다.
- Task 3 문서 정렬·fixture alignment·최종 로컬 검증은 완료됐다. API는 `639 passed, 3 skipped, 1 warning`, core는 `26 passed`, focused D-010은 `43 passed, 1 warning`이며 D-010 assertion과 Ruff도 통과했다. 전체 계획은 parent-level integration decision을 위해 Active로 유지한다. Repository docs checker의 32개 broken link은 기존 문서 부채로 별도 기록한다.
- 로컬 검증은 NVIDIA provider·Docker·persistent service 없이 수행됐다. `NVIDIA_API_KEY`가 필요한 fixture 평가는 실행하지 않았다.
- 다음 후보 D-002, D-004, D-005, D-009는 각각 Production credential·migration·정책 승인이 필요해 `Blocked`다.
- 승인 전에는 Production DB, scheduler, 외부 provider를 변경하지 않는다.

## 차단 기록

- D-002: 현재 Linux checkout에 `DATABASE_URL`과 `DIRECT_URL`이 없어 Production 읽기 전용 실행계획을 수집할 수 없다. credential을 채팅이나 Git으로 요청하지 않으며 승인된 비밀 설정 환경에서 재개한다.

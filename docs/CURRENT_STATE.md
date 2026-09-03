# 현재 상태 (세션 시작 포인터)

세션 시작 시 기본으로 읽는 문서는 `AGENTS.md`와 이 파일뿐이다. `ARCHITECTURE.md`, `docs/design-docs/`,
과거 exec-plan, `docs/learning/`은 작업이 실제로 그 영역을 건드릴 때만 읽는다 — 매 세션 전체를 미리
읽지 않는다([0031](exec-plans/todo/0031-eval-harness-consolidation.md) item 5, 2026-08-08).

## 지금 무엇이 진행 중인가

전체 active 계획 목록과 한 줄 상태는 [docs/exec-plans/active/README.md](exec-plans/active/README.md)에
있다.

현재 `Picked Up` milestone은 없다. F-006 Web grounded QA 프런트 API 정합성을 완료했으며, 기준일 입력은 한국 today() 상한을 다음 한국 자정에 갱신하고 선택값을 고정된 V2 실행 API에 전달한다. 코퍼스 준비·최신성은 프런트에서 조회·표시하지 않고 서버가 처리한다. 체크리스트 내보내기 프런트 제거는 후속 F-007에 남아 있다. 이후 우선순위는 [docs/ROADMAP.md](ROADMAP.md)에서 확인한다. 로드맵은 세션 시작용 얇은 색인이며 모든 실행계획을 읽으라는 뜻이 아니다.

가장 최근 결정은 [ARCHITECTURE.md 결정 기록](../ARCHITECTURE.md#결정-기록)의 최신 날짜 항목들이다.
최근 완료된 구현은 [Web grounded QA 프런트 API 정합성](exec-plans/completed/0064-web-dynamic-today-date-bound.md)이다. KST 기준일 UI 갱신과 V2 prepare/core/finalize/cancel·대화 API 클라이언트 계약을 검증했으며, 코퍼스 상태 최신성은 서버가 사용자에게 보이지 않게 처리한다.

## 언제 더 읽어야 하는가

- 아키텍처·모듈 경계·배포 구조를 건드리는 작업 → `ARCHITECTURE.md`
- "왜 이렇게 만들었는가"가 필요한 작업 → `docs/design-docs/index.md`
- 과거 실행 세부사항(수치·재현 절차)이 필요한 작업 → 해당 `docs/exec-plans/active/` 또는 `completed/` 파일
- 개념 설명이 필요한 작업 → `docs/learning/`
- 알려진 결함·위험과 관련된 작업 → `docs/exec-plans/tech-debt-tracker.md`

## 이 파일을 갱신하는 시점

새 exec-plan이 `active/`로 이동하거나 완료될 때, 또는 굵직한 결정이 추가될 때만 갱신한다. 매 커밋마다
손보지 않는다 — 이 파일 자체가 새로운 상시 유지보수 부담이 되면 "context diet"의 취지에 어긋난다.

# 현재 상태 (세션 시작 포인터)

세션 시작 시 기본으로 읽는 문서는 `AGENTS.md`와 이 파일뿐이다. `ARCHITECTURE.md`, `docs/design-docs/`,
과거 exec-plan, `docs/learning/`은 작업이 실제로 그 영역을 건드릴 때만 읽는다 — 매 세션 전체를 미리
읽지 않는다([0031](exec-plans/todo/0031-eval-harness-consolidation.md) item 5, 2026-08-08).

## 지금 무엇이 진행 중인가

전체 active 계획 목록과 한 줄 상태는 [docs/exec-plans/active/README.md](exec-plans/active/README.md)에
있다.

2026-08-25: D-010([0057](exec-plans/completed/0057-single-stage-router-and-failure-response.md))은 단일 NVIDIA 라우터, 정상 grounded sequence, `routing_unavailable` no-search AI 응답을 구현했고 문서 정렬과 최종 로컬 검증을 마친 뒤 `main`에 병합했다. 최종 API는 `639 passed, 3 skipped, 1 warning`, core는 `26 passed`, focused D-010은 `43 passed, 1 warning`이며 D-010 assertion과 Ruff도 통과했다. Repository docs checker의 32개 broken link은 기존 문서 부채로 별도 기록한다. 로컬 검증은 NVIDIA provider·Docker·persistent service 없이 수행했고, live fixture 평가는 실행하지 않았다.

가장 최근 결정은 [ARCHITECTURE.md 결정 기록](../ARCHITECTURE.md#결정-기록)의 최신 날짜 항목들이다.

## 언제 더 읽어야 하는가

- 아키텍처·모듈 경계·배포 구조를 건드리는 작업 → `ARCHITECTURE.md`
- "왜 이렇게 만들었는가"가 필요한 작업 → `docs/design-docs/index.md`
- 과거 실행 세부사항(수치·재현 절차)이 필요한 작업 → 해당 `docs/exec-plans/active/` 또는 `completed/` 파일
- 개념 설명이 필요한 작업 → `docs/learning/`
- 알려진 결함·위험과 관련된 작업 → `docs/exec-plans/tech-debt-tracker.md`

## 이 파일을 갱신하는 시점

새 exec-plan이 `active/`로 이동하거나 완료될 때, 또는 굵직한 결정이 추가될 때만 갱신한다. 매 커밋마다
손보지 않는다 — 이 파일 자체가 새로운 상시 유지보수 부담이 되면 "context diet"의 취지에 어긋난다.

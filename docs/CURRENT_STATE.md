# 현재 상태 (세션 시작 포인터)

세션 시작 시 기본으로 읽는 문서는 `AGENTS.md`와 이 파일뿐이다. `ARCHITECTURE.md`, `docs/design-docs/`,
과거 exec-plan, `docs/learning/`은 작업이 실제로 그 영역을 건드릴 때만 읽는다 — 매 세션 전체를 미리
읽지 않는다([0031](exec-plans/todo/0031-eval-harness-consolidation.md) item 5, 2026-08-08).

## 지금 무엇이 진행 중인가

전체 active 계획 목록과 한 줄 상태는 [docs/exec-plans/active/README.md](exec-plans/active/README.md)에
있다.

현재 `Picked Up` milestone은 [B-017](exec-plans/active/0088-answer-readability-and-evidence-layout.md)의 결론 우선·쉬운 말·근거 표시 개선이다. 후속 [B-016](exec-plans/todo/0087-clarification-case-grounded-answer-input.md)은 원 질문·누적 fact 기반 답변 입력을 다루고, [B-014](exec-plans/active/0085-clarification-continuation-cross-layer-regression.md)와 [B-009](exec-plans/active/0078-clarification-state-conversation-verification.md)가 순서대로 회귀·acceptance를 수행한다. 별도 [O-002](exec-plans/todo/0089-dev-vercel-preview-environment.md)는 dev Preview 환경을 준비한다.

가장 최근 결정은 [ARCHITECTURE.md 결정 기록](../ARCHITECTURE.md#결정-기록)의 최신 날짜 항목들이다.
최근 완료된 구현은 [B-015 자유 문장 fact 추출](exec-plans/completed/0086-clarification-free-text-fact-extraction.md)이다. 로컬 세션 실행 문제는 2026-10-21 사용자가 해결 완료를 확인했다.

## 언제 더 읽어야 하는가

- 아키텍처·모듈 경계·배포 구조를 건드리는 작업 → `ARCHITECTURE.md`
- "왜 이렇게 만들었는가"가 필요한 작업 → `docs/design-docs/index.md`
- 과거 실행 세부사항(수치·재현 절차)이 필요한 작업 → 해당 `docs/exec-plans/active/` 또는 `completed/` 파일
- 개념 설명이 필요한 작업 → `docs/learning/`
- 알려진 결함·위험과 관련된 작업 → `docs/exec-plans/tech-debt-tracker.md`

## 이 파일을 갱신하는 시점

새 exec-plan이 `active/`로 이동하거나 완료될 때, 또는 굵직한 결정이 추가될 때만 갱신한다. 매 커밋마다
손보지 않는다 — 이 파일 자체가 새로운 상시 유지보수 부담이 되면 "context diet"의 취지에 어긋난다.

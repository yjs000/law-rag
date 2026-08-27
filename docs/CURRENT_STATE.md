# 현재 상태 (세션 시작 포인터)

세션 시작 시 기본으로 읽는 문서는 `AGENTS.md`와 이 파일뿐이다. `ARCHITECTURE.md`, `docs/design-docs/`,
과거 exec-plan, `docs/learning/`은 작업이 실제로 그 영역을 건드릴 때만 읽는다 — 매 세션 전체를 미리
읽지 않는다([0031](exec-plans/todo/0031-eval-harness-consolidation.md) item 5, 2026-08-08).

## 지금 무엇이 진행 중인가

전체 active 계획 목록과 한 줄 상태는 [docs/exec-plans/active/README.md](exec-plans/active/README.md)에
있다.

현재 `Picked Up` milestone은 없다. 다음 진입점은 [E-001 · 실험 E-10 — AI 답변 소표본 평가](exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md)이며, 이후 우선순위는 [docs/ROADMAP.md](ROADMAP.md)에서 확인한다. 로드맵은 세션 시작용 얇은 색인이며 모든 실행계획을 읽으라는 뜻이 아니다.

가장 최근 결정은 [ARCHITECTURE.md 결정 기록](../ARCHITECTURE.md#결정-기록)의 최신 날짜 항목들이다.
구현 전인 최신 승인 설계는
[V2 LlamaIndex 프레임워크 파이프라인 개편](design-docs/v2-llamaindex-framework-redesign.md)이며,
generation 색인·framework Router/QueryEngine/ResponseSynthesizer·문장별 grounding SSE를 다음 구현 후보로
기록한다. 현재 코드가 이미 이 구조로 동작한다는 뜻은 아니다.

## 언제 더 읽어야 하는가

- 아키텍처·모듈 경계·배포 구조를 건드리는 작업 → `ARCHITECTURE.md`
- "왜 이렇게 만들었는가"가 필요한 작업 → `docs/design-docs/index.md`
- 과거 실행 세부사항(수치·재현 절차)이 필요한 작업 → 해당 `docs/exec-plans/active/` 또는 `completed/` 파일
- 개념 설명이 필요한 작업 → `docs/learning/`
- 알려진 결함·위험과 관련된 작업 → `docs/exec-plans/tech-debt-tracker.md`

## 이 파일을 갱신하는 시점

새 exec-plan이 `active/`로 이동하거나 완료될 때, 또는 굵직한 결정이 추가될 때만 갱신한다. 매 커밋마다
손보지 않는다 — 이 파일 자체가 새로운 상시 유지보수 부담이 되면 "context diet"의 취지에 어긋난다.

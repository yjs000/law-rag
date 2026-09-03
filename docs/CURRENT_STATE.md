# 현재 상태 (세션 시작 포인터)

세션 시작 시 기본으로 읽는 문서는 `AGENTS.md`와 이 파일뿐이다. `ARCHITECTURE.md`, `docs/design-docs/`,
과거 exec-plan, `docs/learning/`은 작업이 실제로 그 영역을 건드릴 때만 읽는다 — 매 세션 전체를 미리
읽지 않는다([0031](exec-plans/todo/0031-eval-harness-consolidation.md) item 5, 2026-08-08).

실행계획을 시작·재개할 때는 project-scoped [`roadmap-operator`](../.codex/skills/roadmap-operator/SKILL.md)의
최소 읽기 절차를 따른다. 실행계획 파일의 상단 메타데이터가 정본이고, `docs/ROADMAP.md`는 그 헤더에서
생성되는 얇은 색인이다.

## 지금 무엇이 진행 중인가

전체 milestone의 상태·우선순위·다음 행동은 생성된 [docs/ROADMAP.md](ROADMAP.md)에서 확인한다.
`docs/exec-plans/{todo,active,completed}/README.md`는 artifact 위치를 안내하는 lifecycle navigation이며
상태의 정본이 아니다.

`Picked Up` 항목이 있으면 해당 계획을 재개하고, 없으면 `Todo`의 첫 행을 선택한다. 로드맵은 세션
시작용 얇은 색인이며 모든 실행계획 본문을 읽으라는 뜻이 아니다.

가장 최근 결정은 [ARCHITECTURE.md 결정 기록](../ARCHITECTURE.md#결정-기록)의 최신 날짜 항목들이다.
최근 완료된 구현은 [V2 LlamaIndex 프레임워크 파이프라인 개편](exec-plans/completed/0061-v2-llamaindex-framework-pipeline.md)이다. generation 색인·active pointer, 서버 authoritative `question_execution` 기반 prepare/core/finalize API·grounded SSE와 웹 phase 상태기계를 검증했다.

## 언제 더 읽어야 하는가

- 기본 순서는 `docs/CURRENT_STATE.md` L1-L28, 생성된 `docs/ROADMAP.md`의 마지막 비완료 행, 선택한
  실행계획 파일의 상단 메타데이터, 그 헤더의 `참고 범위`다. 이 네 범위를 벗어나지 않는다.
- 범위 밖 문맥이 반드시 필요하면 읽기 전에 `경로`, `시작줄`, `끝줄`, `이유`를 선언하고 사용자에게
  알리거나 작업 기록에 남긴다. 상태 전이 전후에는 읽은 범위를 간결하게 보고한다.
- 아키텍처·모듈 경계·배포 구조를 건드리는 작업 → `ARCHITECTURE.md`
- "왜 이렇게 만들었는가"가 필요한 작업 → `docs/design-docs/index.md`
- 과거 실행 세부사항(수치·재현 절차)이 필요한 작업 → 해당 `docs/exec-plans/active/` 또는 `completed/` 파일
- 개념 설명이 필요한 작업 → `docs/learning/`
- 알려진 결함·위험과 관련된 작업 → `docs/exec-plans/tech-debt-tracker.md`

## 이 파일을 갱신하는 시점

새 exec-plan이 `active/`로 이동하거나 완료될 때, 또는 굵직한 결정이 추가될 때만 갱신한다. 상태 전이
전후에 사용한 읽은 범위 보고는 작업 기록에 남기되 매 커밋마다 이 파일을 손보지 않는다 — 이 파일
자체가 새로운 상시 유지보수 부담이 되면 "context diet"의 취지에 어긋난다.

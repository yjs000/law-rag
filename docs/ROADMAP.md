<!-- 생성 명령: python scripts/render_roadmap.py; 입력 메타데이터 digest: 00a6b1f683a8612b9fca99ef3f7241ae40b75fb21cd757d41cfb70b71917d7ed -->

# 프로젝트 로드맵

공통 프로젝트의 현재 작업 진입점입니다. 상세 범위·결정·검증은 연결된 실행계획이 권위 문서이며,
실행계획 작성 전인 승인 설계는 연결된 설계 문서를 따릅니다.

## Picked Up

- [OC-001 · Orchestration — OC-001: 우선순위 로드맵 병렬 오케스트레이션](exec-plans/active/0081-oc001-priority-roadmap-orchestration.md) — 다음 행동: B-003과 B-008을 독립 worktree에서 병렬 실행한다.

### OC-001 관리 작업

| 우선순위 | 작업 | 관리 상태 | 선행 작업 |
| --- | --- | --- | --- |
| P0 | [B-010](exec-plans/active/0079-allow-single-character-question-submission.md) | 대기 | B-003, B-008 |
| P1 | [F-007](exec-plans/active/0065-remove-checklist-export-frontend.md) | 대기 | B-003, B-008, B-010 |
| P1 | [F-009](exec-plans/active/0070-nvidia-free-tier-delay-and-sse-progress.md) | 대기 | F-007 |
| P1 | [F-010](exec-plans/active/0077-elementary-plain-language-prompt-refinement.md) | 대기 | B-003, B-008, B-010 |
| - | [B-003](exec-plans/completed/0060-v2-dynamic-today-date-bound.md) | - | 없음 |
| - | [B-008](exec-plans/completed/0076-hide-internal-routing-copy-from-limitations.md) | - | 없음 |


## Todo

- [F-002 · Feature — 실행 취소 범위·완료조건 감사 계획](exec-plans/todo/0012-distributed-question-cancellation.md) — 다음 행동: 현재 V1·V2 실행 취소 경로와 테스트를 대조해 지원 범위와 목표 충족 여부를 판정한다.
- [E-002 · Experiment — 0029: 필요 시 D-full Gold 제작](exec-plans/todo/0029-d-full-gold-on-demand.md) — 다음 행동: D-full 일반화 판단이 필요해지면 대상 문항·비용 상한을 확정한다.
- [E-003 · Experiment — 0031: 실험 D 평가 harness 통합 — machine-readable rubric, conflict detector, 통합 CLI](exec-plans/todo/0031-eval-harness-consolidation.md) — 다음 행동: 대량 판정 반복의 재발 근거를 확인한 뒤 착수 범위를 확정한다.
- [E-001 · Experiment — 0032: 실험 E-10 — AI 답변 소표본 평가 (0025 M6)](exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md) — 다음 행동: 재개할 품질 원인 진단 범위를 선택한다.
- [E-004 · Experiment — 0033: 트래픽 축적 후 라우팅·관측 재검토 묶음](exec-plans/todo/0033-traffic-based-routing-calibration-review.md) — 다음 행동: 오분류 또는 인증 표본이 누적되면 현재 router 정책을 재검토한다.
- [B-001 · Bug — 0047: 추가 정보 재질문 루프 중복 제거 및 미답변 처리](exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md) — 다음 행동: v2 clarification 루프 설계의 입력으로 재현 조건을 유지한다.
- [B-002 · Bug — 0050: 질의 형식 엣지케이스 조사 및 회귀 테스트 뱅크 구축](exec-plans/todo/0050-query-format-edge-case-regression-bank.md) — 다음 행동: 우선 조사할 질의 형식 엣지케이스 범위를 확정한다.
- [E-005 · Experiment — 0058: v2 청킹 ablation — 현재 조문 노드 vs LlamaIndex 하위 청킹](exec-plans/todo/0058-v2-chunking-ablation-d10.md) — 다음 행동: 청킹 파라미터·비용 상한·실험 DB 권한을 확정한다.
- [B-009 · Bug — clarification_required 상태·대화 연결 검증 Implementation Plan](exec-plans/todo/0078-clarification-state-conversation-verification.md) — 다음 행동: clarification 상태 전이표와 첫 질문부터 후속 답변까지의 회귀 시나리오를 고정한다.
- [E-007 · Experiment — LlamaIndex 임베딩·검색 단일 tool화와 선택 호출 가능성 검증](exec-plans/todo/0080-conditional-llamaindex-retrieval-tool-feasibility.md) — 다음 행동: 현재 conditional search 기준선과 단일 retrieval tool의 입력·출력·호출 금지 계약을 먼저 고정한다.

## Blocked


## Done

- [F-006-A · Feature — Web 기준일 선택 상한을 한국 오늘으로 동적 유지 Implementation Plan](exec-plans/completed/0064-web-dynamic-today-date-bound.md) — 다음 행동: 요구사항별 API 계약 회귀 테스트부터 시작
- [F-006-B · Feature — F-006-B 대화형 clarification workflow Implementation Plan](exec-plans/completed/0065-conversational-clarification-workflow.md) — 다음 행동: 완료되어 잔여 작업이 없습니다.
- [DOC-002 · Documentation — 0066: 로드맵 정본·컨텍스트 절약 구현 계획](exec-plans/completed/0066-roadmap-registry-and-context-diet.md) — 다음 행동: 완료 검증 기록을 유지하고 후속 변경에서 roadmap checker를 실행
- [B-004 · Bug — Production Web E2E Completion Loop Implementation Plan](exec-plans/completed/0067-production-web-e2e-completion-loop.md) — 다음 행동: 완료 — 다음 Todo 실행계획을 선택
- [F-008-A · Feature — F-008-A V2 Provider Capacity 3 Slots and Busy Notice Implementation Plan](exec-plans/completed/0067-provider-capacity-and-busy-notice.md) — 다음 행동: none
- [E-006 · Experiment — D-10 Gold batch defect 평가·봉인 기록](exec-plans/completed/0069-d10-gold-failure-driven-regression.md) — 다음 행동: none
- [B-005 · Bug — V2 Question Response Passthrough Implementation Plan](exec-plans/completed/0071-v2-question-response-passthrough.md) — 다음 행동: 완료되어 잔여 작업이 없습니다.
- [B-006 · Bug — NVIDIA Provider Attempt Observability Implementation Plan](exec-plans/completed/0072-provider-attempt-observability.md) — 다음 행동: none
- [DOC-003 · Documentation — 0073: 에이전트 제어면 단순화 실행 계획](exec-plans/completed/0073-agent-control-plane-simplification.md) — 다음 행동: 완료되어 잔여 작업이 없습니다.
- [B-007 · Bug — Runtime Error Observability and Environment Contract Implementation Plan](exec-plans/completed/0074-runtime-error-observability-and-env-contract.md) — 다음 행동: 없음 — 구현·문서·전체 검증 완료.
- [O-001 · Operations — Vercel Environment Scope Rollout Implementation Plan](exec-plans/completed/0075-vercel-environment-scope-rollout.md) — 다음 행동: 없음 — scope rollout, Production 배포와 smoke 검증 완료.
- [B-008 · Bug — 내부 라우팅 문구의 “범위와 한계” 노출 제거 Implementation Plan](exec-plans/completed/0076-hide-internal-routing-copy-from-limitations.md) — 다음 행동: 없음 — 구현·문서·통합 검증 완료.
- [완료 계획 색인](exec-plans/completed/README.md)

## Dropped

- [F-003 · Feature — 0042: 재순위를 실제 검색 경로에 연결](exec-plans/dropped/0042-wire-reranking-into-live-search-path.md) — 폐기 사유: 사용자가 라이브 검색 재순위를 진행하지 않기로 결정했다.
- [F-004 · Feature — 0044: 공급자 중립 답변 모델 선택 계약](exec-plans/dropped/0044-provider-neutral-answer-model-selection.md) — 폐기 사유: 사용자가 provider 중립 모델 선택 계약을 진행하지 않기로 결정했다.
- [F-001 · Feature — V3 LangGraph 에이전트 기본 골격 구현 계획](exec-plans/dropped/0055-v3-langgraph-agent-foundation.md) — 폐기 사유: 사용자가 V3를 아직 진행하지 않기로 결정했다.

<!-- 생성 명령: python scripts/render_roadmap.py; 입력 메타데이터 digest: 207dd70d71dc098206b98fd08b77b0515ef015c28629343a576a2e16fbd90465 -->

# 프로젝트 로드맵

공통 프로젝트의 현재 작업 진입점입니다. 상세 범위·결정·검증은 연결된 실행계획이 권위 문서이며,
실행계획 작성 전인 승인 설계는 연결된 설계 문서를 따릅니다.

## Picked Up


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
- [B-011 · Bug — 0082: clarification 응답의 missing_information이 사용자에게 빈 값으로 전달되는 문제](exec-plans/todo/0082-clarification-missing-information-allowlist-drops-fields.md) — 다음 행동: allowlist 완화안과 언어 계약 재검토안을 비교해 design-doc으로 먼저 고정한다.

## Blocked


## Done

- [F-008-A · Feature — F-008-A V2 Provider Capacity 3 Slots and Busy Notice Implementation Plan](exec-plans/completed/0067-provider-capacity-and-busy-notice.md) — 다음 행동: none
- [E-006 · Experiment — D-10 Gold batch defect 평가·봉인 기록](exec-plans/completed/0069-d10-gold-failure-driven-regression.md) — 다음 행동: none
- [F-009 · Feature — NVIDIA 무료 티어 지연 안내 및 finalize 상단 진행 표시 Implementation Plan](exec-plans/completed/0070-nvidia-free-tier-delay-and-sse-progress.md) — 다음 행동: 없음 — 구현·문서·통합 검증 완료.
- [B-005 · Bug — V2 Question Response Passthrough Implementation Plan](exec-plans/completed/0071-v2-question-response-passthrough.md) — 다음 행동: 완료되어 잔여 작업이 없습니다.
- [B-006 · Bug — NVIDIA Provider Attempt Observability Implementation Plan](exec-plans/completed/0072-provider-attempt-observability.md) — 다음 행동: none
- [DOC-003 · Documentation — 0073: 에이전트 제어면 단순화 실행 계획](exec-plans/completed/0073-agent-control-plane-simplification.md) — 다음 행동: 완료되어 잔여 작업이 없습니다.
- [B-007 · Bug — Runtime Error Observability and Environment Contract Implementation Plan](exec-plans/completed/0074-runtime-error-observability-and-env-contract.md) — 다음 행동: 없음 — 구현·문서·전체 검증 완료.
- [O-001 · Operations — Vercel Environment Scope Rollout Implementation Plan](exec-plans/completed/0075-vercel-environment-scope-rollout.md) — 다음 행동: 없음 — scope rollout, Production 배포와 smoke 검증 완료.
- [B-008 · Bug — 내부 라우팅 문구의 “범위와 한계” 노출 제거 Implementation Plan](exec-plans/completed/0076-hide-internal-routing-copy-from-limitations.md) — 다음 행동: 없음 — 구현·문서·통합 검증 완료.
- [F-010 · Feature — 초등학생도 이해할 수 있는 쉬운 한국어 프롬프트 정교화 Implementation Plan](exec-plans/completed/0077-elementary-plain-language-prompt-refinement.md) — 다음 행동: 없음 - 완료됨(확인된 한계 두 건은 0082, 0083 후속 작업으로 이관).
- [B-010 · Bug — 공백이 아닌 한 글자 질문도 전송 허용 Implementation Plan](exec-plans/completed/0079-allow-single-character-question-submission.md) — 다음 행동: 없음 — 구현·문서·통합 검증 완료.
- [OC-001 · Orchestration — OC-001: 우선순위 로드맵 병렬 오케스트레이션](exec-plans/completed/0081-oc001-priority-roadmap-orchestration.md) — 다음 행동: 없음 — 여섯 자식 모두 Done·completed/이고 통합·전체 검증이 완료됨.
- [완료 계획 색인](exec-plans/completed/README.md)

## Dropped

- [F-003 · Feature — 0042: 재순위를 실제 검색 경로에 연결](exec-plans/dropped/0042-wire-reranking-into-live-search-path.md) — 폐기 사유: 사용자가 라이브 검색 재순위를 진행하지 않기로 결정했다.
- [F-004 · Feature — 0044: 공급자 중립 답변 모델 선택 계약](exec-plans/dropped/0044-provider-neutral-answer-model-selection.md) — 폐기 사유: 사용자가 provider 중립 모델 선택 계약을 진행하지 않기로 결정했다.
- [F-001 · Feature — V3 LangGraph 에이전트 기본 골격 구현 계획](exec-plans/dropped/0055-v3-langgraph-agent-foundation.md) — 폐기 사유: 사용자가 V3를 아직 진행하지 않기로 결정했다.
- [B-012 · Bug — 0083: insufficient_evidence 질문이 routing_unavailable일 때 프롬프트 순응이 비결정적인 문제](exec-plans/dropped/0083-routing-unavailable-non-deterministic-prompt-compliance.md) — 폐기 사유: `routing_unavailable` 이후 LLM이 최종 안내를 생성하는 현재 동작과 출력 변동을 허용하기로 결정했다. 이 질문의 기대 route는 `external_document_required`가 맞지만, 이는 별도의 확장 가능한 routing 개발 calibration pool에서 다룰 평가 항목이며 이 버그 계획으로 재현·수정하지 않는다.

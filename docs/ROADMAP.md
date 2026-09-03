<!-- 생성 명령: python scripts/render_roadmap.py; 입력 메타데이터 digest: 232fab5a89a07dfec0db03e5e06427e344f47dd5207431ed0051a3f51c154e43 -->

# 프로젝트 로드맵

공통 프로젝트의 현재 작업 진입점입니다. 상세 범위·결정·검증은 연결된 실행계획이 권위 문서이며,
실행계획 작성 전인 승인 설계는 연결된 설계 문서를 따릅니다.

## Picked Up

- [B-004 · Bug — Production Web E2E Completion Loop Implementation Plan](exec-plans/active/0067-production-web-e2e-completion-loop.md) — 다음 행동: P0 첫 진입부터 AI 질문·근거 원문 정상 흐름을 배포 환경에서 검증

## Todo

- [F-002 · Feature — 분산 질문 취소 실행 계획](exec-plans/todo/0012-distributed-question-cancellation.md) — 다음 행동: NVIDIA hosted NIM의 explicit cancel ID 제공 여부를 확인하고 설계 가정을 현행화한다.
- [E-002 · Experiment — 0029: 필요 시 D-full Gold 제작](exec-plans/todo/0029-d-full-gold-on-demand.md) — 다음 행동: D-full 일반화 판단이 필요해지면 대상 문항·비용 상한을 확정한다.
- [E-003 · Experiment — 0031: 실험 D 평가 harness 통합 — machine-readable rubric, conflict detector, 통합 CLI](exec-plans/todo/0031-eval-harness-consolidation.md) — 다음 행동: 대량 판정 반복의 재발 근거를 확인한 뒤 착수 범위를 확정한다.
- [E-001 · Experiment — 0032: 실험 E-10 — AI 답변 소표본 평가 (0025 M6)](exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md) — 다음 행동: 재개할 품질 원인 진단 범위를 선택한다.
- [E-004 · Experiment — 0033: 트래픽 축적 후 라우팅·관측 재검토 묶음](exec-plans/todo/0033-traffic-based-routing-calibration-review.md) — 다음 행동: 오분류 또는 인증 표본이 누적되면 현재 router 정책을 재검토한다.
- [F-003 · Feature — 0042: 재순위를 실제 검색 경로에 연결](exec-plans/todo/0042-wire-reranking-into-live-search-path.md) — 다음 행동: 0041의 source_kind 신호를 확인하고 구현 범위를 확정한다.
- [F-004 · Feature — 0044: 공급자 중립 답변 모델 선택 계약](exec-plans/todo/0044-provider-neutral-answer-model-selection.md) — 다음 행동: provider/model 프로필과 공개 선택 범위를 설계한다.
- [B-001 · Bug — 0047: 추가 정보 재질문 루프 중복 제거 및 미답변 처리](exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md) — 다음 행동: v2 clarification 루프 설계의 입력으로 재현 조건을 유지한다.
- [B-002 · Bug — 0050: 질의 형식 엣지케이스 조사 및 회귀 테스트 뱅크 구축](exec-plans/todo/0050-query-format-edge-case-regression-bank.md) — 다음 행동: 우선 조사할 질의 형식 엣지케이스 범위를 확정한다.
- [F-001 · Feature — V3 LangGraph 에이전트 기본 골격 구현 계획](exec-plans/active/0055-v3-langgraph-agent-foundation.md) — 다음 행동: 다음 미시작 태스크의 착수 범위를 명시한다.
- [E-005 · Experiment — 0058: v2 청킹 ablation — 현재 조문 노드 vs LlamaIndex 하위 청킹](exec-plans/todo/0058-v2-chunking-ablation-d10.md) — 다음 행동: 청킹 파라미터·비용 상한·실험 DB 권한을 확정한다.
- [B-003 · Bug — 0060: V2 기준일 지원 상한을 한국 날짜 today로 동적 계산](exec-plans/todo/0060-v2-dynamic-today-date-bound.md) — 다음 행동: v2 temporal adapter 경계를 확정한다.
- [F-007 · Feature — 체크리스트 내보내기 프런트 제거 Implementation Plan](exec-plans/todo/0065-remove-checklist-export-frontend.md) — 다음 행동: UI·클라이언트 제거의 테스트 우선 구현을 시작한다.

## Blocked


## Done

- [F-006-A · Feature — Web 기준일 선택 상한을 한국 오늘으로 동적 유지 Implementation Plan](exec-plans/completed/0064-web-dynamic-today-date-bound.md) — 다음 행동: 요구사항별 API 계약 회귀 테스트부터 시작
- [F-006-B · Feature — F-006-B 대화형 clarification workflow Implementation Plan](exec-plans/completed/0065-conversational-clarification-workflow.md) — 다음 행동: 완료되어 잔여 작업이 없습니다.
- [DOC-002 · Documentation — 0066: 로드맵 정본·컨텍스트 절약 구현 계획](exec-plans/completed/0066-roadmap-registry-and-context-diet.md) — 다음 행동: 완료 검증 기록을 유지하고 후속 변경에서 roadmap checker를 실행
- [완료 계획 색인](exec-plans/completed/README.md)

<!-- 생성 명령: python scripts/render_roadmap.py; 입력 메타데이터 digest: 146abf5943bc308eda13a9c0f811837154cea5efa487275371f2a4cf8bc94cbe -->

# 프로젝트 로드맵

공통 프로젝트의 현재 작업 진입점입니다. 상세 범위·결정·검증은 연결된 실행계획이 권위 문서이며,
실행계획 작성 전인 승인 설계는 연결된 설계 문서를 따릅니다.

## Todo

- [F-002 · Feature — 분산 질문 취소 실행 계획](exec-plans/todo/0012-distributed-question-cancellation.md) — 다음 행동: NVIDIA hosted NIM 기준으로 취소 설계를 현행화
- [E-002 · Experiment — 0029: 필요 시 D-full Gold 제작](exec-plans/todo/0029-d-full-gold-on-demand.md) — 다음 행동: 실제 일반화·회귀 필요 시에만 착수
- [E-003 · Experiment — 0031: 실험 D 평가 harness 통합 — machine-readable rubric, conflict detector, 통합 CLI](exec-plans/todo/0031-eval-harness-consolidation.md) — 다음 행동: rubric·conflict detector·통합 CLI 착수 여부를 결정
- [E-001 · Experiment — 0032: 실험 E-10 — AI 답변 소표본 평가 (0025 M6)](exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md) — 다음 행동: 품질 원인 진단 범위를 선택
- [E-004 · Experiment — 0033: 트래픽 축적 후 라우팅·관측 재검토 묶음](exec-plans/todo/0033-traffic-based-routing-calibration-review.md) — 다음 행동: 실 트래픽 축적 후 단일 QuestionRouter 정책을 재검토
- [F-003 · Feature — 0042: 재순위를 실제 검색 경로에 연결](exec-plans/todo/0042-wire-reranking-into-live-search-path.md) — 다음 행동: 0041의 source_kind 신호를 확인하고 착수 범위를 결정
- [F-004 · Feature — 0044: 공급자 중립 답변 모델 선택 계약](exec-plans/todo/0044-provider-neutral-answer-model-selection.md) — 다음 행동: terra 호환을 유지하는 provider/model 설정 계약을 설계
- [B-001 · Bug — 0047: 추가 정보 재질문 루프 중복 제거 및 미답변 처리](exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md) — 다음 행동: v2 LangGraph 전환의 clarification 루프 입력으로 반영
- [B-002 · Bug — 0050: 질의 형식 엣지케이스 조사 및 회귀 테스트 뱅크 구축](exec-plans/todo/0050-query-format-edge-case-regression-bank.md) — 다음 행동: 우선 조사할 엣지케이스 범위를 확정
- [F-001 · Feature — V3 LangGraph 에이전트 기본 골격 구현 계획](exec-plans/active/0055-v3-langgraph-agent-foundation.md) — 다음 행동: 미시작 Task 12~16의 착수 범위를 명시
- [E-005 · Experiment — 0058: v2 청킹 ablation — 현재 조문 노드 vs LlamaIndex 하위 청킹](exec-plans/todo/0058-v2-chunking-ablation-d10.md) — 다음 행동: 동일 v2 snapshot에서 청킹별 top-k Recall을 비교
- [B-003 · Bug — 0060: V2 기준일 지원 상한을 한국 날짜 today로 동적 계산](exec-plans/todo/0060-v2-dynamic-today-date-bound.md) — 다음 행동: F-005 실행계획에서 temporal contract task 편입 여부를 결정
- [F-006 · Feature — Web 기준일 선택 상한을 한국 오늘으로 동적 유지 Implementation Plan](exec-plans/active/0064-web-dynamic-today-date-bound.md) — 다음 행동: 요구사항별 API 계약 회귀 테스트부터 시작
- [F-007 · Feature — 체크리스트 내보내기 프런트 제거 Implementation Plan](exec-plans/todo/0065-remove-checklist-export-frontend.md) — 다음 행동: UI·클라이언트 제거의 테스트 우선 구현을 시작

## Blocked


## Done

- [DOC-002 · Documentation — 0066: 로드맵 정본·컨텍스트 절약 구현 계획](exec-plans/completed/0066-roadmap-registry-and-context-diet.md) — 다음 행동: 완료 검증 기록을 유지하고 후속 변경에서 roadmap checker를 실행
- [완료 계획 색인](exec-plans/completed/README.md)

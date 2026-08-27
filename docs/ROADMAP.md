# 프로젝트 로드맵

공통 프로젝트의 현재 작업 진입점입니다. 상세 범위·결정·검증은 연결된 실행계획이 권위 문서이며,
실행계획 작성 전인 승인 설계는 연결된 설계 문서를 따릅니다.

## Picked Up

현재 `Picked Up` milestone은 없습니다.

## Todo

- [E-001 · Experiment — 0032: 실험 E-10 — AI 답변 소표본 평가](exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md) — 다음 행동: 품질 원인 진단 범위를 선택
- [F-001 · Feature — V3 LangGraph 에이전트 기본 골격](exec-plans/active/0055-v3-langgraph-agent-foundation.md) — 다음 행동: 미시작 Task 12~16의 착수 범위를 명시
- [F-002 · Feature — 0012: 분산 질문 취소](exec-plans/todo/0012-distributed-question-cancellation.md) — 다음 행동: NVIDIA hosted NIM 기준으로 취소 설계를 현행화
- [E-002 · Experiment — 0029: 필요 시 D-full Gold 제작](exec-plans/todo/0029-d-full-gold-on-demand.md) — 다음 행동: 실제 일반화·회귀 필요 시에만 착수
- [E-003 · Experiment — 0031: 실험 D 평가 harness 통합](exec-plans/todo/0031-eval-harness-consolidation.md) — 다음 행동: rubric·conflict detector·통합 CLI 착수 여부를 결정
- [E-004 · Experiment — 0033: 트래픽 축적 후 라우팅·관측 재검토 묶음](exec-plans/todo/0033-traffic-based-routing-calibration-review.md) — 다음 행동: 실 트래픽 축적 후 단일 QuestionRouter 정책을 재검토
- [F-003 · Feature — 0042: 재순위를 실제 검색 경로에 연결](exec-plans/todo/0042-wire-reranking-into-live-search-path.md) — 다음 행동: 0041의 `source_kind` 신호를 확인하고 착수 범위를 결정
- [F-004 · Feature — 0044: 공급자 중립 답변 모델 선택 계약](exec-plans/todo/0044-provider-neutral-answer-model-selection.md) — 다음 행동: `terra` 호환을 유지하는 provider/model 설정 계약을 설계
- [B-001 · Bug — 0047: 추가 정보 재질문 루프 중복 제거 및 미답변 처리](exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md) — 다음 행동: v2 LangGraph 전환의 clarification 루프 입력으로 반영
- [B-002 · Bug — 0050: 질의 형식 엣지케이스 조사 및 회귀 테스트 뱅크 구축](exec-plans/todo/0050-query-format-edge-case-regression-bank.md) — 다음 행동: 우선 조사할 엣지케이스 범위를 확정
- [E-005 · Experiment — 0058: v2 청킹 ablation](exec-plans/todo/0058-v2-chunking-ablation-d10.md) — 다음 행동: 동일 v2 snapshot에서 청킹별 top-k Recall을 비교
- [F-005 · Feature — V2 LlamaIndex 프레임워크 파이프라인 개편](design-docs/v2-llamaindex-framework-redesign.md) — 기존 `/v2/questions`를 제거하는 authoritative execution 기반 prepare/core/finalize API, typed `next_action`, phase 멱등·timeout·100명 동시접속 계약까지 승인, 아직 구현 전; 다음 행동: 별도 실행계획 작성
- [B-003 · Bug — 0060: V2 기준일 지원 상한을 한국 날짜 today로 동적 계산](exec-plans/todo/0060-v2-dynamic-today-date-bound.md) — 다음 행동: F-005 실행계획에서 temporal contract task로 포함할지 독립 선행 수정으로 둘지 결정

## Blocked

- [D-002 · Operations — 4단계 검색의 Production 실행계획과 병목 확인](exec-plans/completed/0008-four-stage-retrieval-latency-and-debugging.md) — 재개 조건: 승인된 비밀 설정 환경에서 읽기 전용 Production 진단을 실행
- [D-004 · Feature — Supabase 분산 취소와 Realtime Broadcast 운영 연결](exec-plans/todo/0012-distributed-question-cancellation.md) — 재개 조건: 운영 migration 승인을 받은 뒤 2인스턴스 취소·소유자 격리·UX·부하를 검증
- [D-005 · Operations — NVIDIA hosted NIM 실연결·법률 평가](exec-plans/completed/0013-nvidia-hosted-nim-integration.md) — 재개 조건: API key와 정책 승인 뒤 hosted smoke·고정 평가셋·운영 계약을 확인
- [D-009 · Operations — Production 질문 이력 scheduler 적용](exec-plans/completed/0015-history-retention-job.md) — 재개 조건: 대상 Supabase 승인과 extension 확인 뒤 일 1회 scheduler·최초 실행 감사·경보를 확인

## Done

- [DOC-001 · Documentation — 작업 관리 메타데이터와 얇은 로드맵](exec-plans/completed/0059-task-management-metadata-and-roadmap.md) — 작업 관리 계약, 현재 계획 메타데이터, 상태 색인을 완료
- [D-010 · Feature — 단일 단계 라우터와 라우터 불가 AI 응답](exec-plans/completed/0057-single-stage-router-and-failure-response.md) — 라우터와 실패 응답 계약을 완료
- [0056: Python docstring과 Ruff D 규칙](exec-plans/completed/0056-python-docstrings-and-ruff-d.md) — 문서화 규칙을 정비
- [0053: V2 LlamaIndex 검색 파이프라인](exec-plans/completed/0053-v2-llamaindex-retrieval-pipeline.md) — V2 검색 파이프라인을 완료
- [0054: V2 준비 상태와 HNSW 운영](exec-plans/completed/0054-v2-readiness-and-hnsw.md) — 준비 상태와 HNSW 운영을 완료
- [0045: Web/API 질문 timeout 예산 정렬](exec-plans/completed/0045-coordinated-question-timeout-budget.md) — 질문 timeout 예산을 정렬
- [0046: terra 모드 search_only 폴백 제거 (always-generate)](exec-plans/completed/0046-terra-always-generate.md) — always-generate 계약으로 전환
- [0043: 일반인 답변 계약 v2와 가독성 평가](exec-plans/completed/0043-layperson-answer-contract-v2.md) — 답변 계약 v2를 반영
- [0039: 구조화된 API 오류 메시지 표시](exec-plans/completed/0039-error-detail-object-shown-as-object-object.md) — 구조화된 오류 표시를 반영
- [0038: 모델 호출 없는 API는 전부 1초 이내 응답](exec-plans/completed/0038-non-model-endpoints-under-1s.md) — 비모델 API 응답 목표를 달성

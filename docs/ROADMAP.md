<!-- 생성 명령: python scripts/render_roadmap.py; 입력 메타데이터 digest: cd0acf020a7477eb5d26962f3e2becbf9b52dbb669a14f8666f4a8b291aa87e7 -->

# 프로젝트 로드맵

공통 프로젝트의 현재 작업 진입점입니다. 상세 범위·결정·검증은 연결된 실행계획이 권위 문서이며,
실행계획 작성 전인 승인 설계는 연결된 설계 문서를 따릅니다.

## Picked Up

- [P0] [B-020 · Bug — V2가 질문에 필요한 구체 근거를 찾아 답하도록 개선](exec-plans/active/0092-v2-question-directed-evidence.md) — 다음 행동: 화재안전 기준 요약이 근거 검증에서 거부된 원인을 확인하고 색인된 첨부서류 검색 회귀를 확정한다.

## Todo

- [P1] [B-016 · Bug — Clarification 원 질문·누적 사실 기반 답변 입력](exec-plans/todo/0087-clarification-case-grounded-answer-input.md) — 다음 행동: 저장된 원 질문·누적 fact를 검색과 답변에 전달할 최소 데이터 경계 및 보존 방식을 설계하고 구현 계획을 작성한다.
- [P1] [O-002 · Operations — dev 브랜치 Vercel Preview 환경](exec-plans/todo/0089-dev-vercel-preview-environment.md) — 다음 행동: 기존 웹·API Vercel 프로젝트의 Preview 브랜치 설정과 dev 전용 API·인증·데이터 연결을 설계한다.
- [P1] [B-018 · Bug — V1 인용 수치와 체크리스트 수치 불일치 검증](exec-plans/todo/0090-v1-cited-quantity-consistency.md) — 다음 행동: V1 답변 검증에서 C5의 `3천킬로와트`와 체크리스트의 `3kW` 불일치를 재현하고, 오탐을 늘리지 않는 최소 수치 검증 경계를 확정한다.
- [P1] [B-019 · Bug — V2 답변의 인용 근거와 적용 대상·수치 불일치](exec-plans/todo/0091-v2-cited-claim-consistency.md) — 다음 행동: V2 최종 답변의 적용 대상 반전과 수치·단위 불일치 두 건을 재현하고, 게시 전 검증의 최소 범위를 확정한다.
- [P1] [B-021 · Bug — 공식 별지 서식을 답변 근거로 수록](exec-plans/todo/0093-official-statutory-form-evidence.md) — 다음 행동: 국가법령정보 Open API가 전기사업법 시행규칙 별지 제1호·제3호의 서식명과 원문을 어떻게 제공하는지 확인한다.
- [P2] [E-001 · Experiment — 0032: 실험 E-10 — AI 답변 소표본 평가 (0025 M6)](exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md) — 다음 행동: 재개할 품질 원인 진단 범위를 선택한다.
- [P2] [B-001 · Bug — 0047: 추가 정보 재질문 루프 중복 제거 및 미답변 처리](exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md) — 다음 행동: v2 clarification 루프 설계의 입력으로 재현 조건을 유지한다.
- [P3] [E-003 · Experiment — 0031: 실험 D 평가 harness 통합 — machine-readable rubric, conflict detector, 통합 CLI](exec-plans/todo/0031-eval-harness-consolidation.md) — 다음 행동: 대량 판정 반복의 재발 근거를 확인한 뒤 착수 범위를 확정한다.
- [P3] [E-004 · Experiment — 0033: 트래픽 축적 후 라우팅·관측 재검토 묶음](exec-plans/todo/0033-traffic-based-routing-calibration-review.md) — 다음 행동: 오분류 또는 인증 표본이 누적되면 현재 router 정책을 재검토한다.
- [P3] [E-005 · Experiment — 0058: v2 청킹 ablation — 현재 조문 노드 vs LlamaIndex 하위 청킹](exec-plans/todo/0058-v2-chunking-ablation-d10.md) — 다음 행동: 청킹 파라미터·비용 상한·실험 DB 권한을 확정한다.
- [P3] [E-007 · Experiment — LlamaIndex 임베딩·검색 단일 tool화와 선택 호출 가능성 검증](exec-plans/todo/0080-conditional-llamaindex-retrieval-tool-feasibility.md) — 다음 행동: 현재 conditional search 기준선과 단일 retrieval tool의 입력·출력·호출 금지 계약을 먼저 고정한다.

## Blocked

- [P1] [B-009 · Bug — clarification_required 상태·대화 연결 검증 Implementation Plan](exec-plans/active/0078-clarification-state-conversation-verification.md) — 재개 조건: B-013·B-015·B-016·B-014 완료 후 최초 추가 질문부터 최종 답변까지 통합 acceptance를 실행한다.
- [P1] [B-014 · Bug — Clarification Continuation Cross-Layer Regression Implementation Plan](exec-plans/active/0085-clarification-continuation-cross-layer-regression.md) — 재개 조건: B-015·B-016 완료 뒤 API stale case conflict, Web continuation payload, 자유 문장 답변부터 최종 답변까지의 교차 계층 회귀를 고정한다.

## Done

- [DOC-003 · Documentation — 0073: 에이전트 제어면 단순화 실행 계획](exec-plans/completed/0073-agent-control-plane-simplification.md) — 다음 행동: 완료되어 잔여 작업이 없습니다.
- [B-007 · Bug — Runtime Error Observability and Environment Contract Implementation Plan](exec-plans/completed/0074-runtime-error-observability-and-env-contract.md) — 다음 행동: 없음 — 구현·문서·전체 검증 완료.
- [O-001 · Operations — Vercel Environment Scope Rollout Implementation Plan](exec-plans/completed/0075-vercel-environment-scope-rollout.md) — 다음 행동: 없음 — scope rollout, Production 배포와 smoke 검증 완료.
- [B-008 · Bug — 내부 라우팅 문구의 “범위와 한계” 노출 제거 Implementation Plan](exec-plans/completed/0076-hide-internal-routing-copy-from-limitations.md) — 다음 행동: 없음 — 구현·문서·통합 검증 완료.
- [F-010 · Feature — 초등학생도 이해할 수 있는 쉬운 한국어 프롬프트 정교화 Implementation Plan](exec-plans/completed/0077-elementary-plain-language-prompt-refinement.md) — 다음 행동: 없음 - 완료됨(확인된 한계 두 건은 0082, 0083 후속 작업으로 이관).
- [B-010 · Bug — 공백이 아닌 한 글자 질문도 전송 허용 Implementation Plan](exec-plans/completed/0079-allow-single-character-question-submission.md) — 다음 행동: 없음 — 구현·문서·통합 검증 완료.
- [OC-001 · Orchestration — OC-001: 우선순위 로드맵 병렬 오케스트레이션](exec-plans/completed/0081-oc001-priority-roadmap-orchestration.md) — 다음 행동: 없음 — 여섯 자식 모두 Done·completed/이고 통합·전체 검증이 완료됨.
- [B-011 · Bug — 0082: clarification 응답의 missing_information이 사용자에게 빈 값으로 전달되는 문제](exec-plans/completed/0082-clarification-missing-information-allowlist-drops-fields.md) — 다음 행동: 없음 — 구조 검증, 프롬프트 계약, provenance와 전체 회귀 검증 완료.
- [B-013 · Bug — LlamaIndex Clarification Context State Contract Implementation Plan](exec-plans/completed/0084-clarification-workflow-context-state-contract.md) — 다음 행동: 없음 — run별 Context 격리와 관련 회귀 검증 완료.
- [B-015 · Bug — Clarification 자유 문장 fact 추출 Implementation Plan](exec-plans/completed/0086-clarification-free-text-fact-extraction.md) — 다음 행동: 없음 — 4개 Task 전부 완료, task-level review·최종 whole-branch review clean, `main`에 로컬 병합 완료.
- [B-017 · Bug — 답변의 결론 우선·쉬운 말·근거 표시 개선](exec-plans/completed/0088-answer-readability-and-evidence-layout.md) — 다음 행동: 없음 — V2 근거 불일치는 B-019에서 추적한다.
- [B-023 · Bug — V2 공개 요약 전체를 쉬운 말로 표현하기](exec-plans/completed/0095-v2-plain-summary.md) — 다음 행동: 없음.
- [완료 계획 색인](exec-plans/completed/README.md)

## Dropped

- [F-002 · Feature — 실행 취소 범위·완료조건 감사 계획](exec-plans/dropped/0012-distributed-question-cancellation.md) — 폐기 사유: 2026-10-21 사용자가 현재 우선순위에서 이 감사 계획을 삭제하기로 결정했다. 실제 취소 실패가 관찰되면 새 계획으로 범위를 다시 정한다.
- [E-002 · Experiment — 0029: 필요 시 D-full Gold 제작](exec-plans/dropped/0029-d-full-gold-on-demand.md) — 폐기 사유: 2026-10-21 사용자가 대형 Gold 제작 계획을 삭제하기로 결정했다. 현재 가독성 문제의 최소 검증에는 소표본 평가가 적합하다.
- [F-003 · Feature — 0042: 재순위를 실제 검색 경로에 연결](exec-plans/dropped/0042-wire-reranking-into-live-search-path.md) — 폐기 사유: 사용자가 라이브 검색 재순위를 진행하지 않기로 결정했다.
- [F-004 · Feature — 0044: 공급자 중립 답변 모델 선택 계약](exec-plans/dropped/0044-provider-neutral-answer-model-selection.md) — 폐기 사유: 사용자가 provider 중립 모델 선택 계약을 진행하지 않기로 결정했다.
- [B-002 · Bug — 0050: 질의 형식 엣지케이스 조사 및 회귀 테스트 뱅크 구축](exec-plans/dropped/0050-query-format-edge-case-regression-bank.md) — 폐기 사유: 2026-10-21 사용자가 광범위한 엣지케이스 뱅크 계획을 삭제하기로 결정했다. 실제 발견 사례는 해당 기능의 좁은 회귀 테스트로 다룬다.
- [F-001 · Feature — V3 LangGraph 에이전트 기본 골격 구현 계획](exec-plans/dropped/0055-v3-langgraph-agent-foundation.md) — 폐기 사유: 사용자가 V3를 아직 진행하지 않기로 결정했다.
- [B-012 · Bug — 0083: insufficient_evidence 질문이 routing_unavailable일 때 프롬프트 순응이 비결정적인 문제](exec-plans/dropped/0083-routing-unavailable-non-deterministic-prompt-compliance.md) — 폐기 사유: `routing_unavailable` 이후 LLM이 최종 안내를 생성하는 현재 동작과 출력 변동을 허용하기로 결정했다. 이 질문의 기대 route는 `external_document_required`가 맞지만, 이는 별도의 확장 가능한 routing 개발 calibration pool에서 다룰 평가 항목이며 이 버그 계획으로 재현·수정하지 않는다.
- [B-022 · Bug — 자가용 설비와 방화구획의 참조 규칙 수록](exec-plans/dropped/0094-referenced-safety-rules-corpus.md) — 폐기 사유: 사용자 결정에 따라 참조 규칙 수집 대신 현재 확인된 근거의 범위와 공식 원문 확인 방법을 안내한다.

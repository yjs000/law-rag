# 예정 작업 트랙

사용자가 다음 작업 또는 추후 개선안으로 명시했지만 아직 착수하지 않은 실행계획을 둡니다. 전역 우선순위와 상태 순서는 [프로젝트 로드맵](../../ROADMAP.md)을 따릅니다.

## Todo

- [F-002 · Feature — 0012: 분산 질문 취소](0012-distributed-question-cancellation.md) — 다음 행동: NVIDIA hosted NIM 기준으로 취소 설계를 현행화
- [E-002 · Experiment — 0029: 필요 시 D-full Gold 제작](0029-d-full-gold-on-demand.md) — 다음 행동: 실제 일반화·회귀 필요 시에만 착수
- [E-003 · Experiment — 0031: 실험 D 평가 harness 통합](0031-eval-harness-consolidation.md) — 다음 행동: rubric·conflict detector·통합 CLI 착수 여부를 결정
- [E-004 · Experiment — 0033: 트래픽 축적 후 라우팅·관측 재검토 묶음](0033-traffic-based-routing-calibration-review.md) — 다음 행동: 실 트래픽 축적 후 단일 QuestionRouter 정책을 재검토
- [F-003 · Feature — 0042: 재순위를 실제 검색 경로에 연결](0042-wire-reranking-into-live-search-path.md) — 다음 행동: 0041의 `source_kind` 신호를 확인하고 착수 범위를 결정
- [F-004 · Feature — 0044: 공급자 중립 답변 모델 선택 계약](0044-provider-neutral-answer-model-selection.md) — 다음 행동: `terra` 호환을 유지하는 provider/model 설정 계약을 설계
- [B-001 · Bug — 0047: 추가 정보 재질문 루프 중복 제거 및 미답변 처리](0047-clarification-loop-dedup-and-unanswered-handling.md) — 다음 행동: v2 LangGraph 전환의 clarification 루프 입력으로 반영
- [B-002 · Bug — 0050: 질의 형식 엣지케이스 조사 및 회귀 테스트 뱅크 구축](0050-query-format-edge-case-regression-bank.md) — 다음 행동: 우선 조사할 엣지케이스 범위를 확정
- [E-005 · Experiment — 0058: v2 청킹 ablation](0058-v2-chunking-ablation-d10.md) — 다음 행동: 동일 v2 snapshot에서 청킹별 top-k Recall을 비교
- [B-003 · Bug — 0060: V2 기준일 지원 상한을 한국 날짜 today로 동적 계산](0060-v2-dynamic-today-date-bound.md) — 다음 행동: F-005 실행계획에서 temporal contract task로 포함할지 독립 선행 수정으로 둘지 결정

## 등록 계약

- 사용자 요청에서 명시적으로 다음 작업·추후 작업으로 분리한 결과를 항목 하나당 파일 하나로 등록한다.
- 전체 실행 계획 번호와 겹치지 않는 다음 번호를 부여한다. 착수·완료 뒤에도 번호와 파일명은 유지한다.
- 각 항목에는 제안 출처와 날짜, 목적, 범위·비범위, 의존성, 승격 조건, 검증 가능한 완료 조건을 적는다.
- 우선순위나 제품 결정을 사용자가 확정하지 않았다면 `제안됨`으로 표시하고 사실처럼 확정하지 않는다.
- 현재 active 계획에서 미착수 후속 작업을 분리할 때는 양쪽 문서가 서로 연결되게 한다.
- 인증정보, 사용자 데이터, 대화 전문은 복제하지 않고 작업에 필요한 결정만 요약한다.

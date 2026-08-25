> 작업 ID: `E-003`
> 상태: `Todo`
> 유형: `Experiment`
> 보조 라벨: `Evaluation`
> 선행 조건: 사용자가 착수를 명시하고 대량 판정·정정 반복이 다시 문제라는 근거를 확인해야 한다.
> 참고 범위:
> - `docs/exec-plans/todo/0031-eval-harness-consolidation.md` L60-L64 — 착수 승인과 재작업 비용 재발에 따른 승격 조건

# 0031: 실험 D 평가 harness 통합 — machine-readable rubric, conflict detector, 통합 CLI

상태: `제안됨 · 항목 5(agent context diet) 반영 완료(2026-08-08) · 나머지(rubric·conflict
detector·통합 CLI·정확한 token 계산·decision 정규화) 미착수`

제안 출처: 2026-08-07 사용자가 외부(ChatGPT) harness 설계 검토를 공유하고 그 방향으로 최적화를
요청했다. 저비용 항목(rubric/calibration 버전 분리, WORK_CONTRACT scope 제한, learning 문서 갱신
완화)은 같은 날 [plan 0025](../active/0025-approved-questions-to-grounded-answer-roadmap.md)에 바로
반영했다. 이 항목은 그중 실제 코드 인프라가 필요한 나머지를 별도 작업으로 등록한다.

## 목적

D-10 v1→v2→v3처럼 "판정 하나 정정 → 전체 재문서화" 패턴이 반복되는 근본 원인(의미 결정·artifact·SHA·
문서·지표가 분리되지 않음)을 코드로 없앤다. Codex가 매번 관련 스크립트·artifact ID·SHA를 문서에서
찾아 실행하는 대신, 하나의 CLI가 상태를 읽고 결정적으로 처리하게 만든다.

## 범위

1. **machine-readable relevance rubric**: `relevance_2`/`relevance_1`/`relevance_0`을 prose가 아니라
   `requires`/`excludes` 조건으로 구조화하고, `0561`(배경 맥락 아님)·`0601`(위임 조항 아님, 원문
   직접 서술)을 counter-example fixture로 고정한다.
2. **conflict detector**: 이번에 사용자가 수작업으로 한 0026 vs sealed Gold 전수 대조를 자동화한다.
   최소 규칙:
   - `rank <= 3 and relevance == 0` → `HIGH_RANK_NEGATIVE` 플래그
   - `historical_relevance == 2 and current_relevance < 2` → `JUDGMENT_CONFLICT` 플래그
   - `relevance == 2 and not supported_facet` → `DIRECT_EVIDENCE_WITHOUT_FACET` 실패
   - `answerability == fully_answerable and positive_qrel_count == 0` → 실패
   사용자에게는 "30,660건 검토"가 아니라 "자동 통과 N / 검토 필요 M(우선순위 표시)"만 보여준다.
3. **통합 eval CLI + `state.yaml`**: 기존 `experiment_d_*` 스크립트 15개 내외를 당장 삭제하지 않고
   `apps/api/eval/`(schema/dataset/judgments/conflicts/metrics/rerank/context/promotion/report) 공용
   라이브러리로 감싼 뒤 `rag-eval check|diagnose|metrics|rerank|context|report|promote` 인터페이스로
   노출한다. `d10-gold-20260807...` 같은 draft/run ID 하드코딩을 `experiments/d10/state.yaml`
   포인터(mode/rubric/question_set/corpus/retrieval_run/rerank/judgments/milestone) 하나로 옮긴다.
4. **정확한 token 계산**: M4의 `total_chars / 2.2` 근사치를 실제 NVIDIA/tokenizer 계산으로 교체한다.
5. **agent context diet** — 완료(2026-08-08, 아래 결정 기록 참고): 세션 시작 시 항상 읽는 문서를
   `AGENTS.md` + 짧은 `docs/CURRENT_STATE.md` 포인터로 줄이고, `ARCHITECTURE.md`·design docs·과거
   exec-plan·learning은 필요할 때만 읽게 한다.
6. **decision 정규화**: 같은 결정이 0025/0030/design doc/generated summary/learning/commit에 조금씩
   다른 말로 중복되지 않도록, ID가 붙은 구조화 decision record(`{id, scope, type, status, decision,
   supersedes, reason, effective_from}`)를 도입하고 문서는 "현재 계약: EVAL-REL-002"처럼 최신
   ID만 가리킨다.

## 비범위

- 기존 `experiment_d_*` 스크립트의 즉시 삭제나 대규모 리팩터 — 래핑부터 시작하고 안정화된 뒤에만
  걷어낸다.
- LLM 판정을 rubric 자동화로 전부 대체하는 것 — 애매한 "이 조항이 이 facet을 직접 뒷받침하나?" 류
  판단은 여전히 사람/LLM이 한다. 자동화 대상은 명백한 구조·정합성 검증뿐이다.
- M4.5 라우터 구현(별도 [0028](../active/0028-pre-retrieval-question-routing.md) 범위).

## 승격 조건

- 사용자가 착수를 명시한다.
- D-full(0029) 재개처럼 이 패턴(대량 판정·정정 반복)이 다시 필요해지는 시점, 또는 현재 방식의 재작업
  비용이 실제로 다시 문제가 될 때 우선 검토한다.

## 결정 기록

- 2026-08-07: 저비용 항목(rubric/calibration 버전 분리, WORK_CONTRACT scope, learning 갱신 완화)은
  즉시 plan 0025에 반영했다. 코드 인프라가 필요한 나머지(rubric 파일, conflict detector, 통합 CLI,
  state.yaml, context diet, decision 정규화)는 이 todo로 분리해 필요할 때 착수한다.
- 2026-08-08: 사용자가 항목 5(agent context diet)만 지금 착수하기로 결정했다. 코드 인프라(rubric,
  conflict detector, CLI, state.yaml, decision 정규화)가 필요 없는 저비용 항목이라 별도 active plan
  없이 바로 반영했다 — 위 2026-08-07 결정과 같은 패턴("저비용 항목은 즉시 반영, 인프라가 필요한
  나머지만 별도 착수 대상")이다. `docs/CURRENT_STATE.md`(신규)를 세션 시작 시 기본으로 읽는 짧은
  포인터로 추가하고, `AGENTS.md`의 "작업 시작 순서"에서 `ARCHITECTURE.md`·`docs/design-docs/`·
  `docs/product-specs/`를 항상 읽던 것을 작업이 실제로 그 영역을 건드릴 때만 읽도록 좁혔다. 나머지
  항목(rubric/conflict detector/통합 CLI/정확한 token 계산/decision 정규화)은 여전히 코드 인프라가
  필요해 미착수 상태로 `todo/`에 남긴다.

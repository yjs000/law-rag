> 작업 ID: `E-001`
> 상태: `Todo`
> 유형: `Experiment`
> 보조 라벨: `Evaluation`
> 선행 조건: E-10 base 결과가 기록되어 있고, 재개 전 품질 원인 진단 범위를 선택해야 한다.
> 참고 범위:
> - `apps/api/app/adapters/openai_answerer.py` L362-L377 — 구조 검증과 검색·재순위 품질 책임의 현재 진단 경계
> - `docs/exec-plans/completed/0025-approved-questions-to-grounded-answer-roadmap.md` L600-L604 — E-10 안전 gate는 일반 품질·release 근거가 아니며 별도 범위 판단이 필요함

# 0032: 실험 E-10 — AI 답변 소표본 평가 (0025 M6)

상태: `E-10 base 실행 완료(2026-08-08) — 라우팅 7/7 gold 일치, 생성 6회 중 완전 성공 0건
(503 공유 용량 1건, timeout 1건, grounding_failed 4건) — 안전 gate는 전부 통과했으나
품질 원인 미진단`

착수일: 2026-08-08

제안 출처: [0025 M6](../completed/0025-approved-questions-to-grounded-answer-roadmap.md#m6--실험-e-10-ai-답변-소표본-평가)
"실제 호출 전에 별도 active 실행 계획을 만들고 10문항의 호출 수·비용·판정표를 사전 등록한다"는
로드맵 요구에 따라 2026-08-08 사용자가 계획 수립을 지시했다.

## 현재 D-010 실행 계약 (2026-08-25)

D-010(0057)이 현재 런타임 계약이다. 질문은 단일 NVIDIA `QuestionRouter`를 거친 뒤
`legal_search`에 한해 임베딩·검색·답변 생성·검증으로 진행하며, 라우팅 실패는 검색을 시작하지
않고 `routing_unavailable` 안전 응답으로 끝난다. 이 문서의 아래 E-10 범위·호출 수·판정표는
2026-08-08에 작성·실행된 실험의 역사적 증거를 보존하는 것이며 현재 라우팅 계약을 정의하지
않는다.

## 역사적 E-10 실행 기록 (2026-08-08; D-010으로 대체됨)

## 목적과 사용자 결과

0025 M5(2026-08-08 완료)에서 실배선한 NVIDIA 답변 생성 파이프라인을, 이미 sealed된
[D-10 10문항 Gold(0030)](../completed/0030-d-10-full-corpus-qrels-adjudication.md) 기준으로
소표본 평가한다. E-10은 **사용자 확인 진단**이며 일반 release gate가 아니다(0025 M6). D-full
(pilot 50/calibration 200/held-out 800) 규모 평가는
[0029(D-full Gold)](../todo/0029-d-full-gold-on-demand.md)가 먼저 활성화돼야 하며, 0029는 현재
`보류 · 미착수` 상태라 이 계획의 범위 밖이다.

## 범위

1. **E0 — 외부 호출 없는 결정적 검사**(0025 M6 E0 그대로): schema와 네 답변 동작, citation
   ID·source URL·문서·버전·기준일·본문 SHA, 인용 없는 claim·checklist 형식과 인용하지 않은
   숫자·규범어 차단, `no_evidence`·`corpus_unready`·`unsupported_date`·provider 실패 fallback.
   기존 `validate_draft`(`app/adapters/openai_answerer.py`)와
   `test_ai_fallback.py`/`test_grounding_gate.py`가 이미 이 계층을 mock으로 커버하므로, E0은
   그 커버리지가 실제 hosted 응답에도 성립하는지 재확인하는 역할이다.
2. **E-10 base — D-10 10문항 실제 hosted 실행(역사적 기록)**: 동결 M4 문맥(승자 R1+A)으로
   10문항 각각 실제 NVIDIA 답변 생성을 1회 호출하고, 당시의 라우팅(tier1/tier2) 설명도
   실제 파이프라인 기록으로 보존한다. 이 tier 표현은 현재 D-010 런타임에 적용되지 않는다.

## 비범위

- D-full pilot 50문항(E1)·calibration 200문항(E2)·held-out 800문항(E3) — 0029 활성화 후 별도 계획
- 별도 LLM judge 도입 (0025: "추가 비용과 순환 평가 없이 부족한 경우에만 후속 실험으로 검토")
- 실패 시 같은 version 재튜닝 — 변경이 필요하면 새 version으로 처음부터
- `temperature`/`answer_timeout_seconds`의 확정적 튜닝(관찰만 하고, 확정은 결과를 본 뒤 별도 결정)

## 호출 수·비용 사전 등록

- **역사적 라우팅**: 당시 tier1이 D-10 4문항(`0251`·`0111`·`0605`·`0836`)을 무료로 즉시
  처리했다(`route-fixture-v1-results.json` 확인). 나머지 6문항만 당시 tier2 LLM 호출 대상 —
  **최대 6회**.
- **역사적 답변 생성**: `legal_search`로 라우팅되는 문항만 실제 생성 호출 대상. 당시 tier1이 잡은
  4문항 중
  `0605`·`0836`(realtime)·`0251`·`0111`(clarification)은 라우팅 단계에서 차단 응답으로 끝나
  생성 호출이 없다. 나머지 6문항이 당시 tier2에서 `legal_search`로 판정되면 그만큼만 생성
  호출 — **최대 6회**.
- **역사적 총 상한**: 당시 라우팅(tier2) 최대 6회 + 답변 생성 최대 6회 = **최대 12회** 실제
  NVIDIA 호출. 실제로는 tier2가 일부를 `clarification_required`/`realtime_required`/
  `external_document_required`로 판정하면 그만큼 생성 호출이 줄어든다.
- **비용**: NVIDIA 무료 티어라 금전 비용은 0원이다. 다만 공유 worker pool 동시성 제한(32건,
  2026-08-08 조사 - [0028 결정 기록](../completed/0028-pre-retrieval-question-routing.md) 참고)에 걸릴 수
  있어, 필요하면 `scripts/live_fixture_retry_runner.py`와 같은 방식(10초 간격 재시도, 실패한
  케이스만)으로 재시도한다.
- **반복성**: 0025 E3 방식(사전 봉인 10~20문항 3회 반복)은 D-full 규모용이다. 지금은 10문항
  전체가 이미 소표본이므로 첫 실행 결과를 보고 반복 측정 필요 여부를 판단한다 - 미리 3배
  호출을 확정하지 않는다.

## 판정표 (사전 등록)

**필수 안전 gate**(0025 M6 "E-10 필수 안전 gate" 그대로, 하나라도 위반하면 통과 아님):

- 존재하지 않거나 기준일·source·본문이 틀린 citation 0건
- 근거 없는 중대 규범 주장 0건
- `corpus_unready`·unsupported date에서 생성 0건
- provider·schema·grounding 실패 시 검색 전용 fallback 100%

**참고 지표**(diagnostic-only, gate 아님 — 이번 실행으로 처음 실측하므로 아직 임계값을 정하지
않는다):

- D-10 gold의 answerability와 `derive_answer_action()` 결과 일치율 (0025 M5 TODO 최초 검증)
- `generation_profile_key`/`sha256`·라우팅 `explanation` 기록 완전성(0028/M5 diagnostics 참고)
- 답변 생성 latency 분포 (temperature=0.3·answer_timeout_seconds=60 실측 재검증)

## 의존성과 미결정

- D-full 규모(E1/E2/E3)는 0029 활성화 전까지 이 계획 범위 밖이다.
- `derive_answer_action()`의 checklist→action 매핑 규칙은 이번 실행으로 처음 D-10과 대조된다 -
  결과를 보고 규칙을 그대로 확정할지 고칠지는 별도 결정이 필요하다.
- `temperature=0.3`·`answer_timeout_seconds=60`은 이번 실행에서 관찰되는 latency로
  재검증하되, 이 계획 안에서 값을 바꾸지는 않는다(비범위 참고).

## active 승격 조건

- 사용자가 위 호출 수 상한(최대 12회, 무료 티어)과 판정표에 동의하고 실제 실행을 명시적으로
  승인한다.

## 완료 조건

- E0 결정적 검사가 전부 통과한다(기존 mock 기반 테스트 커버리지가 hosted 응답에도 성립).
- D-10 10문항 각각의 실행 결과(route, action, citation, latency, provider 오류 여부, 반복
  호출 여부)를 원자적 JSON으로 게시한다 — model·prompt·schema·context·sampling·code SHA,
  raw structured response, validator 결과, token·지연·비용, provider 오류를 포함한다(0025 M6
  기록 요구사항 그대로).
- 필수 안전 gate 4개를 전부 통과하거나, 위반 건을 숨기지 않고 명시적으로 기록한다.
- 결과를 0025(M6 완료 표시)와 0028(라우팅 실측치 갱신)에 링크한다.

## 결정 기록

- 2026-08-08: 사용자가 M6 계획 수립을 지시했다. E1/E2/E3(D-full 50/200/800)는 0029가 아직
  `보류 · 미착수`라 이 계획의 범위 밖으로 확정하고, E0 + D-10 기반 E-10 base(최대 12회 호출,
  무료 티어)만 지금 active 계획 범위로 잡았다. 실제 실행은 사용자의 별도 승인을 받은 뒤
  진행한다.
- 2026-08-08: 사용자가 실행을 승인해 `scripts/run_experiment_e10.py`로 E-10 base를
  실행했다. 호출 수는 예산 내(라우팅 7회, 생성 6회, 최대 7/7 상한 이내). **라우팅은 완벽했다**
  - tier1이 `0251`(clarification)·`0605`·`0836`(realtime) 3문항을 즉시 잡았고, tier2가
    나머지 7문항을 판정해 D-10 gold와 전부 일치했다(`0111`도 이번엔 `legal_search`가 아니라
    맞게 안 걸렸음 - 이전 개별 호출에서 gold와 갈렸던 것과 다른 결과라 tier2 판단이 매
    호출마다 흔들릴 수 있다는 뜻이기도 하다. 후속 관찰 필요).
  - **생성은 6건 중 완전 성공이 0건이다** - `0201`은 공유 worker pool 503(115/32, 오늘
    이전 관측치보다 더 붐빔), `0111`은 정확히 새 60초 한도에서 timeout, 나머지
    `0521`·`0601`·`0346`·`0943` 4건은 예외 없이 생성됐지만 `validate_draft()` grounding
    gate에서 거부됐다(`grounding_failed`).
  - 안전 gate 4개는 전부 통과했다(근거 없는 citation 0, 근거 없는 주장 사용자 노출 0,
    corpus_unready에서 생성 0, 실패 시 fallback 100%) - **시스템은 정확히 설계대로
    동작했다**(나쁜 답을 사용자에게 보여주지 않고 올바르게 차단했다). 다만
    grounding_failed 67%(4/6)는 안전 문제가 아니라 **품질/유용성 문제**다 - 지금 이대로면
    AI 모드가 거의 항상 검색 전용으로 떨어진다는 뜻이라 원인 진단이 필요하다. 이번 스크립트는
    거부된 draft의 실제 내용을 저장하지 않아 근본 원인(모델 출력이 실제로 근거와 안 맞는지,
    검증기가 이 모델 출력 스타일에 비해 너무 엄격한지) 판단은 후속 작업으로 남긴다.
  - Vercel 배포 반영 여부는 사용자 요청으로 직접 확인하지 않았다.

# 일반인 답변 계약 v2 설계

상태: 승인 전 초안
작성일: 2026-08-09
관련: [0043 실행 계획](../exec-plans/active/0043-layperson-answer-contract-v2.md), [DESIGN.md](../DESIGN.md), [답변 근거 검증](answer-grounding-validation.md)

## 맥락

현재 답변 생성 프롬프트(`answer-system-prompt-v1`)는 인용·근거 안전 규칙은 상세하지만 독자 수준,
전문용어 설명 방식, 정보 우선순위, 문장 길이를 정하지 않는다. 그 결과 `summary`·`sections`·
`checklist`·`limitations`가 법률 조사 보고서 문체로 나와 처음 보는 사용자가 핵심 행동보다 전문
용어를 먼저 보게 된다. [0043](../exec-plans/active/0043-layperson-answer-contract-v2.md)이 이 문제의
목적·범위·완료 조건을 이미 정의했고, 이 문서는 그 실행 설계다.

오늘 세션에서 사용자가 추가로 요청한 "원문은 링크 방식" 요구는 UI 변경이라 0043 원문의 비범위
("답변 화면의 점진적 공개, 섹션 접기, API 응답 스키마 재설계")와 충돌했다. 사용자가 이 설계에서
0043 범위를 원문 링크 추가만 예외로 확장하기로 확정했다 — 스키마 재설계나 새로운 접기/펼치기
메커니즘 도입은 여전히 비범위다(기존 `<details>` 토글 재사용만 허용).

## 결정

### 1. 프롬프트 v2 (신규 함수, 기존 함수 보존)

`apps/api/app/adapters/openai_answerer.py`에 `build_messages_v2()`를 `build_messages()`와 나란히
추가한다. 기존 함수는 수정하지 않는다 — v1 히스토리·평가 artifact가 참조하는 프롬프트 텍스트가
바뀌면 안 된다.

v2 system prompt는 v1의 인용·안전 규칙(근거만 사용, `action` 자기 신고, `unanswerable` 처리 등)을
그대로 유지한 채 다음 문체 규칙을 추가한다:

- `summary`: 최대 3문장. 현재 근거로 확인되는 결론과 가장 먼저 할 일을 포함한다.
- `sections[].claim`: 질문에 직접 답하는 쉬운 소제목 또는 행동 문장.
- `sections[].explanation`: 전문용어는 쉬운 뜻을 먼저 쓰고 원문 용어는 괄호 안에 한 번만 보존한다.
  한 문장에는 조건·예외·행동을 하나만 담는다.
- `checklist[].label`: 동사형 행동 문장.
- `limitations`: 최대 3개. "현재 확인된 것"과 "아직 확정할 수 없는 것"을 분리해서 쓴다.
- 법률명·조문 번호는 이해에 꼭 필요한 경우를 제외하고 본문에서 반복하지 않고, 실질 주장은 기존
  citation ID로 연결한다.
- 제공된 근거에 없는 일반 절차·기관·법률을 쉬운 설명이라는 이유로 추가하지 않는다(v1 규칙 재확인).

`DraftAnswer` 스키마(`apps/api/app/adapters/openai_answerer.py`)와 공개 `QuestionResponse` 스키마는
변경하지 않는다. v2는 프롬프트 텍스트만 바꾸고 같은 필드 구조에 다른 문체로 채운다.

### 2. Generation Profile 분리

`apps/api/app/domain/generation_profiles.py`에 새 상수를 추가한다:

```python
NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE_V2 = GenerationProfile(
    key="nvidia-nemotron-3-ultra-550b-a55b-answer-v2",
    provider="nvidia_nim",
    model="nvidia/nemotron-3-ultra-550b-a55b",
    prompt_version="answer-system-prompt-v2",
    schema_version="draft-answer-v1",  # 불변
    context_version="m4-frozen-r1-a",  # 불변
    temperature=0.3,
    top_p=0.95,
    max_output_tokens=4096,
    profile_version="2",
)
```

기존 `NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE`(v1)은 그대로 둔다. 실행 계획에서 어느 프로필을 언제
호출할지(플래그·환경변수·비교 스크립트 인자 등 구체 배선)를 정한다 — 이 설계 문서는 v2 프로필의
존재와 `sha256` 추적 가능성만 확정한다.

### 3. 가독성 평가 계약

**결정적 테스트** (`apps/api/tests/`): v2 프롬프트 문자열에 위 6개 문체 규칙이 실제 텍스트로 포함됐는지
검사하는 단위 테스트를 추가한다(문자열 포함 검사 — 의미 검증이 아니라 "규칙이 프롬프트에서 삭제되지
않았는지"를 잠그는 회귀 테스트). 기존 스키마·인용 ID·`unanswerable` fallback 테스트는 `DraftAnswer`가
불변이므로 그대로 재사용하고, v2 프로필로도 동일하게 통과해야 한다.

**사람 rubric**: 0043 문서에 정의된 6개 기준(첫 문단 결론+행동, 전문용어 설명 위치, 문장당 단일
조건, 체크리스트만으로 준비 가능, 한계 순서/중복 금지, 근거 없는 보완 금지)을 실행 계획의 비교
표에서 사람이 실제 출력에 적용해 판정한다. 결정적 테스트로 자동화하지 않는다 — 표면 문법만으로
가독성을 판정하면 `answer-grounding-validation.md`가 이미 겪은 오탐 문제를 반복한다.

### 4. 원문 링크 (UI, 0043 범위 확장분)

`apps/web/app/page.tsx`의 근거 카드(`<details>`, 현재 라인 286 부근)에서 인용문
(`<blockquote>{citation.quote}</blockquote>`) **바로 아래**에 원문 링크를 추가한다:

```tsx
<a href={citation.source_url} target="_blank" rel="noreferrer">원문 보기 ↗</a>
```

`<summary>`(헤더: `citation.id · document_title · path`, `version_label`)는 변경하지 않는다 — 접힌
상태에서는 지금처럼 조·항 헤더만 보이고, 사용자가 토글을 펼쳤을 때만 인용문과 원문 링크가 함께
나타난다. `Citation.source_url`은 백엔드 스키마(`packages/law-rag-core/.../schemas.py`)와 프론트
타입(`apps/web/lib/contracts.ts`)에 이미 존재하므로 스키마 변경이 없다 — 프론트 렌더링 한 줄
추가로 끝난다.

### 5. 후속 todo로 분리: 실제(hosted) v1·v2 비교 실행

D-10 `lay-energy-0201` 포함 최대 3문항 v1·v2 비교(0043 범위 4번)는 이 설계에서 확정하지 않는다.
NVIDIA 실제 호출 횟수·재시도 상한은 실행 전에 다시 명시하고 사용자의 외부 호출 승인을 받는다.
hosted 경로(Web 재요청, Vercel 함수 종료 전 fallback) 계약은 더 이상 별도로 설계 중이 아니다 —
[0045 조정된 질문 timeout 예산](../exec-plans/completed/0045-coordinated-question-timeout-budget.md)이
API 서버측 전체 예산 52초·Web attempt 55초·최초 시도 포함 최대 3회·UX 전체 170초 상한 계약으로
이미 전달했다(계약 요약은 [RELIABILITY.md](../RELIABILITY.md) "조정된 질문 timeout 예산 (0045)"
참고). 이 설계와 뒤따르는 실행 계획은 **1~4번(프롬프트 v2, 프로필,
결정적 테스트, 원문 링크 UI)까지만 구현·검증**하고, "실제 비교를 무엇으로·몇 번·어떤 승인으로
실행할지"는 [0043 실행 계획](../exec-plans/active/0043-layperson-answer-contract-v2.md)에 후속 항목으로
남긴다 — 0045가 전달한 timeout 계약 위에서, 호출 제한 설계가 끝난 뒤 별도로 착수한다. 실행 결과는
아래 "결정 기록" 2026-08-10 항목에 기록한다.

## 비범위 (재확인)

- 검색·재순위·문맥 조립 변경 또는 근거 부족을 프롬프트로 보완
- 인용 검증 완화, 법률 기억 기반 보충, 다른 corpus·외부 웹 근거 도입
- `DraftAnswer`·`QuestionResponse` 스키마 필드 추가·변경
- 원문 링크 외의 신규 UI 메커니즘(기존 `<details>` 토글 외 새 접기/펼치기, 점진적 공개)
- 실제 hosted v1·v2 비교 실행 자체(위 5번, 후속 todo)

## 결과

- 긍정적: v1 프롬프트·프로필·평가 이력을 전혀 건드리지 않고 v2를 나란히 추가 — 롤백은 v2 프로필
  참조를 끊는 것만으로 끝난다. 원문 링크는 기존 스키마 필드를 노출만 하므로 위험이 낮다.
- 부정적: 프롬프트가 v1/v2 두 벌이 되어 유지보수 지점이 늘어난다. 문체 규칙이 실제로 지켜지는지는
  결정적 테스트로 보장하지 못하고 사람 rubric에 의존한다(의도적 — 표면 문법 검증의 오탐 위험을
  피하기 위함, `answer-grounding-validation.md` 결정과 일관).
- 비용: NVIDIA 실제 호출 비용은 5번(후속 todo)으로 미뤄졌으므로 이 설계 자체의 구현·테스트는
  추가 API 비용이 들지 않는다.

## 검증

- 결정적 테스트(3번)가 v2 프롬프트에서 통과하고, 기존 v1 대상 테스트가 회귀 없이 통과한다.
- 원문 링크가 근거 카드에서 렌더링되고 `source_url`로 정상 이동하는지 프론트 테스트 또는 수동
  확인으로 검증한다.
- 재검토 완료(2026-08-10): 5번(실제 비교)을 실행했다. 결과는 위 "결정 기록" 참고.

## 결정 기록

- 2026-08-09: `NvidiaNimAnswerer`에 `message_builder` 주입 파라미터(기본값 `build_messages`)를 추가해 v1 동작을 바꾸지 않으면서 v2를 나중에 배선할 수 있게 했다.
- 2026-08-09: 근거 카드를 `apps/web/app/citation-card.tsx`로 분리해 `renderToStaticMarkup` 기반 단위 테스트(기존 `safe-text.test.tsx` 패턴)로 원문 링크 위치를 검증할 수 있게 했다.
- 2026-08-10: 범위 4번(실제 hosted v1/v2 비교)을 [0045](../exec-plans/completed/0045-coordinated-question-timeout-budget.md) hosted 검증 통과 후 실행했다. `apps/api/scripts/run_experiment_0043_v1_v2_compare.py`로 D-10 문항 3개(`lay-energy-0201`, `lay-energy-0251`, `lay-energy-0521`) 중 실제 생성까지 간 2개(`0251`은 라우팅에서 `clarification_required`로 빠져 생성 미실행)에 대해 같은 검색 결과(hits) 위에서 v1·v2 답변을 각각 실제 NVIDIA 호출로 생성해 비교했다. 결과: `action` 판정은 두 문항 모두 v1=v2로 동일(근거 없는 주장을 추가하지 않음), 문체는 v2가 뚜렷이 개선됨 — summary가 조문 번호 나열형에서 서술형 안내문으로, checklist 항목이 "-하기" 행동형으로 통일되고 중복이 줄었으며(`lay-energy-0521`에서 v1 7개 → v2 4개), `lay-energy-0521`에서는 v2만 질문자가 밝힌 상황("발전량은 기록되나 REC가 미발급")을 요약 첫 문장에서 직접 짚었다. 원자료는 `apps/api/evaluation/experiment-0043-v1-v2-compare-results.json`에 보존한다.
- 2026-08-10: 위 비교 결과를 근거로 사용자 승인을 받아 `main.py`의 `_answerer()`가 `build_messages_v2`를 기본 `message_builder`로 쓰도록 전환했다. `main.py`의 `generation_profile_key`/`generation_profile_sha256` 진단 필드도 `NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE_V2`를 가리키도록 함께 바꿔, 로그가 실제로 쓰인 프롬프트와 어긋나지 않게 했다. `build_messages()`(v1) 함수와 `NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE`(v1) 상수는 삭제하지 않고 그대로 남겨 롤백 시 `message_builder` 인자만 되돌리면 되게 했다.

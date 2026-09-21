# clarification missing_information 구조적 검증 (B-011)

## 상태

승인·구현 완료 — 2026-09-21. 사용자는 고정 라벨 allowlist를 없애고, 모델이 필요한 추가 정보를
자연어로 묻고 답변 예시를 함께 제공하도록 프롬프트 계약을 강화하는 안을 승인했다. 서버는
필드 의미를 제한하지 않고 출력의 구조와 표시 안전성만 검증한다.

## 문제

[B-011 / exec-plan 0082](../exec-plans/completed/0082-clarification-missing-information-allowlist-drops-fields.md)
에서 등록됨. `clarification_required` route에서 사용자에게 "추가 정보: - [ ]"만 표시되고
실제로 무엇을 입력해야 하는지 전혀 안내되지 않는다. F-010 Task 3에서 대표 질문("제 설비
용량에 맞는 절차는 무엇인가요?")으로 2회 독립 실행해 재현했다(우연한 provider flake 아님).

## 원인

`apps/api/app/application/answering.py`의 `safe_clarification_missing_fields()`는
모델/router가 만든 `missing_information` 문자열을 신뢰하지 않는 외부 입력으로 취급해
`_SAFE_CLARIFICATION_FIELD_ALIASES` 사전에 등록된 6개 고정 라벨(설비용량, 전압, 전기 사용
방식, 공사 종류, 토지 지목, 용도지역)과 **정확히 일치**할 때만 통과시키는 input allowlist다.

반면 `apps/api/app/adapters/openai_answerer.py`(L455-461, F-010에서 승인된 언어 계약)는
모델에게 "각 항목은 무엇을 알려줘야 하는지와 함께 간단한 예시 값을 붙여 쓴다(예:
'발전설비용량(예: 50kW)')"라고 요구한다. 이 형식은 애초에 예시 값을 담을 자리가 없는
라벨 전용 allowlist를 구조적으로 통과할 수 없어, missing_information이 사실상 항상 빈다.

## 왜 고정 allowlist로 되돌아갈 수 없는가

라벨 매핑 테이블을 6개(또는 몇 개든) 고정 사전으로 유지하는 안(예시값 서버측 매핑)도
검토했으나, 사용자가 명시적으로 거부했다 — 라벨 집합이 앞으로 계속 늘어날 도메인
질문(전기사업법 외 다른 법 영역 등)에서 코드 변경 없이 확장 가능해야 한다.

## 목표

1. 고정 라벨 집합 없이, 새 라벨이 등장해도 코드 변경 없이 통과할 수 있는 검증 방식으로
   전환한다.
2. 모델이 만든 자연어 질문과 예시 값(`"발전설비의 용량은 얼마인가요? (예: 50kW)"`)을
   사용자가 그대로 보고 답할 수 있게 한다.
3. AGENTS.md "외부 입력은 시스템 경계에서 검증한다" 불변조건을 유지한다 — 신뢰하지 않는
   모델 출력을 무검증으로 내보내지 않는다.
4. 기존 `missing_information: list[str]` 인터페이스를 유지해 호출자와 저장 형식을 바꾸지 않는다.

## 비목표

- `openai_answerer.py`의 언어 계약(F-010 승인) 자체는 변경하지 않는다.
- 사용자 후속 답변 처리 경로(질문 재제출 파이프라인)의 구조 자체는 바꾸지 않는다.
- route classifier 로직(B-012 소관)은 다루지 않는다.

## 설계

`_SAFE_CLARIFICATION_FIELD_ALIASES` 고정 사전과 exact-match 조회를 삭제하고,
`safe_clarification_missing_fields()`를 **구조적 검증기**로 교체한다. 의미(어떤 법률 분야의
어떤 사실인지)가 아니라 형태(길이·표시 안전성·개수)만 검증해서 새 질문이 코드 변경 없이
통과하게 한다. `missing_information`은 계속 `list[str]`이며 각 문자열이 한 개의 자연어
질문과 답변 예시를 함께 담는다.

검증 규칙 (모델 출력 및 router `missing_fields` 양쪽에 동일 적용):

- **길이 상한**: strip 후 항목당 160자. 자연어 질문과 짧은 예시는 허용하되 긴 답변 생성은
  차단한다.
- **표시 안전성**: 개행·탭·Unicode 제어문자, 마크다운/HTML 제어문자(`#`, `*`, `` ` ``,
  `[`, `]`, `<`, `>`), URL 스킴(`http://`, `https://`, `://`)이 있으면 항목 전체를 거부한다.
- **질문 형태**: 예시가 있는 자연어 항목은 `? (예: ...)` 또는 `? (예시: ...)` 형태여야 한다.
  pre-routing classifier의 기존 호환성을 위해 예시 없는 짧은 명사형 라벨은 허용하되,
  `...입니다`·`...됩니다` 같은 서술형 법률 주장은 거부한다. 이는 법률 주장의 진위를
  판정하는 의미 allowlist가 아니라 clarification과 답변 문장을 구분하는 출력 형태 계약이다.
- **중복 제거**: 처음 등장한 순서를 보존한 채 dedupe.
- **개수 상한**: 최대 5개 항목까지만 통과.
- **빈 문자열/공백만 있는 값**: strip 후 거부.

두 가지 입력 형태를 모두 같은 함수로 처리한다:

1. **Pre-routing classifier** 출력(`RouteDecision.missing_fields`) — 예시 값 없는 평문
   라벨(예: `"설비용량"`).
2. **모델 생성** `missing_information` — F-010 언어 계약에 따른 자연어 질문과 예시 형식(예:
   `"발전설비의 용량은 얼마인가요? (예: 50kW)"`).

`clarification_resubmission_summary()`의 `fields_block` 조립은 그대로 유지하되
(`- {검증된 문자열}: [ ]` 한 줄씩), 검증을 통과한 원본 문자열을 그대로 나열한다 — 평문
라벨이면 `- 설비용량: [ ]`, 자연어 질문이면
`- 발전설비의 용량은 얼마인가요? (예: 50kW): [ ]`로 렌더링된다.

## 호환성 (기존 테스트)

`apps/api/tests/test_clarification_answering.py`의 다음 테스트는 입력
`("설비용량", "전기사업법이 적용됩니다")`에 대해 요약이 정확히
`"추가 정보:\n- 설비용량: [ ]"`로 끝나고 `"전기사업법이 적용됩니다"`는 나타나지 않아야
한다고 이미 고정되어 있다 — 새 구조적 규칙(특히 길이 상한)이 이 두 문자열을 기존과
동일하게 분류해야 한다:

- `test_initial_clarification_route_preserves_clarification_action_in_core`
- `test_generated_clarification_core_with_retrieval_is_preserved`
- `test_successful_core_repair_persists_clarification_transition`

## 영향 범위

- `apps/api/app/application/answering.py` — `_SAFE_CLARIFICATION_FIELD_ALIASES` 삭제,
  `safe_clarification_missing_fields()` 구조적 검증으로 교체.
- `apps/api/app/adapters/openai_answerer.py` — 모든 clarification 생성 프롬프트가 자연어
  질문과 예시를 함께 요구하고 법적 판단·답변을 금지하도록 계약 통일.
- `apps/api/app/domain/generation_profiles.py` — 변경된 V1·V2 prompt provenance를 각각
  `answer-system-prompt-v1.1`, `answer-system-prompt-v2.2`로 기록.
- `apps/api/tests/test_clarification_missing_information.py` — 새 라벨 확장성, 자연어 질문과
  예시 보존, 위험 패턴 거부, 개수 상한, dedupe 테스트.
- `apps/api/tests/test_layperson_prompt_v2.py` — 프롬프트 계약 회귀 테스트.
- 변경 없음: 사용자 후속 답변 처리 경로.

## 완료 조건

- 새 라벨(6개 고정 집합에 없는 것)이 통과함을 테스트로 확인.
- 모델이 만든 `"질문? (예: 값)"`이 예시 값째로 사용자에게 노출됨을 테스트로 확인.
- 마크다운/URL/코드펜스/개행이 섞인 후보 문자열이 거부됨을 테스트로 확인.
- 위 "호환성" 절의 기존 3개 테스트가 코드 변경 없이 그대로 통과.
- 고정 라벨에 없던 자연어 질문과 예시가 V1·V2 공용 요약 렌더러에서 보존됨을 확인.

## 권한 계약

| Boundary | Destination or resource | Operation | Data/credential involved | Mutation/retention | Purpose | Status and date | Runtime gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 저장소 | B-011 관련 코드·테스트·문서 | 로컬 수정·검증·커밋 | credential·개인 사건자료 없음 | Git 변경과 로컬 commit | 버그 수정과 회귀 방지 | Approved — 2026-09-21 사용자 “응 그렇게 가자” 및 저장소 커밋 정책 | diff·테스트·커밋 전 민감정보 확인 |
| Python 환경 | 이 격리 worktree의 `.venv` | `uv sync --all-packages --locked` | 공개 패키지 metadata | 로컬 가상환경과 cache | 테스트 실행 환경 준비 | Approved — 2026-09-21 runtime 승인, 실행 완료 | lockfile 고정, 제품 dependency 변경 없음 |
| 외부 모델 | NVIDIA/OpenAI 등 hosted API | 호출하지 않음 | credential·질문 전송 없음 | 없음 | 결정적 로컬 검증으로 대체 | Not required — 2026-09-21 | live 대표 질문 평가는 이번 완료조건에서 제외 |
| 데이터베이스·배포 | 로컬/원격 DB, Vercel, 운영 서비스 | 사용하지 않음 | 없음 | 없음 | 변경 범위 밖 | Not required — 2026-09-21 | 접근 금지 |
| 원격 Git | push·PR | 수행하지 않음 | commit metadata 외 전송 없음 | 원격 변경 없음 | 로컬 완료까지만 수행 | Not required — 2026-09-21 | 별도 사용자 승인 필요 |

## 결정 기록

- 2026-09-21: 사용자는 고정 필드 allowlist 대신 모델이 필요한 추가정보를 자유롭게 묻고
  예시 답변을 함께 요구하는 방식을 선택했다. `list[str]` 계약을 유지하면서 의미 allowlist를
  제거하고, 프롬프트 형식과 서버의 구조·표시 안전성 검증을 결합한다. 길이만으로 자연어
  문장을 차단하는 기존 초안 규칙은 승인 방향과 충돌하므로 폐기했다.
- 2026-09-21: 자유형 항목은 `?`로 끝나는 질문 뒤에 예시가 와야 한다. 이 구조는 고정 필드
  집합 없이 확장되면서도 `"전기사업법이 적용됩니다. (예: 적용)"` 같은 서술형 법률 주장을
  clarification 항목으로 공개하지 않게 한다. prompt provenance는 V1 `v1.1`, V2 `v2.2`로 올렸다.

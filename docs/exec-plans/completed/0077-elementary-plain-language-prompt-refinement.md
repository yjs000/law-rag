> 작업 ID: `F-010`
> 상태: `Done`
> 유형: `Feature`
> 보조 라벨: `UX`, `Evaluation`
> 선행 조건: 실제 모델 출력 평가에는 NVIDIA 개발 credential과 network 실행 승인이 필요하다.
> 다음 행동: 없음 - 완료됨(확인된 한계 두 건은 0082, 0083 후속 작업으로 이관).
> 오케스트레이션: `OC-001`
> 참고 범위:
> - `apps/api/app/adapters/openai_answerer.py` L184-L330 — V2 답변·core 프롬프트의 현재 일반인 문체 계약
> - `apps/api/app/adapters/nvidia_nim_clarification.py` L50-L78 — 추가 질문 후보를 만드는 clarification 판단 프롬프트
> - `apps/api/tests/test_layperson_prompt_v2.py` L36-L147 — 현재 쉬운 말·근거 안전 프롬프트 회귀 테스트

# 초등학생도 이해할 수 있는 쉬운 한국어 프롬프트 정교화 Implementation Plan

**Goal:** 법률을 처음 보는 사용자와 초등학생도 핵심 뜻을 따라갈 수 있도록 답변과 추가 질문을 짧고 쉬운 한국어로 만들되, 법률 의미·근거·인용 안전성은 그대로 지킨다.

**Language contract:** 한 문장에는 한 가지 뜻만 담고, 짧은 생활 언어를 먼저 쓴다. 법률 용어가 꼭 필요하면 바로 쉬운 뜻을 붙인다. 긴 명사 나열, 이중 부정, 내부 상태명, 불필요한 영어를 피한다. 추가 질문은 “무엇을 알려 달라는지”와 간단한 입력 예시를 바로 이해할 수 있게 쓴다.

### Task 1: 쉬운 말 기준과 평가 회귀 고정 [x] 완료

- **결과:** 쉬운 말의 합격 기준이 주관적인 인상 대신 반복 가능한 프롬프트·출력 평가표와 실패 테스트로 고정된다.
- **대상:** `apps/api/tests/test_layperson_prompt_v2.py` L36-L147 수정 약 35줄, 쉬운 말 대표 질문 fixture 새 파일 약 60줄, 합계 약 95줄.
- **실행 절차:** 짧은 문장, 한 문장 한 뜻, 쉬운 말 우선, 법률 용어 즉시 풀이, 행동 중심 안내, 추가 질문 입력 예시를 프롬프트 필수 문구로 검증한다. 허가·신고·기준일·적용 대상·근거 부족·clarification을 포함한 대표 질문을 정하고, 각 출력에 대해 설명 없는 전문용어 없음·질문에 바로 답함·다음 행동이 분명함·근거 밖 주장 없음의 네 기준을 기록한다. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_layperson_prompt_v2.py`로 RED를 확인한다.
- **완료 증거:** 새 회귀 테스트가 현재 프롬프트에서 의도한 이유로 실패하고, 대표 질문마다 네 가지 합격 기준이 명시된다.
- **의존성:** 없음.

### Task 2: 답변·추가 질문 프롬프트 최소 정교화 [x] 완료

- **결과:** 정상 답변, core 요약, 근거 부족 안내와 clarification 질문이 같은 쉬운 말 규칙을 따르며 기존 grounding 규칙은 약해지지 않는다.
- **대상:** `apps/api/app/adapters/openai_answerer.py` L184-L330 및 L427-L456 수정 약 28줄, `apps/api/app/adapters/nvidia_nim_clarification.py` L50-L78 수정 약 10줄, `apps/api/app/domain/generation_profiles.py` L75-L93 prompt version 수정 약 2줄, 합계 약 40줄.
- **실행 절차:** Task 1의 언어 계약을 V2 detail·core·검색 없는 안내·clarification 후보 생성 프롬프트에 같은 의미로 반영한다. 쉬운 설명을 이유로 근거에 없는 법률·기관·절차를 추가하지 못하게 기존 금지 규칙과 citation ID 계약을 유지한다. prompt version을 올리고 focused API 테스트를 통과시킨 뒤 diff에서 V1 호환 프롬프트가 의도치 않게 바뀌지 않았는지 확인한다.
- **완료 증거:** 쉬운 말 회귀 테스트와 기존 citation·grounding·action 테스트가 통과하고, 모든 변경 프롬프트가 같은 문체 규칙과 근거 안전 규칙을 가진다.
- **의존성:** Task 1의 언어 계약과 대표 질문 fixture.

### Task 3: 대표 출력 평가와 전체 검증 [x] 완료

> 2026-09-18 진행 메모: 실제 NVIDIA 개발 credential과 network 실행 승인을 받아 대표
> 질문 6건을 실제 모델(nvidia/nemotron-3.5-lightning-30b-a3b)에 동일 설정으로 실행했다.
> 4건(허가·신고·기준일·적용 대상)은 네 기준을 모두 충족했다. 2건(clarification,
> 근거 부족)은 평가 중 F-010 소유 범위 밖의 구조적 한계가 발견되어, 사용자 승인에 따라
> 이번 Task 3의 완료 증거를 "언어 계약이 적용된 4개 대표 문항 전원 통과, 2건은 범위 밖
> 한계로 확인되어 별도 작업으로 분리"로 조정하고 각각 후속 작업으로 이관했다.

- **완료 증거(조정됨, 사용자 승인 2026-09-18):** 언어 계약이 실제로 적용되는 4개 대표
  문항(허가·신고·기준일·적용 대상) 전원이 네 기준을 충족했고, 남은 2개 문항은 F-010
  소유 범위 밖 원인으로 확인되어 각각 [0082](../completed/0082-clarification-missing-information-allowlist-drops-fields.md),
  [0083](../dropped/0083-routing-unavailable-non-deterministic-prompt-compliance.md)로
  분리 등록했다. 기존 grounding·citation 회귀는 계속 통과하고, 계획이 `Done`으로 생성된
  로드맵에 반영된다.

**평가 기록 (2026-09-18, NVIDIA 개발 credential 실사용, provider: nvidia_nim, model:
nvidia/nemotron-3.5-lightning-30b-a3b — API 키 값은 어디에도 기록하지 않음):**

각 질문은 event loop 재사용 문제(Windows/asyncio에서 같은 프로세스로 여러 `/v1/questions`
호출 시 두 번째 호출부터 `SSLWantReadError`/`APIConnectionError` 발생)를 피하기 위해
질문당 새 프로세스로 독립 실행했다.

| id | category | no_unexplained_jargon | directly_answers | clear_next_action | no_ungrounded_claims | 판정 |
| --- | --- | --- | --- | --- | --- | --- |
| permit | 허가 | PASS(전기사업법 조문으로 즉시 풀이) | PASS | PASS(checklist 동사형 3건) | PASS(전부 인용 근거) | PASS |
| report | 신고 | PASS(시행규칙 조문 인용과 함께) | PASS(신고가 1건이 아니라 2건임을 직접 답함) | PASS(checklist 동사형 2건) | PASS | PASS |
| effective_date | 기준일 | PASS | PASS(시행일·소급 예외·유리조항 예외까지 답함) | PASS(checklist 3건) | PASS(전부 인용 근거) | PASS |
| applicability | 적용 대상 | PASS | PASS(근거 없음을 직접 답함) | PASS(빈 근거 시 unanswerable 안전 규칙에 따라 sections·checklist 의도적으로 비움) | PASS | PASS |
| clarification | clarification | N/A | N/A | **FAIL** — missing_information이 빈 값으로 전달됨(원인: 다운스트림 input allowlist, 0082 참고) | N/A | 범위 밖 한계 → 0082 |
| insufficient_evidence | 근거 부족 | N/A | N/A | N/A | **비결정적** — routing_unavailable 안내 프롬프트 준수 여부가 재실행마다 다름(0083 참고) | 범위 밖 한계 → 0083 |

**검증:** `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_layperson_prompt_v2.py`
통과(코드 변경 없어 회귀 없음). roadmap/docs checker 통과(아래 결과 기록 참고).

**결과 기록:**
- 대표 질문 6건 중 4건(허가·신고·기준일·적용 대상)이 쉬운 말 네 기준을 모두 충족했다.
- 2건(clarification, 근거 부족)은 F-010 소유 범위(`openai_answerer.py`,
  `nvidia_nim_clarification.py`) 밖 원인(input allowlist, router 신뢰성)으로 확인되어
  [0082](../completed/0082-clarification-missing-information-allowlist-drops-fields.md),
  [0083](../dropped/0083-routing-unavailable-non-deterministic-prompt-compliance.md)로
  분리 등록했다.
- 근거·인용 안전성은 어떤 문항에서도 낮추지 않았다 — 평가 중 프롬프트/allowlist/router
  코드는 변경하지 않았다.
- **의존성:** Task 1과 Task 2 완료, NVIDIA 개발 credential과 network 실행 승인.

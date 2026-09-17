> 작업 ID: `F-010`
> 상태: `Todo`
> 유형: `Feature`
> 보조 라벨: `UX`, `Evaluation`
> 선행 조건: 실제 모델 출력 평가에는 NVIDIA 개발 credential과 network 실행 승인이 필요하다.
> 다음 행동: 쉬운 말 품질 기준과 대표 질문 평가표를 회귀 테스트로 먼저 고정한다.
> 참고 범위:
> - `apps/api/app/adapters/openai_answerer.py` L184-L330 — V2 답변·core 프롬프트의 현재 일반인 문체 계약
> - `apps/api/app/adapters/nvidia_nim_clarification.py` L50-L78 — 추가 질문 후보를 만드는 clarification 판단 프롬프트
> - `apps/api/tests/test_layperson_prompt_v2.py` L36-L147 — 현재 쉬운 말·근거 안전 프롬프트 회귀 테스트

# 초등학생도 이해할 수 있는 쉬운 한국어 프롬프트 정교화 Implementation Plan

**Goal:** 법률을 처음 보는 사용자와 초등학생도 핵심 뜻을 따라갈 수 있도록 답변과 추가 질문을 짧고 쉬운 한국어로 만들되, 법률 의미·근거·인용 안전성은 그대로 지킨다.

**Language contract:** 한 문장에는 한 가지 뜻만 담고, 짧은 생활 언어를 먼저 쓴다. 법률 용어가 꼭 필요하면 바로 쉬운 뜻을 붙인다. 긴 명사 나열, 이중 부정, 내부 상태명, 불필요한 영어를 피한다. 추가 질문은 “무엇을 알려 달라는지”와 간단한 입력 예시를 바로 이해할 수 있게 쓴다.

### Task 1: 쉬운 말 기준과 평가 회귀 고정

- **결과:** 쉬운 말의 합격 기준이 주관적인 인상 대신 반복 가능한 프롬프트·출력 평가표와 실패 테스트로 고정된다.
- **대상:** `apps/api/tests/test_layperson_prompt_v2.py` L36-L147 수정 약 35줄, 쉬운 말 대표 질문 fixture 새 파일 약 60줄, 합계 약 95줄.
- **실행 절차:** 짧은 문장, 한 문장 한 뜻, 쉬운 말 우선, 법률 용어 즉시 풀이, 행동 중심 안내, 추가 질문 입력 예시를 프롬프트 필수 문구로 검증한다. 허가·신고·기준일·적용 대상·근거 부족·clarification을 포함한 대표 질문을 정하고, 각 출력에 대해 설명 없는 전문용어 없음·질문에 바로 답함·다음 행동이 분명함·근거 밖 주장 없음의 네 기준을 기록한다. `.\scripts\run_python.ps1 -m pytest apps/api/tests/test_layperson_prompt_v2.py`로 RED를 확인한다.
- **완료 증거:** 새 회귀 테스트가 현재 프롬프트에서 의도한 이유로 실패하고, 대표 질문마다 네 가지 합격 기준이 명시된다.
- **의존성:** 없음.

### Task 2: 답변·추가 질문 프롬프트 최소 정교화

- **결과:** 정상 답변, core 요약, 근거 부족 안내와 clarification 질문이 같은 쉬운 말 규칙을 따르며 기존 grounding 규칙은 약해지지 않는다.
- **대상:** `apps/api/app/adapters/openai_answerer.py` L184-L330 및 L427-L456 수정 약 28줄, `apps/api/app/adapters/nvidia_nim_clarification.py` L50-L78 수정 약 10줄, `apps/api/app/domain/generation_profiles.py` L75-L93 prompt version 수정 약 2줄, 합계 약 40줄.
- **실행 절차:** Task 1의 언어 계약을 V2 detail·core·검색 없는 안내·clarification 후보 생성 프롬프트에 같은 의미로 반영한다. 쉬운 설명을 이유로 근거에 없는 법률·기관·절차를 추가하지 못하게 기존 금지 규칙과 citation ID 계약을 유지한다. prompt version을 올리고 focused API 테스트를 통과시킨 뒤 diff에서 V1 호환 프롬프트가 의도치 않게 바뀌지 않았는지 확인한다.
- **완료 증거:** 쉬운 말 회귀 테스트와 기존 citation·grounding·action 테스트가 통과하고, 모든 변경 프롬프트가 같은 문체 규칙과 근거 안전 규칙을 가진다.
- **의존성:** Task 1의 언어 계약과 대표 질문 fixture.

### Task 3: 대표 출력 평가와 전체 검증

- **결과:** 실제 대표 출력도 쉬운 말 기준을 충족하며 변경 결과와 한계가 문서에 남는다.
- **대상:** Task 1의 대표 질문 평가 기록 약 40줄, `docs/product-specs/grounded-legal-qa.md` 결정 기록 추가 약 4줄, 이 계획 결과 기록 약 10줄, `docs/ROADMAP.md` renderer 생성 변경.
- **실행 절차:** 승인된 개발 credential과 network 경계에서 대표 질문을 동일 설정으로 실행하고 네 기준을 문항별로 판정한다. 실패 문항은 프롬프트를 최소 조정한 뒤 다시 평가하며, 법률 정확성이나 인용 안전성을 낮춰 문체 점수를 올리지 않는다. API 포맷·lint·타입·단위 테스트와 고정 평가셋 회귀를 실행한다. 결과와 남은 한계를 기록하고 계획을 `completed/`로 이동한 뒤 roadmap renderer와 checker를 실행한다.
- **완료 증거:** 모든 대표 문항이 네 기준을 충족하고 기존 grounding·citation 회귀가 통과하며 계획이 `Done`으로 생성된 로드맵에 반영된다.
- **의존성:** Task 1과 Task 2 완료, NVIDIA 개발 credential과 network 실행 승인.

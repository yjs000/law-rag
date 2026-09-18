> 작업 ID: `B-012`
> 상태: `Todo`
> 유형: `Bug`
> 보조 라벨: `Evaluation`
> 선행 조건: 실제 모델 재현에는 NVIDIA 개발 credential과 network 실행 승인이 필요하다.
> 다음 행동: routing_unavailable 재현율을 소표본으로 측정해 classifier 문제인지 프롬프트 순응 문제인지 분리한다.
> 참고 범위:
> - `apps/api/app/adapters/openai_answerer.py` L436-L441 — 재시도 안내만 담으라는 routing_unavailable 안내
> - `apps/api/app/application/v1/guidance.py` L38-L94 — draft를 그대로 요약에 반영하는 경로
> - `apps/api/app/application/v1/answering.py` L1-L40 — 라우팅 분류 단계와 provider 재시도 예산

# 0083: insufficient_evidence 질문이 routing_unavailable일 때 프롬프트 순응이 비결정적인 문제

상태: `제안됨 (2026-09-18)`

제안 출처: F-010 Task 3(대표 출력 평가)에서 실제 NVIDIA 개발 credential로
`insufficient_evidence` 대표 질문("계약서상 위약금 조항이 유효한가요?")을 2회 독립
실행해 재현했다.

## 재현 요약

- 질문: "계약서상 위약금 조항이 유효한가요?" (fixture id: `insufficient_evidence`,
  `apps/api/tests/fixtures/layperson_plain_language_questions.py`)
- 1회차: `route=routing_unavailable`, summary가 프롬프트 규칙대로 "법률 검색을 진행할 수
  없습니다. 잠시 후 다시 시도해 주시기 바랍니다." 형태의 재시도 안내만 담음(규칙 준수).
- 2회차(같은 질문, 새 프로세스로 독립 재실행): 마찬가지로 `route=routing_unavailable`이지만
  summary가 "계약의 종류와 위약금 금액, 당사자의 협의 내용에 따라 달라집니다... 법률
  전문가에게 상담해 보시기 바랍니다"처럼 법률 유사 안내를 생성함 — `routing_unavailable`
  안내 프롬프트의 "법률 결론, 법령명, 조문 번호, 기관명, 인용 또는 다른 확인 절차를 만들지
  않는다"는 명시적 금지를 어김.
- 같은 질문, 같은 route 라벨인데 두 실행의 프롬프트 순응 여부가 다름 — 비결정적.

## 원인 후보(미확정)

- route classifier가 이 질문을 일관되게 `routing_unavailable`로 잘못 분류하고 있을 가능성
  (원래 의도는 "질문 분류를 일시적으로 처리할 수 없어 법령 검색을 시작하지 못했다"는
  transient 상태인데, 매번 같은 질문에서 재현되면 단순 일시 장애가 아닐 수 있다 — 이 질문은
  성격상 `external_document_required`가 더 맞을 수 있다).
- `build_blocked_route_messages()`의 `routing_unavailable` 안내를 실제 모델이 확률적으로
  따르지 않는 answer_generation 신뢰성 문제일 가능성.

이 작업은 둘을 구분하지 못한 채로 등록한다 — 후속 조사에서 먼저 분리해야 한다.

## 왜 F-010 Task 3에서 고치지 않았는가

- route classifier 로직과 재시도/신뢰성 처리는 `openai_answerer.py`,
  `nvidia_nim_clarification.py` 소유 범위 밖이다.
- 원인이 classifier 오분류인지 generation 프롬프트 미준수인지 구분되지 않은 상태에서
  prompt만 손대는 것은 근거 없는 변경이 될 위험이 있다(AGENTS.md "근거 없는 기술·법률
  요구사항을 임의로 확정" 금지).

## 완료 조건

- 이 질문(및 유사한 사용자 보유 문서 의존 질문들)을 소표본 반복 실행으로 재현해 원인을
  classifier 오분류 vs generation 프롬프트 미준수로 분리한다.
- classifier 문제면 라우팅 규칙/로직을 수정하고, generation 문제면
  `routing_unavailable` 안내 프롬프트를 강화하거나 검증 게이트를 추가한다.
- 같은 질문을 3회 이상 반복 실행해 안내 프롬프트 규칙(법률 결론·기관명·확인 절차를 만들지
  않음)을 모두 준수함을 확인한다.

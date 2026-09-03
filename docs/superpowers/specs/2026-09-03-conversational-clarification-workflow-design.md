# F-006 대화형 clarification workflow 설계

## 목적

사용자 사실이 부족해도 현재 확정 사실과 법령 근거로 답변하고, 남은 blocking 사실은 대화형 질문 포맷으로 수집한다. 모든 blocking 사실이 채워지면 full 답변으로 자동 완료한다. 사용자가 명시적으로 현재 정보로 답변을 요청하면 conditional 답변으로 완료한다.

## 작업 구조

`F-006`은 roadmap의 상위 Feature이며 저장소 metadata에 Epic 유형이 없으므로 Feature 본문에서 에픽 역할을 한다. 실행은 한 번에 하나의 milestone만 Picked Up으로 둔다.

1. case domain과 상태 전이
2. DB migration, 저장소, 소유자 격리와 만료
3. NVIDIA Ultra 기반 route/turn 판단과 LlamaIndex Workflow
4. 구조화된 claim 생성과 결정론적 grounding 검증
5. 기존 V2 API와 웹 chat UX 연결
6. 통합 회귀, 문서화, B-001 재질문 버그 완료 판정

기존 B-001은 삭제하지 않고 Task 6의 회귀 완료 조건으로 연결한다. realtime tool, 사용자 보유 문서 workflow, FunctionAgent tool loop는 비범위다.

## 정본 상태와 LlamaIndex 경계

`clarification_cases`가 장기 대화 정본이다. `question_execution`은 한 턴의 검색·생성·frozen citation만 소유한다. Context는 요청 단위 임시 상태이고 영속하지 않는다.

```python
class RequiredFact:
    id: str
    label: str
    why_needed: str
    blocking: bool
    group: str
    priority: int
    status: Literal["unanswered", "answered", "declined", "invalid", "conflicting", "no_longer_needed"]
    value: JsonValue | None
    source_turn_id: UUID | None

class ClarificationCase:
    case_id: UUID
    owner_scope: str
    capability_hash: str | None
    original_question: str
    as_of_date: date
    project_stage: str
    conversation_id: UUID | None
    required_facts: list[RequiredFact]
    status: Literal["waiting_for_user", "completed", "cancelled", "expired"]
    version: int
    expires_at: datetime
```

LlamaIndex `Workflow`, 요청 단위 `Context`, custom `Event`, `@step`을 orchestration에 쓴다. 매 요청마다 case snapshot을 DB에서 읽어 Context에 넣고 optimistic version 검사를 거쳐 저장한다.

## 대화·질문 포맷 계약

최초 질문에서 NVIDIA Ultra는 route와 모든 blocking fact 후보를 structured output으로 제안한다. 서버가 fact ID, 상태, 우선순위를 정본으로 만든다.

- 최초 clarification: 모든 blocking fact를 질문 포맷으로 표시한다.
- 후속 대화: `answered`, `declined`, `no_longer_needed` 항목을 제거한 모든 잔여 항목을 표시한다.
- 잔여가 6개 이상이면 의미상 관련된 3~5개만 현재 그룹으로 보이고, 해당 그룹이 정리되면 다음 그룹을 보인다.
- 아직 화면에 없는 그룹의 사실도 전체 case fact 목록과 대조해 병합한다.
- `waiting_for_user`는 다음 사용자 메시지를 기다릴 뿐 자동 모델 호출이나 재질문을 하지 않는다.

후속 메시지 의도는 `provide_facts`, `ask_about_case`, `request_answer_now`, `cancel_case`, `start_new_question`, `ambiguous` 중 하나다. 취소와 명시적 새 질문은 case를 종료한다. 명시적 답변 요청은 추출된 사실을 먼저 병합한 뒤 conditional 답변으로 종료한다.

## 답변과 결정론적 grounding

답변 정책은 `interim`, `full`, `conditional`이다. interim은 남은 사실이 있어도 현재 근거로 답할 수 있는 일반 규칙과 하위 사례 적용 결론을 답하고, 남은 사실에 의존하는 결론은 조건부로 표현한다.

```python
class GroundedClaim(BaseModel):
    text: str
    claim_kind: Literal["general_rule", "case_application", "conditional"]
    citation_ids: list[str]
    required_fact_ids: list[str] = []

def validate_claim(claim: GroundedClaim, case: ClarificationCase) -> bool:
    if not claim.text.strip() or not claim.citation_ids:
        return False
    if not all(citation in frozen_citation_ids for citation in claim.citation_ids):
        return False
    if claim.claim_kind == "general_rule":
        return not claim.required_fact_ids
    if claim.claim_kind == "case_application":
        return bool(claim.required_fact_ids) and all(
            case.fact(fid).status == "answered" for fid in claim.required_fact_ids
        )
    if claim.claim_kind == "conditional":
        return bool(claim.required_fact_ids) and all(
            case.has_fact(fid) for fid in claim.required_fact_ids
        )
    return False
```

검증기는 문구를 해석하거나 금칙어를 탐지하지 않는다. claim 구조, frozen citation registry, fact 상태만 검사한다. interim에서도 해당 claim의 모든 필요 사실이 answered이고 citation이 있으면 case_application을 허용한다.

## V2 API와 workflow

별도 resume endpoint는 만들지 않는다. 기존 `POST /v2/question-executions`에 `clarification_case_id`와 익명 사용자용 `clarification_capability`를 선택 필드로 더한다. 대기 case도 기존 `complete.response`에 clarification 블록을 넣어 반환한다.

```python
async def handle_user_turn(case, user_text):
    judgment = await ultra_interpreter.classify_and_extract(
        original_question=case.original_question,
        unresolved_facts=case.unresolved_facts(),
        user_text=user_text,
    )
    if judgment.intent == "cancel_case":
        return await close_case(case, reason="user_cancelled")
    if judgment.intent == "start_new_question":
        return await close_case_and_start_new_question(case, user_text)

    case = await repository.merge_valid_facts(case, judgment.submitted_facts)
    policy = "conditional" if judgment.intent == "request_answer_now" else (
        "full" if case.all_blocking_facts_answered() else "interim"
    )
    response = await run_v2_legal_answer(case, policy=policy)
    if policy == "interim":
        return response.with_clarification(await repository.mark_waiting(case))
    await repository.complete(case)
    return response
```

웹은 응답의 case ID를 chat state에 보관하고 다음 자유 텍스트에 자동 첨부한다. 질문 포맷은 답변 아래 구조화 체크리스트로 표시한다.

## 실패·보안·완료 조건

Ultra route/의도/추출 실패는 case를 변경하지 않고 안전 응답으로 끝낸다. 값 검증 실패는 해당 fact만 invalid로 두며, 유효한 다른 사실은 병합한다. 동시 입력은 version check로 하나만 반영한다. 익명 case는 capability, 로그인 case는 owner scope로 격리한다. case는 24시간 뒤 만료하며 질문 원문·fact 값은 telemetry, 로그, 공개 SSE event에 넣지 않는다.

검증에는 최초 전체 포맷, 후속 항목 제거, 6개 이상 그룹화, 자유 대화의 grounded interim 답변, full 자동 완료, conditional 완료, claim의 citation·fact 상태 검증, ownership, expiry, concurrent update, provider failure, v1/V2 회귀를 포함한다.

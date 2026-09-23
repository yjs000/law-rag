# Clarification 자유 문장 fact 추출 설계

`B-015` 작업의 설계 문서다. `B-013`(per-run Context 경계)이 완료된 뒤 이 설계를
구현한다.

## 배경

Web(`apps/web/app/page.tsx:571-573`)은 continuation 답변을 오직 `question: trimmed`
자유 문장으로만 보낸다. JSON 구조화 payload를 만드는 코드는 없다.

서버는 이 텍스트를 `user_text`로 넘기고(`apps/api/app/api/v2/executions.py:208`),
현재 운영 중인 유일한 continuation 추출기는
`StructuredClarificationContinuationExtractor`이다(`apps/api/app/bootstrap.py:354`).

이 추출기는 `user_text`를 JSON으로 파싱 시도한다
(`apps/api/app/adapters/structured_clarification_continuation.py:22-25`).
사람이 쓰는 자유 문장은 유효한 JSON이 아니므로 이 파싱은 **항상 실패**하고,
키워드 매칭 기반 `_free_text_intent`로 떨어져 `submitted_facts`가 항상 빈 채로
반환된다. 즉 사용자가 필요한 사실을 정확히 답해도 case에 저장되지 않는
경로가 프로덕션에서 상시 발생하는 버그다.

## 목표

자유 문장 답변에서 저장된 미해결 fact(`RequiredFact`, 서버가 발급한
`fact_id` 보유)에 대응하는 값을 LLM으로 추출·검증·병합하고, 일부만 답한
경우 답하지 않은 fact만 다시 묻는다.

## 기존 인프라 확인

`LlamaIndexClarificationWorkflow`(`apps/api/app/adapters/llamaindex_clarification_workflow.py`)의
턴 단계:

```
load_case → interpret_turn → validate_and_merge → select_policy → format_questions
```

- `interpret_turn`(:90-108)은 `continuation_extractor.extract_continuation(...)`을
  호출하고, **예외가 발생하면 그대로 잡아서** `InterpreterFailed`로 라우팅한다.
- `safe_provider_failure`(:111-122)는 case를 변경하지 않고
  `error_code="clarification_interpreter_unavailable"`, `policy="interim"`으로
  안전하게 종료한다. **이 안전장치는 이미 존재하며 재사용 가능하다.**
- `validate_and_merge`(:125-151)는 `judgment.submitted_facts`를
  `merge_submitted_facts(case, submissions)`에 넘겨 병합한다. 이 함수
  (`clarification_workflow.py:159-176`)는 case에 없는 `fact_id`를 무시하므로,
  모델이 목록 밖 id를 만들어내도 안전하다.
- `format_questions`(:176-199)는 `group_remaining_facts(remaining_facts())`로
  남은 fact를 묶어 `ClarificationQuestionFormat`을 만들어 클라이언트에 반환한다.
  재질문 루프는 여기서 자연히 발생하며, 별도 횟수 상한은 두지 않는다 — case
  TTL(`bootstrap`에서 주입되는 `case_ttl`)과 소유권 검증이 무한 대기를 막는다.

이 인프라 덕분에 새 추출기는 **자체 실패 처리 로직이 필요 없다**: 실패 시
그냥 예외를 던지면 기존 `InterpreterFailed` 경로가 처리한다.

## 설계

### 1. JSON 구조화 경로 제거

`structured_clarification_continuation.py`의 JSON 파싱 시도(`:22-25`)와
키워드 기반 `_free_text_intent`(:33-43)를 삭제한다. 프로덕션에서 한 번도
성공한 적 없는 죽은 경로이며, 다른 클라이언트도 이 경로에 의존하지 않는다
(운영 배선이 이 클래스 하나뿐).

### 2. `LlmClarificationContinuationExtractor` 신설

`apps/api/app/adapters/`에 새 어댑터 추가. `ContinuationFactIntentExtractor`
프로토콜(`clarification_workflow.py:112-121`)을 구현.

입력:
- `original_question`
- `unresolved_facts: tuple[RequiredFact, ...]` — 각 fact의 `id`, `label`,
  `why_needed`만 프롬프트에 노출 (value/status 등 내부 필드는 제외)
- `user_text`

프롬프트 지시:
- 목록에 있는 `fact_id`만 사용할 것 (새 id를 만들지 말 것)
- 명확히 답변된 fact만 `status="answered"`로 값과 함께 제출
- 답변을 거부한 fact만 `status="declined"`로 제출 (값 없음)
- 애매하거나 언급되지 않은 fact는 **아예 결과에 포함하지 말 것** — 임의로
  채우지 않는다
- intent 분류: `provide_facts` / `ask_about_case` / `request_answer_now` /
  `cancel_case` / `start_new_question` / `ambiguous` (기존
  `ClarificationIntent` 리터럴 그대로 재사용)

출력: 기존 `ClarificationTurnJudgment`(`intent`, `submitted_facts`,
`required_facts=()`)를 그대로 구성. 새 모델 타입 불필요.

실패 처리: 모델 타임아웃, 스키마 검증 실패, provider 오류는 **잡지 않고
그대로 전파**한다. 호출자(`interpret_turn`)가 이미 이를 `InterpreterFailed`로
변환해 안전하게 처리한다.

로깅: 사용자 원문·추출된 fact 값·capability를 로그/이벤트에 싣지 않는다.
어댑터 내부에 사용자 텍스트나 값을 로깅하는 코드를 추가하지 않는다.

### 3. 배선 교체

`apps/api/app/bootstrap.py:443-448`의
`build_structured_clarification_continuation_extractor()`를
`build_llm_clarification_continuation_extractor(settings)`로 교체.
기존 `InitialClarificationJudge`가 쓰는 것과 같은 모델 어댑터(설정에 따른
Ultra/NVIDIA 클라이언트)를 재사용해 새 provider 연동을 만들지 않는다.

## 데이터 흐름 요약

```
user_text (자유 문장)
  → LlmClarificationContinuationExtractor
      (unresolved_facts의 id/label/why_needed만 제공)
  → ClarificationTurnJudgment.submitted_facts: tuple[FactSubmission, ...]
      [{fact_id, status: answered|declined, value}]
  → merge_submitted_facts(case, submitted_facts)
      - 목록에 없는 fact_id → 무시
      - declined → status=DECLINED, value=None
      - answered + JSON 값 → status=ANSWERED, value=값
      - answered + JSON 불가 값 → status=INVALID, value=None
  → 새 ClarificationCase (불변, replace로 생성) → repository.merge로 저장
  → remaining_facts() 감소 → format_questions가 남은 fact만 재질문
```

## 완료 조건

- 실제 Web 형식(순수 자유 문장)으로 답한 fact가 저장되고 `remaining_count`가
  감소한다.
- 부분·복수·모호·거부·취소·새 질문·추출 실패(타임아웃/파싱오류) 경계가
  정상·실패·경계 테스트로 고정된다. 실패 케이스는 `InterpreterFailed` 경로로
  case 불변·`error_code` 설정을 검증한다.
- JSON 구조화 파싱 경로가 코드베이스에서 제거된다.
- B-016이 저장된 사실을 사용할 수 있도록 case의 값·상태 계약(`RequiredFact`,
  `FactStatus`)을 변경하지 않고 유지한다.

## 후속 연결

`B-013`의 per-run Context 경계가 완료된 뒤 구현한다. 사실 추출과 병합이
완료되면 `B-016`이 원 질문과 누적 사실을 검색·답변 입력으로 연결한다.
`B-014`는 두 작업을 포함한 실제 자유 문장 흐름을 교차 계층 회귀로 고정한다.

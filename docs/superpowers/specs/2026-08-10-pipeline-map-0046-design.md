# 0046 기준 질문 파이프라인 지도 갱신 설계

## 목적

`docs/generated/law-rag-question-pipeline-map.html`을 0046의 Terra always-generate
계약에 맞춘다. 0045의 시간 예산·타임아웃 변경은 이 지도에서 제외한다.

## 범위

- 지도 상단의 기준 시점과 참조 링크를 0046 구현 상태로 갱신한다.
- `answer_mode=terra`의 흐름을 사전 라우팅 뒤의 두 경로로 보인다.
  - `legal_search`: 검색 후 근거가 0건이어도 LLM이 `unanswerable` 응답을 생성한다.
  - `realtime_required`, `external_document_required`, `clarification_required`: 임베딩·검색을
    건너뛰고 전용 LLM 프롬프트로 응답을 생성한다.
- 빈 근거에서는 `unanswerable`, 또는 `missing_information`이 있는
  `clarification_required`만 구조 검증을 통과하며, 법적 주장은 생성하지 않는다는 경계를
  명시한다.
- AI 미가용, 생성 예외, 구조 검증 실패는 기존 `search_only` 또는 차단 안내문으로 폴백한다.
- `docs/exec-plans/active/README.md`에 활성 0046 계획을 목록 규칙에 맞춰 추가한다.

## 비범위

- 0045의 요청 시간 예산, 클라이언트 재시도, 타임아웃 값은 지도에서 제거하거나 언급하지 않는다.
- 검색 2~4단계의 존재 이유, URL 허용목록의 필터, 검색 전용 안전망, Precision/MRR 측정은
  HTML의 새 설명으로 추가하지 않는다. 이 내용은 작업 완료 보고에서만 설명한다.
- 서비스 동작, 테스트, API 스키마, 생성 프롬프트는 변경하지 않는다.

## 표현 방식

기존의 단계형 HTML·인라인 코드·근거 링크 구조를 유지한다. 기존 단일 생성 단계 앞에
`0046: Terra 생성 분기`를 두고, 검색 결과 0건 및 사전 차단 질문도 AI 생성에 도달함을
명확하게 표시한다. 폴백은 생성 경로의 오른쪽 또는 하단에 별도 안전 경계로 표시해,
정상 경로와 혼동되지 않게 한다.

## 검증

- HTML을 정적 검토해 0045 전용 숫자·링크·문구가 남지 않았는지 확인한다.
- 0046 계약의 핵심 용어(`answer_blocked_route`, `unanswerable`,
  `clarification_required`, `search_only`)와 구현 링크를 대조한다.
- `active/README.md`의 0046 링크가 실제 실행 계획 파일로 열리는지 확인한다.

## 결정 기록

- 2026-08-10: 사용자가 0046만 포함하고 0045는 제외하도록 확정했다. 지도는 시간 예산이
  아니라 무근거·사전 차단 요청의 Terra 생성 계약을 전달하는 데 집중한다.

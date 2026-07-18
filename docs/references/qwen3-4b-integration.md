# Qwen3:4b 연결 준비사항

기준 시점: 2026-07-18  
상태: 구현 전 검토, Ollama 사용은 가정

## 확인한 현재 제약

- 답변 모델과 어댑터가 `gpt-5.6-terra` 및 OpenAI Responses `responses.parse`에 고정되어 있다.
- 답변 생성과 임베딩이 하나의 `OPENAI_API_KEY` 존재 여부로 함께 활성화된다.
- Web/API 계약의 모드 이름과 사용자 문구가 `terra`에 고정되어 있다.
- Vercel에서 사용자 PC의 `localhost:11434`에는 접근할 수 없다.

Ollama 공식 문서는 `/v1/chat/completions`와 `/v1/responses` 일부 호환 및 JSON schema 기반 구조화 출력을 제공한다고 설명한다. 현재 코드의 `responses.parse(text_format=Pydantic)` 완전 호환은 smoke test 없이 가정하지 않는다.

## 구현 전 필요한 결정

1. 실행 위치: 로컬 개발 전용, API와 같은 사설망 서버, TLS·인증 외부 endpoint 중 하나를 확정한다.
2. 생성 API: Ollama native chat, OpenAI-compatible chat completions, Responses 중 구조화 출력 성공률이 가장 높은 경로를 smoke test로 선택한다.
3. 임베딩: 생성 모델 `qwen3:4b`와 분리해 기존 OpenAI 임베딩 유지 또는 별도 embedding 모델·재색인 계획을 확정한다.
4. 외부 모드명을 `ai`로 일반화할지 기존 `terra` wire 값을 호환용으로 유지할지 결정한다.

## 필수 코드 변경

- `ANSWER_PROVIDER`, `ANSWER_BASE_URL`, `ANSWER_API_KEY`, `ANSWER_MODEL`, 생성 timeout을 독립 설정한다.
- provider-neutral Answerer 포트와 factory를 만들고 `DraftAnswer.model_validate*`로 경계를 검증한다.
- JSON 밖 thinking, 코드펜스, 누락 필드, 잘못된 enum과 존재하지 않는 citation ID를 실패 처리한다.
- Answerer와 Embedder 활성화 조건·키·모델·timeout을 분리한다.
- 연결 거부, timeout, 429/503, context 초과, JSON/schema 실패에도 검색 전용 결과를 보존한다.
- base URL allowlist/HTTPS 정책을 두고 endpoint·키·질문·법령 원문 전문을 로그에 남기지 않는다.
- Web의 Terra 표시와 한도 안내를 공급자 중립 문구로 바꾸고 이력 호환을 검증한다.
- 제품 명세, RAG 설계 결정 기록, `.env.example`, 운영 문서와 `docs/learning/`을 함께 갱신한다.

## 필수 테스트

- 설정: provider별 필수값, URL, timeout, 알 수 없는 provider/model 거절
- 어댑터: 정상 한국어 구조화 출력과 invalid JSON/schema/thinking 혼입/timeout/429/503
- API: Qwen 성공, 장애·grounding 실패 시 검색 근거 보존, search-only 모델 호출 0회
- 임베딩: 공급자 분리, keyword fallback, 차원·모델 불일치와 재색인 계약
- grounding: 숫자, 부정, 의무·면제, 과잉 일반화, 없는 인용 회귀
- 운영 smoke: 고정 평가셋 구조화 성공률, p50/p95, timeout·grounding·fallback률

## 공식 참고자료

- https://docs.ollama.com/api/openai-compatibility
- https://docs.ollama.com/capabilities/structured-outputs
- https://ollama.com/library/qwen3


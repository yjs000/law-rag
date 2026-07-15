# Terra 런타임 폴백 계약

작성일: 2026-07-15

## 문제

브라우저가 Terra를 요청했더라도 서버의 AI 설정, API 결제·quota, 임베딩, 생성 또는 근거 검증 단계가 실패하면 API는 안전하게 검색 전용 결과를 반환한다. 기존 응답의 `mode=search_only`만으로는 사용자가 처음부터 검색 전용을 선택했는지 Terra가 실패했는지 구분할 수 없었다.

## 계약

`POST /v1/questions`는 다음 두 필드를 함께 반환한다.

- `requested_answer_mode`: 요청 당시의 `terra` 또는 `search_only`
- `fallback_reason`: Terra 요청이 검색 전용으로 바뀐 안전한 분류. 오류 전문, 키, 계정 정보는 포함하지 않는다.

공개 분류는 `ai_disabled`, `quota_exhausted`, `billing_or_quota_error`, `embedding_error`, `generation_error`, `grounding_failed`, `no_evidence`다. 명시적인 검색 전용 요청은 `fallback_reason=null`이다.

`GET /v1/corpus/status`는 `ai_available`과 함께 `ai_unavailable_reason`을 반환한다. 서버 설정으로 꺼져 있으면 `ai_disabled`, 현재 함수 인스턴스에서 결제·quota 오류를 관측했으면 `quota_exhausted`다.

## 데이터 흐름

1. Terra 요청 시 서버 설정과 현재 인스턴스의 quota 차단 상태를 확인한다.
2. 임베딩 실패는 키워드 검색을 계속 허용한다. 검색 근거까지 없으면 `embedding_error`로 검색 전용 응답을 반환한다.
3. 생성 호출의 HTTP 402/429는 해당 응답에 `billing_or_quota_error`를 기록하고 현재 인스턴스의 Terra 사용을 차단한다.
4. 이후 같은 인스턴스의 Terra 요청은 OpenAI를 호출하지 않고 `quota_exhausted`로 반환한다.
5. 생성 결과가 인용 근거 검증을 통과하지 못하면 `grounding_failed`로 폐기한다.

## 한계

API 키가 존재한다는 사실만으로 OpenAI 크레딧 잔액을 선제 확인할 수 없다. 별도의 유료 생성 호출 없이 `ai_available=true`는 설정상 준비 상태를 뜻한다. 최초 402/429를 관측한 뒤에야 런타임 상태가 바뀐다.

Vercel 서버리스의 프로세스 전역 상태는 함수 인스턴스별이며 재시작·스케일아웃 시 공유되지 않는다. 베타에서는 안전한 요청별 폴백을 보장하고, 모든 인스턴스에 즉시 적용되는 비용 차단은 이후 Supabase `runtime_flags` 같은 영속 상태로 옮겨야 한다.

## 직접 검증

```powershell
cd apps/api
..\..\.venv\Scripts\python.exe -m pytest tests/test_ai_fallback.py tests/test_grounding_gate.py -q
```

검증 범위는 명시적 검색 전용, AI 비활성화, 임베딩 실패, 생성 실패, 402/429 이후 전역 차단, 근거 검증 실패와 오류 전문 비노출이다.

## 다음 학습 주제

- 영속 `runtime_flags`를 이용한 서버리스 인스턴스 간 AI circuit breaker
- 사용자별 AI quota와 OpenAI 프로젝트 비용 한도의 조합

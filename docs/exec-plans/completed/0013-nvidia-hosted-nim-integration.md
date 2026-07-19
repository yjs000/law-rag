# NVIDIA Hosted NIM 생성 모델 연결

기준 시점: 2026-07-19  
상태: 구현 완료, 외부 운영 검증은 TD-014로 이관

## 목적

NVIDIA hosted NIM의 최상위 법률 RAG 후보를 provider-neutral 생성 경계에 연결하고, 기존 검색·인용 검증·검색 전용 fallback을 유지한다.

## 결정과 가정

- 기본 후보는 `nvidia/nemotron-3-ultra-550b-a55b`다. NVIDIA가 Frontier reasoning, 한국어, high-stakes RAG, hosted free endpoint를 명시한 현재 최상위 자사 모델이기 때문이다.
- 무료 endpoint는 prototype/trial이며 24시간 Production SLA나 무상 운영 계약으로 간주하지 않는다.
- 기존 `terra` wire 값은 호환성을 위해 유지하되 내부 provider는 `openai` 또는 `nvidia_nim`으로 분리한다.
- reasoning은 초기 구조화 출력 검증에서는 끄고, 법률 평가셋에서 별도 비교한다.
- 운영 API key와 외부 smoke test는 사용자 병목이다. 키 없이 adapter·mock·fallback까지만 검증한다.

## TODO

- [x] 설정: provider/base URL/key/model/timeout/max output을 분리한다.
- [x] adapter: NVIDIA Chat Completions와 JSON schema를 DraftAnswer로 검증한다.
- [x] 통합: main factory와 embedding key를 분리하고 기존 fallback을 보존한다.
- [x] 테스트: 정상 JSON, 빈/잘못된 JSON, provider 설정과 기존 fallback을 검증한다.
- [x] 취소: provider response ID 취소 가능 범위와 분산 신호 부하를 문서화한다.
- [x] 문서: 사용자 발급·Vercel 등록·평가·Production 전환 작업을 정리한다.

## 완료 조건

- NVIDIA key가 있으면 해당 adapter가 선택되고, key가 없으면 AI 비활성으로 검색 전용 결과가 유지된다.
- 모델 출력은 Pydantic schema와 기존 인용 grounding gate를 모두 통과해야 AI 답변으로 노출된다.
- 외부 API를 호출하지 않는 전체 단위 테스트와 lint가 통과한다.

## 사용자 병목

1. NVIDIA Developer 계정에서 API key 발급
2. Vercel Production/Preview에 `NVIDIA_API_KEY` 등록
3. Trial 약관으로 공개 24시간 서비스를 운영하지 않고 Production endpoint/Partner 계약을 확정
4. 운영 전 실제 API smoke와 법률 고정 평가셋 실행 승인

## 진행 기록

- 2026-07-19: NVIDIA hosted adapter, provider 설정, guided JSON schema, timeout·출력 상한과 공급자 중립 UI 문구를 구현했다.
- 2026-07-19: API key가 없어 외부 smoke는 실행하지 않았다. Trial endpoint를 24시간 Production 무료 서비스로 간주하지 않는다.

## 잔여 작업

- 사용자 API key 등록 후 Preview smoke와 고정 법률 평가셋 실행 — `TD-014`
- NVIDIA 계정의 Trial rate limit·데이터 보존 확인 — `TD-019`
- 공개 운영 전 partner endpoint 또는 NVIDIA AI Enterprise 계약 결정 — `TD-014`, `TD-019`

## 완료 결과

키 없이 가능한 adapter·설정·fallback·취소 계약·문서·회귀 테스트를 완료했다. 외부 key, Trial 정책과 Production 계약이 필요한 검증은 구현 완료 조건과 분리해 기술 부채 추적기로 이관했으므로 이 계획을 완료 처리한다.

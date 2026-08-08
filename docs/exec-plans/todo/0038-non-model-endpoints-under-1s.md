# 0038: 모델 호출 없는 API는 전부 1초 이내 응답

상태: `제안됨 · 미착수`

제안 출처: 2026-08-08 사용자가 모델(NVIDIA 임베딩·생성) 사용을 제외한 전체 API가 1초
이내로 응답해야 한다고 지시하고, 이를 강제하는 테스트를 먼저 만들고 통과하도록 구현할
것을 요구했다.

## 범위 확정 필요 사항

`apps/api/app/main.py`의 엔드포인트 중 모델(NVIDIA 임베딩/생성)을 호출하지 않는 것들이
대상이다:

- 제외(모델 호출함, 1초 기준 대상 아님): `POST /v1/search`(임베딩), `POST /v1/questions`
  (임베딩 + terra 모드면 생성)
- 대상(1초 이내여야 함): `GET /health`, `POST /v1/questions/{id}/cancel`,
  `POST /v1/auth/mock/google`, `GET /v1/auth/me`, `POST /v1/auth/logout`,
  `DELETE /v1/account`, `GET /v1/questions/history`, `GET /v1/conversations`,
  `GET /v1/conversations/{id}/turns`, `DELETE /v1/conversations/{id}`,
  `GET /v1/questions/history/{id}`, `DELETE /v1/questions/history/{id}`,
  `GET /v1/questions/history/{id}/checklist`, `GET /v1/provisions/{id}`,
  `GET /v1/documents/{id}/changes`, `GET /v1/corpus/status`

착수 시 이 분류가 맞는지, 그리고 "1초"가 p50/p95/p99 중 무엇을 기준으로 하는지, 콜드
스타트(Vercel 서버리스 첫 요청)를 포함할지를 먼저 확정해야 한다 - 지금은 사용자 지시를
그대로 옮긴 것이지 확정된 결정이 아니다.

## 설계 (미착수, 방향만)

- 테스트를 먼저 작성한다(`superpowers:test-driven-development` 적용 대상) - 각 대상
  엔드포인트를 호출해 응답 시간을 측정하고 1초 초과 시 실패하는 테스트를
  `apps/api/tests/`에 추가한다. DB·Supabase 등 외부 의존은 목/픽스처로 대체해 네트워크
  변동성이 테스트를 흔들지 않게 한다(이 저장소는 이미 `postgres_identity`/
  `identity_repository` 이중 경로가 있어 인메모리 경로로 테스트 가능할 가능성이 높다).
- 테스트가 실패하는 지점(느린 경로)을 먼저 찾은 뒤에만 구현에 들어간다
  (`superpowers:systematic-debugging` Phase 1 - 추측성 최적화 금지).
- 흔한 후보 원인: DB 커넥션 각 요청마다 새로 여는지, Supabase Auth 검증 호출 지연,
  N+1 쿼리, 불필요한 동기 I/O.

## 비범위

- `/v1/search`, `/v1/questions`의 모델 호출 구간 자체의 지연은 이번 항목이 아니다
  (NVIDIA 쪽 지연은 이미 별도로 다루고 있음 - [feat(api): retry NVIDIA answer
  generation](../../../apps/api/app/adapters/nvidia_nim_answerer.py) 커밋 참고).

## 승격 조건

- 사용자가 착수를 명시하고, 위 "범위 확정 필요 사항"의 기준(p50/p95/콜드스타트 포함
  여부)을 확정한다.

## 완료 조건

- 대상 엔드포인트 전부에 대해 1초 이내 응답을 강제하는 자동화 테스트가 존재하고 통과한다.
- 테스트가 실제 코드 지연을 재현 가능하게 잡아낸다는 걸 한 번은 일부러 지연을
  주입해(예: sleep) 실패시켜 확인한다(테스트가 실제로 유효함을 증명).

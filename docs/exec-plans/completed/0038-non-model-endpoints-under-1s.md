# 0038: 모델 호출 없는 API는 전부 1초 이내 응답

상태: `완료 (2026-08-09)`

제안 출처: 2026-08-08 사용자가 모델(NVIDIA 임베딩·생성) 사용을 제외한 전체 API가 1초
이내로 응답해야 한다고 지시하고, 이를 강제하는 테스트를 먼저 만들고 통과하도록 구현할
것을 요구했다.

## 확정 범위

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

사용자는 2026-08-09에 각 API 호출을 개별 측정해 하나라도 1초를 넘으면 실패하도록
확정했다. Vercel 콜드 스타트 첫 요청도 운영에서 별도로 측정하며 1초를 넘으면 실패로
기록한다.

## 설계

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

## 완료 조건

- 대상 엔드포인트 전부에 대해 1초 이내 응답을 강제하는 자동화 테스트가 존재하고 통과한다.
- 테스트가 실제 코드 지연을 재현 가능하게 잡아낸다는 걸 한 번은 일부러 지연을
  주입해(예: sleep) 실패시켜 확인한다(테스트가 실제로 유효함을 증명).

## 구현 결과 (2026-08-09)

- `test_non_model_endpoint_latency.py`에서 범위의 16개 비모델 엔드포인트를 모두 실제
  FastAPI `TestClient`로 호출하고, 각 호출의 경과 시간이 개별적으로 1초 미만인지
  검사한다. 실패 메시지에는 엔드포인트와 실제 시간이 포함된다.
- 계정·질문·대화 데이터가 필요한 경로는 테스트 안에서 생성해 인증 성공 경로를
  측정한다. 존재하지 않는 요청 취소와 조문은 정상적인 404 경로를 측정한다.
- 가상 시계를 1.001초로 주입한 경계 테스트가 실패하는 것을 확인해 1초 게이트가
  실제로 동작함을 고정했다.
- `/v1/corpus/status`의 운영 첫 측정은 8.647초, 연속 측정은 6.12~6.68초로 실패했다.
  원인은 `NullPool` 환경에서 코퍼스 건수·시계열 상태·마지막 동기화를 읽을 때 DB 연결을
  세 번 순차 생성한 것이었다. 세 조회를 하나의 `corpus_overview()` 연결 안에서 실행하도록
  바꾼 뒤에도 첫 요청 5.256초, 연속 요청 3.03~3.21초여서 기준을 통과하지 못했다.
- 남은 원인은 Vercel 함수 기본 리전(미국 `iad1`)과 Supabase DB 리전(서울) 사이의 장거리
  연결 왕복이었다. API의 단일 실행 리전을 `icn1`로 지정해 DB와 같은 지역에 배치했다.
- 최종 운영 측정은 `/v1/corpus/status` 첫 요청 **0.580초**, 연속 요청 **0.175~0.433초**,
  `/health` **0.281초**였다. 첫 요청을 포함해 모두 1초 미만이므로 운영 완료 조건을
  통과했다.
- 전체 API 검증은 `618 passed, 2 skipped`, Ruff와 GitHub Actions의 Python·Web 작업은
  모두 통과했다.

# 0039: 구조화된 에러 detail이 "[object Object]"로 표출됨

상태: `제안됨 · 미착수`

제안 출처: 2026-08-08 사용자가 로컬 API(port 8000)로 미래 기준일(2026-09-03)을 테스트하다
`unsupported_corpus_date` 422 응답을 받았는데, 실제 사람이 읽을 메시지 대신 객체 자체가
그대로 화면에 표시되는 걸 발견했다.

## 재현

```
POST /v1/questions  as_of_date=2026-09-03
→ 422 {"detail":{"code":"unsupported_corpus_date","message":"현재 corpus는 검증된 기준일
  범위 안에서만 검색할 수 있습니다.","requested_as_of_date":"2026-09-03",
  "supported_from":"2024-07-01","supported_through":"2026-08-08",
  "corpus_snapshot_id":"corpus-sha256:..."}}
```

[0035](0035-as-of-date-picker-future-limit.md)(기준일 미래 선택 제한)가 구현되면 이 특정
재현 경로는 막히지만, 아래 원인 자체는 별개 버그라 0035와 독립적으로 남긴다 - 서버가
객체 `detail`을 내려주는 다른 경로(`corpus_unready` 503 등)에서도 같은 문제가 난다.

## 원인

`apps/web/lib/api-client.ts`의 공용 `request()`가 에러를 이렇게 처리한다:

```ts
const body = await response.json().catch(() => null);
throw new Error(body?.detail ?? "요청을 처리하지 못했습니다.");
```

([api-client.ts:41-43](../../../apps/web/lib/api-client.ts:41) 부근)

백엔드가 `detail`을 **문자열**로 보내는 경로(대부분의 `HTTPException(detail="...")`)는
문제없지만, 아래 두 경로는 `detail`을 **객체**로 보낸다:

- `_require_supported_as_of_date`의 `unsupported_corpus_date`(422) —
  [main.py:724-733](../../../apps/api/app/main.py:724)
- `_corpus_unready_http_error`의 `corpus_unready`(503) —
  [main.py:696-703](../../../apps/api/app/main.py:696)

`new Error(object)`는 `object`를 문자열로 강제 변환해 `"[object Object]"`가 되고, 이게
그대로 `error` state에 담겨 화면에 표시된다. 실제 사람이 읽을 문구는
`body.detail.message`에 있는데 안 쓰인다.

## 설계 (미착수, 방향만)

- `request()`의 에러 처리에서 `detail`이 객체면 `detail.message`를, 문자열이면 그대로
  쓰도록 분기한다(예: `typeof body?.detail === "string" ? body.detail : body?.detail?.message ?? fallback`).
- 객체 `detail`의 나머지 필드(`code`, `supported_from/through`, `corpus_snapshot_id` 등)를
  UI에서 추가로 활용할지는(예: "지원 범위: 2024-07-01~2026-08-08" 같은 안내) 별도 결정 -
  이번 항목은 "사람이 읽을 수 있게"까지만 고친다.
- 백엔드가 앞으로 새 객체 `detail` 에러를 추가해도 프론트가 깨지지 않도록, 이 처리는
  특정 `code` 값에 의존하지 않고 `message` 필드 유무만 본다.

## 비범위

- 0035(기준일 미래 선택 자체를 막기)와는 별개다. 둘 다 착수해도 되고 하나만 해도 된다.
- 백엔드가 에러를 내려주는 형식(객체 vs 문자열) 자체를 통일하는 리팩터는 이번 항목이
  아니다.

## 승격 조건

- 사용자가 착수를 명시한다.

## 완료 조건

- `unsupported_corpus_date`, `corpus_unready` 에러가 발생했을 때 화면에 `[object Object]`가
  아니라 실제 한글 메시지가 뜬다.
- 기존처럼 문자열 `detail` 에러는 그대로 잘 표시된다(회귀 없음).
- 회귀 테스트 추가(`api-client-flow.test.ts` 또는 동등한 위치에 객체/문자열 `detail` 둘 다
  검증).

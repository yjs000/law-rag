# 0037: 계정(로그인 사용자) 사용 한도 제거 - 토글 가능한 모듈로

상태: `완료 (2026-08-09)`

제안 출처: 2026-08-08 사용자가 로그인 계정의 일일 사용 한도(AI 10회/일 · 검색 100회/일)를
없애야 한다고 지시했다. 단, 완전히 코드를 지우지 말고 나중에 다시 켤 수 있게 토글
가능한 모듈로 만들고, 지금은 "한도 없음" 상태로 두라고 명시했다. 서버 쪽 구현도 지금
하지 말고 이 항목으로만 남긴다.

[0034](../active/0034-web-auth-rehydration-throttle.md)와 마찬가지로 `apps/api/app/main.py`가
대상이지만, 이번엔 익명 한도를 없앤 [feat(api): remove anonymous daily quota limits](../../../apps/api/app/main.py)
커밋과 짝을 이루는 후속 작업이다 - 그때는 익명만 없앴고, 계정(로그인) 한도는
`authenticated_ai_daily_limit`/`authenticated_search_daily_limit`로 남겨뒀다.

## 원인

`apps/api/app/main.py`의 `_check_quota`가 로그인 사용자에게 계정 단위 한도를 건다:

```python
async def _check_quota(kind: str, *, user: MockUser | None = None) -> None:
    if user is None or not postgres_identity:
        return
    account_limit = (
        settings.authenticated_ai_daily_limit
        if kind == "ai"
        else settings.authenticated_search_daily_limit
    )
    if not await postgres_identity.consume_quota(user.id, date.today(), kind, account_limit):
        raise HTTPException(status_code=429, detail="오늘의 계정 사용 한도를 초과했습니다.")
```

([main.py:747-756](../../../apps/api/app/main.py:747) 부근, `settings.py`의
`authenticated_ai_daily_limit`/`authenticated_search_daily_limit` 참조)

프론트 계정 모달에도 이 값이 하드코딩된 문구로 노출된다: `계정 사용 한도: AI 10회/일 ·
검색 100회/일 (베타)` ([page.tsx:225](../../../apps/web/app/page.tsx:225)) - 이 문구도 같이
정리 대상이다.

## 설계 (미착수, 방향만)

- `Settings`에 `account_quota_enabled: bool = False` 같은 단일 토글을 추가한다(이름은
  구현 시 확정). 기본값을 `False`로 둬서 "지금은 한도 없음" 상태를 만족한다.
- `_check_quota`의 계정 분기 전체를 `if not settings.account_quota_enabled: return`으로
  감싸거나, 토글이 꺼져 있으면 `postgres_identity.consume_quota` 호출 자체를 건너뛴다 -
  기존 `authenticated_ai_daily_limit`/`authenticated_search_daily_limit`/
  `postgres_identity.consume_quota` 로직 자체는 지우지 않고 그대로 둬서, 나중에 토글만
  다시 켜면 복구되게 한다(사용자가 "추후에 다시 생길지도 모른다"고 명시).
- 프론트 계정 모달의 `계정 사용 한도` 줄은 토글이 꺼진 상태를 반영해 숫자를 보여주지
  않거나(예: "제한 없음") 줄 자체를 없앤다 - 백엔드가 실제로 한도를 걸지 않는데 프론트가
  숫자를 보여주면 거짓 정보가 된다.
- 토글 상태를 프론트가 알아야 문구를 맞게 보여줄 수 있는지, 아니면 프론트는 그냥
  "한도 없음"으로 고정 문구를 쓰고 백엔드 토글과 별개로 두는지는 착수 시 결정한다.

## 비범위

- 익명 사용자 한도(이미 별도로 완전히 제거함, 토글 없음)는 이번 항목이 아니다.
- UI에서 토글을 직접 조작하는 관리자 화면은 만들지 않는다 - 사용자가 "UI까진 없지만"이라고
  명시했다. 토글은 서버 설정(환경 변수/코드 상수) 수준이다.

## 승격 조건

- 사용자가 착수를 명시한다.

## 완료 조건

- 로그인 계정이 하루에 몇 번을 요청해도 429가 나지 않는다.
- 계정 모달에 더 이상 존재하지 않는 한도 숫자가 노출되지 않는다.
- 토글을 다시 켜면(설정값만 바꿔서) 기존 계정 한도 로직이 그대로 복구된다는 걸 테스트로
  증명한다(즉 로직 자체는 삭제되지 않고 조건부로만 꺼져 있어야 한다).

## 구현 결과 (2026-08-09)

- `Settings.account_quota_enabled: bool = False` 토글을 추가했다
  ([settings.py](../../../apps/api/app/settings.py)).
- `_check_quota`를 `if user is None or not postgres_identity or not
  settings.account_quota_enabled: return`으로 감쌌다 - 기존 `authenticated_ai_daily_limit`/
  `authenticated_search_daily_limit`/`postgres_identity.consume_quota` 호출 로직은 그대로
  남겨뒀다([main.py](../../../apps/api/app/main.py)).
- `apps/api/tests/test_account_quota_toggle.py` 신규: (1) 토글 기본값 False일 때
  `consume_quota`가 거부(False)를 반환해도 `_check_quota`가 절대 호출하지 않음을
  증명(`DenyingPostgresIdentity.calls == 0`), (2) 토글을 True로 켜면 동일한 거부 응답에
  429가 발생하고 `consume_quota`가 실제로 호출됨을 증명 - 즉 로직이 삭제되지 않고
  조건부로만 꺼져 있음을 회귀 테스트로 고정했다.
- 계정 모달의 `계정 사용 한도` 줄을 `AI 10회/일 · 검색 100회/일 (베타)`에서 `제한 없음`
  고정 문구로 바꿨다(프론트는 토글 상태를 조회하지 않고, 현재 기본값에 맞는 문구만 표시).
- `pytest`(api, 588 passed) 전체 통과, `npm test`(web) 전체 통과.

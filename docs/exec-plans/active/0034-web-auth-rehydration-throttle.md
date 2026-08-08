# 0034: 웹 프런트 탭 포커스 시 불필요한 인증·이력 재조회 억제

상태: `제안됨 · 미착수 — 설계 확정, 코드 수정 대기`

제안 출처: 2026-08-08 사용자가 배포된 `law-rag-web.vercel.app`에서 다른 창에 갔다가
돌아올 때마다 인증 재검토(`/v1/auth/me`)와 질문 이력 재조회가 반복되는 걸 확인하고,
"화면을 아예 껐다 켰을 때·로그아웃했을 때 등"은 재호출이 필요하되 단순 탭 전환은
줄여야 한다는 요구와 함께 설계·todo 등록을 지시했다.

## 원인

`apps/web/app/page.tsx`의 마운트 이펙트가 Supabase `onAuthStateChange` 이벤트를 구독한다:

```js
const { data: { subscription } } = createClient().auth.onAuthStateChange((event) => {
  const action = authEventAction(event);
  if (action === "clear") clearAuthenticatedWorkspace();
  else if (action === "hydrate") void Promise.resolve().then(hydrateUser);
});
```

```js
export function authEventAction(event: string): "clear" | "hydrate" | "ignore" {
  if (event === "SIGNED_OUT") return "clear";
  if (event === "SIGNED_IN" || event === "USER_UPDATED") return "hydrate";
  return "ignore";
}
```

Supabase JS SDK는 탭이 포커스를 다시 받을 때 세션을 재확인하면서 `SIGNED_IN`을 다시 쏘는
경우가 있다(앱이 만든 폴링이 아니라 SDK 내부 동작). `authEventAction`은 `SIGNED_IN`을
무조건 "hydrate"로 취급해 `hydrateUser()` → `/v1/auth/me` 재호출 → `setUser(새 객체)`로
이어지고, 아래 이펙트가 `user` **참조**가 바뀔 때마다 이력을 다시 불러온다:

```js
useEffect(() => {
  if (user) void Promise.resolve().then(() => refreshHistory());
}, [refreshHistory, user]);
```

즉 이미 로그인된 채로 탭만 왔다 갔다 해도 "재인증 + 이력 재조회"가 매번 발생한다.

## 설계 (2026-08-08 확정, 미구현)

**1) `hydrateUser()`에서 user id가 실제로 안 바뀌었으면 `setUser()`를 호출하지 않는다**

```js
const storedUser = await getStoredUser();
setUser((prev) => (prev?.id === storedUser?.id ? prev : storedUser));
```

참조가 유지되면 `refreshHistory` 이펙트가 안 따라 돈다 - 이것만으로 "탭 전환마다 이력
재로딩"은 해결된다.

**2) `/v1/auth/me` 호출 자체도 짧은 간격 안에서는 throttle한다**

```js
const lastHydrateAt = useRef(0);
const MIN_INTERVAL_MS = 60_000; // 1분

const hydrateUser = async ({ force = false } = {}) => {
  if (!force && Date.now() - lastHydrateAt.current < MIN_INTERVAL_MS) return;
  lastHydrateAt.current = Date.now();
  // ...기존 로직
};
```

- `SIGNED_OUT`: throttle 적용 안 함 - 항상 즉시 `clearAuthenticatedWorkspace()`.
- 마운트 시(최초 로드, 새로고침/탭 새로 열기 포함): `force: true`로 항상 실행 - "화면을
  아예 껐다 켰다"는 이 경로로 자연히 처리된다.
- `SIGNED_IN`/`USER_UPDATED`(탭 재포커스로 인한 재발생 포함): throttle 적용. 진짜 새
  로그인이면 직전에 `SIGNED_OUT`(또는 최초 무세션 상태)이 있었을 것이므로 자연히 통과한다.

## 범위

- `apps/web/app/page.tsx`의 `hydrateUser`/`authEventAction`/관련 `useEffect`만 수정한다.
- 백엔드(`apps/api`) 변경 없음.
- Supabase SDK 자체의 이벤트 발생 빈도를 바꾸려 하지 않는다 - 앱이 이벤트에 반응하는
  방식만 조정한다.

## 비범위

- 로그인·로그아웃 흐름 자체의 UX 변경
- 대화 이력 캐싱·페이지네이션 로직 변경(0034는 재호출 트리거만 줄인다)

## 승격 조건

- 사용자가 착수를 명시한다.

## 완료 조건

- 로그인된 상태에서 탭을 반복 전환해도(1분 이내) `/v1/auth/me`·이력 재조회 네트워크
  요청이 추가로 나가지 않는다.
- 새로고침·새 탭 열기·로그아웃·실제 재로그인에서는 여전히 정상적으로 재검증된다.
- `apps/web/lib/api-client-flow.test.ts` 또는 동등한 테스트로 회귀 검증한다.

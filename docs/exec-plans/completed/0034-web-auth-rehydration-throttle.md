# 0034: 웹 프런트 탭 포커스 시 불필요한 인증·이력 재조회 억제

상태: `완료 (2026-08-09)`

## 진행 기록

- 2026-08-08: 사용자가 착수를 명시해 `todo/`에서 `active/`로 이동. `apps/web/app/page.tsx`에
  아래 설계대로 구현:
  - `hydrateUser`가 `{ force }` 옵션을 받고, 마운트 시에만 `force: true`로 호출한다.
  - throttle·id 비교 판단을 `shouldHydrateNow`/`nextAuthUser` 순수 함수로 분리해
    `authEventAction`과 같은 방식으로 `apps/web/lib/auth-page-state.test.ts`에서 검증한다
    (`HYDRATE_THROTTLE_MS` export 포함).
  - `npm test`(51 passed), `tsc --noEmit` 통과 확인.
  - 미검증: 실제 브라우저에서 탭 재포커스 시 네트워크 요청이 실제로 억제되는지는
    dev 서버 preview 환경이 구성되지 않아 아직 확인하지 못했다.
- 2026-08-09: [0040](../completed/0040-verify-auth-rehydration-throttle-in-production.md)에서
  GitHub Deployments API로 배포 확인 + 코드 재검토(effect가 마운트 시 한 번만 실행됨을
  확인, throttle 로직 자체엔 버그 없음) 후, 사용자가 "탭 재포커스로는 아예 재호출 안 함"을
  최종 결정했다. `authEventAction`을 `(event, hasActiveSession)` 시그니처로 바꿔 진짜
  재로그인(직전 `SIGNED_OUT` 이후 첫 `SIGNED_IN`)에서만 hydrate하도록 재설계 - 60초
  throttle은 여전히 안전망으로 유지하되, 탭 재포커스만으로는 60초가 지나도 재호출되지
  않는다. `npm test`(64 passed), `tsc --noEmit` 통과.
- 2026-08-09: 후행 커밋 `7d84c51`의 production 배포와 로그인된 Chrome 세션에서 최종
  확인했다. 최초 로드 후 60초가 지난 상태로 새 탭을 열고 닫아 원래 탭을 5회 재포커스해도
  로그인 상태와 질문 이력 8건이 유지됐고, 브라우저의 관측 요청 자산에는 최초
  `/v1/auth/me`와 `/v1/conversations` 항목만 각각 1개 존재했다. 60초 이후 재포커스에서도
  추가 재수화가 발생하지 않는 완료 조건을 충족했다.

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

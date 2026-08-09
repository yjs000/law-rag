# 0040: 탭 재포커스 시 /v1/auth/me 재호출 - 배포됐는데도 재현되는 원인 조사

상태: `완료 (2026-08-09)`

제안 출처: 2026-08-08 사용자가 배포된 `law-rag-web.vercel.app`에서 탭을 왔다갔다 할 때
`/v1/auth/me`가 여전히 계속 호출된다고 보고했다. [0034](0034-web-auth-rehydration-throttle.md)
(같은 날 구현·커밋됨)가 정확히 이 문제를 다루는데, 처음엔 "아직 배포 안 됐을 것"으로
추정했으나 **Vercel API로 직접 확인한 결과 이미 배포돼 있었다** — 아래 "배포 확인" 참고.
즉 배포 문제가 아니라 **진짜 버그이거나 설계값(60초 throttle) 자체가 사용자 기대와 안
맞는 것**일 가능성이 높다.

## 배포 확인 (2026-08-08)

```
git fetch origin main
→ origin/main 최신 커밋: 7bc04b0 (0034 커밋 d810b2c보다 뒤)

Vercel get_project(law-rag-web).latestDeployment:
  id: dpl_7RVcZwj4TmMZrGL53GnZmXvoYkuf
  target: production, readyState: READY
  githubCommitSha: 7bc04b0...
```

`7bc04b0`은 `main` 브랜치에서 0034 커밋(`d810b2c`)의 후행 커밋이므로, **0034 변경사항이
포함된 상태로 프로덕션에 배포돼 있다.** 재배포는 필요 없다.

## 원인 후보 (우선순위순, 배포 확인 후 재정렬)

1. **(유력) 60초 throttle 자체가 사용자 기대와 다름.** 0034는 재호출을 완전히 막은 게
   아니라 `HYDRATE_THROTTLE_MS = 60_000`([page.tsx](../../../apps/web/app/page.tsx))
   안에서만 억제한다 - 60초 넘게 텀을 두고 탭을 오가면 다시 호출되는 게 **의도된
   동작**이다. 사용자가 "여전히 계속 호출된다"고 느낀 게 60초 이내 재호출(진짜 버그)인지,
   60초 넘겨서마다 한 번씩(설계상 정상이지만 사용자는 "탭 전환으로는 아예 재호출 안
   해야 한다"고 기대)인지 아직 구분이 안 됐다.
2. **(가능성 있음) throttle 로직 자체의 버그.** `lastHydrateAt`이 `useEffect` 내부의
   일반 `let` 변수([page.tsx](../../../apps/web/app/page.tsx))인데, 이 effect의
   의존성 배열이 `[clearAuthenticatedWorkspace]`뿐이라 정상적으로는 마운트 시 한 번만
   실행돼야 한다. 만약 React 18 Strict Mode(개발 모드에서 effect 이중 실행) 또는 다른
   이유로 이 effect가 재실행되면 `lastHydrateAt`이 리셋돼 throttle이 무력화될 수 있다 -
   프로덕션 빌드에서도 이게 재현되는지 확인이 필요하다.
3. **(가능성 낮음, 배제됨) 다른 호출 경로.** grep으로 `/v1/auth/me`를 부르는 코드가
   `hydrateUser()` 하나뿐임을 확인했다(로컬 소스 기준, 배포본과 동일 커밋이라 유효).

## 설계 (미착수, 방향만)

- 먼저 사용자가 실제로 겪은 게 "60초 이내 재호출"인지 "60초 넘겨서 한 번씩"인지부터
  확인한다 - 배포된 사이트에서 Network 탭 타임스탬프로 재호출 간격을 재본다.
- 60초 이내 재호출이면: 위 원인 후보 2번(effect 재실행)부터 조사한다.
- 60초 넘겨서 한 번씩이라면 버그가 아니라 설계값 문제다 - "탭 전환으로는 아예 재호출하지
  않는다"가 실제로 원하는 동작인지 확정하고, 그렇다면 `authEventAction`이 탭 재포커스로
  인한 `SIGNED_IN`을 아예 `"ignore"`로 처리하도록(진짜 새 로그인과 구분할 방법이 필요 -
  예: 마지막 `SIGNED_OUT` 이후 처음 오는 `SIGNED_IN`만 처리) 재설계한다.

## 비범위

- 0034 자체의 재구현(이미 완료·커밋·배포됨)은 이번 항목이 아니다.

## 승격 조건

- 사용자가 착수를 명시한다.

## 완료 조건

- 배포된 사이트에서 로그인 상태로 탭을 반복 전환했을 때(60초 이내) `/v1/auth/me` 추가
  호출이 없다.
- 60초를 넘긴 재포커스에서의 재호출이 사용자 기대와 일치하는지(허용/비허용) 확정되고,
  필요하면 로직이 그에 맞게 조정된다.

## 구현 결과 (2026-08-09)

- **배포 재확인**: `gh api repos/yjs000/law-rag/deployments`로 GitHub Deployments API를
  직접 조회 - 최신 production 배포(`law-rag-web`, deployment id `5809275674`,
  `2026-08-08T13:50:02Z`, state `success`)의 `sha`가 `a2eb41f`로, 0034 커밋(`d810b2c`)의
  후행 커밋임을 재확인했다. 기존 Vercel API 기반 결론과 일치 - 배포 문제가 아니었다.
- **코드 재검토**: `page.tsx`의 인증 `useEffect` 의존 배열이 `[clearAuthenticatedWorkspace]`
  하나뿐이고 그 `useCallback`의 의존 배열이 `[]`(참조 안정)임을 확인 - 즉 프로덕션
  빌드에서 이 effect는 마운트 시 한 번만 실행된다. `lastHydrateAt`이 effect 재실행으로
  리셋되는 버그(원인 후보 2번)는 재현되지 않는다.
- **결론**: 원인 후보 1번(60초 throttle이 설계상 정상 동작)이 맞았다. 60초를 넘긴 재포커스
  마다 `/v1/auth/me`가 다시 호출되는 게 코드상 의도된 동작이었다.
- **사용자 결정 (2026-08-09)**: "탭 재포커스로는 아예 재호출 안 함"을 선택 - 60초 주기
  재호출도 없애고, 실제 재로그인(직전 `SIGNED_OUT` 이후 첫 `SIGNED_IN`)에서만 재호출하도록
  재설계하기로 확정.
- **구현**: `authEventAction(event, hasActiveSession)`으로 시그니처를 바꿔, `SIGNED_IN`은
  `hasActiveSession`이 `false`일 때만(즉 아직 세션이 없다고 알고 있을 때만) `"hydrate"`를
  반환하고, 이미 세션이 있다고 판단되면 `"ignore"`한다. `USER_UPDATED`는 항상 hydrate하고
  `SIGNED_OUT`은 세션 상태와 무관하게 항상 clear한다. effect 안에 `hasActiveSession`
  closure 변수를 추가해 `hydrateUser` 성공 시 `storedUser !== null`로 갱신하고, 실패
  또는 `SIGNED_OUT` 처리 시 `false`로 되돌린다.
- **검증**: `auth-page-state.test.ts`에 `authEventAction` 새 시그니처 테스트(실제 로그인 vs
  탭 재포커스 노이즈 구분) 추가. `npm test`(64 passed), `tsc --noEmit` 통과. 브라우저
  preview로 페이지가 정상 렌더링됨을 확인. 배포된 사이트에서의 실제 탭 반복 전환
  네트워크 재현은 이 세션에서 수행하지 않았다 - 다음 배포 후 확인 권장.

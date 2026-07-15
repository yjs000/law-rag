# Google OAuth·Supabase Auth 연결 설계

상태: 승인 전 초안
작성일: 2026-07-15

## 목적

`law-rag`의 Google 로그인은 Web이 Google 토큰을 직접 관리하는 구조가 아니다. Google은 사용자를 식별하고 동의를 받는 OpenID Connect 공급자이고, Supabase Auth가 OAuth client secret, Google callback, 사용자 연결과 애플리케이션 세션 발급을 담당한다. Next.js Web은 로그인 시작과 최종 PKCE code 교환을 담당하며, FastAPI는 발급된 Supabase JWT만 검증한다.

Google 로그인은 OAuth 2.0 Authorization Code 흐름에 OpenID Connect의 `openid`, `email`, `profile` scope를 더한 형태로 이해한다. 비밀번호와 Google access token을 애플리케이션이 직접 받지 않는다.

## 이 프로젝트에 입력할 값

현재 Production Web은 `https://law-rag-web.vercel.app`, Supabase project ref는 `ijoqcauleoobbxdbdhxg`다.

### Google Cloud → Google 인증 플랫폼 → 클라이언트 → `law-rag-web`

승인된 JavaScript 원본:

```text
https://law-rag-web.vercel.app
http://localhost:3000
```

승인된 리디렉션 URI:

```text
https://ijoqcauleoobbxdbdhxg.supabase.co/auth/v1/callback
```

주의:

- JavaScript 원본은 `scheme + host + port`만 입력한다. 경로와 trailing slash를 붙이지 않는다.
- Google redirect URI는 Supabase Dashboard의 Google provider 화면에 표시되는 callback URL과 문자 단위로 같아야 한다.
- `https://law-rag-web.vercel.app/auth/callback`은 Google redirect URI가 아니다. 이 주소는 Supabase가 인증 완료 후 브라우저를 돌려보낼 애플리케이션 callback이다.
- hosted Supabase를 localhost Web에서도 함께 사용한다면 Google에는 hosted Supabase callback 하나만 있으면 된다.
- Supabase CLI로 Auth까지 로컬 실행할 때만 별도로 `http://127.0.0.1:54321/auth/v1/callback`을 추가한다.

### Supabase Dashboard → Authentication → Sign In / Providers → Google

Google Cloud에서 발급한 값을 다음 필드에 저장한다.

- Client ID: Google OAuth Web client ID
- Client Secret: Google OAuth Web client secret
- Google provider: enabled

Client ID는 브라우저에 노출될 수 있는 식별자지만 Client Secret은 비밀이다. Client Secret을 Git, `.env` 커밋, `NEXT_PUBLIC_*`, 브라우저 번들 또는 채팅에 넣지 않는다. 이 구성에서는 Supabase Dashboard만 secret을 보관한다.

`Authentication → OAuth Server`에서 OAuth client를 새로 등록하지 않는다. 그 화면의 `Public client`와 `Token endpoint auth method`는 Supabase를 다른 애플리케이션의 identity provider로 제공할 때 쓰는 반대 방향의 기능이다. 이 프로젝트는 Supabase의 Google social provider를 사용하므로 두 옵션 모두 설정 대상이 아니다. 별도의 OAuth Server client를 만들거나 OAuth Server 기능을 활성화하지 않는다.

### Supabase Dashboard → Authentication → URL Configuration

Site URL:

```text
https://law-rag-web.vercel.app
```

Redirect URLs:

```text
https://law-rag-web.vercel.app/auth/callback
http://localhost:3000/auth/callback
```

Production은 정확한 callback URL을 등록한다. 현재는 Preview OAuth를 열지 않는다. Preview 로그인이 필요해지면 운영 사용자·비밀 경계를 검토하고 별도 OAuth client와 Supabase 프로젝트를 우선 사용한다. `*.vercel.app` 전체를 Google 또는 Production Supabase에 광범위하게 허용하지 않는다.

## 표준 흐름과 이 프로젝트의 역할

```text
사용자 브라우저
  1. Google 로그인 클릭
  v
Next.js Web
  2. Supabase signInWithOAuth(provider=google,
     redirectTo=https://law-rag-web.vercel.app/auth/callback) 호출
  3. PKCE verifier는 브라우저/서버 세션에 보관하고 challenge만 전달
  v
Supabase Auth /authorize
  4. state와 Google authorization request 구성
  v
Google Authorization Server
  5. Google 로그인·동의·OIDC scope 승인
  6. authorization code와 state를 Supabase callback으로 반환
  v
https://ijoqcauleoobbxdbdhxg.supabase.co/auth/v1/callback
  7. Supabase가 Client Secret으로 Google code를 교환
  8. Google ID token 검증 후 auth.users 생성 또는 기존 identity 연결
  9. 일회용 Supabase auth code를 Web callback으로 전달
  v
https://law-rag-web.vercel.app/auth/callback
  10. Web이 PKCE verifier로 exchangeCodeForSession 실행
  11. Supabase access/refresh session을 안전한 cookie에 저장
  v
FastAPI + Supabase PostgreSQL
  12. 요청마다 Supabase JWT의 서명·issuer·audience·만료 검증
  13. 내부 user ID와 auth.uid()를 기준으로 인가·RLS 적용
```

리디렉션이 두 종류인 이유는 신뢰 경계가 두 번 바뀌기 때문이다.

1. Google → Supabase: Google authorization code를 client secret을 가진 Supabase만 받아야 한다.
2. Supabase → Web: Supabase 인증을 마친 브라우저가 애플리케이션 callback으로 돌아와 PKCE session 교환을 마쳐야 한다.

## 설정과 코드의 대응 관계

| 값 | 설정 위치 | 실제 사용 주체 | 역할 |
|---|---|---|---|
| Web origin | Google Authorized JavaScript origins | Google | 허용된 Web origin 식별 |
| Supabase callback | Google Authorized redirect URIs | Google → Supabase | Google code를 받을 고정 endpoint |
| Client ID/Secret | Supabase Google provider | Supabase → Google | OAuth client 인증 |
| Site URL | Supabase URL Configuration | Supabase | `redirectTo`가 없을 때의 기본 복귀 URL |
| Web `/auth/callback` | Supabase Redirect URLs | Supabase → Web | 허용된 로그인 완료 목적지 |
| `redirectTo` | Next.js 로그인 시작 코드 | Web → Supabase | 이번 요청이 돌아올 정확한 callback |

## 코드 구현 시 보안 계약

- `signInWithOAuth`는 Authorization Code + PKCE를 사용한다.
- `/auth/callback`은 `code` 존재 여부와 오류를 검사하고 `exchangeCodeForSession`을 한 번만 수행한다.
- callback 이후 이동할 `next` 값은 `/`로 시작하는 내부 상대 경로만 허용해 open redirect를 막는다.
- OAuth `state`, PKCE verifier와 세션 cookie는 프레임워크/Supabase SDK의 검증 경로를 사용하며 임의로 생략하지 않는다.
- Production cookie는 `Secure`, `HttpOnly`, 적절한 `SameSite`를 적용한다.
- FastAPI는 JWT payload를 단순 decode하지 않고 Supabase JWKS 서명, `iss`, `aud`, `exp`를 검증한다.
- Google provider ID와 애플리케이션 내부 사용자 ID를 분리한다. 소유권 판단은 이메일 문자열이 아니라 검증된 내부 user ID로 한다.
- 로그인 성공만으로 약관 동의가 생긴 것으로 간주하지 않는다. 신규 가입 UI에서 받은 동의 버전과 시각을 별도 저장한다.
- Google access/refresh token은 Google API를 호출할 제품 요구가 없으므로 별도 저장하지 않는다. 애플리케이션에는 Supabase session만 필요하다.

## 설정 후 검증 순서

1. Google OAuth client의 JavaScript origins와 Supabase callback을 저장한다.
2. Supabase Google provider에 Client ID/Secret을 저장하고 활성화한다.
3. Supabase Site URL과 두 개의 정확한 Web callback URL을 저장한다.
4. Google 앱이 Testing 상태라면 테스트 사용자에 실제 로그인할 Google 계정을 추가한다.
5. Web의 `/auth/callback`과 Supabase client 구현이 완료된 뒤 localhost에서 로그인·취소·재로그인을 확인한다.
6. Production에서 로그인, 새 사용자 생성, 기존 사용자 복원, refresh, 로그아웃을 확인한다.
7. 다른 사용자의 질문 이력 접근이 FastAPI 인가와 RLS 양쪽에서 거부되는지 확인한다.
8. 계정 삭제 후 질문·세션·내보내기 등 사용자 연결 데이터 삭제 전파를 확인한다.

설정만 완료해도 현재 화면의 Google 버튼이 바로 동작하는 것은 아니다. 저장소에는 아직 실제 Supabase OAuth 시작과 `/auth/callback` session 교환 코드가 없으며, 구현은 실행 계획 `0004-google-authentication.md`의 다음 단계다.

## 대표 오류

| 증상 | 주된 원인 | 확인 위치 |
|---|---|---|
| `redirect_uri_mismatch` | Google에 등록한 Supabase callback과 요청의 URI가 다름 | Google Authorized redirect URIs |
| `origin_mismatch` | Web의 scheme/host/port가 JavaScript origins에 없음 | Google Authorized JavaScript origins |
| 로그인 뒤 localhost 또는 잘못된 페이지로 이동 | Supabase Site URL 또는 `redirectTo` allowlist 불일치 | Supabase URL Configuration |
| Google 동의 화면에서 접근 차단 | Testing 앱의 테스트 사용자 누락 또는 Audience 설정 | Google Audience |
| callback은 왔지만 로그인 세션이 없음 | PKCE verifier cookie 유실, code 중복 교환 또는 callback 구현 오류 | Next.js `/auth/callback` |
| API만 401 | Supabase session은 있으나 FastAPI JWT 검증/전달 미구현 | Web API client와 FastAPI auth adapter |

## Production 전 결정

현재 `vercel.app` 주소로 베타 테스트는 가능하지만, 공개 서비스의 Google branding/verification과 피싱 방어를 위해서는 운영자가 소유한 custom domain을 권장한다. custom domain을 도입하면 Google JavaScript origin, Supabase Site URL/Redirect URLs와 Web 환경변수를 같은 변경에서 갱신한다. Google redirect URI는 Supabase Auth custom domain을 별도로 도입하지 않는 한 기존 Supabase callback을 유지한다.

## 공식 참고

- [Supabase: Login with Google](https://supabase.com/docs/guides/auth/social-login/auth-google)
- [Supabase: Redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls)
- [Google: OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google: OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [Google: OAuth 2.0 Policies](https://developers.google.com/identity/protocols/oauth2/policies)

## 결정 기록

- 2026-07-15: Google은 identity provider, Supabase Auth는 OAuth confidential client와 session issuer, Next.js는 PKCE client/callback, FastAPI는 Supabase JWT resource server 역할로 분리한다. Client Secret과 Google code 교환을 브라우저·FastAPI에 중복 구현하지 않기 위함이다.
- 2026-07-15: Production Google redirect URI는 hosted Supabase callback 하나로 고정하고, Production/localhost Web callback은 Supabase redirect allowlist에서 관리한다. 두 redirect 계층을 혼동해 callback mismatch나 open redirect를 만들지 않기 위함이다.

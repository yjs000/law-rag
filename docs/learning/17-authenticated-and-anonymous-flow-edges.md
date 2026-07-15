# 로그인·익명 전체 흐름의 인증 경계

## 배운 점

OAuth 성공 여부만으로 로그인 사용자 여정이 끝나지 않는다. 초기 세션 복원, 동의가 없는 부분 생성 계정, 질문 이력 소유권, 로그아웃 직후 화면 메모리와 늦게 끝난 요청까지 같은 개인정보 경계로 다뤄야 한다. 익명 흐름도 질문 미저장뿐 아니라 quota 주체 검증, 빈 결과와 검색 장애의 구분이 필요하다.

## Web 상태 전이

초기 인증 상태는 `checking`이다. 이 상태에서 로그인 버튼을 먼저 보이면 실제 세션이 있는 사용자에게 로그아웃된 것처럼 보인다. 복원이 끝난 뒤에만 로그인 또는 계정 UI를 표시한다.

Supabase 인증 이벤트는 다음처럼 제한한다.

- `SIGNED_OUT`: 사용자, 질문 이력, 현재 질문·답변·인용과 계정 모달을 모두 초기화한다.
- `SIGNED_IN`, `USER_UPDATED`: API의 `/v1/auth/me`를 다시 읽는다.
- 토큰 갱신 잡음은 UI를 불필요하게 초기화하지 않는다.

각 인증 전환에는 epoch를 증가시킨다. 이전 epoch에서 시작된 이력 요청이 나중에 완료돼도 결과를 버리면 로그아웃 뒤 질문 목록이 되살아나는 경쟁 조건을 막을 수 있다.

## OAuth callback 경계

callback의 `next`는 `/`로 시작하는 것만으로 충분하지 않다. `//external.example`과 역슬래시 변형은 URL 해석에서 외부 origin이 될 수 있으므로 차단한다. 성공·오류 redirect는 요청 origin 또는 검증된 HTTPS Site URL만 사용한다. 취소 사유는 `access_denied`처럼 UI에 필요한 안전한 열거값만 보존한다. PKCE verifier와 state 검증은 Supabase SSR 교환 경로를 유지한다.

## 가짜 ID 기반 API 흐름

실제 계정 대신 고정된 가짜 Supabase auth UUID 두 개를 사용해 다음 흐름을 반복한다.

1. 동의 없는 첫 `/v1/auth/me`는 409다.
2. 정확한 약관·개인정보 버전 한 쌍으로 내부 프로필을 만든다.
3. owner 질문만 owner 이력에 저장한다.
4. stranger의 detail·delete는 존재를 숨기는 404다.
5. 계정 삭제 뒤 owner 프로필·질문은 사라지고 기존 토큰은 거부되며 stranger는 유지된다.

Bearer 헤더의 공백·복수 토큰, 만료·위조 토큰, 공급자의 비정상 JSON·UUID·날짜·metadata는 모두 fail-closed 처리한다. 공급자 네트워크 장애는 잘못된 자격증명과 구분해 재시도 가능한 503으로 반환한다.

## 익명 질문과 quota

익명 질문은 응답을 만들더라도 이력 저장 경로에 들어가지 않는다. 이후 로그인해도 과거 익명 질문을 소급 저장하지 않는다. Production의 잘못되거나 누락된 `x-forwarded-for`와 복수 IP 체인은 공격자가 quota 주체를 회전하지 못하도록 하나의 fail-closed 주체로 모은다. quota는 종류·주체·날짜별로 분리하고 설정값은 1 이상만 허용한다.

검색 결과 없음은 정상 `no_results`이고, 저장소 장애는 내부 호스트·자격정보를 숨긴 503이다. 두 상태를 구분해야 사용자가 질문을 구체화할지 나중에 재시도할지 알 수 있다.

## 검증

가짜 ID·토큰·IP만 사용한 API 테스트와 Web 상태 테스트를 권위 회귀로 둔다. 실제 Google 계정, CAPTCHA, 2단계 인증과 운영 계정 삭제는 자동 회귀에서 제외한다. 대표 전체 검증은 `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`이다.

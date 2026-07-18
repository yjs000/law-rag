# 21 대화 이력 페이지네이션과 인증 지연

## 문제

초기 UI는 질문·응답 한 쌍만 보유해 다음 질문이 이전 화면을 덮어썼다. 로그인하면 질문 이력의 모든 응답 JSON과 인용 원문을 한 번에 받았고, 사용자 확인 과정에서 같은 Supabase session을 두 번 읽었다. API는 인증 요청마다 새 HTTP client를 만들고 기존 프로필도 매번 UPDATE했다.

## 구현 계약

- `conversations`가 첫 질문 제목, 최근 갱신 시각, 턴 수를 보유하고 `question_history`는 순서 있는 턴을 저장한다.
- 대화 목록은 20개 요약만 keyset cursor로 읽는다. 응답·인용·진단은 목록에 포함하지 않는다.
- 대화를 열면 최신 20개 턴을 읽고 위쪽 스크롤 또는 `이전 대화 불러오기`로 과거 페이지를 추가한다.
- 기존 질문 이력 API는 하위 호환을 위해 유지한다. 기존 행은 migration에서 각 1턴 대화로 backfill한다.
- 소유권은 API의 `user_id` 조건, 복합 외래키와 RLS로 중복 검증한다.
- 한 대화는 사용자·도우미 메시지 400개를 넘지 않는다. 다음 요청/응답 쌍이 한도를 넘기 전에 새 대화를 만들고 전환 사실을 안내한다.
- 브라우저 중지 버튼은 fetch를 abort하고 늦은 응답을 버린다. 서버 계산·쿼터·저장을 확정적으로 취소하는 기능으로 표현하지 않는다.

## 인증 지연 개선

`getStoredUser`는 얻은 access token을 `/auth/me` 요청에 재사용해 session 조회를 한 번으로 줄였다. Supabase Auth adapter는 프로세스 안에서 `httpx.AsyncClient`를 재사용하고 FastAPI lifespan에서 닫는다. 프로필 email/display name이 바뀌지 않으면 UPDATE하지 않는다. 이력 read는 동기 전체 purge 대신 `expires_at > now()`로 만료 데이터를 숨기며 물리 삭제는 별도 cleanup 계약으로 유지한다.

이 변경으로 코드상 중복 세션 조회, HTTP 연결 생성, 불필요 DB 쓰기는 제거됐다. 다만 실제 Production 지연의 Vercel cold start, Supabase Auth RTT, DB 연결 대기별 기여율은 Server-Timing 또는 분산 trace 측정 전에는 확정할 수 없다.

## 검증 경계

- API 159개, core 3개 테스트
- Web chat-state와 API client를 포함한 43개 테스트
- Ruff, ESLint, TypeScript, 문서 검사와 Production build
- 실제 400 메시지 UI E2E와 Production 로그인 p50/p95는 후속 운영 측정 항목


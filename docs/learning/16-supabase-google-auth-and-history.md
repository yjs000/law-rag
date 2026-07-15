# Supabase Google 인증과 질문 이력 연결

작성일: 2026-07-15

Google은 신원 제공자이고 Supabase Auth가 PKCE code 교환과 세션 발급을 담당한다. Next.js는 `@supabase/ssr` cookie 세션을 유지하고, FastAPI 호출 때 access token만 Bearer 헤더로 전달한다. Google client secret과 `sb_secret_...` 키는 브라우저에 전달하지 않는다.

FastAPI는 Supabase Auth `/auth/v1/user`로 토큰과 최신 사용자를 검증한다. Supabase 공급자 ID와 애플리케이션 내부 UUID는 분리한다. 신규 내부 프로필은 베타 이용약관·개인정보 처리방침 버전이 함께 전달된 경우에만 생성한다. 질문 이력은 내부 UUID 소유권 조건으로 조회·삭제하고 생성 후 1년이 되면 제거한다.

데이터베이스에는 `user_profiles`, `user_consents`, `question_history`, `checklist_exports`, `account_usage`를 추가했다. RLS는 Supabase Data API의 방어선이고, pooler로 직접 연결하는 FastAPI는 검증된 사용자 ID를 쿼리 조건에 넣는 애플리케이션 권한 검사를 함께 사용해야 한다.

배포 전 남은 외부 입력은 Web의 `NEXT_PUBLIC_SUPABASE_URL`과 `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`다. publishable key는 공개 사용 전제지만 secret/service-role key와 혼동하면 안 된다.

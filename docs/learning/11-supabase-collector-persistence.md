# Supabase collector 영속화

## 목표와 결과

고정 공인 IP PC의 collector가 국가법령정보 공동활용 Open API 현재 원문을 검증한 뒤 Supabase Storage와 PostgreSQL에 반영하고, Vercel API가 같은 데이터를 읽도록 연결했다.

2026-07-15 검증 기준으로 현재 허용 목록 9문서, 9버전, 3,050조문과 private Storage 객체 9개가 저장되었다. 같은 명령 재실행은 9개 모두 `unchanged`였다.

## 저장 순서

1. JSON 우선/XML 폴백 응답을 도메인 스키마와 SHA-256으로 검증한다.
2. `source_kind/source_id/MST-effective_from-SHA256.format` 경로로 private Storage에 원문을 저장한다.
3. `legal_documents`, `document_versions`, `provisions`를 한 DB 트랜잭션에서 upsert한다.
4. `ingestion_runs`에 원문이나 비밀 없이 ready·unchanged·failed 집계만 기록한다.

Storage 객체는 content-addressed 경로이며 `x-upsert=false`로 덮어쓰지 않는다. Supabase가 중복 객체와 없는 bucket을 HTTP 400 안의 논리 상태 409·404로 반환하므로 상태 코드와 구조화 오류를 함께 검증한다.

## 새 Secret API key

`sb_secret_...`는 JWT가 아닌 opaque API key다. Storage 요청에는 `apikey` 헤더로 보내며 `Authorization: Bearer`에 넣지 않는다. DB 연결은 별도의 PostgreSQL URL을 사용한다.

## API 검증

Production API의 corpus status가 9개 모두 ready를 반환했고, PGroonga 검색, 조문 ID 상세 조회, 검색 전용 질문의 10개 인용이 Supabase 데이터로 왕복했다. PowerShell 파이프에서 한국어가 손상될 수 있어 자동 검증은 UTF-8 JSON 또는 ASCII Unicode escape를 사용한다.

## 남은 경계

현재 Supabase 어댑터는 `sync-current`만 활성화한다. `sync-history`에는 출처 삭제 레코드를 검색에서 격리할 열, 체크포인트와 원자 승격 계약이 더 필요하다. 이 계약이 완성되기 전에는 명령을 실패시켜 현재 검증 코퍼스를 보존한다.

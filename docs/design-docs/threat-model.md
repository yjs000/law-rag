# 위협 모델

상태: 승인
최종 갱신: 2026-07-14

## 범위와 신뢰 경계

```text
Browser(untrusted input)
  -> Vercel Next.js(same-origin /api proxy, untrusted display data)
  -> Vercel FastAPI(validation/authz/rate limit)
       -> OpenAI(minimum retrieved evidence only)
       -> Supabase(user ownership/RLS and persistence boundary)

Law Open API(untrusted external document)
  -> fixed-public-IP Windows collector(exact allowlist/schema/hash)
  -> Supabase active corpus(trusted only after validation)
```

국가법령정보 Open API도 외부 입력이다. 공식 출처라는 이유로 구조와 문자열을 신뢰하지 않으며 정확 명칭, 문서 종류, MST, 시행일, 조문 구조와 원문 해시를 검증한 뒤에만 활성 코퍼스로 승격한다.

## 주요 위협과 통제

| 위협 | 공격 경로 | 현재 통제 | 출시 전 잔여 통제 |
|---|---|---|---|
| 프롬프트 주입 | 질문·법령 문자열이 모델 지시를 덮음 | 근거를 데이터로 구분, 구조화 출력, 인용 게이트, 실패 시 검색 전용 | 실제 모델 공격 평가셋 |
| 허위·무관 인용 | 모델이 존재하지 않거나 무관한 ID 생성 | 검색 후보 ID 허용 목록과 주장별 인용 검증 | 의미 일치 기준 운영 튜닝 |
| XSS | 질문·원문·모델 문자열을 HTML로 렌더링 | React 텍스트 렌더링, 원문 HTML 금지 | CSP와 브라우저 자동 검사 |
| SSRF | 변조된 원문 URL을 서버가 조회 | 수집 base URL 고정, HTML 우회 금지, 원문 URL allowlist | 배포 egress 정책 |
| 인증·소유권 우회 | 다른 사용자의 이력 ID 열거 | 서버측 사용자 ID 검사, 실패 시 동일한 404 | 실제 Supabase RLS |
| 비밀·개인정보 로그 노출 | 질문·OC·API 키·원문 전문 기록 | OC URL 치환, 질문/원문 없는 관측 이벤트 계약 | 중앙 로그 마스킹 검사 |
| 오래된·부분 코퍼스 | 수집 일부 실패가 최신으로 표시 | 문서별 원자 승격, 마지막 성공·누락 경고 | 최신성 알림과 운영 호출 |
| 과도한 사용 | 익명 API 반복 호출 | 일별 HMAC rate limit | 분산 저장소와 프록시 제한 |
| Preview 경계 혼동 | 가변 Preview origin이 운영 API·데이터에 접근 | 목업은 외부 연결 없음 | Next.js 동일 출처 프록시, 환경별 자원·비밀 분리, wildcard CORS 금지 |
| collector 공개 노출 | 집 PC의 포트포워딩·터널을 통한 침입 | collector는 CLI 전용 | 인바운드 포트 금지, Open API·Supabase outbound만 허용 |

## 개인정보 흐름

- 익명 질문은 처리 후 저장하지 않는다.
- 로그인 질문은 내부 사용자 ID에만 연결하고 1년 뒤 삭제한다.
- 계정 삭제는 질문, 세션, 내보내기 및 파생 사용자 데이터를 함께 제거한다.
- 관측 이벤트에는 질문, 이메일, IP 원문, 법령 원문 전문을 포함하지 않는다.
- 실제 Supabase 전환 시 Google 공급자 ID와 내부 사용자 ID를 분리하고 RLS 및 백업 삭제 수명주기를 별도로 검증한다.

## 검증과 승인 조건

- 프롬프트 주입, 무관 인용, XSS, SSRF, 과도 입력, 인증 우회 회귀 테스트 통과
- 비밀 패턴과 질문 원문이 로그·Git 산출물에 없음을 검사
- 실제 Google OAuth·Supabase 연결 시 데이터 흐름과 삭제 전파를 다시 검토
- 공개 배포 전에 CSP, TLS, 프록시 요청 제한, 백업 복구 훈련을 완료

## 결정 기록

- 2026-07-14: 목업 단계의 위협 경계를 코드 회귀 테스트와 연결한다. 실제 외부 서비스 통제는 자격정보가 준비된 후 별도 출시 게이트로 유지한다.
- 2026-07-14: 운영 경계를 Vercel Web/FastAPI, Supabase 영속 계층, 고정 공인 IP Windows collector로 분리한다. Preview는 Next.js 동일 출처 프록시를 사용하고 collector는 공개 인바운드를 받지 않는다.

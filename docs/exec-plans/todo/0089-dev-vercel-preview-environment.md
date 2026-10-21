> 작업 ID: `O-002`
> 상태: `Todo`
> 우선순위: `P1`
> 유형: `Operations`
> 보조 라벨: `Reliability`, `UX`
> 선행 조건: B-017 로컬 출력 기준 확정 후 별도 dev 배포의 필요성과 외부 쓰기 범위를 확인한다.
> 다음 행동: 기존 웹·API Vercel 프로젝트의 Preview 브랜치 설정과 dev 전용 API·인증·데이터 연결을 설계한다.
> 참고 범위:
> - `apps/web/lib/api-client.ts` L19-L19 — 브라우저가 사용할 API URL
> - `apps/api/app/settings.py` L68-L77 — API의 허용 웹 origin 설정
> - `docs/design-docs/vercel-supabase-deployment.md` L1-L80 — 기존 Vercel·Supabase 배포 경계

# dev 브랜치 Vercel Preview 환경

## 목적과 완료 조건

운영 `main`을 유지하면서 `dev`의 실제 웹·API를 같은 버전으로 비교할 수 있는 Preview 환경을 준비한다. 브랜치를 만드는 것만으로 운영과 분리된 인증·데이터·URL이 생기지는 않는다.

- 웹과 API가 모두 `dev`의 같은 commit을 배포하고, 웹의 API URL은 dev API를 가리킨다.
- API CORS origin, Supabase OAuth redirect, 필요한 환경변수 scope를 dev URL에 맞춘다. 운영 DB를 테스트·초기화 대상으로 사용하지 않는다.
- 질문·로그인·인용 확인 smoke를 통과하고 배포 commit과 URL을 기록한다.

## 실행 순서

1. **경계 설계** — 결과: 기존 Vercel 웹·API 프로젝트와 Preview branch 설정, 비밀값·DB 분리 방안. 대상: 이 계획 결과 기록 약 20~35줄, 필요 시 `docs/design-docs/vercel-supabase-deployment.md` L1-L80 약 10~25줄. 절차: 현재 프로젝트 설정과 환경변수의 이름·scope만 읽어 운영과 dev 연결을 표로 대조한다. 완료 증거: 운영 자원 사용 여부와 외부 쓰기 대상이 명시됨. 의존성: B-017 기준 확정.
2. **Preview 구성** — 결과: `dev` 브랜치의 웹·API Preview 배포. 대상: Vercel 프로젝트 Preview 환경, Supabase redirect 설정, 필요 시 설정 문서 약 10~25줄. 절차: 사용자 승인을 받은 뒤 정확한 브랜치 push와 외부 설정 변경을 실행한다. 완료 증거: 양쪽 배포가 동일 commit이고 운영 도메인이 변경되지 않음. 의존성: 1의 경계 설계와 외부 쓰기 승인.
3. **종단 확인** — 결과: 로그인·질문·인용 smoke 기록. 대상: 이 계획 결과 기록 약 15~25줄. 절차: dev 웹에서 dev API 요청, 세션 유지, 근거 링크를 확인하고 운영 배포 상태도 재확인한다. 완료 증거: dev와 운영 URL·commit·테스트 결과가 구분되어 기록됨. 의존성: 2의 배포.

## 비용 판단

기존 Vercel 프로젝트의 Preview 브랜치를 우선 사용한다. 별도 프로젝트나 유료 Custom Environment는 실제 분리 요구가 확인될 때만 검토한다.

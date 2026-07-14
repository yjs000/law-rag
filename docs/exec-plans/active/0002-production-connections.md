# 실행 계획 0002: 실제 서비스 연결

상태: 사용자 자격정보 준비 대기
작성일: 2026-07-14
소유자: 미지정

## 목적

목업 경계로 검증한 분산에너지 법령 RAG를 실제 Supabase, Google OAuth, OpenAI, 단일 고정 IP 클라우드 서버에 연결한다.

## 선행 입력

- `gpt-5.6-terra` 권한이 있는 OpenAI API 키
- Supabase 프로젝트 URL, DB 연결 문자열, service role과 Storage 설정
- Google OAuth client와 확정된 공개 redirect URL
- 고정 공인 출구 IP 클라우드 서버와 도메인

비밀값은 채팅·Git에 전달하지 않고 서버 또는 CI Secret에 직접 등록한다.

## 단계

### Supabase와 데이터 수명주기

- [ ] PostgreSQL·pgvector·PGroonga·Storage·Supavisor 연결
- [ ] 목업 manifest 235개 버전을 트랜잭션과 불변 원문 객체로 이관
- [ ] 질문 이력 1년 자동 삭제와 계정 삭제의 DB·Storage·백업 전파 검증
- [ ] `runtime_flags`, 수집 실행, 평가 실행 상태 영속화

### Google OAuth와 사용자 경계

- [ ] Google 공급자만 노출하고 ID 토큰·redirect·세션 회전 검증
- [ ] 내부 사용자 ID 분리와 질문 이력 RLS·교차 사용자 접근 차단
- [ ] 개인정보 처리방침, 국외 이전, 보유·삭제 정책 검토

### OpenAI와 품질 게이트

- [ ] 실제 Terra 구조화 출력에 결정적 인용 게이트 적용
- [ ] quota·권한·모델 오류의 검색 전용 폴백과 영속 상태 검증
- [ ] 사람 검토 평가셋으로 의미 게이트 오탐·미탐 측정

### 단일 서버 배포와 운영

- [ ] Web/API/collector 독립 프로세스, TLS, CORS, CSP, 프록시 요청 제한 구성
- [ ] 새 고정 공인 IP를 법제처에 등록하고 주 1회 collector 작업 검증
- [ ] 중앙 로그·메트릭·알림, 백업·복구, 롤백, 삭제 전파 훈련
- [ ] 공개 URL에서 질문→답변/검색 전용→인용 원문→이력→내보내기 종단 검증

## 롤백

- AI 장애는 `AI_MODE=off` 검색 전용으로 전환한다.
- 새 코퍼스는 검증 완료 후 원자 승격하며 직전 색인 버전을 보존한다.
- 인증·DB 전환 실패 시 공개 쓰기 경로를 닫고 목업 인증을 production에서 활성화하지 않는다.

## 차단 요소

현재 코드는 외부 자격정보 없이 계속 테스트할 수 있지만, 위 단계의 실제 연결과 공개 배포는 선행 입력이 준비될 때 시작한다.

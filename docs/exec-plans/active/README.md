# 활성 실행 계획

현재 진행 중인 복잡한 작업의 실행 계획을 둔다. 각 계획에는 완료 조건, 체크리스트, 결정 로그, 진행 기록, 차단 요소를 포함한다.

- [0002: 실제 서비스 연결](0002-production-connections.md) — 운영 영속화·개인정보 수명주기·종단 검증
- [0008: 4단계 검색 지연과 디버깅](0008-four-stage-retrieval-latency-and-debugging.md) — Production EXPLAIN·region/pool·재측정 대기
- [0012: 분산 질문 취소](0012-distributed-question-cancellation.md) — 설계 현행화와 DB/API/Web 운영 구현 대기
- [0015: 질문 이력 보존 정리 작업](0015-history-retention-job.md) — 로컬 함수 계약 완료, Production scheduler 승인 대기
- [0022: 검색 인덱스 재설계와 실험 D 평가](0022-retrieval-index-and-experiment-d-1000.md) — 검색 인프라·D-10 완료, D-full Gold는 [예정 작업 0029](../todo/0029-d-full-gold-on-demand.md)로 보류
- [0025: 승인 질문에서 근거 기반 AI 답변까지](0025-approved-questions-to-grounded-answer-roadmap.md) — M0~M4 완료(승자 R1+A), M4.5는 [0028](0028-pre-retrieval-question-routing.md)에서 진행 중
- [0028: 검색 전 질문 라우팅과 조건부 query 보강](0028-pre-retrieval-question-routing.md) — 착수 2026-08-07, route schema(1단계) 전, 입력은 질문 text+법령 corpus만
- [0034: 웹 프런트 탭 포커스 시 불필요한 인증·이력 재조회 억제](0034-web-auth-rehydration-throttle.md) — 착수 2026-08-08, `apps/web/app/page.tsx` 구현 완료(`shouldHydrateNow`/`nextAuthUser` 추출) 및 테스트 통과, 완료 조건의 실제 브라우저 재현 검증만 남음

Discord thread `1528216345924337805`에서 시작한 작업의 착수 순서와 단일 `Picked Up` 상태는 [Discord 작업 보드](../../ROADMAP.md)에서 관리한다. 다른 환경에는 해당 보드를 적용하지 않는다.

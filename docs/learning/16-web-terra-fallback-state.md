# 16. Web Terra 폴백 상태 동기화

## 배운 문제

사용자가 화면에서 Terra를 선택했더라도 API는 키 비활성화, 쿼터·결제 오류, 생성 실패 또는 근거 검증 실패 때문에 안전하게 검색 전용 응답을 반환할 수 있다. Web이 요청 당시 선택만 유지하면 화면은 Terra인데 모든 실제 응답은 검색 전용인 모순이 생긴다.

## 구현 선택

초기 기본값은 Terra로 유지한다. 코퍼스 상태의 `ai_available=false`는 Terra 옵션을 `현재 사용 불가`로 비활성화하고 검색 전용으로 전환하는 신호다. 질문 응답에서는 `mode`를 실제 동작의 권위 값으로 삼고, `requested_answer_mode=terra`와 `fallback_reason`이 있는 검색 전용 응답을 폴백으로 처리한다.

모든 자동 전환은 `role=status`와 `aria-live=polite`인 배너에서 `Terra 한도 초과로 검색 전용으로 전환합니다.`라고 알린다. 새 계약 필드가 없는 배포가 섞일 수 있으므로, 요청이 Terra였는데 응답 `mode`가 검색 전용인 경우도 같은 폴백으로 해석한다. 사용자가 처음부터 검색 전용을 요청한 경우에는 폴백 알림을 띄우지 않는다.

## 데이터 흐름

```text
corpus.ai_available=false -> 전환 알림 -> Terra 비활성화 -> search_only 선택
Terra 요청 -> API mode=search_only + fallback_reason -> 전환 알림 -> search_only 선택
Terra 요청 -> 구버전 API mode=search_only -> 요청/응답 차이 감지 -> 동일 전환
```

## 검증

```powershell
pnpm.cmd --filter @law-rag/web test
pnpm.cmd --filter @law-rag/web typecheck
pnpm.cmd --filter @law-rag/web lint
```

순수 helper 테스트로 AI 사용 가능 초기 상태, 사용 불가 초기 상태, Terra 폴백, 명시적 검색 전용, 구버전 응답을 검증한다.

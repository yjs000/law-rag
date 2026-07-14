# 04 웹 인증 상태, 질문 이력과 내보내기

## 개념과 선택 이유

현재 인증은 Google 로그인을 모사하는 목업 세션이다. 브라우저는 목업 access token만 보관하고, 로그인한 요청에만 `Authorization` 헤더를 붙인다. 익명 질문은 서버에 저장되지 않으며 첫 성공 응답 뒤 로그인 안내를 세션당 한 번만 표시한다. `sessionStorage`는 브라우저 탭 세션이 끝나면 사라지므로 이 용도에 맞고, 로그인 세션을 보관하는 `localStorage`와 목적을 분리할 수 있다.

질문 이력과 PDF 출력은 소유권을 확인해야 하므로 API를 통해 처리한다. Markdown과 CSV는 이미 검증된 체크리스트 DTO를 브라우저에서 표현 형식만 바꾼다. 서로 다른 내보내기 형식이 같은 DTO를 사용하면 내용과 인용이 어긋나는 것을 막을 수 있다.

답변과 원문을 좌우 패널로 고정하면 주장과 근거를 오가며 읽기 쉽다. 인용 버튼은 선택 상태를 `aria-pressed`로 알리고 같은 ID의 원문에 키보드 포커스를 옮긴다. 문서 종류 필터는 API가 제공하는 `source_kind`를 우선 사용하고, 구형 목업 응답에는 법령명 분류를 적용한다. 필터는 근거 패널만 좁히며 답변 자체를 숨기지 않는다.

외부 법령 원문과 모델 문자열은 `dangerouslySetInnerHTML` 없이 React 텍스트 노드로만 렌더링한다. 회귀 테스트는 HTML 공격 문자열이 태그가 아니라 이스케이프된 텍스트가 되는지 확인한다. 로그인 안내 대화상자의 키보드 계산은 순수 함수로 분리해 초기 포커스, Tab 순환, Shift+Tab, ESC, 원래 컨트롤로의 포커스 복귀를 DOM 환경 없이 검증한다.

## 데이터 흐름

익명 질문 → 답변 성공 → 세션 최초 여부 확인 → 로그인 안내 → 닫기 또는 Google 목업 로그인.

로그인 질문 → bearer token과 질문 전송 → 서버가 질문·답변 저장 → 이력 목록 갱신 → 상세 열기·삭제·PDF 출력. 로그인 전 익명 질문은 로그인 후에도 소급 저장하지 않는다.

인용 버튼 → 응답의 인용 ID → 동일 ID를 가진 원문 카드로 포커스와 스크롤 이동.

코퍼스 상태 → 마지막 동기화 시각·경고·문서별 `missing/failed` 상태 → 질문 패널의 최신성 경고. 기준일은 질문 검색 조건이 되고, 문서 종류는 반환된 원문을 법률·시행령·시행규칙·행정규칙으로 좁힌다.

## 직접 실행

```powershell
pnpm.cmd --filter @law-rag/web lint
pnpm.cmd --filter @law-rag/web typecheck
pnpm.cmd --filter @law-rag/web test
pnpm.cmd --filter @law-rag/web build
```

## 다음 학습 주제

실제 Google OAuth의 Authorization Code + PKCE 흐름, HttpOnly 세션 쿠키, 1년 만료 작업과 계정 삭제 전파, Playwright 기반 스크린리더 의미·색상 대비·실제 브라우저 포커스 검사를 학습한다.

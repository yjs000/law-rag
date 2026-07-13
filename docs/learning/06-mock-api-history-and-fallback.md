# 06. 목업 인증, 질문 이력, 검색 전용 폴백

## 개념

API는 실제 Supabase 연결 전에도 제품 흐름을 검증할 수 있도록 메모리 기반 Google 목업 사용자·세션·질문 이력을 제공한다. 익명 질문은 저장하지 않고, 인증된 질문만 사용자 ID에 귀속한다. 질문은 생성일로부터 1년 뒤 만료되며 계정 삭제 시 세션, 질문, 내보내기 메타데이터를 함께 지운다.

답변 생성기는 `gpt-5.6-terra` 하나만 허용한다. AI 비활성화, 권한, quota, 모델 및 호출 오류가 발생하면 다른 모델을 호출하지 않고 검색 원문과 인용을 유지한 검색 전용 응답으로 전환한다.

## 왜 선택했는가

- 인증·보존·삭제 정책을 외부 서비스 비용 없이 먼저 테스트한다.
- 익명 입력을 저장하지 않는 계약을 저장소 경계에서 강제한다.
- 생성 장애가 법령 원문 검색 장애로 전파되지 않게 한다.
- Markdown, CSV, 단순 PDF가 하나의 canonical 체크리스트를 렌더링하게 해 형식별 내용 불일치를 줄인다.

## 데이터 흐름

```text
Bearer mock session -> question -> temporal search -> citations
                              |                  |
                              |                  +-> Terra failure -> search_only
                              v
                   authenticated history only
                              |
               Markdown / CSV / simple PDF export
```

운영 모드에서는 목업 로그인 라우트를 열지 않는다. 실제 서비스 전환 시 같은 애플리케이션 포트 뒤에 Supabase Google OAuth와 PostgreSQL 저장소를 연결한다.

## 직접 실행할 명령

```powershell
uv sync --project apps/api
uv run --project apps/api pytest
uv run --project apps/api ruff check .
uv run --project apps/api uvicorn app.main:app --reload
```

## 다음 학습 주제

- Google OAuth의 ID 토큰 검증과 서버 세션 회전
- PostgreSQL row-level security와 소유권 검사
- 개인정보 삭제의 백업·Storage 수명주기 전파
- 주장과 인용 원문의 의미 일치 자동 평가

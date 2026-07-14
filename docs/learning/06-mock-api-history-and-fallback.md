# 06. 목업 인증, 질문 이력, 검색 전용 폴백

## 개념

API는 실제 Supabase 연결 전에도 제품 흐름을 검증할 수 있도록 메모리 기반 Google 목업 사용자·세션·질문 이력을 제공한다. 익명 질문은 저장하지 않고, 인증된 질문만 사용자 ID에 귀속한다. 질문은 생성일로부터 1년 뒤 만료되며 계정 삭제 시 세션, 질문, 내보내기 메타데이터를 함께 지운다.

답변 생성기는 `gpt-5.6-terra` 하나만 허용한다. AI 비활성화, 권한, quota, 모델 및 호출 오류가 발생하면 다른 모델을 호출하지 않고 검색 원문과 인용을 유지한 검색 전용 응답으로 전환한다.

생성 답변은 모델 호출과 별개의 결정적 인용 게이트를 통과해야 한다. 각 주장·설명·체크리스트가 가리키는 인용 ID가 실제 검색 결과에 존재하고, 일반적인 표현을 제외한 핵심 용어의 절반 이상이 해당 원문에 있어야 한다. 허가·신고·등록·금지·벌칙 같은 규범 용어와 숫자는 원문에 직접 존재해야 한다. 이 규칙은 의미를 완벽히 이해하는 판정기가 아니라 과도한 주장을 설명 가능하게 차단하는 보수적 하한선이다.

## 왜 선택했는가

- 인증·보존·삭제 정책을 외부 서비스 비용 없이 먼저 테스트한다.
- 익명 입력을 저장하지 않는 계약을 저장소 경계에서 강제한다.
- 생성 장애가 법령 원문 검색 장애로 전파되지 않게 한다.
- Markdown, CSV, 단순 PDF가 하나의 canonical 체크리스트를 렌더링하게 해 형식별 내용 불일치를 줄인다.
- 모델을 검증자로 다시 호출하지 않아 같은 입력의 합격·실패가 항상 동일하고 장애 비용이 늘지 않는다.
- 원문 링크는 `https` 국가법령정보 호스트만 허용해 악성 링크와 SSRF 후보가 응답 경계 밖으로 나가지 못하게 한다.
- 관측 이벤트 타입이 요청 ID·모드·결과만 받게 해 질문과 원문 전문을 실수로 로그에 추가하기 어렵게 한다.

## 데이터 흐름

```text
Bearer mock session -> question -> temporal search -> citations
                              |                  |
                              |                  +-> Terra failure -> search_only
                              v
                   authenticated history only
                              |
               Markdown / CSV / simple PDF export

claim + citation IDs -> existing citation -> core-term/normative/number gate
                                            |
                                      failure -> search_only
```

운영 모드에서는 목업 로그인 라우트를 열지 않는다. 실제 서비스 전환 시 같은 애플리케이션 포트 뒤에 Supabase Google OAuth와 PostgreSQL 저장소를 연결한다.

검색 평가기는 Recall@10뿐 아니라 표시된 인용 ID 존재율과 인용문-검색 원문 완전 일치율을 계산한다. 두 인용 지표는 100%가 아니면 비정상 종료한다. 의미 게이트의 핵심 용어 절반 기준은 고정 평가셋 오탐·미탐을 관찰하며 버전이 있는 규칙으로 조정해야 하며, 조용히 완화해서는 안 된다.

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
- 한국어 형태소 분석을 이용한 결정적 핵심 용어 규칙의 정밀도 개선
- 주장-인용 의미 평가셋과 사람 검토 기준 수립

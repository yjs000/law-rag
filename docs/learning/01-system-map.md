# 1. 시스템 지도와 실행 경계

## 한 문장 지도

law-rag는 브라우저가 직접 법령이나 AI 제공자를 호출하지 않고, Web과 API를 거쳐 검증된 법령
코퍼스에서 근거를 찾도록 만든 모노레포다. 수집은 국가법령정보 공동활용 Open API에 등록된 고정 공인
IP의 Windows PC에서 별도 collector가 맡는다.

```text
고정 공인 IP Windows PC
  └─ collector ── 국가법령정보 Open API
          └─ 검증된 원문·조문 ── Supabase Storage + PostgreSQL
                                      ↑
브라우저 ── Next.js Web ── FastAPI ──┼─ 검색
                                      └─ NVIDIA hosted NIM 생성·임베딩
```

이 배치는 세 가지 실패를 분리한다.

1. 사용자의 웹 요청이 끊겨도 장시간 수집 계약이 바뀌지 않는다.
2. AI가 실패해도 검증된 원문 검색은 계속할 수 있다.
3. 수집 PC는 공개 인바운드 서버가 아니며, Web과 API는 법제처 등록 IP 제약을 떠안지 않는다.

## 모노레포지만 실행 단위는 다르다

모노레포는 코드를 한 Git 저장소에서 함께 검토한다는 뜻이지, 모든 프로그램을 한 프로세스로 띄운다는
뜻이 아니다.

| 위치 | 역할 | 운영 실행 위치 |
|---|---|---|
| `apps/web` | 채팅, 근거 보기, 로그인·이력 UI, 동일 출처 API 프록시 | Vercel Next.js |
| `apps/api` | 인증, 질문 검증, 검색, 답변·인용 조립, 내보내기 | Vercel FastAPI Function |
| `apps/collector` | 허용 법령 수집, 검증, 원문·DB 동기화 | 고정 공인 IP Windows PC |
| `packages/law-rag-core` | 법령 DTO, 파서, 순수 도메인 규칙 | 위 Python 앱이 공유 |

의존성은 `domain → application → ports ← adapters → delivery` 방향을 지킨다. 도메인은 “조문 버전이
유효한가”, “파서 결과 ID가 맞는가” 같은 규칙을 알고, FastAPI·SQLAlchemy·NVIDIA SDK는 모른다.
외부 SDK를 adapter 뒤에 두면 공급자를 바꾸더라도 법령과 인용 규칙을 다시 쓰지 않아도 된다.

브라우저에도 secret을 두지 않는다. Supabase service-role key, NVIDIA key, 국가법령정보 API OC는 서버나
수집 PC의 비밀 저장소에만 둔다. Preview Web은 상대 `/api/*`를 사용해 FastAPI로 프록시하므로 가변
Preview origin을 넓은 CORS 허용 목록으로 풀지 않는다.

## 런타임과 재현성

현재 기준 런타임은 Node.js 24, pnpm 11, Python 3.14와 uv다. 정확한 patch 버전은 프로젝트 설정과
lockfile이 권위다. lockfile은 같은 의존성 그래프를 재현하고, pnpm 설치 스크립트는 허용된 패키지만
실행한다. Python은 루트 uv workspace 아래 API·collector·공용 패키지를 연결한다.

DB 연결도 용도에 따라 나눈다.

- API의 짧은 요청은 Supavisor transaction pooler를 사용하고 prepared statement cache를 끈다.
- migration과 session advisory lock이 필요한 collector 작업은 session-mode 직접 연결을 사용한다.
- 같은 URL을 아무 곳에나 쓰면 session lock을 잡은 연결과 해제할 연결이 달라질 수 있다.

## 사용자 질문 한 건의 큰 흐름

```text
1. Web이 질문, 기준일, 답변 모드를 API에 보낸다.
2. API가 입력·인증·코퍼스 준비 상태와 지원 날짜를 검증한다.
3. 조문 직접 조회 또는 자연어 검색으로 근거 후보를 만든다.
4. 검색 전용이면 근거를 그대로 조립한다.
5. AI 모드이면 검증된 근거만 생성 provider에 보낸다.
6. 서버가 구조화 출력과 인용 ID를 다시 검증한다.
7. 실패하면 근거를 버리지 않고 검색 전용 응답으로 낮춘다.
8. Web은 답변의 인용을 같은 원문 카드와 연결한다.
```

핵심은 생성 모델이 법령 저장소나 사용자 권한을 직접 다루지 않는다는 점이다. API가 검색 근거를
선택하고, 모델은 그 범위 안에서 초안을 만들며, API가 다시 검증한 결과만 사용자에게 보낸다.

## 어디가 권위 문서인가

학습 코스는 이유를 빠르게 이해하는 문서다. 변경 전에 다음 권위를 확인한다.

- 배포·모듈·데이터 흐름: [아키텍처](../../ARCHITECTURE.md)
- 기술 선택과 대체 이력: [기술 스택 ADR](../design-docs/technology-stack.md)
- 사용자에게 보이는 계약: [에너지 사업 법령 채팅](../product-specs/grounded-legal-qa.md)
- 보안 불변조건: [보안](../SECURITY.md), [위협 모델](../design-docs/threat-model.md)

## 직접 확인

저장소 루트에서 대표 검증을 실행한다.

```powershell
pnpm.cmd verify
```

개별 개발 서버와 세부 검증 명령은 루트 `package.json`, 각 앱의 `pyproject.toml`과 README를 우선한다.
문서에 고정된 과거 테스트 개수는 현재 성공을 증명하지 않으므로 외우지 않는다.

## 핵심 확인

1. collector를 Vercel API 안에서 실행하지 않는 이유는 무엇인가?
2. 도메인 계층이 외부 SDK를 직접 import하지 않는 이유는 무엇인가?
3. AI 생성이 실패해도 원문 검색을 살릴 수 있는 경계는 어디인가?

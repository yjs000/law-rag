# 5. 사용자·개인정보·장애 안전

## 안전은 답변 뒤가 아니라 요청 전체에 있다

법률 답변의 안전은 인용만 검사한다고 끝나지 않는다. 로그인 복원, 익명 질문 저장 여부, rate limit,
코퍼스 갱신, AI 장애, 브라우저 취소와 늦은 응답도 사용자가 실제로 겪는 계약이다.

```text
사용자 상태 확인
→ 입력·quota·코퍼스 상태
→ 검색·선택적 생성
→ 결과 상태를 명시
→ 인증된 이력만 저장
→ 보존기간 만료·계정 삭제
```

각 단계는 실패 원인을 숨기지 않되 질문·원문·secret을 로그에 남기지 않아야 한다.

## 인증은 Google, 세션은 Supabase, 권한은 API

Google은 신원 제공자이고 Supabase Auth가 Authorization Code + PKCE 교환과 세션을 담당한다. Next.js는
`@supabase/ssr` cookie 세션을 유지하고 FastAPI 호출 때 access token을 Bearer로 보낸다. Google client
secret, Supabase secret/service-role key는 브라우저에 보내지 않는다.

FastAPI는 Supabase Auth로 토큰과 현재 사용자를 검증한 뒤 공급자 ID와 별도의 내부 사용자 UUID를
사용한다. 신규 내부 프로필은 현재 약관·개인정보 버전 동의가 함께 있을 때만 만든다. 질문 이력의
조회·상세·삭제에는 언제나 내부 사용자 ID 소유권 조건을 넣는다.

RLS는 Supabase Data API 경로의 방어선이다. pooler로 PostgreSQL에 직접 연결하는 FastAPI 요청에서는
RLS만 기대하지 않고 애플리케이션 쿼리에도 검증된 사용자 ID 조건을 넣는다. 다른 사용자의 이력은
존재 여부도 드러내지 않도록 404로 처리한다.

Web은 초기 인증 상태를 `checking`으로 둔다. 세션 복원이 끝나기 전에 로그인 버튼을 보여 주면 이미
로그인한 사용자가 로그아웃된 것처럼 보인다. 로그아웃 때는 사용자와 이력뿐 아니라 화면 메모리의 현재
질문·답변·인용도 지운다. 인증 epoch 이전에 시작한 늦은 요청 결과를 버려 로그아웃 뒤 이력이 다시
나타나는 경쟁 조건을 막는다.

OAuth callback의 `next`도 로컬 경로처럼 보인다고 그대로 믿지 않는다. `//external.example`과 역슬래시
변형을 차단하고 요청 origin 또는 검증된 HTTPS Site URL만 사용한다.

## 익명 질문과 대화 이력

익명 질문은 응답을 만들 수 있지만 서버 이력에 저장하지 않는다. 나중에 로그인해도 과거 익명 질문을
소급 저장하지 않는다. 첫 익명 응답 뒤 로그인 안내는 탭 세션당 한 번만, 대화를 막지 않는 방식으로
표시한다.

로그인 질문은 `conversations`와 순서 있는 `question_history` turn으로 저장한다. 목록은 응답 원문 전체가
아니라 20개 대화 요약을 keyset cursor로 읽고, 대화를 열 때 최신 20개 turn을 가져온다. 과거 turn은
추가 페이지로 읽는다. 이 구조는 로그인 직후 모든 인용 원문을 내려받는 비용과 개인정보 노출 범위를
줄인다.

메시지 개수는 모델 context 비용이 아니다. 짧은 메시지 여러 개보다 긴 법령 원문 하나가 더 클 수 있다.
현재는 완료된 최근 대화와 새 질문의 보수적 토큰 추정이 24,576 입력 예산을 넘기 전에 새 대화로
전환한다. 이전 답변은 대화 맥락일 뿐 법률 근거가 아니며, 매 질문의 실질 주장은 현재 검색 결과로 다시
검증한다. 중단·오류 응답은 다음 context에 넣지 않는다.

## 보존과 삭제는 실제 DB 작업이다

질문은 생성 시 `expires_at = 생성 시각 + 1년`을 갖는다. 조회에서 만료 행을 숨기는 것만으로 보존 정책이
완성되지는 않는다. 주기적인 PostgreSQL retention 함수가 export, 만료 질문, 대화 집계를 한 transaction
안에서 정리하고 결과를 감사 행에 남긴다.

- 실제 삭제 수는 `DELETE ... RETURNING`으로 센다.
- 같은 cutoff 재실행은 삭제 0건의 성공이 되는 멱등 작업이다.
- advisory transaction lock으로 정리 작업을 직렬화한다.
- 실패 감사에는 SQLSTATE만 남기고 SQL 오류 전문·사용자·질문 식별자를 남기지 않는다.
- `SECURITY DEFINER` 함수는 search path와 객체 schema를 고정하고 service role만 실행한다.

계정 삭제는 프로필, 질문·대화, 세션, export, 동의 등 사용자와 연결된 데이터를 제거한다. DB 백업과
Storage의 수명주기는 별도 운영 계약이므로 “현재 행 삭제”만으로 모든 복제본이 즉시 사라진다고
과장하지 않는다.

## rate limit은 신뢰 경계다

Production Vercel Function의 socket peer는 프록시 주소일 수 있다. Vercel이 덮어쓰는 단일
`x-forwarded-for` 공개 IP를 정규화하고 날짜별 HMAC 주체로 바꿔 quota를 센다. IP 원문은 DB나 로그에
저장하지 않는다.

개발·테스트에서는 전달 헤더를 신뢰하지 않고 socket peer를 사용한다. Production에서 헤더가 없거나
복수 체인·잘못된 IP면 공격자가 골라 바꿀 수 있는 일부 값을 쓰지 않고 하나의 fail-closed 주체로
묶는다. AI와 검색 전용 quota는 별도 카운터다.

IP rate limit은 완전한 사용자 식별이 아니다. VPN·이동통신 변경으로 우회할 수 있고 공유 NAT에서는
여러 사용자가 같은 한도를 쓸 수 있다. 비용 상한, 로그인 사용자 quota, WAF와 이상 사용 관측을 함께
검토해야 한다.

## AI provider와 폴백

생성 provider와 임베딩 provider는 별도 포트다. 현재 생성 후보는 NVIDIA hosted Nemotron 계열이고 API의
기존 `terra` wire 값은 호환을 위해 남아 있다. provider 규모나 모델 설명이 이 서비스의 법률 정확도를
증명하지 않으므로 실제 평가와 운영 설정이 가용 여부의 권위다.

생성은 검색 근거를 받은 뒤에만 실행한다. guided/structured generation을 사용해도 Pydantic schema와
인용 gate를 서버에서 다시 검사한다. 다음 상태는 다른 모델로 자동 전환하지 않고 검색 전용 응답으로
낮춘다.

- AI가 설정상 비활성
- 인증·권한·timeout·provider 오류
- 402/429 quota·결제 오류
- 빈 응답·JSON/schema 불일치
- 근거 없음 또는 인용 gate 실패

응답은 사용자가 요청한 모드와 실제 `mode`, 안전한 `fallback_reason`을 함께 보낸다. Web은 실제 응답
모드를 권위로 선택 상태를 갱신하고 접근 가능한 live status로 전환을 알린다. 오류 전문, key, 계정
상태는 공개하지 않는다.

`ai_available=true`는 무과금 잔액 조회 결과가 아니라 현재 설정상 준비 상태다. 서버리스 인스턴스가
최초 402/429를 본 뒤 그 인스턴스에서 차단할 수는 있지만, 영속 runtime flag 없이 모든 인스턴스가 즉시
같은 상태가 된다고 보장하지 않는다.

## 결과 없음·장애·갱신 중을 나눈다

사용자에게 모두 “답변이 없습니다”로 보이면 다음 행동을 고를 수 없다.

| 상태 | 뜻 | 사용자 행동 |
|---|---|---|
| `no_results` | 준비된 코퍼스에서 해당 경로·근거를 못 찾음 | 법령명·조문·사업 쟁점을 구체화 |
| `unsupported_corpus_date` | 수집된 검색 가능 코퍼스의 지원 범위 밖 기준일 | 상태 API에 표시된 범위 안 날짜 선택 |
| `corpus_unready` | 수집·벡터 검증 중이라 검색을 닫음 | 잠시 뒤 재시도, 상태 확인 |
| retrieval 5xx | 저장소나 검색 경로 장애 | 나중에 재시도 |
| AI fallback | 검색은 성공했지만 생성하지 못함 | 원문·검색 전용 결과 확인 |

빈 결과 화면에서는 로그인 유도보다 원인과 질문 수정 동작을 우선한다. 답변과 원문을 연결하는 인용
컨트롤은 키보드 포커스와 `aria-pressed` 상태를 제공한다. 외부 원문과 모델 문자열은
`dangerouslySetInnerHTML` 없이 텍스트로 렌더링한다.

Markdown·CSV·PDF export는 서로 다른 답을 만들지 않고 이미 검증된 하나의 checklist DTO를 각 형식으로
표현한다. PDF도 소유권을 확인하는 API 경계를 거친다.

## 중지 버튼이 보장하는 것

브라우저의 `AbortController`는 현재 연결을 끊고 늦은 응답을 화면에서 버릴 수 있다. 이것만으로 서버
계산, provider GPU 작업, quota와 저장이 확정적으로 취소되는 것은 아니다.

단일 프로세스에서는 request ID와 소유자에 연결한 `asyncio.Task.cancel()`로 await 지점에 취소를
전파할 수 있다. serverless scale-out에서는 취소 요청이 다른 인스턴스에 도착할 수 있으므로 프로세스
메모리 registry만으로는 부족하다. 공유 DB의 취소 상태와 작업 인스턴스의 watcher가 함께 있어야 하며,
provider가 별도 cancel API를 제공하지 않으면 이미 시작한 외부 계산·과금 회수도 보장할 수 없다.

현재 제품 계약은 “응답 대기를 중지하고 늦은 응답을 무시”하는 수준을 과장하지 않는다. 완전한 분산
취소는 [분산 질문 취소 설계](../design-docs/distributed-question-cancellation.md)의 별도 제안이다.

## 관측 가능성과 로그 최소화

문제를 재현하려면 입력 검증, 파싱, embedding, retrieval, generation, outcome을 나눠 상태·후보 수·시간을
기록한다. 그러나 다음은 로그나 관측 event에 넣지 않는다.

- 질문 원문과 법령 원문 전문
- access token, API key, DB URL과 provider 오류 전문
- IP 원문과 불필요한 사용자 식별자

request ID, 실행 모드, 안전한 오류 분류, 후보 수와 latency만으로 먼저 진단한다. 개인정보가 필요한
운영 분석은 승인된 읽기 경로와 최소 범위로 수행한다.

## 직접 확인

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

운영 OAuth, scheduler, quota와 외부 provider 동작은 로컬 합성 테스트가 대신 증명하지 않는다. 실제
운영 검증이 필요한 항목은 [신뢰성 목표](../RELIABILITY.md)와 관련 실행 계획에서 별도로 확인한다.

## 핵심 확인

1. 익명 질문을 로그인 뒤 소급 저장하지 않는 이유는 무엇인가?
2. `mode=search_only`만으로는 명시적 선택과 AI 실패 폴백을 왜 구분할 수 없는가?
3. 브라우저 중지 버튼이 provider 계산 취소를 보장한다고 말하면 안 되는 이유는 무엇인가?

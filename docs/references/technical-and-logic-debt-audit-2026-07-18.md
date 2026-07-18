# 기술·로직 부채 감사

기준 시점: 2026-07-18  
범위: Web, FastAPI, collector, 공용 schema, Supabase/PostgreSQL, 검색·생성·이력·취소 경계

## 즉시 반영한 개선

1. 운영 환경이 개발용 `RATE_LIMIT_SECRET`, 메모리 코퍼스 또는 빠진 Supabase 설정으로 조용히 시작하지 못하도록 startup validation을 추가했다.
2. 모델 입력용 이전 대화가 매 질문 이력에 중복 저장되지 않도록 저장 전 `conversation_context`를 제거했다.
3. 직접 API 호출이 Web 토큰 제한을 우회하지 못하도록 대화 컨텍스트 총 24,576자 보수 상한을 추가했다. 실제 모델 tokenizer 검사는 여전히 필요하다.
4. 이전 답변을 모델의 `assistant` 역할로 신뢰시키지 않고 “신뢰하지 않는 JSON 데이터”인 user payload로 전달하도록 경계를 강화했다.
5. 한글 수사·복수 항·조문 범위는 정확 경로 집합으로 조회하고 역방향·21개 이상 범위의 부분 결과/자연어 fallback을 막았다.
6. 분산 취소 상태 전이와 등록 전 tombstone을 memory coordinator 및 두 인스턴스 mock으로 검증했다.

## 열린 부채

| 우선순위 | 영역 | 확인한 구멍 | 영향 | 종료 조건 |
|---|---|---|---|---|
| P0 | 개인정보 | PostgreSQL `purge_expired()`는 구현돼 있지만 scheduler/cron 호출 경로가 없다 | 1년 만료 행이 조회에서는 숨겨져도 DB에 계속 남을 수 있음 | 인증된 정리 job, 실행 감사 메트릭, 실제 만료 삭제 통합 테스트 |
| P0 | 운영 검증 | 공개 URL에서 실제 로그인→검색/AI→인용→이력 종단 증거가 없다 | 목업 통과를 출시 안전으로 오인 | Production Preview 고정 평가셋과 장애 시나리오 통과 |
| P1 | 분산 취소 | 실행 태스크 레지스트리가 프로세스 로컬이며 공유 coordinator는 mock만 존재 | 다른 Vercel 인스턴스 취소가 현재 404 | Supabase migration, PostgreSQL coordinator, watcher, Web 확인 상태 종단 테스트 |
| P1 | 생성 공급자 | Answerer와 설정이 `gpt-5.6-terra`/OpenAI Responses에 고정 | Qwen3:4b endpoint를 설정해도 호출되지 않음 | provider-neutral adapter/factory, Ollama/NIM structured output smoke와 fallback 테스트 |
| P1 | 임베딩 색인 | 질의 임베딩 생성 코드는 있으나 전체 조문 임베딩을 채우는 운영 backfill/index job이 없다 | pgvector 후보가 비어 키워드 검색만 동작할 수 있음 | 버전 고정 backfill CLI, 진행 체크포인트, 모델·차원별 개수/Recall 검증 |
| P1 | 임베딩 일관성 | `hybrid_search`가 query의 embedding 모델·차원·색인 버전으로 행을 제한하지 않는다 | 다른 모델 벡터 혼합·중복·순위 왜곡 위험 | 함수 인자에 모델/차원/버전 추가, DB constraint와 migration 계약 테스트 |
| P1 | 모델 예산 | Web 추정과 문자 상한만 있고 실제 tokenizer 기준 system+근거+schema+출력 합산 게이트가 없다 | context 초과·비용/지연·근거 잘림 | server tokenizer 권위 계산, 근거 trimming, 24,575/24,576/24,577 및 장문 인용 테스트 |
| P1 | 모델 취소 | local task cancel은 되지만 upstream이 받은 계산 취소/환불은 provider별 미검증 | UI 중지 뒤에도 GPU 계산 지속 가능 | provider cancellation ID 지원 확인 또는 worker process 강제 종료 계약 |
| P1 | AI 상태 | quota-exhausted flag와 관측 누계가 프로세스 메모리 | 인스턴스마다 모드·메트릭 불일치 | `runtime_flags`와 중앙 metric backend, TTL/recovery 테스트 |
| P1 | 로컬 추론 | Vercel이 사용자 PC localhost에 직접 접근할 수 없고 queue worker가 없다 | 로컬 Qwen은 개발 PC에서만 사용 가능 | outbound inference queue, 인증 worker, TTL/동시성/검색전용 timeout 종단 테스트 |
| P1 | 외부 timeout | OpenAI client 생성에 명시적 timeout/max output 설정이 연결되지 않았다 | 긴 생성·리소스 고착 | provider별 connect/read/generation timeout, max output, retry 0/제한 정책 테스트 |
| P1 | 검색 품질 | 실제 PostgreSQL에서 신규 다중 경로·시행일 경계 실행 증거가 없다 | memory/SQL 문자열 테스트와 Production 차이 가능 | disposable PostgreSQL migration 통합 테스트와 EXPLAIN 기록 |
| P2 | 취소 UX | Web은 취소 API 오류를 삼키고 즉시 stopped로 표시한다 | DB/네트워크 실패인데 서버 중지 성공처럼 보일 수 있음 | `요청됨/확인 중/취소됨/실패` 상태와 503 재시도 UI |
| P2 | 법령명 인식 | 최대 단어 수 휴리스틱과 catalog alias에 의존한다 | 조사·특수 구두점·긴 비정상 명칭에서 오분류 | catalog trie/정규화 matcher와 property-based 변형 테스트 |
| P2 | 보존 운영 | collector 고아 raw object 정리 정책과 복구 시험이 없다 | 저장 비용 증가·삭제 정책 불명확 | 참조 추적 dry-run, 보존 승인, 복구 후 정리 시험 |
| P2 | 관측 | 단계 이벤트는 있으나 중앙 trace/cost/cancel latency가 없다 | 회귀·장애 위치와 비용 파악 지연 | request ID 기반 중앙 trace와 SLI 대시보드 |

## 사용자 병목

다음 항목은 코드가 사용자 결정을 대신하면 안 된다.

1. Supabase 운영 migration 및 retention cron 실행 승인
2. 로컬 모델 PC의 공개 인바운드 금지 유지 여부와 outbound queue 채택
3. 현재 GTX 1650을 유지할지 RTX 40/50·Windows 11 장비로 교체할지
4. OpenAI 임베딩 비용을 유지할지 로컬 임베딩으로 전환하고 전체 재색인할지
5. 로컬 worker가 질문·검색 근거를 처리하는 개인정보/가용성 운영 책임 수락

## 권장 순서

1. P0 만료 삭제 job과 Production 설정/종단 검증
2. Supabase 분산 취소 migration과 상태 UX
3. Qwen provider-neutral adapter 전에 outbound queue PoC와 실제 GTX 1650 성능 측정
4. 임베딩 backfill 및 모델 일관성 migration
5. 실제 tokenizer 예산·출력 제한·provider 취소를 포함한 Qwen 고정 평가

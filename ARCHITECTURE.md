# 분산에너지 법령 RAG 아키텍처

상태: `MVP 구현 중`
최종 갱신: 2026-07-13

## 목적

일반 사용자가 분산에너지 사업 규제를 질문하면 국가법령정보 공동활용 Open API 원문만으로 기준일에 유효한 의무·예외·인허가를 설명한다. 답변의 실질 주장은 조·항·호·목 인용으로 검증되며, 검증 실패나 AI 쿼터 소진 시 원문 검색만 제공한다.

## 배포와 데이터 흐름

```text
고정 출구 IP self-hosted Actions ── JSON 우선/XML 폴백 ──> 국가법령정보 Open API
       │                    │
       │                    └─ HTML·PDF·외부 법률 사이트 금지
       v
Supabase Storage(raw) ──> 정규화/해시/버전 ──> Supabase PostgreSQL
                                                  │ PGroonga + pgvector
                                                  v
Browser ──> Next.js 16/Vercel ──> FastAPI/Vercel ──> RRF 검색
                                      │                 │
                                      └─ OpenAI ports <─┘
                                         Responses + Structured Outputs
```

웹과 API는 같은 저장소에서 별도 Vercel 프로젝트로 배포한다. API는 Python 3.14 런타임, 웹은 Node 24/pnpm 11을 사용한다. DB 연결은 Supavisor transaction pooler를 전제로 prepared statement cache를 끈다.

## 모듈 경계

의존성은 `domain -> application -> ports <- adapters -> delivery` 방향이다.

- `domain`: 법령 버전, 조문, 공개 API 계약과 순수 검증 규칙
- `application`: 수집, 검색, 답변 조립, 인용 검증 유스케이스
- `ports`: 법령 저장소·임베딩·답변 모델·원문 저장소 계약
- `adapters`: 국가법령 API, Supabase/PostgreSQL/Storage, OpenAI 구현
- `delivery`: FastAPI 엔드포인트, GitHub Actions 수집, Next.js 워크벤치

도메인 계층은 FastAPI, SQLAlchemy, OpenAI SDK를 import하지 않는다. 브라우저는 OpenAI와 Supabase service role에 직접 접근하지 않는다.

## 수집 계약

MVP는 정확 명칭 허용 목록 9개만 수집한다. 법령은 `eflaw`, 행정규칙은 `admrul&nw=1`을 사용한다.

1. 같은 요청을 `type=JSON`으로 호출한다.
2. JSON 문법뿐 아니라 법령명, ID/MST, 조문 구조를 도메인 객체까지 정규화한다.
3. 지원되지 않는 형식 또는 스키마 검증 실패 때만 `type=XML`로 재호출한다.
4. timeout/5xx는 같은 포맷으로 지수 백오프 재시도한 뒤 실패시킨다. 일시 장애를 XML 폴백으로 감추지 않는다.
5. JSON/XML은 같은 `LegalDocumentRecord`가 되어야 하며 포맷, SHA-256, 파서 버전, 폴백 사유를 기록한다.
6. 원문은 Supabase Storage에 보존한다. HTML과 PDF로 우회하지 않는다.

## 저장과 검색

- `legal_documents`: 안정적인 출처 ID와 정확 명칭
- `document_versions`: MST, 공포/시행/종료일, 원문 포맷·해시·경로
- `provisions`: 조·항·호·목 경로와 원문
- `provision_embeddings`: 모델·차원·색인 버전별 512차원 벡터
- `legal_relationships`: 상하위법·위임·인용 관계
- `derived_obligations`: 행위자·조건·의무 유형과 검증 상태
- `ingestion_runs`, `evaluation_runs`, `runtime_flags`: 운영·평가 상태

검색은 기준일 유효 버전을 먼저 제한하고 PGroonga 한국어 전문 검색과 pgvector 의미 검색을 병렬 수행한다. 두 순위를 RRF로 결합한다. 임베딩 API를 사용할 수 없으면 PGroonga 검색만 유지한다.

## 답변 안전 게이트

1. 질문의 기준일과 사업 단계를 검증한다.
2. 하이브리드 검색으로 근거 후보를 구성한다.
3. Responses API Structured Outputs로 답변·체크리스트·인용 ID를 받는다.
4. 모든 실질 주장과 체크리스트에 존재하는 인용 ID가 있는지 검사한다.
5. 실패, quota 402/429, AI 비활성 시 검색 전용 응답으로 전환한다.

현재 인용 게이트는 인용 ID 존재와 원문 반환을 보장한다. 주장-원문 의미 일치 자동평가와 법령 관계 확장은 다음 품질 게이트다.

## 공개 API

- `POST /v1/questions`
- `POST /v1/search`
- `GET /v1/provisions/{id}`
- `GET /v1/documents/{id}/changes`
- `GET /v1/corpus/status`
- `GET /health`

연혁 본문 경로가 XML/JSON 계약 테스트를 통과하기 전 변경 API는 `supported=false`를 반환한다. HTML로 기능을 가장하지 않는다.

## 운영 원칙

- 키는 `.env`가 아닌 Vercel/GitHub Secrets에 둔다.
- 질문 원문, IP, 원문 전문을 로그에 남기지 않는다.
- AI 장애와 검색 장애를 분리한다.
- 법제처에 등록한 고정 공인 IP의 GitHub self-hosted runner가 주 1회 및 수동 수집을 실행한다. 공용 runner와 Vercel에서 법령 API를 직접 호출하지 않는다.
- 공개 서비스의 rate limit HMAC 저장과 평가셋 Recall@10 게이트는 배포 전 필수 잔여 작업이다.

## 결정 기록

| 날짜 | 결정 | 이유 |
|---|---|---|
| 2026-07-13 | 국가법령정보 Open API만 법률 코퍼스로 사용 | 출처와 버전 추적을 단순하고 검증 가능하게 유지 |
| 2026-07-13 | JSON 우선, 정규화 실패 시 XML 폴백 | 전송 효율과 개발 편의성을 얻되 XML 호환성을 보존 |
| 2026-07-13 | Next.js/FastAPI/Supabase/Vercel/GitHub Actions | 무료 우선 공개 MVP와 학습 목적에 적합 |
| 2026-07-13 | OpenAI를 포트 뒤에 배치하고 검색 전용 폴백 제공 | AI 비용·장애가 원문 조회를 중단하지 않게 함 |
| 2026-07-13 | 법령 수집만 고정 출구 IP의 self-hosted runner 사용 | Open API가 등록 IP/도메인을 검증하며 공용 runner 출구 IP는 고정되지 않음 |

# 에너지 법령 RAG 아키텍처

상태: `MVP 구현 중`
최종 갱신: 2026-08-09

## 목적

일반 사용자가 에너지 사업 규제를 질문하면 국가법령정보 공동활용 Open API 원문만으로 기준일에 유효한 의무·예외·인허가를 설명한다. 답변의 실질 주장은 조·항·호·목 인용으로 검증되며, 검증 실패나 AI 쿼터 소진 시 원문 검색만 제공한다.

모든 구현 판단이 따르는 기본 원칙은 [핵심 신념](docs/design-docs/core-beliefs.md)에 있다.

## 문서 지도

이 문서는 각 영역을 한 문단으로 요약만 한다. "왜 이렇게 만들었는가"의 전체 논증과 대안 비교는 아래 설계 문서(`docs/design-docs/`, 상태·전체 목록은 [색인](docs/design-docs/index.md))와 실행 계획(`docs/exec-plans/`)에 있다 — 이 표가 그 지도다.

| 이 문서의 영역 | 한눈에 무엇인가 | 자세히 |
|---|---|---|
| 배포와 데이터 흐름 | collector(수집)·Supabase(저장)·Vercel(API/Web)이 어떻게 나뉘어 도는지 | [기술 스택 ADR](docs/design-docs/technology-stack.md) · [Vercel·Supabase 운영 전환](docs/design-docs/vercel-supabase-deployment.md) |
| 수집 계약 | 법제처 Open API에서 법령 원문을 어떻게 가져오는지 | [Open API 수집 계약](docs/design-docs/open-law-api-ingestion.md) |
| 저장과 검색 | 조문을 어떻게 저장하고 질문에 맞는 근거를 어떻게 찾는지(벡터 검색 우선) | [RAG 파이프라인](docs/design-docs/rag-pipeline.md) · [검색 인덱스·임베딩 계보](docs/design-docs/retrieval-index-storage.md) · [근거 우선 검색 품질](docs/design-docs/evidence-first-retrieval-quality.md) · [시간 효력 모델](docs/design-docs/temporal-validity.md) |
| 질문 사전 라우팅 | 검색 전에 "이 질문이 법령만으로 답이 되는가"부터 거르는 단계 | [질문 사전 라우팅 설계](docs/design-docs/pre-retrieval-question-routing.md) · [0028 실행 계획](docs/exec-plans/active/0028-pre-retrieval-question-routing.md) |
| 답변 안전 게이트 | AI가 근거 없는 주장을 하지 못하게 막는 검증 절차 | [AI 차별화](docs/design-docs/ai-differentiation.md) · [답변 근거 검증](docs/design-docs/answer-grounding-validation.md) · [0032 실행 계획](docs/exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md) |
| 검색 품질 검증(실험 D) | 검색이 실제로 맞는 조문을 찾는지 사람이 표본으로 확인하는 절차 | [평가 전략](docs/design-docs/evaluation-strategy.md) · [D-10 수동 진단](docs/design-docs/experiment-d-10-manual-review.md) · [D-10 M2/M3 calibration](docs/design-docs/experiment-d-10-m3-calibration.md) · [D-10 전수 qrel](docs/design-docs/experiment-d-10-gold-adjudication.md) · [D-full 1,000문항](docs/design-docs/experiment-d-1000-evaluation.md) |
| 인증과 계정 | 로그인·세션·계정 삭제가 어떻게 연결되는지 | [Google OAuth·Supabase Auth 연결](docs/design-docs/google-oauth-supabase-flow.md) |
| 질문 취소 | 사용자가 요청 도중 멈추면 무슨 일이 일어나는지 | [분산 질문 취소](docs/design-docs/distributed-question-cancellation.md) |
| 보안·신뢰 경계 | 무엇을 신뢰하고 무엇을 안 믿는지, 주요 위협과 통제 | [위협 모델](docs/design-docs/threat-model.md) |

## 배포와 데이터 흐름

```text
고정 공인 IP Windows PC의 collector ── JSON 우선/XML 폴백 ──> 국가법령정보 Open API
       │                         │
       │                         └─ HTML·PDF·외부 법률 사이트 금지
       └─ OS 스케줄러 ──> 정규화/해시/버전 ──> Supabase DB + private Storage
                                                  │ PGroonga + pgvector
                                                  v
Browser ──> Vercel Next.js ── 동일 출처 /api 프록시 ──> Vercel FastAPI
                                                        ├─ Supabase 검색·Auth·Storage
                                                        └─ NVIDIA hosted NIM + Structured Outputs
```

Web과 stateless FastAPI는 Vercel, 영속 상태는 Supabase에 배치한다. collector는 국가법령정보 Open API에 등록된 고정 공인 IPv4 Windows PC에서 실행하고 검증된 현재 버전을 Supabase private Storage와 PostgreSQL에 반영한다. 로컬 파일 저장소는 외부 자격정보가 없는 개발·테스트 fallback이다. 집 PC는 공개 인바운드 요청을 받지 않는다. API는 Python 3.14 런타임, 웹은 Node 24/pnpm 11을 사용한다. Supabase DB 연결 시에는 Supavisor transaction pooler를 전제로 prepared statement cache를 끈다.

Python 실행 단위는 같은 저장소 안에서 두 프로젝트로 분리한다.

- `apps/api`: 질문·검색·인증·내보내기 API를 제공하며 운영에서는 stateless Vercel Function으로 실행
- `apps/collector`: 국가법령정보 수집 전용 CLI/배치 프로젝트. API와 독립적으로 고정 공인 IP Windows PC의 OS 스케줄러가 실행

공유 도메인 타입과 파서는 인프라 실행 단위에 종속되지 않는 공용 패키지로 추출한다. `apps/web`은 기존 프런트엔드 프로젝트이며 위의 두 Python 실행 단위 구분에 포함하지 않는다.

## 모듈 경계

의존성은 `domain -> application -> ports <- adapters -> delivery` 방향이다.

- `domain`: 법령 버전, 조문, 공개 API 계약과 순수 검증 규칙
- `application`: 수집, 검색, 답변 조립, 인용 검증 유스케이스
- `ports`: 법령 저장소·임베딩·답변 모델·원문 저장소 계약
- `adapters`: 국가법령 API, Supabase/PostgreSQL/Storage, NVIDIA NIM 외부 생성·임베딩 provider 구현
- `delivery`: FastAPI 엔드포인트, collector CLI·OS 스케줄러, Next.js 워크벤치

도메인 계층은 FastAPI, SQLAlchemy, 외부 모델 SDK를 import하지 않는다. 브라우저는 NVIDIA NIM과 Supabase service role에 직접 접근하지 않는다.

## 수집 계약

MVP는 정확 명칭 허용 목록 9개만 수집한다. 법령은 `eflaw`, 행정규칙은 `admrul&nw=1`을 사용한다.

1. 같은 요청을 `type=JSON`으로 호출한다.
2. JSON 문법뿐 아니라 법령명, ID/MST, 조문 구조를 도메인 객체까지 정규화한다.
3. 지원되지 않는 형식 또는 스키마 검증 실패 때만 `type=XML`로 재호출한다.
4. timeout/5xx는 같은 포맷으로 지수 백오프 재시도한 뒤 실패시킨다. 일시 장애를 XML 폴백으로 감추지 않는다.
5. JSON/XML은 같은 `LegalDocumentRecord`가 되어야 하며 포맷, SHA-256, 파서 버전, 폴백 사유를 기록한다.
6. 원문은 Supabase Storage에 보존한다. HTML과 PDF로 우회하지 않는다.

## 저장과 검색

조문을 조·항·호·목 단위로 저장하고, 질문이 들어오면 그 조문들 중 근거가 될 만한 것을 찾아온다. 벡터(의미) 검색이 기본이고, 벡터로 못 찾을 때만 키워드 검색이 보조로 개입한다.

- `legal_documents`: 안정적인 출처 ID와 정확 명칭
- `document_versions`: `안정 ID + MST + 시행일` 버전 키, 공포/시행/종료일, 원문 포맷·해시·경로
- `provisions`: 조·항·호·목 경로와 원문
- `embedding_profiles`, `provision_embeddings`: 제공자·모델·입력 유형·축약·정규화·본문 템플릿 계약과 그 프로필로 만든 차원 가변 벡터
- `corpus_snapshots`, `retrieval_profiles`, `retrieval_index_builds`: 코퍼스 세대와 dense·lexical 등 독립 검색기의 설정·구축 계보
- `retrieval_configurations`, `retrieval_releases`: 검색기 구성과 특정 snapshot/build 조합을 고정한 배포 단위 및 활성 포인터
- `legal_relationships`: 상하위법·위임·인용 관계
- `derived_obligations`: 행위자·조건·의무 유형과 검증 상태
- `ingestion_runs`, `evaluation_runs`, `runtime_flags`: 운영·평가 상태와 dataset·code·corpus·retrieval release 계보

검색은 먼저 corpus 전체 준비 게이트와 동적으로 계산한 기준일 지원 범위를 검사한 뒤 기준일 유효 버전을 제한한다. 지원 시작일은 오늘 이하인 수집 완료·현재 parser·검색 가능 버전의 `effective_from` 전역 최솟값이고, 지원 종료일은 UTC+9 한국 날짜의 오늘이며 양끝을 포함한다. 이는 저장된 버전 전체의 법률별 연속성·중복 여부를 검증한 공통 timeline이라는 뜻이 아니다. 오늘 유효한 provision population의 개수와 검색 콘텐츠 지문으로 `corpus-sha256:*` ID를 계산하며, 달력 날짜·`effective_to`·임베딩 프로필은 content ID 입력에 넣지 않는다. 따라서 시행·개정·폐지 경계와 검색 콘텐츠 변경이 없으면 날짜가 지나도 같은 ID를 유지한다.

전체 검색 준비 게이트가 닫혔거나 오늘 유효한 provision이 0개이거나 시간 identity를 완성할 수 없으면 검색 엔드포인트는 HTTP `503`, 코드 `corpus_unready`로 닫힌다. 준비되지 않은 `/v1/corpus/status`에서는 지원 시작일과 snapshot ID가 `null`일 수 있다. 준비된 범위 밖 날짜는 일부 문서만 남은 결과를 근거 부족처럼 반환하지 않고 임베딩·저장소 검색 전에 HTTP `422`, 코드 `unsupported_corpus_date`로 거부한다. 코퍼스 변경이 있으면 publisher는 `corpus.search_ready=false`를 먼저 커밋하고 65초 동안 기존 요청을 drain한 뒤 변경분을 단일 transaction으로 반영·검증한다. 이때 새 요청과 실제 PostgreSQL 검색 직전의 재검사는 lock을 기다리지 않고 즉시 `503 corpus_unready`로 닫히며, 검색 SQL 안의 준비 게이트도 점검 전환과 겹친 요청이 부분 결과를 반환하지 않게 한다. 성공한 publisher만 같은 반영 transaction 끝에서 게이트를 다시 열고, 실패하면 변경분을 전부 rollback한 채 게이트를 닫아 둔다. `/v1/corpus/status`는 계산된 `corpus_snapshot_id`, `supported_as_of_from`, `supported_as_of_through`, 준비 상태와 사유를 노출한다. 요청에서 날짜를 생략하면 API는 서버 시간대가 아니라 한국 날짜의 오늘을 사용한다.

법률명·조문 경로를 명시한 질문은 direct-path로 조회한다. 일반 질문은 query embedding이 준비됐을 때 pgvector dense-only 검색을 실행하고, 후보가 있으면 그 dense 순위만 반환한다. 운영 v1 dense와 실험 D는 기준일 유효 population을 먼저 `MATERIALIZED`한 exhaustive exact cosine을 사용한다. 이 v1·실험 경로에서는 HNSW를 사용하지 않으며 새 인덱스·build·release도 만들지 않는다. 별도 v2 LlamaIndex 테이블(`data_law_rag_llamaindex`)의 HNSW는 사용자 승인된 운영자 전용 `HnswIndexManager`만 생성·삭제·상태 확인할 수 있고, ingestion과 API 요청은 이를 자동으로 바꾸지 않는다. dense 결과가 0건이거나 embedding 경로가 없을 때에만 PGroonga 4단계 keyword 검색을 독립 fallback으로 실행한다. dense와 keyword 점수는 합치지 않으며 hybrid와 RRF는 현재 검색 경로에 없다.

의미 검색은 질의와 저장 벡터의 profile key가 같을 때만 실행한다. 현재 임베딩 provider는 NVIDIA hosted NIM의 `nvidia/nemotron-3-embed-1b`이며 native 2048차원의 첫 512개를 L2 재정규화해 저장한다. production 응답은 같은 조의 하위 조각을 조 단위로 묶을 수 있지만, 실험 D의 검색 평가는 qrels와 같은 raw `provision_id` 단위를 사용하고 direct-path, keyword fallback, 조 단위 grouping을 우회한다.

운영 웹/API의 확정 벡터 원본은 PostgreSQL `provision_embeddings`뿐이다. 로컬 bundle과
`embeddings.jsonl`은 점검 반영 전 준비·운반 계층이며 runtime 검색 fallback이 아니다. 새 로컬 벡터는
transaction B에서 DB에 복사되고 전체 검증과 commit을 통과한 뒤에만 사용자 검색에 노출된다.

## 질문 사전 라우팅 (0028)

`terra`(AI) 답변 요청은 embedding·검색보다 먼저 2단계 라우터를 거친다. 목적은 "같은 주제인가"(임베딩이 재는 것)와 "지금 근거만으로 답할 수 있는가"(임베딩이 못 재는 화용론적 판단)를 분리하는 것이다. 자세한 문제 탐색·확정 근거는 [0028](docs/exec-plans/active/0028-pre-retrieval-question-routing.md)을 참고한다.

- **tier1** (`app/domain/routing.py`의 `route_tier1`): 비용 0, 결정적 Kiwi 형태소 분석 기반 키워드/정규식 규칙. 승인된 질문은행 1,000문항 전수 분석으로 만든 사전([tier1-term-dictionary-analysis-v1.json](apps/api/evaluation/tier1-term-dictionary-analysis-v1.json))을 쓴다. "정말 답할 수 없는 것만 타이트하게 거른다"는 원칙으로, 위양성(답할 수 있는데 차단)을 줄이는 쪽으로 2026-08-08에 조정했다.
- **tier2** (`route_tier2`, `app/adapters/nvidia_nim_route_classifier.py`): tier1이 못 잡으면 NVIDIA NIM LLM에게 라우팅 자체를 판단하게 한다. 원래는 임베딩 최근접 방식이었으나, "같은 주제 유사도"와 "이 근거로 답이 되는가"가 다른 질문이라는 게 드러나 2026-08-08에 LLM judgment로 교체했다. tier2 실패(timeout·오류)는 요청을 막지 않고 `legal_search`로 안전하게 넘어간다.
- **tier3**: 미확정, 아직 미사용.

판정은 4가지 route로 나온다: `legal_search`(검색·생성 정상 진행), `clarification_required`(설비용량 등 사용자 사실이 빠짐 — 텍스트로 재질문, 후속 대화 자동 수집 없음), `realtime_required`/`external_document_required`(법령 검색으로 원천적으로 답할 수 없음 — 결정적 차단 메시지, embedding·검색·LLM 호출 0회). `clarification_required`가 아닌 두 차단 route는 tier2가 판단했을 경우 LLM이 직접 생성한 `explanation`(왜 이 근거로는 안 되는지)을 그대로 사용자 안내 문구에 재사용한다 — 별도 LLM 호출을 추가하지 않고 이미 계산된 판단 근거를 노출하는 방식이다.

라우팅 tier2가 "확인/대조" 같은 표현을 과대 해석해 `external_document_required`로 잘못 차단한 사례가 실측에서 발견됐다(TD-024). 트래픽이 쌓이면 [0033](docs/exec-plans/todo/0033-traffic-based-routing-calibration-review.md)에서 재검토한다.

## 답변 안전 게이트

검색으로 근거를 찾은 뒤에도 AI가 근거 없는 주장을 답에 섞어 내지 못하게 막는 절차다. 아래 5단계 중 하나라도 실패하면 AI 답변 대신 검색 결과만 보여준다(원문 자체는 사용자가 항상 볼 수 있다).

1. 질문의 기준일이 현재 corpus 지원 범위 안인지와 사업 단계를 검증한다.
2. 위 사전 라우팅을 통과([legal_search]인 경우만)하면 direct-path 또는 dense-only 검색으로 근거 후보를 구성하고, dense가 0건일 때만 독립 keyword fallback을 사용한다.
3. provider adapter의 JSON schema 출력으로 답변·체크리스트·인용 ID와 함께, 모델이 스스로 판단한 완결성 신호 `action`(`fully_answerable`/`partially_answerable`/`clarification_required`/`unanswerable`)과 `missing_information`을 받는다. 검증기는 이 명시적 신호로 요구 수준을 정하며 summary 텍스트에서 확신도를 추측하지 않는다.
4. 모든 실질 주장과 체크리스트에 존재하는 인용 ID가 있는지 검사한다. `action=unanswerable`이면 sections·checklist가 비어도 되지만 summary·limitations의 무근거 규범 주장(다른 법령·기관을 단정)은 계속 차단한다. `action=clarification_required`면 (사전 라우팅이 아니라 실제 검색·생성을 해본 뒤에야 드러난 부족함이므로) `missing_information`만 있으면 통과하고, 같은 재질문 응답 형식으로 사용자에게 반환한다.
5. 로그인 계정 일일 quota 로직은 `account_quota_enabled`로 토글하며 현재 기본값은 `False`라 요청을 막지 않는다. 토글을 켰을 때만 AI 10회/일·검색 100회/일 한도를 적용한다. NVIDIA 생성 실패, provider가 반환한 결제·quota 402/429, 권한 오류, AI 비활성 시에는 다른 생성 모델로 자동 전환하지 않고 검색 전용 응답으로 전환한다.

현재 인용 게이트는 인용 ID 존재와 원문 반환을 보장한다. 주장-원문 의미 일치 자동평가와 법령 관계 확장은 다음 품질 게이트다. 검증 로직(`app/adapters/openai_answerer.py`의 `validate_draft`)은 근거 원문에서 조문 경로(`hit.path`)를 빠뜨려 정확한 조문 인용을 무근거 숫자로 오판하던 버그와, 한국어 겸양 표현("판단할 수 없다")이 법적 금지 주장과 표면 문법이 같아 오탐되던 버그를 2026-08-08에 고쳤다 — 상세 진단은 [0032](docs/exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md)를 참고한다. 검증기 코드를 고칠 때마다 재확인을 위해 유료·rate-limited API를 다시 호출하는 낭비를 없애기 위해, 진단 스크립트(`scripts/diagnose_grounding_failures.py`)가 검색 근거(`SearchHit`) 원문을 통째로 저장하고, `scripts/replay_grounding_validation.py`가 그 저장분으로 `validate_draft()`만 새 API 호출 없이 재실행한다.

## 검색 품질 검증 (실험 D)

"실험 D"는 검색이 실제로 맞는 조문을 찾아오는지 사람이 표본으로 확인하는 사내 품질 검증 절차 이름이다(제품 기능이 아니다). 현재는 사용자가 결과를 직접 확인한 10개 질문(D-10)만으로 소규모 점검(calibration)을 한다 — 아직 통계적으로 일반화할 수 있는 정식 평가(D-full, 아래 참고)는 아니다.

현재 실험 D는 사용자 확인을 마친 D-10 10문항만 소표본 calibration에 사용한다. M2 frozen contract는
질문·판정·원래 raw top 10 안의 직접 근거·알려진 무관 top 5와 corpus/profile/artifact SHA를 결박한다.
preflight는 이를 로컬에서 검증하며 DB·NVIDIA를 호출하지 않는다. M3는 저장된 동일 raw top 10과 R1을
비교하고 새 top 5 미판정 후보를 다시 사람이 확인한다.

이 10문항에는 독립 주석·corpus 전수 qrels·held-out split이 없으므로 `full gold`, `Evidence Recall`,
`held-out 성능`, `population 일반화`, `production release gate`로 사용하지 않는다. 허용값은 manual
direct-evidence hit@1/3/5/10, 첫 근거 순위와 reciprocal rank@10, 알려진 무관 top 5와 문맥 판정 수다.
과거 실험 C의 로컬 205청크와 결과는 기준값으로 사용하지 않는다.

2026-08-07 D-10 전용 Gold 후보 workflow가 같은 snapshot의 10문항×3,066개 전수 relevance 판정과 qrel·
reference 초안을 생성했다. 현재 상태는 `pending_user_review`이며, positive와 일괄 relevance-0 판정을
사용자가 모두 adjudication하기 전에는 위 비Gold 제한을 유지한다. 승인 뒤에도 이미 조정에 사용한 10문항의
calibration Gold이므로 held-out·일반화·일반 release gate로 사용하지 않는다.

승인된 일반 사용자 질문 1,000개와 D-full Gold schema·runner는 삭제하지 않는다. 10문항 밖 일반화나
운영 회귀가 실제로 필요할 때만 질문을 현재 corpus에서 다시 검사하고 독립 qrels·reference·adjudication을
작성한다. 그때만 다음 보존된 D-full runner 계약을 활성화한다.

D-full runner는 다음 순서를 강제한다.

1. dataset, 질문은행, 질문 승인 manifest, gold adjudication manifest와 critical code provenance를 검증한다.
2. 초기 `REPEATABLE READ, READ ONLY` transaction에서 지원 기준일·corpus·벡터 상태와 gold preflight를 통과하기 전에는 질문을 임베딩하지 않는다.
3. 질문 임베딩 뒤 별도 `READ COMMITTED, READ ONLY` transaction의 첫 snapshot-taking statement로 PostgreSQL corpus mutation 공유 advisory lock을 얻는다.
4. 같은 연결과 잠금 transaction 안에서 전체 검색 가능 corpus와 문항별 기준일 유효 population, qrels·distractor·후보 pool, 벡터 profile·coverage·L2 norm과 transaction·planner 설정을 다시 검증한다.
5. 기준일별 대표 query의 `EXPLAIN` plan과 plan SHA-256을 검색 전에 기록한다. 실험 D primary dense baseline은 기준일 유효 population 전체를 `MATERIALIZED`한 뒤 모두 비교하는 exhaustive exact cosine만 사용한다. 통과한 경우에만 모든 질문을 raw provision exact cosine 검색으로 11개까지 조회하며, 10위와 11위의 raw cosine 점수가 같으면 top 10 경계를 임의로 자르지 않고 실행을 실패시킨다. HNSW identity·상태·결과 비교는 이 runner의 입력이나 결과에 포함하지 않는다.
6. 같은 공유 lock을 마지막 검색까지 유지한 뒤에만 지표를 계산한다. 결과에는 입력·질문·corpus·벡터·query plan·임베딩 batch 크기·PostgreSQL/pgvector 버전과 검색 설정·critical code commit 및 파일 해시를 기록한다.
7. 전체 실행이 성공한 경우에만 새 run JSON을 임시 파일에서 원자적으로 게시한다. 기존 run을 덮어쓰지 않으며 실패 시 완성 결과 파일을 만들지 않는다.

annotation pool은 방법별 설정 해시와 정확한 `top_k`, 실제 후보 ID와 후보 집합 해시를 보존한다. 비전체검사 방법은 후보 수가 `min(top_k, 기준 corpus 크기)`와 정확히 같아야 하고, 방법별 후보의 합집합은 문항별 판정 pool과 정확히 같아야 한다. `full_corpus_manual_review` 방법을 선언하면 그 후보 집합은 해당 문항 기준일에 유효한 전체 검색 가능 provision 집합과 정확히 같아야 한다.

D-full을 다시 활성화한 경우에만 핵심 검색 평균의 primary 모집단을 조정에 쓰지 않은 `test` split의
`fully_answerable` 문항으로 둔다. grade 2 직접 qrels를 기준으로 Recall@1/3/5/10, HitRate@1/3/5/10,
Direct Precision@5와 MRR@10을 계산하고 Precision@5는 grade 1 보조 문맥과 grade 2 직접 근거를 모두
센다. nDCG와 facet 지표, family macro와 bootstrap 95% 구간도 이 정식 Gold 경로에서만 계산한다.

## 공개 API

- `POST /v1/questions`
- `POST /v1/search`
- `GET /v1/provisions/{id}`
- `GET /v1/documents/{id}/changes`
- `GET /v1/corpus/status`
- `GET /health`

연혁 본문 경로가 XML/JSON 계약 테스트를 통과하기 전 변경 API는 `supported=false`를 반환한다. HTML로 기능을 가장하지 않는다.

`POST /v1/questions`, `POST /v1/search`, `GET /v1/provisions/{id}`는 현재 corpus가 준비되지 않았으면 `503 corpus_unready`로 닫고, 동적 지원 범위 밖 `as_of_date`는 provider·실제 검색 호출 전에 같은 `422 unsupported_corpus_date` 계약으로 차단한다. 날짜 기본값은 UTC+9 한국 날짜의 오늘이다.

## 운영 원칙

- 키는 저장소에 커밋하지 않고 Vercel·Supabase 환경 설정 또는 collector PC의 OS 비밀 저장소에 둔다.
- 질문 원문, IP, 원문 전문을 로그에 남기지 않는다.
- AI 장애와 검색 장애를 분리한다.
- 법제처에 등록한 고정 공인 IPv4 Windows PC에서 `apps/collector`를 별도 프로세스로 실행한다. Vercel, 공용 runner와 브라우저에서 법령 API를 직접 호출하지 않으며 collector PC에 포트포워딩이나 공개 API를 열지 않는다.
- 현재 버전 collector와 Vercel API, Google 인증과 사용자 질문 이력은 Supabase에 연결되어 있다. 연혁·삭제 격리와 영속 운영 플래그는 후속 단계다.
- 익명 질문은 저장하지 않는다. 운영 로그인은 Supabase Google OAuth만 지원하며 질문 이력은 PostgreSQL에 생성일부터 1년 보존 후 삭제한다. 계정 삭제 시 질문·이력·세션·내보내기·동의 등 해당 사용자와 연결된 데이터를 삭제한다. 개발·테스트의 목업 인증은 production에서 비활성화한다.
- 공개 서비스의 rate limit HMAC 저장은 배포 전 필수 잔여 작업이다. D-10 10문항은 안전·동작 확인에만
  사용하며 정량적 일반 release gate가 필요하면 예정 작업 0029의 독립 Gold를 먼저 만든다.

## 결정 기록

| 날짜 | 결정 | 이유 |
|---|---|---|
| 2026-07-13 | 국가법령정보 Open API만 법률 코퍼스로 사용 | 출처와 버전 추적을 단순하고 검증 가능하게 유지 |
| 2026-07-13 | JSON 우선, 정규화 실패 시 XML 폴백 | 전송 효율과 개발 편의성을 얻되 XML 호환성을 보존 |
| 2026-07-13 | 초기안: Next.js/FastAPI/Supabase/Vercel/GitHub Actions(단일 클라우드 서버 결정으로 배포안 대체) | 무료 우선 공개 MVP와 학습 목적에 적합 |
| 2026-07-13 | OpenAI를 포트 뒤에 배치하고 검색 전용 폴백 제공 | AI 비용·장애가 원문 조회를 중단하지 않게 함 |
| 2026-07-13 | 초기안: 법령 수집에 고정 출구 IP의 self-hosted runner 사용(아래 OS 스케줄러 결정으로 대체) | Open API가 등록 IP/도메인을 검증하며 공용 runner 출구 IP는 고정되지 않음 |
| 2026-07-13 | Terra 오류 시 대체 생성 모델 없이 검색 전용 모드 사용 | 모델 변경으로 검증되지 않은 품질 차이가 숨겨지는 것을 방지 |
| 2026-07-13 | Python 실행 단위를 API와 collector 두 프로젝트로 분리 | 웹 요청과 장시간·예약 수집의 장애 및 배포 수명주기를 분리 |
| 2026-07-13 | Supabase·Vercel·로그인은 목업 우선 | 외부 자격정보 없이 제품 흐름과 계약을 먼저 검증 |
| 2026-07-15 | Google OAuth는 Supabase Auth PKCE, API 인증은 Supabase 사용자 검증 | 브라우저에 secret을 노출하지 않고 실제 질문 이력을 사용자별로 저장 |
| 2026-07-13 | 실제 로그인은 Google만 지원 | 초기 인증 선택지와 계정 연결 복잡도를 최소화 |
| 2026-07-13 | 질문 이력 1년 보존, 계정 삭제 시 사용자 관련 데이터 전부 삭제 | 사용자 통제권과 개인정보 최소 보존 원칙 적용 |
| 2026-07-13 | 웹·API·collector를 같은 클라우드 서버의 독립 프로세스로 배치 | 고정 공인 IP와 초기 운영 단순성을 함께 확보 |
| 2026-07-14 | [대체됨] 주 1회 수집하고 검증된 문서 변경을 즉시 활성 코퍼스에 반영 | 당시 문서 단위 반영 계약이며 2026-08-04 점검 모드 원자 반영으로 대체됨 |
| 2026-07-14 | Open API `delHst`를 법적 폐지가 아닌 출처 레코드 가용성으로 관리 | 삭제 응답에 폐지 여부·삭제 사유가 없으므로 법적 효력 종료를 추론하지 않기 위함 |
| 2026-07-14 | collector 로컬 설정은 `.env` 후 `.env.local`을 읽고 프로세스 환경변수를 최우선 적용 | 개발 비밀값을 커밋하지 않으면서 실행 시 명시적으로 재사용 |
| 2026-07-14 | 위 단일 서버 배치를 Vercel Web/FastAPI + Supabase + 고정 공인 IP Windows collector로 대체 | 공개 서버 운영 부담과 Open API 고정 IP 제약을 분리하고 API를 stateless하게 운영 |
| 2026-07-14 | Preview Web은 Next.js 상대 `/api/*` 동일 출처 프록시 사용 | 가변 Preview origin을 FastAPI CORS wildcard로 허용하지 않고 환경 경계를 유지 |
| 2026-07-14 | 질문 요청에서 Terra 또는 검색 전용을 명시적으로 선택 | 사용자가 생성 모델 호출 여부를 통제하면서 Terra 단일 모델·안전 폴백 계약을 유지 |
| 2026-07-15 | [대체됨] collector `sync-current`는 검증된 원문을 content-addressed private Storage에 먼저 보존하고 DB 문서·버전·조문을 트랜잭션 반영 | 원문 계보 계약은 유지하되 정기 운영 진입점은 2026-08-04 `apply-prepared`로 대체됨 |
| 2026-07-19 | 생성 기본 후보를 NVIDIA hosted Nemotron 3 Ultra로 변경하고 기존 `terra` wire 값은 호환용으로 유지 | 로컬 PC 공개 없이 Vercel outbound 호출이 가능하며 provider 변경 중 기존 클라이언트 호환을 보존 |
| 2026-07-23 | 임베딩 provider를 NVIDIA hosted Nemotron 3 Embed 1B로 교체하고 검색 시 모델 ID를 필터링 | 한국어 hosted 실험과 기존 512차원 계약을 유지하면서 OpenAI·NVIDIA 벡터 공간 혼합을 방지 |
| 2026-08-03 | 실험 D primary dense baseline을 exhaustive exact cosine으로 고정 | 근사화 변수를 현재와 미래의 품질 판정에서 영구 배제하고 근거 찾기 자체의 재현성을 유지 |
| 2026-08-03 | [대체됨] HNSW 설계·평가를 gold 1,000문항과 근거 찾기 전수 검증 이후의 별도 승인 단계로 보류 | 당시에는 근거 찾기와 근사 인덱스 중 무엇을 측정했는지 구분하기 위해 보류했으나, 2026-08-04 영구 제외 결정으로 대체됨 |
| 2026-08-04 | HNSW를 현재와 미래의 제품·실험 경로에서 영구 제외하고 exhaustive exact cosine을 유지 | 근사 인덱스 도입으로 품질 판정과 운영 복잡도를 다시 늘리지 않기로 한 사용자 결정. 2026-08-03의 “검증 후 재검토” 결정을 대체하며, 기존 물리 인덱스는 사용·재구축·튜닝·평가·release 연결하지 않는 역사적 잔여물로만 남김 |
| 2026-08-03 | [대체됨] 당시 감사한 corpus 지원 기준일을 `2026-06-03..2026-08-03` 양끝 포함으로 고정하고 범위 밖 요청을 `422`로 거부 | 당시 9개 open version과 3,066개 조문을 기준으로 한 안전 경계였으나, 2026-08-04 동적 시간 계약으로 대체됨 |
| 2026-08-04 | 지원 시작일은 오늘 이하인 수집·현재 parser·검색 가능 버전의 `effective_from` 전역 최솟값, 종료일은 한국 날짜의 오늘로 계산하고 오늘 유효 population의 content identity를 상태로 노출 | 날짜 상수를 매일 고치지 않으면서 현재 수집 corpus만 검색하고, 준비 불완전은 `503`, 범위 밖은 검색 전 `422`로 분리하기 위함. 이 계산은 법률별 timeline 연속성을 검증했다는 주장이 아님 |
| 2026-08-04 | 일 1회 로컬 bundle을 준비하고 변경이 있을 때만 `gate=false → 65초 drain → DIRECT_URL 단일 반영 transaction → gate=true`로 게시 | 드문 corpus 갱신을 위해 모든 운영 reader에 shared lock이나 고가용성 세대 전환을 추가하지 않고, 짧은 점검 중단으로 비용과 복잡도를 낮춤. writer lock과 실험 D lock은 유지 |
| 2026-08-04 | 로컬 벡터는 준비·운반에만 사용하고 웹/API 검색은 DB에 검증·commit된 활성 벡터만 사용 | 미확정 파일과 사용자 검색 경계를 분리하고, 점검 transaction이 성공한 시점에만 새 벡터로 전환 |
| 2026-08-07 | 실험 D의 현재 필수 범위를 사용자 확인 D-10 10문항 frozen calibration으로 축소하고 D-full Gold는 필요 시 재개 | 현재 의사결정 비용을 줄이되 10문항을 Gold·held-out·일반 release 근거로 과장하지 않고 기존 1,000문항 자산을 보존 |
| 2026-08-08 | 질문 사전 라우팅을 tier1(Kiwi 결정적 키워드)+tier2(LLM judgment) 2단계로 확정하고 embedding·검색보다 먼저 실행([0028](docs/exec-plans/active/0028-pre-retrieval-question-routing.md)) | 임베딩 유사도는 "같은 주제인가"만 재고 "이 근거로 답이 되는가"라는 화용론적 판단은 못 함 - 공인 문헌(Self-RAG, Adaptive-RAG, FLARE 등) 조사 후 판단 자체를 LLM에 맡기기로 결정 |
| 2026-08-08 | tier2를 임베딩 최근접에서 NVIDIA NIM LLM judgment(`route_tier2`)로 교체 | threshold gate형 임베딩 유사도가 화용론적 충분성 판단에 구조적으로 부적합함을 실측(0201 오분류 사례)으로 확인 |
| 2026-08-08 | tier1 사전을 승인된 질문은행 1,000문항 전수 분석으로 재구축하고, 위양성(답할 수 있는 질문 차단)을 줄이는 방향으로 타이트닝 | "정말 답할 수 없는 것만 걸러낸다"는 사용자 원칙 - 과차단이 과소차단보다 사용자 피해가 큼 |
| 2026-08-08 | `realtime_required`/`external_document_required` 차단 응답에 tier2 LLM이 이미 생성한 `explanation`을 재사용해 노출 | 별도 LLM 호출 없이 "왜 이 근거로 안 되는지"를 사용자에게 그대로 안내 - 기존 계산 결과를 버리지 않음 |
| 2026-08-08 | `DraftAnswer`에 `action`(fully/partially_answerable, clarification_required, unanswerable)과 `missing_information`을 구조화 필드로 추가하고 검증기가 이를 근거로 요구 수준을 분기 | 검증기가 summary 텍스트에서 확신도·완결성을 정규식으로 추측하던 것을 모델의 명시적 신호로 대체 - 텍스트 추측은 오탐(겸양 표현을 금지 주장으로 오판 등)의 근본 원인이었음 |
| 2026-08-08 | `unanswerable` 응답도 정형화된 "법령 corpus로 답할 수 없습니다"로 끝내지 않고, 모델이 생성한 근거 설명을 노출하되 다른 법령·기관 지목은 단정형이 아닌 권유형만 허용 | 사용자가 왜 답이 안 되는지 알 수 있게 하면서도, 근거 없는 다른 법령·기관에 대한 단정적 주장(오탐 위험)은 계속 차단 |
| 2026-08-08 | grounding 검증기(`validate_draft`)의 evidence 문자열에 조문 경로(`hit.path`)를 포함하고, 메타인지 동사 뒤 겸양 표현("판단할 수 없다")을 신호에서 제외 | 정확히 인용된 조문 번호가 무근거 숫자로, 인식론적 겸양이 법적 금지 주장으로 오판되던 grounding_failed 오탐 두 근본 원인을 제거 |
| 2026-08-08 | 진단 스크립트가 검색 근거(`SearchHit`) 원문 전체를 저장하고, 별도 replay 스크립트로 검증기 코드 변경을 새 API 호출 없이 재검증 | 검증기를 고칠 때마다 재확인을 위해 유료·rate-limited API를 다시 호출하는 반복 낭비를 제거 |
| 2026-08-09 | 답변 생성 provider를 NVIDIA NIM 하나로 고정하고 OpenAI 설정·실행 분기를 제거 | 운영 비교·fallback에 OpenAI를 쓰지 않는다는 기존 결정을 기본값이 아니라 실행 가능한 코드 경계로 확정 |
| 2026-08-09 | 로그인 계정 일일 quota 로직을 삭제하지 않고 `account_quota_enabled=False` 토글로 비활성화 | 현재는 한도 없이 통과시키되, 추후 환경 변수로 토글만 켜면 기존 AI 10회/일·검색 100회/일 제한을 복구할 수 있게 함. 익명 일일 quota는 별도 결정으로 제거된 상태 |
| 2026-08-09 | `Citation.source_kind`를 API 응답까지 전달 | DB·검색 결과에 있던 출처 종류를 제목 문자열 추측 없이 프런트가 사용하게 함 |
| 2026-08-09 | `/v1/questions` 조정된 timeout 예산을 `52 < 55 < 60` 사슬로 고정한다: Vercel 함수 60초는 애플리케이션이 스스로 거는 timeout이 아니라 플랫폼이 강제로 연결을 끊는 kill switch로만 취급하고, API 서버측 전체 예산 52초를 하나의 요청 안에서 routing·embedding·retrieval·generation stage가 나눠 쓰며, provider 재시도(`ANSWER_GENERATION_MAX_ATTEMPTS`)는 생성 40초 slice 안에 갇혀 별도 예산을 받지 않는다. Web은 각 서버 요청을 55초로 끊어 새 `client_request_id`와 새 서버측 예산으로 처음부터 다시 시작하고, "3회"는 최초 시도를 포함한 총 Web 시도 횟수이지 최초 1회 + 추가 재시도 3회가 아니다. 생성 stage가 예산을 다 써도 이미 확보한 근거를 지우지 않고 검증된 `generation_error` 검색 전용 폴백으로 끝낸다 | 각 경계를 명시적 숫자·재시도 계약으로 고정해, API가 아직 안전한 검색 전용 폴백을 만들 수 있는데도 Vercel이 먼저 연결을 끊어 사용자가 원인 불명 오류만 보는 상황과, 뒤늦은 생성 stage timeout이 이미 검증된 근거를 지워버리는 상황을 둘 다 방지 |
| 2026-08-18 | v1 운영·실험 D의 HNSW 금지는 유지하되, 별도 v2 LlamaIndex 테이블에 한해 사용자 승인된 운영자 `HnswIndexManager`를 허용 | v1/평가의 exhaustive exact 기준선을 보존하면서 v2의 독립 운영 실험을 ingestion·API 자동 변경 없이 명시적으로 통제하기 위함 |

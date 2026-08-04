# 실행 계획 0022: 검색 인덱스 재설계와 실험 D 1,000문항 평가셋

상태: 진행 중
작성일: 2026-08-03
소유자: Codex

## 목적과 사용자 결과

현재 DB에 남아 있는 `hybrid_search`/RRF 중심 스키마를 현재의 dense-only 설계와 일치시킨다. 문서 임베딩의 모델·차원·입력 유형·변환 버전을 명시적으로 추적하고, 향후 BM25나 다른 검색기를 추가할 때 dense 테이블과 점수를 섞지 않고 독립 후보를 비교할 수 있게 한다. 그 뒤 운영 corpus의 벡터를 실제로 생성하고, 일반 사용자 질문 1,000개를 승인·독립 주석한 gold로 승격해 실험 D에서 검색·근거 충분성·근거 부족 경계를 평가한다.

## 기존 사용자 변경 보호

작업 시작 시 다음 변경은 사용자의 기존 작업으로 확인했으며 수정·스테이징·커밋하지 않는다.

- `docs/generated/experiment-b-embedding-results.md`
- `docs/generated/experiment-b-embedding-runs.json`
- `docs/learning/index.md`
- `docs/learning/28-llamaindex-retrieval-postprocessing-and-future-context-pipeline.md`

## 범위

- 현재 마이그레이션과 운영 DB 상태의 읽기 전용 감사
- hybrid SQL 함수 제거와 임베딩 프로필/벡터 저장 구조 재설계
- 현재 NVIDIA passage/query 변환 계약을 프로필로 고정
- 향후 BM25를 독립 retriever로 추가할 수 있는 경계와 평가 결과 스키마 정의
- 반복 실행·체크포인트·콘텐츠 해시 검증이 가능한 임베딩 backfill 명령 구현
- 운영 DB 마이그레이션과 실제 임베딩 생성. 이미 생성된 물리 HNSW 인덱스는 역사적 자산으로만 기록
- 현재 corpus가 완전하게 지원하는 기준일 범위를 backend에 고정하고 범위 밖 검색을 fail-closed
- 공식 NVIDIA·LlamaIndex 등 1차 자료의 RAG 평가 방식을 비교
- 실험 D 일반 사용자 질문은행 1,000개를 승인한 뒤 독립 answerability·qrels·reference contexts·reference response·분할·검토 상태를 가진 approved gold로 승격
- 자동 검증과 사람이 직접 볼 모호한 문항 목록 생성
- 일반 사용자형 에너지 질문 후보 1,000개 생성·검토

## 비범위

- BM25, hybrid, RRF, reranker를 현재 검색 경로에 채택
- 벤치마크 결과를 미리 만들어 기록
- 정답을 모르는 프로덕션 질문에 Evidence Recall을 런타임 게이트로 적용
- 원문에 없는 답을 LLM 기억으로 보완
- 사용자 기존 실험 B 결과 수정
- 취소된 v2 12문항 전체 검토본 재생성 또는 수정
- 일반 사용자 질문 승인 전 gold 정답·qrels 자동 추론이나 검색 품질 실행
- 질문-정답 gold와 근거 찾기 전수 검증 전 HNSW 설계·튜닝·평가·비교 또는 새 인덱스 작업
- 기준일 범위의 프런트 차단 구현. 상태 API를 사용하는 후속 TODO로만 남김

## 설계 원칙

1. 현재 런타임은 dense-only이고, dense 0건일 때만 독립 keyword fallback을 사용한다.
2. 검색기는 독립적으로 후보와 원점수를 반환한다. 향후 결합은 DB 함수에 숨기지 않고 버전이 기록되는 별도 실험 계층에서 수행한다.
3. 저장 벡터에는 어떤 passage 입력과 변환으로 만들었는지 재현 가능한 프로필과 콘텐츠 해시를 둔다.
4. 질문 임베딩과 passage 임베딩은 같은 모델/차원 공간이되 입력 유형은 각각 `query`/`passage`로 구분한다.
5. 평가셋 정답은 corpus의 `document_id`, `version_id`, `provision_id`, `path`, 원문 근거로 추적 가능해야 한다.
6. 정답 없는 1,000문항 질문은행은 질문 범위·말투 검토용 임시 산출물이다. 사용자 승인과 독립 qrels·reference response 주석을 마친 `approved_gold`만 고정 평가 자료이며, 모호한 문항은 별도 검토 큐로 분리한다.
7. 실험 D는 exhaustive exact cosine으로 질문-정답과 근거 찾기 자체를 먼저 검증한다. HNSW는 이 평가의 상태·게이트·결과에 넣지 않는다.
8. 현재 corpus는 9개 문서·3,066개 조문이 모두 갖춰진 `2026-06-03..2026-08-03` 양끝 포함 기준일만 검색한다.

## 완료 조건

- DB head 마이그레이션에 hybrid/RRF 실행 함수가 남지 않는다.
- 임베딩 프로필과 벡터의 차원·콘텐츠 해시·생성 시각·프로필 연결을 DB가 검증한다.
- dense 쿼리가 현재 NVIDIA 512차원 프로필을 명시하고, 실험 D runner는 물리 HNSW 상태와 무관하게 exhaustive exact cosine만 실행한다.
- backfill을 재실행해도 콘텐츠가 같은 행은 다시 API 호출하지 않는다.
- 대상 조문 수, 생성/재사용/실패 수와 프로필 상태를 비밀정보 없이 출력한다.
- 운영 corpus의 현재 대상 조문마다 최신 콘텐츠 해시와 일치하는 임베딩이 존재한다.
- 실험 D gold가 승인된 질문은행·별도 question approval manifest와 질문 문구·범위 해시로 일치하고 정확히 1,000문항이다.
- 별도 gold adjudication manifest가 전체 dataset과 1,000개 문항별 완성 payload의 canonical SHA-256을 봉인하고 `질문 승인 < 문항 review < gold adjudication` 시간 순서를 만족한다.
- gold는 `fully_answerable | partially_answerable | clarification_required | unanswerable` 상태, 필수 답변 요소, qrels, frozen reference contexts와 reference response의 불변조건을 통과한다.
- fully answerable의 supported 요소마다 grade 2 직접 근거가 있고, unanswerable은 qrels 없이 근거 부족 사유를 명시한다.
- 후보 수집 방법별 설정 해시·정확한 top-k·후보 집합 해시가 있으며, 방법별 후보 합집합과 판정 pool이 일치한다. 전체 corpus 직접 검토를 선언한 문항은 해당 기준일의 전체 유효 검색 population과 정확히 일치한다.
- runner가 초기 `REPEATABLE READ, READ ONLY` preflight 전에 embed/search를 실행하지 않고, 별도 `READ COMMITTED, READ ONLY` corpus mutation 공유 transaction lock 안에서 preflight·retrieval 상태를 다시 확인한 뒤 마지막 raw provision 검색까지 잠금을 유지한다.
- runner가 기준일별 대표 exhaustive exact cosine query plan과 SHA-256을 기록하고, 물리 HNSW identity·상태·비교값을 평가 입력이나 결과에 넣지 않는다.
- runner는 raw top 11에서 10/11 동점을 실패시키고 Recall·HitRate·Precision·Direct Precision·MRR@10·graded nDCG·facet 지표를 고정 공식으로 계산한다.
- primary 지표는 held-out test의 fully-answerable 문항만 사용하고 calibration 및 calibration+test 결합값은 diagnostic-only로 분리한다.
- primary 집계는 같은 상황의 5개 표현 변형을 먼저 묶는 scenario-family macro이며, family 단위 결정적 bootstrap 2,000회로 95% 신뢰구간을 계산한다.
- 성공 run만 retrieval plan·상태·입력·embedding batch 크기·PostgreSQL/pgvector 버전·transaction/planner 설정·clean code provenance와 실제 순위를 포함한 새 JSON으로 원자 기록하고 실패 시 부분 결과나 기존 run 덮어쓰기가 없다.
- 평가에 연결된 모든 provision ID는 다른 gold 검사보다 먼저 현재 parser corpus ID 집합과 대조하며, 하나라도 없으면 `non_current_parser_provision_ids`로 즉시 실패한다.
- `/v1/questions`, `/v1/search`, `/v1/provisions/{id}`가 지원 범위 밖 기준일을 임베딩·repository 호출 전에 `422 unsupported_corpus_date`로 거부하고 `/v1/corpus/status`가 snapshot ID와 양쪽 경계를 노출한다.
- 자동 통과 문항과 사람 검토 필요 문항이 분리된다.
- API·collector·core 테스트, Ruff, 문서 검사가 통과한다.

## TODO

### 2026-08-03 retrieval 계보 재감사

- [x] 담당: 주 에이전트 — BM25를 구현하지 않고도 corpus snapshot, retriever profile, index build, retrieval configuration/release를 독립적으로 추적할 수 있는 additive migration `0011`과 계약 테스트를 추가한다.
- [x] 담당: `retrieval_catalog_docs` — 확정 스키마와 현재 exact dense/HNSW 보류 경계를 설계·생성·학습 문서에 반영하고, 과거 실행 보고서의 HNSW 승격 조건 설명을 바로잡는다.
- [x] 담당: 주 에이전트 — 전체 diff와 기존 사용자 변경 비혼입을 검토하고 로컬 검증 후 운영 DB에 migration만 적용한다. 데이터셋 검색, NVIDIA 질문 임베딩, BM25/RRF, 새 HNSW 작업은 실행하지 않는다.
- [ ] 담당: 사용자 → 주 에이전트 — 1,000문항 질문 문구와 범위를 승인한다. 승인 전에는 approval manifest, pilot, gold/qrels, 실제 실험 D를 생성하거나 실행하지 않는다.

- [x] 현재 코드·마이그레이션·문서와 기존 사용자 변경 범위를 감사한다.
- [x] 공식 RAG 평가 자료를 비교하고 실험 D 평가 계약을 확정한다.
- [x] 임베딩 프로필과 독립 검색기 경계를 설계 문서로 확정한다.
- [x] DB 마이그레이션·도메인 타입·repository·테스트를 구현한다.
- [x] 반복 가능한 임베딩 backfill·상태 확인 CLI와 테스트를 구현한다.
- [x] 운영 DB와 분리된 재개 가능 로컬 벡터 체크포인트 생성·검증·적재 경로를 구현한다.
- [x] 운영 DB를 마이그레이션하고 벡터를 실제 생성한다. 함께 생성된 물리 HNSW 인덱스는 삭제하지 않되 현재 품질 평가에서 사용하지 않는 보류 자산으로 분류한다.
- [x] 과거 parser 기반 synthetic 1,000문항 생성기·검증기·초안·검토 큐를 제거하고 일반 사용자 gold 경로만 유지한다.
- [x] 전체 회귀 검증, 실제 건수 감사, 문서화와 기능별 커밋을 완료한다.
- [x] 과거 synthetic 생성 규칙과 그 산출물을 제거한다.
- [x] 현재 파서로 운영 corpus를 재수집하고 변경된 조문의 벡터를 다시 생성한다.
- [x] synthetic control 재사용을 폐기하고 현재 parser corpus에 없는 모든 평가 연결 ID를 즉시 오류로 차단한다.
- [x] 미승인 draft 또는 현재 corpus와 맞지 않는 qrels를 탐지하는 독립 읽기 전용 gold preflight를 추가한다.
- [x] approved-gold-only 평가 runner에서 초기 preflight와 corpus 공유 transaction lock 안의 locked preflight를 강제하고 마지막 검색까지 같은 corpus를 유지한다.
- [x] raw provision top 11 경계 검사, Recall/HitRate/Precision/MRR@10/nDCG/facet metric core, query plan·retrieval state·critical code 지문과 원자적 결과 게시를 구현하고 합성 fixture로 검증한다.
- [x] 실험 D runner에서 HNSW 상태·게이트·결과 비교를 제거하고 exhaustive exact cosine만 남긴다.
- [x] 운영 dense 검색도 exhaustive exact cosine으로 고정해 HNSW가 수동 검색 검증에 섞이지 않게 한다.
- [x] 기존 `hnsw_ready`를 backfill 프로필 승격과 exact 검색 준비 조건에서 제거하고 상태 진단값으로만 남긴다.
- [x] 현재 corpus 지원 기준일 `2026-06-03..2026-08-03`을 backend에 고정하고 범위 밖 요청을 검색 전에 차단하며 상태 API에 경계를 노출한다.
- [ ] 프런트 날짜 선택기가 상태 API의 지원 범위를 표시하고 범위 밖 선택·제출을 막는다. 서버 `422`는 최종 권위로 유지한다.
- [x] 일반인 gold의 질문 승인·answerability·facet·qrel·기준문맥·blind 주석·split 불변조건을 실행 가능한 Pydantic 계약으로 고정한다.
- [x] 질문 승인과 gold adjudication을 별도 manifest로 분리하고 전체 dataset·문항별 canonical hash 및 승인 시간 순서를 preflight에서 검증한다.
- [x] pool 방법별 exact top-k·후보 hash·합집합과 문항 기준일별 full-corpus population 불변조건을 실행 계약과 preflight에 추가한다.
- [x] held-out test fully-answerable만 primary로 두고 calibration·combined를 diagnostic-only로 분리한다.
- [ ] 사용자가 수동 검토 10문항과 실험 D 질문 구성을 확인한다.
- [ ] 사용자 확인 후에만 1,000문항을 검색기에 입력해 실험 D 지표를 측정한다.
- [x] 공식기관 공개 FAQ·절차 주제로 일반 사용자형 에너지 질문 후보 1,000개를 별도 생성한다.
- [x] 일반 사용자 질문은행이 Recall 평가셋이 아니라 질문 검토 중간 산출물임을 설계·출처 문서에 명시한다.
- [x] 일반 사용자 질문 1,000개를 세 구간으로 전수 읽고 상황 불일치·중복 의도·위험 작업 표현을 교정한다.
- [x] 대표 15문항과 고위험 35문항을 모은 질문 승인 검토표와 전체 질문 해시 검증기를 만든다.
- [x] 승인 manifest가 있을 때만 만들 수 있는 50문항 질문 전용 pilot 작업표 생성기와 엄격한 non-gold 계약을 만든다.
- [x] 사용자가 일반 사용자 질문 문구와 범위를 승인하고 실제 question approval manifest를 만든다. pilot 작업표와 gold 주석은 별도 후속 단계로 남긴다.
- [ ] 사용자가 일반 사용자 질문을 승인한 뒤 별도 gold 파일에 answerability·필수 답변 요소·qrels·기준 답변을 독립 주석한다.
- [ ] 승인·주석·adjudication을 마친 실제 1,000문항만 runner로 실행하고 결과를 기록한다.
- [ ] 1,000문항 gold와 근거 찾기 전수 검증 완료 후 HNSW 설계안을 별도로 제시하고 사용자 승인을 받는다.

## 검증과 롤백

- 마이그레이션 전 테이블·함수·행 수·프로필별 벡터 수를 읽기 전용으로 기록한다.
- 새 테이블에 복사하고 계약 검증을 마친 뒤 기존 구조를 교체한다.
- 임베딩 backfill은 기존 조문이나 원문을 수정하지 않고 파생 벡터만 upsert한다.
- 실패 시 이미 생성된 동일 해시 벡터를 보존하고 재실행으로 미완료 행만 처리한다.
- 운영 데이터 삭제가 필요한 예상 밖 상태가 발견되면 진행을 멈추고 사용자에게 대상과 복구 방법을 보고한다.

## 결정 로그

- 2026-08-03: 현재 검색 알고리즘은 dense-only로 유지하며 BM25·RRF는 평가셋 확장 후 비교한다.
- 2026-08-03: 미래 검색 결합 가능성은 `hybrid_search` 같은 DB 내 고정 RRF 함수가 아니라 독립 retriever 결과와 버전이 있는 평가 계층으로 확보한다.
- 2026-08-03: 사용자 요청에 따라 마이그레이션과 임베딩 backfill은 설계·테스트 완료 후 실제 운영 DB에 실행한다.
- 2026-08-03: 일반 사용자형 1,000문항은 질문 후보 은행으로 분리한다. 정답 없는 상태가 더 좋은 평가라는 뜻이 아니며, 질문 승인 후 별도 gold 주석 없이는 Recall을 계산하지 않는다.
- 2026-08-03: 실험 D primary dense baseline은 문항 기준일의 전체 유효 population을 비교하는 exhaustive exact cosine으로 고정한다.
- 2026-08-03: HNSW는 1,000문항 gold와 근거 찾기를 모두 검증한 뒤 별도 설계를 제시하고 사용자가 명시적으로 승인할 때까지 보류한다. 기존 물리 인덱스는 삭제하지 않지만 현재 runner의 상태·게이트·결과에 사용하지 않는다.
- 2026-08-03: 현재 corpus 지원 기준일은 `2026-06-03..2026-08-03` 양끝 포함이다. 범위 밖은 부분 corpus 검색 대신 backend에서 차단하고, 프런트 차단은 후속 TODO로 둔다.
- 2026-08-03: 취소된 v2 12문항 전체본은 생성하거나 수정하지 않는다.
- 2026-08-04: 과거 parser 기반 synthetic dataset·qrels·생성·검토 경로와 API parser 호환 래퍼를 삭제하고 core parser v3 하나만 사용한다.
- 2026-08-04: 평가 JSON의 모든 `provision_id`와 `*_provision_ids`는 현재 searchable corpus ID 집합과 한 번 대조하며, 하나라도 없으면 다른 gold 검사보다 먼저 `non_current_parser_provision_ids`로 실패한다.

## 진행 기록

- 2026-08-03: DB에는 현재 호출되지 않는 4인자·5인자 `hybrid_search` 함수 계보와 RRF 설명이 남아 있고, `provision_embeddings`가 모델 정보와 벡터 변환 계약을 한 행에 혼합함을 확인했다.
- 2026-08-03: 전체 조문 임베딩을 반복 가능하게 채우는 운영 CLI가 없음을 확인했다.
- 2026-08-03: pgvector 공식 권고에 따라 차원 가변 열과 현재 프로필 전용 512차원 partial expression HNSW 인덱스를 구현했다.
- 2026-08-03: NVIDIA의 retrieval/answer 분리, BEIR qrels, LlamaIndex labelled RAG 구조를 결합한 법률 평가 계약을 확정했다.
- 2026-08-03: 실제 Supabase 3,066개 조문을 읽어 2,569개 유효 근거를 기준으로 1,000문항을 생성했다. calibration 200/test 800, positive 850/negative 150, 수동 검토 12개다.
- 2026-08-03: API 테스트 268개(2개 skip), Ruff, 문서 검사 117개를 통과했다.
- 2026-08-03: 운영 DB 마이그레이션 실행은 승인 검토에서 서비스 중단 위험 때문에 거부됐다. DB는 0004 상태이며 0008 적용과 벡터 backfill은 사용자 명시 승인 대기다.
- 2026-08-03: 승인 대기 중에도 NIM 벡터 생성을 진행할 수 있도록 `.data/embeddings/` JSONL 체크포인트를 추가했다. 원문은 저장하지 않으며 중단 후 해시 기준으로 재개할 수 있다.
- 2026-08-03: NVIDIA NIM passage 벡터를 로컬 체크포인트에 3,066/3,066개 생성했다. 512차원, L2 norm, 현재 본문 해시를 전부 검증했으며 누락·stale은 0개다. 완성 후 재실행 결과 API 생성은 0건이었다. 파일은 33,696,689바이트이고 SHA-256은 `0D828204D71A389534B6B20F1A3392FFEA5AFA18C4625CE97E410E28E36F89EE`다. 운영 Supabase는 계속 0004/벡터 0건 상태로 보존했다.
- 2026-08-03: 체크포인트 변경 후 API 271개 통과(2개 skip), core 4개, collector 37개, Ruff, 문서 검사 118개를 통과했다.
- 2026-08-03: 사용자 승인 후 운영 Supabase를 `0004→0008`로 마이그레이션했다. 최종 상태는 조문 3,066개, 현재 프로필 벡터 3,066개, 누락·stale·비단위 벡터 각 0개, HNSW ready, hybrid 함수 없음이다.
- 2026-08-03: 실제 query 임베딩 검색에서 `query_dimensions=512`, `retrieval_strategy=dense_only`를 확인했다. “태양광 발전 설비는 법에서 어떻게 정의하나요?”의 1위는 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 `제2조/호3.`이고 cosine 점수는 `0.590565657053332`였다.
- 2026-08-03: 최종 회귀 검증은 API 275개 통과(2개 skip), core 4개, collector 37개, Ruff, 문서 검사 118개를 통과했다. 실험 D 전용 검증 2개도 통과했다.
- 2026-08-03: 실험 D 전용 검증은 JSON 구조, 1,000개 개수, 분할·범주 비율, qrels의 참조 무결성만 검사했다. 1,000개 질문을 실제 검색기에 입력하는 검색 품질 실험은 실행하지 않았다.
- 2026-08-03: 사용자 검토를 위해 검색을 호출하지 않는 전체 1,000문항 Markdown 검토본을 생성했다. 추가 정적 감사에서 장·절 구조 표지가 조문 답으로 연결된 7개, 삭제 조문이 일반 대조군에 포함된 32개, 기준 답과 문자열 유사도 0.80 이상인 `semantic_paraphrase` 116개를 발견했다. 제9000조대 outside-corpus 75개는 의도된 합성 음성 대조군이며, hard-contrast 100개는 모두 distractor ID를 가진다.
- 2026-08-03: v2 감사 결과를 반영한 v3 검토 초안을 생성했다. 구조 표지·삭제 조문·문자열 유사도 0.80 이상 의미 질문·유사도 0.30 미만 hard distractor는 각각 0개다. outside-corpus 75개는 실제 corpus 밖 법률 질문 60개와 존재하지 않는 조문 15개로 나눴고, 수동 검토는 11개다.
- 2026-08-03: v3 변경 후 실제 검색을 호출하지 않는 정적·단위·회귀 검증을 완료했다. API 276개 통과(2개 skip), collector 37개, core 4개, Ruff와 문서 120개 검사가 통과했다. 1,000문항 검색 품질 실험은 실행하지 않았다.
- 2026-08-03: 수동 검토 중 `다음 각 호·목`을 여는 조각의 하위 문맥이 qrels에서 빠진 사례를 발견했다. 질문 후보 최소 길이와 근거 문맥 최소 길이를 분리해 짧은 하위 호·목도 evidence closure에 포함했고, 자동 감사의 누락 수를 0개로 만들었다.
- 2026-08-03: 의미 질문은 행위 주체 역할명을 선택적으로 포함하고 동일 질문이 복수 근거를 가리키는 후보 212개를 제외한다. 재생성 결과 1,000문항, 수동 검토 10개이며 검색 실험은 실행하지 않았다.
- 2026-08-03: evidence closure 변경 후 API 279개 통과(2개 skip), collector 37개, core 4개, Ruff와 문서 121개 검사가 통과했다. 실제 데이터셋 검색·순위·점수 측정은 실행하지 않았다.
- 2026-08-03: 공공기관 FAQ·절차 안내 15개에서 질문 주제만 조사해 일반 사용자형 합성 질문 1,000개를 별도 생성했다. 정규화 중복·근접 중복·법조문형 표현·길이·형식 오류는 각각 0개이며, 정답·qrels·기대 문서는 포함하지 않았다. 이 질문은행을 검색기에 입력하는 실험은 실행하지 않았다.
- 2026-08-03: 초기 200개 상황×공통 후속문 조합을 전체 읽기 감사한 결과 의미 충돌과 부정확한 사용자 유형·단계·scope 가설을 발견했다. 상황별 호환 질문 묶음으로 세분화하고 문항별 자동 메타데이터를 제거했으며, 출처는 주제 수준의 영감 자료임을 명시했다.
- 2026-08-03: 1,000문항을 1–350, 351–700, 701–1000 세 구간으로 다시 전수 읽어 상황과 공통 문구가 어긋난 문항, 독립 질문에서 선행 문맥이 빠진 문항, 일반인이 전기설비를 직접 조작하도록 읽힐 수 있는 문항을 교정했다. 2026-08-04 `lay-energy-0511` 사용자 수정을 더해 최종 생성기는 전수 읽기 교정 163건을 ID별로 고정하며, 질문 세트 SHA-256은 `523325a6d86d2503492ff4dd8479f0a7e6045950dcef9288f970da0ae44d5a1a`이다.
- 2026-08-03: 일반 사용자 gold는 질문 승인 뒤에만 작성한다. answerability를 full·partial·clarification·unanswerable로 구분하고, 넓은 질문은 필수 답변 요소별 qrels와 facet coverage를 평가하도록 계약을 보강했다.
- 2026-08-03: 질문 문구 SHA와 별도로 scenario family·intent·technology·질문 변형까지 포함한 scope SHA를 도입했다. 승인 후 split에 영향을 주는 범위 메타데이터를 다시 계산해 바꾸는 것을 preflight가 거부한다.
- 2026-08-03: 문항별 판정 pool은 외부 경로만 선언하지 않고 모든 후보 ID와 후보 집합 SHA를 gold 안에 직접 고정한다. 모든 후보는 positive qrel 또는 distractor로 전수 분류하며 실제 searchable provision 전체와 대조한다.
- 2026-08-03: Recall·HitRate·MRR@10·nDCG 모집단은 fully answerable로 한정하고 partial·clarification·unanswerable은 별도 지표로 보고한다. 검증하지 않는 stratified/seed 주장은 제거하고 200/800 family 배정 자체를 동결한다.
- 2026-08-03: 후보 질문은행의 법령명 목록 해시를 실제 parser corpus fingerprint와 분리했다.
- 2026-08-03: `scripts.preflight_experiment_d_gold`가 승인 상태, 질문 문구·범위 해시, corpus fingerprint, qrel ID·원문 SHA·메타데이터를 읽기 전용으로 검증하도록 추가했다. 독립 CLI는 임베딩과 검색을 실행하지 않으며, 실제 runner는 같은 검사를 초기 단계와 corpus 공유 잠금 안에서 다시 수행하도록 연결했다.
- 2026-08-03: 운영 DB에서 과거 평가 ID가 현재 corpus와 맞지 않음을 확인했으며 해당 평가 산출물은 2026-08-04에 제거했다.
- 2026-08-03: Vercel CLI 58.1의 backend framework rewrite 동작 변경으로 catch-all rewrite가 `/health`와 `/v1/*`를 `/app/main.py`로 바꾸어 404를 내는 것을 빌드·런타임 로그로 확인했다. rewrite를 제거하고 `app.main:app` entrypoint를 명시한 `f44f045`를 배포해 운영 별칭의 health와 OpenAPI route를 복구했다.
- 2026-08-03: 운영 Supabase를 `0010 (head)`로 올리고 capability=true, corpus gate=false와 API `503 corpus_unready`를 확인한 뒤 parser v3로 9개 문서·3,066개 조문을 다시 동기화했다. 수집은 JSON 9/9, fallback·실패 0이고 재미리보기 변경도 0이다.
- 2026-08-03: parser v3 체크포인트에서 2,956개 벡터를 동일 passage SHA로 재사용하고 110개만 NVIDIA NIM에서 새로 생성했다. 3,066개를 DB에 적재한 뒤 누락·stale·비단위 벡터 0, HNSW ready, profile active, corpus search ready를 확인했다. 체크포인트는 67,393,498 bytes, SHA-256 `3E335D908B00EA87F88648358A8CCB3DB2823A79562B781E6CBFC54350F9673F`다.
- 2026-08-03: 실험 D 데이터셋을 실행하지 않고 운영 smoke query 1개만 확인했다. 512차원 dense-only 결과 1위는 신재생에너지법 `제2조/호3.`이고 cosine은 `0.590565657053332`였다.
- 2026-08-03: `scripts.evaluate_experiment_d_gold` runner를 구현했다. clean critical code provenance와 초기 preflight·retrieval 상태 검증 뒤에만 질문을 임베딩하고, corpus mutation 공유 transaction lock 안에서 locked preflight·exact query plan capture와 모든 raw provision 검색을 수행한다.
- 2026-08-03: runner는 질문마다 11개를 조회해 raw cosine 내림차순·provision ID tie-break·중복·유한값을 확인하고 10/11 동점이면 실패한다. 결과에는 corpus·vector·query plan·critical code 지문, 실제 순위와 지표를 담고 전체 성공 후에만 새 run 파일을 원자 게시한다.
- 2026-08-03: metric core는 fully answerable에서 grade 2 qrels의 Recall·HitRate·Direct Precision, grade 1+2 Precision, MRR@10, grade 2/1 nDCG@1/3/5/10, supported facet recall과 전체 facet 충족률을 계산한다. primary는 scenario-family macro와 family bootstrap 95% 신뢰구간이며 partial·clarification·unanswerable은 core 평균과 분리한다.
- 2026-08-03: 질문 approval manifest와 gold adjudication manifest를 분리했다. adjudication manifest는 전체 gold dataset과 문항별 완성 payload의 canonical SHA-256을 봉인하며, preflight는 모든 문항에서 질문 승인·독립 review·최종 adjudication의 엄격한 시간 순서를 확인한다.
- 2026-08-03: annotation pool은 방법별 설정 SHA-256·exact top-k·후보 ID 집합 SHA-256을 기록한다. 방법별 후보의 합집합은 판정 pool과 같아야 하고 full-corpus 검토는 각 문항 기준일의 전체 유효 검색 population과 같아야 한다.
- 2026-08-03: 초기 구현에서는 `REPEATABLE READ, READ ONLY` 상태 점검과 공유 advisory lock을 얻는 `READ COMMITTED, READ ONLY` 검색 구간을 분리하고 HNSW plan 여부도 검사했다. 후속 보류 결정으로 HNSW 검사 필드는 제거했으며 transaction·잠금·exact plan 기록은 유지한다.
- 2026-08-03: 운영 읽기 전용 plan 감사에서 물리 HNSW는 valid·ready였지만 현재 3,066개 production 형태 query는 exact sort를 선택했다. HNSW 후보 CTE는 현재 기준일에는 빨랐지만 과거 기준일 유효 행을 0/3/7개만 반환한 사례가 있어 primary 품질 기준선으로 채택하지 않았다.
- 2026-08-03: 초기 구현의 성공 payload에는 HNSW 물리 identity·valid/ready 상태도 포함했으나 후속 보류 결정으로 제거했다. 현재 payload는 실제 embedding batch 크기, PostgreSQL·pgvector 버전, transaction·planner 설정, clean Git commit과 핵심 파일 SHA-256을 기록한다. primary metric은 held-out test fully-answerable이고 calibration·combined는 diagnostic-only다.
- 2026-08-03: runner 동작은 합성 fixture로만 검증했다. 사용자 승인, 독립 gold 주석과 adjudication이 끝나지 않았으므로 실제 일반 사용자 1,000문항의 NVIDIA 임베딩·검색·지표 실행은 하지 않았다.
- 2026-08-03: 후속 결정으로 runner의 HNSW identity·valid/ready 상태와 plan 비교 필드를 제거했다. 기존 물리 인덱스와 과거 plan 감사값은 역사적 사실로만 보존하며 현재 품질 결과로 사용하지 않는다.
- 2026-08-03: 운영 DB 읽기 전용 감사에서 9개 open version, 3,066개 provision, 가장 늦은 `effective_from=2026-06-03`, snapshot through `2026-08-03`을 확인해 현재 지원 범위를 코드·API에 고정했다.
- 2026-08-04: 질문 승인 검토에서 고위험 35문항을 유지 2개, `clarification_required` 검토 의도 12개, `unanswerable` 검토 의도 21개로 확정했다. `lay-energy-0511` 문구를 수정한 새 질문·범위 해시로 1,000문항 question approval manifest를 생성했으며 gold 주석·임베딩·검색은 실행하지 않았다.
- 2026-08-03: retrieval 계보 재감사에서 독립 검색기의 설정·build·release와 평가 실행을 같은 corpus 세대에 묶을 DB 계약이 없음을 확인했다. Additive migration `0011`로 8개 catalog 테이블과 평가 계보 열을 추가해 운영 Supabase에 적용했다. 적용 후 `0011 (head)`, 조문·현재 벡터 각 3,066개, 누락·stale·비단위 벡터 0, profile·corpus gate 활성, `hybrid_search` 없음이 유지됐다. 질문 데이터셋, NVIDIA 질문 임베딩, BM25/RRF와 새 HNSW 작업은 실행하지 않았다.

## 잔여 검토

- NVIDIA API는 32개 사전 배치와 전체 재개 실행으로 확인했으며 실패 없이 3,066개를 생성했다.
- 일반 사용자 질문 승인 뒤 blind candidate pool의 모든 후보를 qrel 또는 distractor로 판정하고, 작성자와 다른 검토자가 answerability·필수 요소·reference response를 adjudication해야 한다.
- 1,000문항 gold와 근거 찾기 전수 검증이 끝난 뒤에만 HNSW 설계안을 작성하고 사용자 승인을 요청한다. 승인 전에는 관련 실행·비교를 하지 않는다.
- 프런트는 후속 작업에서 `/v1/corpus/status`의 지원 범위를 읽어 날짜 선택·제출을 막는다.

## 현재까지 결과

- 현재 검색 경로는 dense-only이며 BM25·hybrid·RRF·reranker는 도입하지 않았다.
- DB는 모델 이름만이 아니라 query/passage 유형, 원본·저장 차원, 축약·정규화, 본문 템플릿 버전을 프로필로 추적한다.
- 운영 parser v3 corpus 9문서·3,066개 조문에 현재 NVIDIA 512차원 passage 벡터가 준비됐고, 모델 독립 corpus gate와 profile gate가 모두 활성화됐다. 기존 partial HNSW 인덱스는 물리적으로 남아 있지만 현재 품질 평가와 HNSW 승인 판단에 사용하지 않는 보류 자산이다.
- 과거 parser 기반 synthetic 검토 초안과 qrels는 삭제했으며 다시 평가 입력으로 사용하지 않는다.
- 실험 D 실제 검색 실행과 Recall/HitRate/Precision/MRR@10/nDCG/facet 결과 산출은 독립 gold 주석·adjudication, gold adjudication manifest와 initial/locked preflight가 모두 끝난 뒤에만 진행한다. 질문 문구·범위 승인은 완료했다.
- 일반 사용자 질문은행은 질문 승인을 마쳤지만 아직 gold가 아니므로 자체로 Recall/HitRate/Precision/MRR@10/nDCG를 산출할 수 없다. 독립 근거 주석을 완료한 문항만 현실적 자연어 평가셋으로 사용한다.
- 미래 BM25는 독립 retriever로 측정한 뒤 동일 qrels에서 dense-only보다 개선되는 경우에만 별도 실험으로 채택한다.

# Graph Report - law-rag  (2026-09-03)

## Corpus Check
- 602 files · ~500,836 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 8006 nodes · 15726 edges · 500 communities (416 shown, 84 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1267 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1d31c902`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- experiment_search.py
- ProvisionRecord
- publish_prepared_bundle
- law_json.py
- 실행 계획 0022: 검색 인덱스 재설계와 실험 D 1,000문항 평가셋
- RawResponse
- anonymous_rate_limit_subject
- evaluate_experiment_d_gold.py
- experiment_d_manual_review.py
- postgres_repository.py
- test_experiment_d_gold_preflight.py
- 실행 계획 0002: 실제 서비스 연결
- corpus_update_bundle.py
- MemoryLegalRepository
- 0025 Approved Questions to Grounded Answer Roadmap
- test_question_timeout_budget.py
- MemoryQuestionCancellationCoordinator
- SearchTrace
- NvidiaNimEmbedder
- test_experiment_d_pilot_worklist.py
- test_experiment_d_gold_contract.py
- prepared_publisher.py
- LawOpenApiClient
- Lay energy question bank v1 draft
- evaluate_dense_retrieval
- LlamaIndex Module Guides and law-rag v2
- Settings
- devDependencies
- SearchHit
- question_scope_set_sha256
- PostgresLegalRepository
- experiment_d_gold_contract.py
- Single QuestionRouter
- create_experiment_d_question_approval.py
- test_experiment_d_gold_runner.py
- HnswIndexManager
- ingestion/service.py
- DeletionRecord
- law_rag_core/domain/schemas.py
- experiment_d_10_frozen_contract.py
- Settings
- Energy-law RAG architecture
- test_ingest.py
- chat-state.ts
- QuestionRequest
- ROADMAP.md
- RoadmapRegistryFixtures
- Vercel Web and FastAPI
- experiment_d_local_rerank.py
- render_experiment_d_layperson_approval_review.py
- 0043 Layperson Answer Contract v2
- MockIdentityRepository
- V2QuestionExecutionService
- SourceKind
- preflight_experiment_d_gold.py
- experiment_d_10_gold_review.py
- RouteJudgment
- get_settings
- design-docs/index.md
- experiment_d_manual_review_contract.py
- _GenerationRepository
- api-client.ts
- CorpusSnapshot
- law_rag_collector/service.py
- compilerOptions
- diagnose_grounding_failures.py
- api/dependencies.py
- DenseCandidate
- law_rag_core/domain/catalog.py
- experiment_d_manual_review_results.py
- experiment_d_pilot_contract.py
- page.tsx
- 토큰 컨텍스트·서버 취소·검색 범위 개선
- _answer_question
- PostgresQuestionExecutionRepository
- 기술·로직 부채 감사
- LlamaIndexLegalRepository
- corpus.py
- search_only_answer
- parse_provision_references
- AGENTS.md
- roadmap_registry.py
- ports/question_execution.py
- test_backfill_embeddings.py
- PostgresIdentityRepository
- run_experiment_0043_v1_v2_compare.py
- test_prepared_update.py
- PostgresExperimentDBackend
- AgentState
- _node
- NvidiaNimQuestionRouter
- Experiment D-10 Gold review draft
- Evaluation and Experiment Reading
- test_layperson_prompt_v2.py
- experiment_d_10_context_assembly.py
- CorpusTemporalState
- 실행 계획 0008: 4단계 검색, 1초 지연 목표, RAG 디버깅
- LegalRepository
- corpus_preflight.py
- contracts.ts
- Evidence-First Retrieval and Answers
- 전기사업법 제12조 허가 취소 등
- test_question_cancellation.py
- main.py
- RouteDecision
- generation-retry.ts
- 0053 LlamaIndex v2 Retrieval Pipeline
- Clarification Loop Handling Plan
- Law Corpus Lifecycle
- User, Privacy, and Failure Safety
- 코퍼스 운영·롤백 런북
- ExecutionPhase
- 실행 계획 0025: 승인 질문에서 근거 기반 AI 답변까지
- OpenAI Vector embeddings
- 일반 사용자형 에너지 질문 의도 설계
- Nemotron 3 Embed 1B
- check_docs.py
- v1/answering.py
- 사용 중·조건부 추천 상세
- Database schema
- Alembic autogenerate
- Energy Business Legal Chat
- D-10 수동 검색·문맥 진단
- PlanRecord
- test_v2_search.py
- V2 LlamaIndex 검색(Retrieval) 파이프라인 구현 계획
- LegalDocumentRecord
- derive_answer_action
- query/retriever.py
- Security and Privacy
- New User Onboarding
- select_generation_hits
- MemoryQuestionExecutionRepository
- test_prepared_publisher_postgres.py
- GenerationResult
- _RowsResult
- CorpusSearchStatus
- System Map and Execution Boundaries
- Discord Error Ledger
- Repository Rules (AGENTS.md)
- test_experiment_d_manual_review_results.py
- _BeginContext
- V2: LlamaIndex 프레임워크 파이프라인 개편 설계
- test_graph.py
- test_api_factory_composition.py
- ExperimentDBackend
- 실행 계획 0020: 실험 D — 검색 문맥 구성
- RAG 평가 방법 공식 자료
- scripts
- RetrievalGeneration
- sse.py
- PostgresGenerationRepository
- 실행 계획 0017: 실험 B — NVIDIA NIM 두 문장 임베딩과 코사인 유사도
- cli.py
- checklist-export.ts
- Product Sense
- fetch_provisions
- Production retrieval debug revision 0004
- Operational vector index build report
- 실험 C Dense 검색 후보 관찰
- 2026-07-19 사건
- bootstrap.py
- test_non_model_endpoint_latency.py
- test_mock_auth_history.py
- Reliability
- Dense article-level search baseline
- Experiment D search context safety gate
- R1 plus A
- Reciprocal Rank Fusion
- test_security_boundaries.py
- QuestionTaskRegistry
- test_experiment_d_local_rerank.py
- Traffic Routing Calibration Review
- V2 Chunking Ablation
- V2 Dynamic Today Date Bound Plan
- Output 512 dimensions
- Project Roadmap
- Qwen3:4b 연결 준비사항
- FrozenCitation
- 실험 D — 검색 문맥 안전 게이트 평가
- legal_search_router
- ActiveGenerationIndexProvider
- validate_node
- Corpus Support Range
- Exhaustive Exact Dense Search
- law-rag-agent Workspace
- 실행 계획 0006: 예시 질문 기반 답변 품질 평가
- 질문 이력 보존 정리 작업 실행 계획
- 실행 계획 0021: 프로덕션을 근거 우선 실험 설계와 정렬
- 0034 Web Auth Rehydration Throttle
- Distributed Question Cancellation Plan
- Todo Execution Plans Index
- Evaluation Harness Consolidation Plan
- Live Search Reranking Plan
- Provider-Neutral Answer Model Selection Plan
- R1 local rerank
- Experiment D-10 manual diagnostic
- RAG 검색·근거 선택 패턴
- 검색 성능·관측 공식 자료
- vercel.json
- answer-mode.ts
- Embedding Profile
- 실행 계획 0001: MVP 기반 확정
- 실행 계획 0016: 실험 A — 일반 텍스트 조문 청킹 관찰
- Harness Engineering 적용 메모
- route.ts
- post_edit_lint.py
- LangGraph StateGraph
- 실행 계획 0003: 채팅 중심 웹 경험
- 학습 노트 통합 실행 계획
- Article 12 license cancellation
- account.py
- 0034: 웹 프런트 탭 포커스 시 불필요한 인증·이력 재조회 억제
- Application Trust Boundary
- v2 Dense Retriever
- E-10 Base Execution
- Active Execution Plan Index
- 0059 Task Management Metadata and Roadmap
- Experiment A chunking results
- 실제 터미널 출력
- v2-execution.ts
- Quality Scorecard
- 로드맵 정본·컨텍스트 절약 설계
- 4. 평가와 실험 읽기
- Vercel·Supabase 운영 전환 설계
- dialog-focus.ts
- web/proxy.ts
- Current State Session Start Pointer
- Execution-Plan Metadata Contract
- Effective-Date Half-Open Interval
- Korean translation materials
- 실행 계획 0018: 실험 C — 지정 장·조 로컬 벡터 검색
- 참고 자료 카탈로그
- Expired Question-History Purge
- law-rag-api
- SupabaseRawStorage
- 0004_retrieval_diagnostics.py
- 0006_history_retention_job.py
- 0007_embedding_model_filter.py
- test_history_retention_migration.py
- test_v3_thread_migration.py
- 0036 Account Modal Model Label
- 0037 Account Quota Toggle
- 0056 Python Docstrings and Ruff D
- Electricity permit sentence A
- lay-energy-0346 rerank case
- .ready_state_has_complete_bounds
- Bug issue form
- GitHub CI workflow
- layout.tsx
- LlamaIndexLegalRepository
- Completed Execution Plans Index
- 실행 계획 0026: 실험 D-10 수동 검색·문맥 진단
- NVIDIA 로컬 추론과 Vercel 연결 검토
- RLS and auth.uid ownership
- Issue-template configuration
- Documentation issue form
- Feature or improvement form
- vector_index_contract.py
- next.config.ts
- postcss.config.mjs
- Tasks 12-16 Not Started
- P0-P3 Priority Levels
- corpus.search_ready capability gate
- audiovisual-rights-transfer-presumption
- copyright-act-purpose
- electricity-commission-functions
- renewable-basic-plan-cycle
- solar-is-renewable-energy
- Relevance 1 count 3
- 0601 relevance correction
- 직접 포트 공개 금지
- NVIDIA Hosted NIM Trial Endpoint
- NIM OpenAI 호환 API
- chunking/__init__.py
- context/__init__.py
- law_rag_core/__init__.py
- sharp and unrs-resolver build allowlist
- .write_nodes
- Normal Guidance Routes
- XSS and SSRF
- Seoul icn1 Region
- account_usage table
- anonymous_usage table
- derived_obligations table
- evaluation_runs table
- ingestion_runs table
- legal_relationships table
- PGroonga indexes
- Unrelated solar-energy sentence
- lay-energy-0561
- lay-energy-0605
- lay-energy-0836
- lay-energy-0943
- Relevance 0 count 30,622
- Gold sealed false
- Known irrelevant top-5 count 28 to 18
- Corpus evidence gap for 0605, 0836, and 0943
- M3 manual direct evidence
- R1+A calibration winner
- R1 plus B
- Raw plus A
- Context blocked 3
- Context insufficient 6
- Context sufficient 1
- lay-energy-0601 approval case
- lay-energy-0605 approval case
- lay-energy-0881 approval case
- Maintain decision
- Question scope set SHA-256
- Question set SHA-256
- lay-energy-0111
- lay-energy-0381
- lay-energy-0511
- lay-energy-0671
- lay-energy-0741
- lay-energy-0921
- lay-energy-0961
- Minimum latency 90.980 ms
- P50 latency 1,031.311 ms
- P95 latency 5,462.805 ms
- text-embedding-ada-002
- Nine corpus documents
- 3,066 current provisions
- 0060: V2 기준일 지원 상한을 한국 날짜 today로 동적 계산
- V3 LangGraph 에이전트 기본 골격 구현 계획
- 실행 계획 0019: 실험 C — 검색 후보 관찰·기록·평가
- 0028: 검색 전 질문 라우팅과 조건부 query 보강
- 0030: D-10 전수 qrel과 사용자 adjudication
- 작업 관리 메타데이터와 얇은 로드맵
- 실행 계획 0004: Google 인증과 계정 수명주기
- 분산 취소·검색 문법·로컬 AI·부채 감사
- Discord 에이전트 오버레이
- NVIDIA Hosted NIM 생성 모델 연결
- v2 설계
- 실행 계획 0005: 로그인·익명 사용자 전체 흐름 엣지케이스
- 0039: 구조화된 에러 detail이 "[object Object]"로 표출됨
- 실행 계획 0027: 실험 D-10-R1 로컬 재정렬
- 실행 계획 0009: 연속 대화, 이력 페이지네이션, 인증 지연 개선
- NVIDIA RAG 및 이벤트 기반 취소 실행 계획
- 단계 구조
- Auto Generating Migrations
- AnswerEvent
- 실행 계획 0007: Production 자연어 검색과 단계별 관측
- Vector embeddings(벡터 임베딩)
- v1 to LangChain/LangGraph/LlamaIndex Evolution
- Google OAuth·Supabase Auth 연결 설계
- 분산 질문 취소 실행 계획
- 에너지 법령 RAG 아키텍처
- [역사 문서] terra 모드에서 search_only 폴백 제거 (always-generate)
- 검색 인덱스와 임베딩 계보 설계
- v3 설계
- 일반인 답변 계약 v2 설계
- V2 준비 상태와 HNSW 구현 계획
- Use cases
- Matryoshka Representation Learning
- 근거 우선 검색 품질 설계
- install_git_hooks.py
- 국가법령정보 Open API 수집 계약
- 0032: 실험 E-10 — AI 답변 소표본 평가 (0025 M6)
- 2. 법령 코퍼스의 생애주기
- 3. 근거 우선 검색과 답변
- 5. 사용자·개인정보·장애 안전
- Target File Structure
- 분산 질문 취소 설계
- 실험 D-10 전수 qrel과 사용자 adjudication
- Python docstring 정책
- terra 모드 search_only 폴백 제거 (always-generate) Implementation Plan
- 청크
- electricity-business-license-out-of-scope
- 실험 D-10 수동 검색·문맥 진단
- 0024 점검 모드 기반 코퍼스 원자 반영
- 0066: 로드맵 정본·컨텍스트 절약 구현 계획
- 파일 구조
- Web 기준일 선택 상한을 한국 오늘으로 동적 유지 Implementation Plan
- Task 3 실행 보고서: v1/v2 HTTP router 분리
- v1 to v2 to v3 Pipeline Diagram
- Global Constraints
- 평가 전략
- 검토한 선택지
- 실험 D-full 1,000문항 평가 설계
- 이전 finding 확인
- 기술 스택 ADR
- test_postgres_identity.py
- D-010 Single-Stage Router and Safe Routing-Unavailable Response Implementation Plan
- 운영 벡터 인덱스 구축 결과
- FakeResult
- 보안 및 개인정보
- Task 3 실행 보고서: v2 API 리소스 지연 초기화
- completed/README.md
- 답변 근거 검증 설계 (validate_draft)
- RAG 파이프라인 설계
- 실험 D-10 수동 검색·문맥 진단
- 단일 단계 라우터와 라우터 불가 응답
- 0041: 법제처 API의 법종구분코드를 실제로 파싱해 저장·응답에 반영
- 프론트엔드 아키텍처
- 0058: v2 청킹 ablation — 현재 조문 노드 vs LlamaIndex 하위 청킹
- 에너지 사업 법령 채팅
- NVIDIA Nemotron 3 Embed 1B 조사
- 신뢰성
- 0046 기준 질문 파이프라인 지도 갱신 설계
- 실험 D — 검색 문맥 구성
- PhaseDeadline
- Law RAG Collector
- ADR-NNNN: 결정 제목
- 실험 D-10 M2 동결과 M3 소표본 calibration
- 시간 효력 모델
- 6. v1에서 LangChain/LangGraph/LlamaIndex 버전으로: 로직이 어떻게 바뀌었나
- 0033: 트래픽 축적 후 라우팅·관측 재검토 묶음
- F-006 대화형 clarification workflow 설계
- 실험 D-10-R1 부모 표제·직접성 로컬 재정렬
- Task 2 실행 보고서: 관리형 v2 HNSW 인덱스
- D-010 Task 3 Report
- 1. 시스템 지도와 실행 경계
- 0046 기준 질문 파이프라인 지도 설계
- api/__init__.py
- 제품 감각
- 단계
- 실행 순서와 에이전트별 TODO
- 에이전트별 TODO
- 검색 계약
- application/v1/__init__.py
- 실험 C — Dense 검색 후보 관찰
- 실행 계획 운영법
- 검색 성능과 관측 공식 자료
- PULL_REQUEST_TEMPLATE.md
- phase_service.py
- 제품 디자인 원칙
- 2026-07-14 병렬 품질 강화 TODO
- 단계
- RAG 디버깅 보고서 계약
- Agent별 TODO
- 실험 D-10-R1 부모 표제·직접성 로컬 재정렬 결과
- 실험 D-10 사용자 확인 수동 진단
- Production 검색 디버깅 결과: DB revision 0004
- 0045: Web/API 질문 timeout 예산 정렬 Implementation Plan
- CLAUDE.md
- Findings
- 단계별 구조화 관측
- 실제 후보
- Task 4 report: Scoped pre-commit installation and CI enforcement
- 품질 점수표
- 실험 A — 기존 법령 파서 청킹 관찰
- 위협 모델
- 범위와 비범위
- TODO와 에이전트 배정
- 실험 D-10 Gold review draft 요약
- db-schema.md
- 계획 본문
- frontend-api-boundary.test.ts
- GitHub 이슈와 PR 운영
- 질문 사전 라우팅 설계 (0028, 대체됨)
- check_roadmap.py
- Task 2 구현·self-review 보고서
- 0066 final whole-branch review
- Task 1 구현·self-review 보고서
- Task 5 report: Minimal-reading operator workflow and project documentation
- Task 3 report: Normalize current plan headers and remove duplicate status indexes
- Task 4 fix-round 재리뷰 — scoped roadmap pre-commit hook
- Task 5 fix-round re-review — minimal-reading operator workflow
- Task 5 review — minimal-reading operator workflow
- Roadmap Operator
- Task 3 review: Normalize current plan headers and remove duplicate status indexes
- Task 2 independent review
- Task 4 review — changes requested
- SDD ledger — current plan: `docs/exec-plans/completed/0066-roadmap-registry-and-context-diet.md`
- scripts/__init__.py
- task-1-brief.md
- task-2-brief.md
- task-3-brief.md
- task-4-brief.md

## God Nodes (most connected - your core abstractions)
1. `SourceKind` - 110 edges
2. `main_module()` - 107 edges
3. `PostgresLegalRepository` - 82 edges
4. `SearchHit` - 82 edges
5. `QuestionRequest` - 70 edges
6. `MemoryLegalRepository` - 60 edges
7. `RawResponse` - 53 edges
8. `LegalDocumentRecord` - 47 edges
9. `RoadmapRegistryFixtures` - 47 edges
10. `MemoryQuestionExecutionRepository` - 44 edges

## Surprising Connections (you probably didn't know these)
- `임베딩 모델·차원·버전 분리` --semantically_similar_to--> `모델·차원·버전 필터 검색`  [INFERRED] [semantically similar]
  docs/references/nvidia-nemotron-3-embed-1b-2026-07-23.md → experiments/embeddings/README.md
- `프로젝트 1000문항·200 Scenario Family 설계` --semantically_similar_to--> `D-full 1000문항 설계`  [INFERRED] [semantically similar]
  docs/references/rag-evaluation-methods-2026-08-03.md → experiments/d_gold_10/README.md
- `검색 후보와 직접 근거 분리` --semantically_similar_to--> `직접 근거 선택`  [INFERRED] [semantically similar]
  docs/references/rag-retrieval-patterns-2026-08-03.md → experiments/context/README.md
- `Concurrent HNSW DDL` --semantically_similar_to--> `Operator-only v2 HNSW exception`  [INFERRED] [semantically similar]
  .superpowers/sdd/0054-v2-readiness-and-hnsw/task-2-report.md → ARCHITECTURE.md
- `Single-stage NVIDIA QuestionRouter` --semantically_similar_to--> `Single-stage NVIDIA QuestionRouter`  [INFERRED] [semantically similar]
  .superpowers/sdd/0057-single-stage-router-and-failure-response/task-3-report.md → ARCHITECTURE.md

## Import Cycles
- None detected.

## Communities (500 total, 84 thin omitted)

### Community 0 - "experiment_search.py"
Cohesion: 0.05
Nodes (113): _article_chunks(), _atomic_write_many(), _build(), build_context_package(), _candidate_rank(), ContextRecordingError, _evidence_case(), _load_context_runs() (+105 more)

### Community 1 - "ProvisionRecord"
Cohesion: 0.16
Nodes (26): build_nodes(), changed_provision_ids(), Any, ProvisionRecord, TextNode, Pure source-change detection and LlamaIndex node transformations., Return new or changed provisions by comparing canonical passage hashes., Build deterministic LlamaIndex nodes with citation metadata. (+18 more)

### Community 2 - "publish_prepared_bundle"
Cohesion: 0.09
Nodes (35): apply_migration(), drop_database_objects(), load_migration(), asyncio, reset_database(), test_retention_avoids_delete_deadlock_and_counts_actual_export_deletes(), test_retention_is_safe_during_concurrent_turn_save_and_has_strict_acl(), publish_prepared_bundle() (+27 more)

### Community 3 - "law_json.py"
Cohesion: 0.07
Nodes (59): asyncio, test_domain_alias_finds_formal_renewable_energy_title(), test_future_version_is_excluded_before_effective_date(), TextNode, _chunk_payload(), _display_path(), ExperimentRunError, main() (+51 more)

### Community 4 - "실행 계획 0022: 검색 인덱스 재설계와 실험 D 1,000문항 평가셋"
Cohesion: 0.09
Nodes (31): 2026-08-03 retrieval 계보 재감사, approved gold, content-derived corpus snapshot ID, 현재 parser provision ID preflight, D-10 frozen calibration, D-full 1,000문항 0029 이관, 동적 지원 기준일 범위, 임베딩 profile (+23 more)

### Community 5 - "RawResponse"
Cohesion: 0.06
Nodes (49): RawResponse, plan_provision_sync(), ProvisionRecord, SupabaseRawStorage, _corpus_gate_call_indices(), _deletion_repository(), _DeletionConnection, _DeletionEngine (+41 more)

### Community 6 - "anonymous_rate_limit_subject"
Cohesion: 0.27
Nodes (10): anonymous_rate_limit_subject(), _canonical_ip(), daily_subject_hash(), date, Return a canonical, non-persisted subject for anonymous quota hashing. Vercel…, test_daily_subject_hash_hides_and_rotates_ip(), test_forwarded_chain_and_invalid_ip_fail_closed_to_one_subject(), test_ipv4_mapped_ipv6_cannot_create_a_second_subject() (+2 more)

### Community 7 - "evaluate_experiment_d_gold.py"
Cohesion: 0.11
Nodes (40): _arguments(), _atomic_publish(), _audit_or_raise(), _candidate_record(), _canonical_json_bytes(), _capture_query_plans(), _current_code_provenance(), _embed_all_questions() (+32 more)

### Community 8 - "experiment_d_manual_review.py"
Cohesion: 0.10
Nodes (48): _arguments(), _article_contexts(), _article_root(), _atomic_publish_run(), _atomic_write_query_cache(), _cache_file_sha256(), _cache_key(), _canonical_json_bytes() (+40 more)

### Community 9 - "postgres_repository.py"
Cohesion: 0.08
Nodes (33): Corpus 항목 상태 조회를 v1 저장소에 위임한다., _async_url(), _corpus_items(), _corpus_temporal_population_statement(), _corpus_temporal_state(), _dense_search_parameters(), _dense_search_statement(), _elapsed_ms() (+25 more)

### Community 10 - "test_experiment_d_gold_preflight.py"
Cohesion: 0.14
Nodes (42): embedding_text_sha256(), EmbeddingProfile, legal_provision_embedding_text(), Build the versioned passage text used for provision embeddings., canonical_gold_dataset_sha256(), Hash the complete validated gold dataset using canonical JSON., audit_gold_dataset(), question_set_sha256() (+34 more)

### Community 11 - "실행 계획 0002: 실제 서비스 연결"
Cohesion: 0.11
Nodes (21): exhaustive exact cosine, 고정 공인 IP Windows collector, Google OAuth, HNSW 검색 경로 제외, Matryoshka Representation Learning, OpenAI embedding model 발표, pgvector 공식 문서, Preview 상대 /api 프록시 (+13 more)

### Community 12 - "corpus_update_bundle.py"
Cohesion: 0.08
Nodes (64): test_content_snapshot_identity_does_not_include_the_calendar_date(), _bundle(), BundleState, _atomic_write(), _build_manifest(), canonical_corpus_population_fingerprint(), canonical_corpus_publish_snapshot_id(), canonical_corpus_snapshot_id() (+56 more)

### Community 13 - "MemoryLegalRepository"
Cohesion: 0.06
Nodes (49): _date_or_none(), MemoryLegalRepository, date, Path, UUID, CorpusSearchUnavailableError, RuntimeError, Raised when the current corpus generation is not safe to search. (+41 more)

### Community 14 - "0025 Approved Questions to Grounded Answer Roadmap"
Cohesion: 0.05
Nodes (46): Apply Prepared Transaction, Atomic Corpus Publication, Base Snapshot Fingerprint, Embedding Cache Generation, 0024 Maintenance Corpus Publish, Prepare Current Bundle, Search Ready Gate, Corpus-First Answer Roadmap (+38 more)

### Community 15 - "test_question_timeout_budget.py"
Cohesion: 0.28
Nodes (16): _allow_quota(), client(), _hit(), _LegalRouter, _payload_json(), asyncio, fixture, TestClient (+8 more)

### Community 16 - "MemoryQuestionCancellationCoordinator"
Cohesion: 0.12
Nodes (26): CancelSignalResult, ExecutionNotOwnedError, ExecutionStatus, InvalidExecutionTransitionError, MemoryQuestionCancellationCoordinator, _now(), datetime, Exception (+18 more)

### Community 17 - "SearchTrace"
Cohesion: 0.08
Nodes (41): _elapsed_ms(), _match_score(), _natural_trace(), datetime, Keep the highest-ranked leaf for each document/article pair., _stage_trace(), _unique_article_hits(), _anchored_query() (+33 more)

### Community 18 - "NvidiaNimEmbedder"
Cohesion: 0.07
Nodes (43): NvidiaNimEmbedder, NVIDIA hosted NIM embedding adapter with the existing batch contract., Release the process-owned NVIDIA HTTP client., GenerationProfile, 0025 M5 item 4: model/prompt/schema/context/sampling settings, versioned…, _atomic_write(), _code_fence(), _display_float() (+35 more)

### Community 19 - "test_experiment_d_pilot_worklist.py"
Cohesion: 0.14
Nodes (41): _arguments(), _artifact_name(), atomic_write_worklist(), build_pilot_worklist(), create_pilot_worklist(), _file_sha256(), _load_json_object(), main() (+33 more)

### Community 20 - "test_experiment_d_gold_contract.py"
Cohesion: 0.12
Nodes (42): canonical_gold_case_payload_sha256(), ExperimentDGoldCase, ExperimentDGoldDataset, GoldMetricProtocol, Hash one complete validated gold-case payload using canonical JSON., _append_direct_supported_facet(), _case(), _corpus_snapshot() (+34 more)

### Community 21 - "prepared_publisher.py"
Cohesion: 0.05
Nodes (50): _apply_prepared_transaction(), _BoundEngine, _BoundTransactionContext, _chunks(), current_corpus_snapshot_id(), _embedding_source_sha256(), AsyncConnection, T (+42 more)

### Community 22 - "LawOpenApiClient"
Cohesion: 0.11
Nodes (27): _compact_date(), LawOpenApiClient, LawOpenApiError, ParsedResponse, AsyncClient, date, DeletionKind, RuntimeError (+19 more)

### Community 23 - "Lay energy question bank v1 draft"
Cohesion: 0.05
Nodes (42): Clarification-required control, Nine-document energy corpus, Lay energy question approval review v1, Thirty-five high-risk questions, Fifteen intents, lay-energy-0201 approval case, not_annotated status, 1,000-question bank (+34 more)

### Community 24 - "evaluate_dense_retrieval"
Cohesion: 0.12
Nodes (39): _answerability_diagnostic_report(), _case_metrics(), _control_pair_diagnostics(), _dcg(), evaluate_dense_retrieval(), _family_bootstrap_confidence_intervals(), _family_macro_average(), _family_primary_report() (+31 more)

### Community 25 - "LlamaIndex Module Guides and law-rag v2"
Cohesion: 0.20
Nodes (16): v2 LlamaIndex search, D-10 Recall authority, LlamaIndex Module Guides and law-rag v2, Domain-owned routing, date filtering, and validation, LlamaIndex evaluation module, Explicit changed-node ingestion, High-level query and agent exclusion, Ingestion Pipeline (+8 more)

### Community 26 - "Settings"
Cohesion: 0.08
Nodes (27): BaseSettings, model_validator, Settings, main(), 0025 M5 item 6: bounded hosted smoke test for real NVIDIA answer generation.…, DenyingPostgresIdentity, MonkeyPatch, consume_quota always denies, so a passing test proves the toggle controls it. (+19 more)

### Community 27 - "devDependencies"
Cohesion: 0.05
Nodes (39): dependencies, next, react, react-dom, @supabase/ssr, @supabase/supabase-js, devDependencies, eslint (+31 more)

### Community 28 - "SearchHit"
Cohesion: 0.16
Nodes (33): DraftAnswer, 구조 검증만 한다: 인용 ID가 실제 제공된 근거를 가리키는지, action별로 요구되는 필드가 채워졌는지. 문장 내용이 근거와 의미적으로…, validate_draft(), _draft_from_dict(), _hit_from_dict(), main(), 검증기(validate_draft) 코드를 고친 뒤 실제 근거·draft로 재검증한다 - 새 NVIDIA 호출 0회. 2026-08-08…, _draft() (+25 more)

### Community 29 - "question_scope_set_sha256"
Cohesion: 0.10
Nodes (28): Frozen corpus context recorded with the approved Experiment D question bank.…, _canonical_sha256(), question_scope_payload(), question_scope_set_sha256(), question_scope_sha256(), Canonical identities for the Experiment D layperson question bank., Return the fields a user approves as one question's text and scope., _arguments() (+20 more)

### Community 30 - "PostgresLegalRepository"
Cohesion: 0.11
Nodes (33): PostgresLegalRepository, _ConnectionContext, _document(), _FakeConnection, _FakeEngine, _MappingsResult, asyncio, parametrize (+25 more)

### Community 31 - "experiment_d_gold_contract.py"
Cohesion: 0.09
Nodes (23): ApprovalManifestSourceBank, ApprovedQuestion, canonical_gold_corpus_snapshot_id(), ExperimentDGoldAdjudicationManifest, GoldAdjudicatedCase, GoldAnnotationProtocol, GoldAnnotationReview, GoldAsOfPopulation (+15 more)

### Community 32 - "Single QuestionRouter"
Cohesion: 0.06
Nodes (35): Answer Generation, Answer Validation, Blocked Answer Generation, Blocked Fallback, Blocked Response Validation, Evidence Retrieval, Evidence Source Validation, legal_search Route (+27 more)

### Community 33 - "create_experiment_d_question_approval.py"
Cohesion: 0.14
Nodes (35): _arguments(), atomic_write_manifest(), build_question_approval_manifest(), _canonical_sha256(), create_question_approval(), load_question_bank(), main(), parse_approved_at() (+27 more)

### Community 34 - "test_experiment_d_gold_runner.py"
Cohesion: 0.22
Nodes (31): run_and_publish_approved_gold(), FakeBackend, FakeEmbedder, _fixed_clock(), gold_bundle(), GoldFixtureBundle, PublisherSpy, asyncio (+23 more)

### Community 35 - "HnswIndexManager"
Cohesion: 0.09
Nodes (24): HnswIndexManager, main(), AsyncEngine, Explicit, operator-controlled lifecycle for the v2 pgvector HNSW index., Manage the optional v2 HNSW index without coupling it to ingestion., Return whether the exact v2 index exists in the public catalog., Create the index if it is absent and report whether creation was requested., Create the v2 cosine HNSW index using a non-transactional connection. (+16 more)

### Community 36 - "ingestion/service.py"
Cohesion: 0.06
Nodes (59): Compatibility facade and CLI for the v2 LlamaIndex ingestion pipeline. The…, Readable stages for the v2 LlamaIndex ingestion pipeline., _changed_provisions(), GenerationIngestionService, _has_unchanged_source(), IncrementalIngestionService, IngestionResult, _mark_generation_failed() (+51 more)

### Community 37 - "DeletionRecord"
Cohesion: 0.20
Nodes (21): _clean(), _date(), DeletionPage, DeletionRecord, _first(), _json_records(), parse_deletions_json(), parse_deletions_xml() (+13 more)

### Community 38 - "law_rag_core/domain/schemas.py"
Cohesion: 0.08
Nodes (34): post, Request, Return allowed legal-search results from the v1 repository., search(), AiFailureCategory, AiFallbackReason, AiRuntimeState, ChangeItem (+26 more)

### Community 39 - "experiment_d_10_frozen_contract.py"
Cohesion: 0.14
Nodes (31): _arguments(), ArtifactBinding, ArtifactBindings, FrozenCase, FrozenD10ContractError, FrozenD10EvaluationContract, FrozenRunBinding, load_frozen_contract() (+23 more)

### Community 40 - "Settings"
Cohesion: 0.07
Nodes (42): build_checkpointer_context(), _psycopg_database_url(), Settings, get_settings(), BaseSettings, Settings, test_build_checkpointer_context_normalizes_url_and_returns_context_manager(), test_build_checkpointer_context_requires_database_url() (+34 more)

### Community 41 - "Energy-law RAG architecture"
Cohesion: 0.08
Nodes (34): Task 2 HNSW execution report, Concurrent HNSW DDL, HnswIndexManager, Task 3 v2 API execution report, Lazy v2 resource initialization, Stable v2 not-ready 503, D-010 verification evidence, D-010 Task 3 report (+26 more)

### Community 42 - "test_ingest.py"
Cohesion: 0.05
Nodes (53): main(), Any, IngestionResult, Run the legacy mutable-table service through its original import path., Build and publish the next retrieval generation from configured services., Run the generation service while retaining the established injection seams., Run the transform stage through the original pipeline-factory seam., run_generation_ingestion() (+45 more)

### Community 43 - "chat-state.ts"
Cohesion: 0.12
Nodes (30): submit(), appendPendingTurn(), applyLiveCoreSummary(), AssistantChatMessage, ChatMessage, ChatSession, completedConversationTurns(), completePendingTurn() (+22 more)

### Community 44 - "QuestionRequest"
Cohesion: 0.10
Nodes (42): NvidiaNimAnswerer, Any, QuestionRoute, NVIDIA hosted NIM adapter with a schema-validated legal answer boundary., 0046: 사전 라우팅이 legal_search 밖으로 걸러낸 질문(embedding·검색 없음)에 근거 없이 LLM을 호출한다 -…, Release the process-owned NVIDIA HTTP client., build_blocked_route_messages(), build_core_messages() (+34 more)

### Community 45 - "ROADMAP.md"
Cohesion: 0.05
Nodes (34): 언제 더 읽어야 하는가, 이 파일을 갱신하는 시점, 지금 무엇이 진행 중인가, 현재 상태 (세션 시작 포인터), 활성 실행 계획, 기술 부채 추적기, 등급, 열린 항목 (+26 more)

### Community 46 - "RoadmapRegistryFixtures"
Cohesion: 0.11
Nodes (4): load_registry(), Load parseable plan index headers from the repository. Legacy completed plans…, Path, RoadmapRegistryFixtures

### Community 47 - "Vercel Web and FastAPI"
Cohesion: 0.08
Nodes (26): Ownership Checks and RLS, Privacy-Safe Logs, DB TTL Capacity Lease, FinalAnswerCoordinator, Frozen CitationRegistry, Grounded Sentence Verifier, Pipeline Issue Ledger, Authoritative question_execution (+18 more)

### Community 48 - "experiment_d_local_rerank.py"
Cohesion: 0.15
Nodes (29): _active_concepts(), _arguments(), _article_path(), _atomic_publish(), build_comparison(), _canonical_json_bytes(), _cli_path(), _concept_matches() (+21 more)

### Community 49 - "render_experiment_d_layperson_approval_review.py"
Cohesion: 0.14
Nodes (29): ApprovalReviewError, _arguments(), _canonical_sha256(), _cell(), load_question_bank(), main(), _mapping(), Namespace (+21 more)

### Community 50 - "0043 Layperson Answer Contract v2"
Cohesion: 0.07
Nodes (31): As-of Date Clamping, Future-Date Boundary, Korea-Date Picker Limit, 0035 As-of Date Future Limit, Single-Connection Corpus Overview, Non-Model Endpoint One-Second SLA, One-Second Latency Test, 0038 Non-Model Endpoint Latency (+23 more)

### Community 51 - "MockIdentityRepository"
Cohesion: 0.16
Nodes (9): MockIdentityRepository, MockSession, _one_year_after(), ConversationSummary, datetime, MockUser, QuestionResponse, UUID (+1 more)

### Community 52 - "V2QuestionExecutionService"
Cohesion: 0.09
Nodes (23): PhaseRequest, PrepareQuestion, Validated transport input needed to create or replay an execution., Validated transport ownership input for a core or finalize phase., PhaseRun, Any, MockUser, V2ExecutionDependencies (+15 more)

### Community 53 - "SourceKind"
Cohesion: 0.09
Nodes (50): parametrize, test_open_api_error_is_not_treated_as_empty_search(), parametrize, test_admin_rule_json_sections_get_stable_article_paths(), test_chapter_marker_does_not_replace_first_article(), test_exact_allowlist_title_is_enforced(), test_flat_json_subitems_are_restored_under_their_numbered_items(), test_flat_json_subitems_skip_deleted_numbered_item_when_counts_match() (+42 more)

### Community 54 - "preflight_experiment_d_gold.py"
Cohesion: 0.09
Nodes (28): load_provisions(), load_provisions_from_connection(), AsyncConnection, Current-parser corpus records used by Experiment D validation and retrieval., SourceProvision, _arguments(), as_of_population_fingerprints(), AsOfPopulationFingerprint (+20 more)

### Community 55 - "experiment_d_10_gold_review.py"
Cohesion: 0.10
Nodes (53): AnnotationProposal, _arguments(), ArtifactBinding, _atomic_publish_directory(), build_draft(), _canonical_bytes(), CorpusBinding, D10GoldReviewError (+45 more)

### Community 56 - "RouteJudgment"
Cohesion: 0.10
Nodes (25): A provider judgment for one of the four provider-resolvable routes., RouteJudgment, _configure_ai(), _FailingRouter, _hit(), _payload_json(), _ProviderTimeoutRouter, asyncio (+17 more)

### Community 57 - "get_settings"
Cohesion: 0.16
Nodes (13): get_settings(), do_run_migrations(), run_async_migrations(), _arguments(), Namespace, 계정 질문 이력의 검색 단계별 진단을 읽기 전용 JSON으로 출력한다., _run(), _arguments() (+5 more)

### Community 58 - "design-docs/index.md"
Cohesion: 0.07
Nodes (18): AI 차별화와 안전 설계, 결정 기록, 제품 표현 원칙, 핵심 신념, 문서, 버전 표기, 상태 정의, 새 문서가 필요한 경우 (+10 more)

### Community 59 - "experiment_d_manual_review_contract.py"
Cohesion: 0.16
Nodes (25): ExperimentD10QuestionInput, _file_sha256(), FrozenQuestionIdentity, load_manual_pilot_artifacts(), ManualPilotInputError, BaseModel, model_validator, Path (+17 more)

### Community 61 - "api-client.ts"
Cohesion: 0.09
Nodes (32): Home(), handleDeleteAccount(), handleGoogleAuth(), handleLogout(), jumpToCitation(), loadOlderTurns(), removeHistory(), startNewChat() (+24 more)

### Community 62 - "CorpusSnapshot"
Cohesion: 0.21
Nodes (19): CorpusSnapshot, RetrievalState, _candidates(), _code_provenance(), FakeBackend, FakeEmbedder, FakeLockedReader, _provision() (+11 more)

### Community 63 - "law_rag_collector/service.py"
Cohesion: 0.08
Nodes (44): _date(), effective_periods(), EffectiveVersion, HistoryVersion, parse_history_json(), parse_history_xml(), Any, 시행일 오름차순으로 ``[시행일, 다음 시행일)`` 효력 기간을 계산한다. (+36 more)

### Community 64 - "compilerOptions"
Cohesion: 0.07
Nodes (26): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+18 more)

### Community 65 - "diagnose_grounding_failures.py"
Cohesion: 0.25
Nodes (13): _contains_normative_assertion(), _evidence_for_citations(), 근거와 겹치는 용어 비율(>=50%)을 요구해 무근거 주장을 막는다. 2026-08-08: `unanswerable` action의…, _strip_epistemic_hedges(), _terms(), _text_matches_evidence(), _texts_match_citations(), diagnose_validate_draft() (+5 more)

### Community 66 - "api/dependencies.py"
Cohesion: 0.07
Nodes (41): ConsentRequiredError, Exception, AsyncClient, Exception, UUID, SupabaseAuth, SupabaseAuthError, SupabaseAuthUnavailableError (+33 more)

### Community 67 - "DenseCandidate"
Cohesion: 0.17
Nodes (6): DenseCandidate, _candidate(), FakeLockedReader, date, Any, FakeBackend

### Community 68 - "law_rag_core/domain/catalog.py"
Cohesion: 0.08
Nodes (41): ActivationMetadata, _clean(), _json_values(), _markers(), Any, date, 활성 manifest에 들어가기 전에 문서 단위 불변조건을 모두 확인한다., 검색·임베딩 전에 원문 위치와 부모 관계를 결정적으로 검증한다. (+33 more)

### Community 69 - "experiment_d_manual_review_results.py"
Cohesion: 0.18
Nodes (25): _arguments(), _atomic_create_json(), _canonical_json_bytes(), _cli_path(), CompletedJudgment, ExperimentD10ManualReview, _final_judgment(), finalize_confirmed_review() (+17 more)

### Community 70 - "experiment_d_pilot_contract.py"
Cohesion: 0.15
Nodes (20): canonical_pilot_worklist_payload_sha256(), ExperimentDPilotAnnotationWorklist, PilotQuestion, PilotQuestionApprovalBinding, PilotSelection, PilotSourceBankBinding, BaseModel, model_validator (+12 more)

### Community 71 - "page.tsx"
Cohesion: 0.07
Nodes (26): AnswerView(), AuthDocument, authEventAction(), AuthStatus, AuthView, clampAsOfDate(), coreCitations(), HYDRATE_THROTTLE_MS (+18 more)

### Community 72 - "토큰 컨텍스트·서버 취소·검색 범위 개선"
Cohesion: 0.13
Nodes (18): 입력 토큰 예산 24,576, 조문 경로 검색 파서, 출력 토큰 예산 4,096, Qwen3:4b 연결 준비, 최근 완료 턴 선택, 요청 ID 기반 서버 취소 endpoint, 시스템·근거·구조화 여유 4,096, Qwen native 32,768 토큰 컨텍스트 (+10 more)

### Community 73 - "_answer_question"
Cohesion: 0.08
Nodes (25): ACCOUNT_QUOTA_ENABLED, answer_generation stage, _answer_question, answer_validation stage, Authenticated and consented storage, Blocked-route generation, Citation source_kind, clarification_required action (+17 more)

### Community 74 - "PostgresQuestionExecutionRepository"
Cohesion: 0.25
Nodes (13): StoredQuestionExecution, _json_mapping(), PostgresQuestionExecutionRepository, AsyncEngine, datetime, ExecutionStatus, UUID, Atomically commit a completed phase and its replayable event log. (+5 more)

### Community 75 - "기술·로직 부채 감사"
Cohesion: 0.07
Nodes (28): 생성 실패 시 검색 전용 폴백, Outbound 추론 작업 큐, Provider-neutral Answerer 포트, Qwen 장애 시 검색 전용 폴백, 구조화 출력·Grounding 검증, 대화 컨텍스트 중복 제거, 분산 취소 Tombstone 검증, 정확 조문 경로 매칭 (+20 more)

### Community 76 - "LlamaIndexLegalRepository"
Cohesion: 0.06
Nodes (33): LlamaIndexLegalRepository, date, datetime, UUID, v2 LlamaIndex 검색과 v1 저장소 위임을 결합한다., 단일 조문 조회를 v1 저장소에 위임한다., Corpus 검색 상태 조회를 v1 저장소에 위임한다., Corpus 기준일 범위 상태 조회를 v1 저장소에 위임한다. (+25 more)

### Community 77 - "corpus.py"
Cohesion: 0.05
Nodes (43): bind_app_dependencies(), _FactoryCompositionMain, Any, Module-like request facade that binds routes to one app factory's adapters., Bind a non-production app factory's resources for one HTTP request., Restore the previous factory binding after a request completes., reset_app_dependencies(), changes() (+35 more)

### Community 78 - "search_only_answer"
Cohesion: 0.16
Nodes (19): search_only_answer(), citation_quality(), enforce_quality(), main(), _answer_text(), _assert_terms(), _hits(), parametrize (+11 more)

### Community 79 - "parse_provision_references"
Cohesion: 0.21
Nodes (13): _compact(), _document_title(), _korean_number(), _normalize_korean_provision_numbers(), _number_value(), parse_provision_references(), ProvisionQuery, ProvisionReference (+5 more)

### Community 80 - "AGENTS.md"
Cohesion: 0.13
Nodes (14): Discord 전용 오버레이, Docker·로컬 DB 정책, GitHub 인증 확인, graphify, Subagent 모델·reasoning 정책, 개발 작업 워크플로우, 검증 계약, 권위 문서 (+6 more)

### Community 81 - "roadmap_registry.py"
Cohesion: 0.11
Nodes (36): _canonical_record(), _canonical_reference(), _display_path(), _error(), _git_output(), _has_index_header(), _header_lines(), _is_plan_relative_path() (+28 more)

### Community 82 - "ports/question_execution.py"
Cohesion: 0.12
Nodes (14): ActiveGeneration, ActiveGenerationProvider, PhaseLease, Protocol, Explicit ports used by the v2 question-execution use case., The frozen generation and index used for one prepare operation., Port for resolving the current generation once at prepare time., A provider-capacity lease whose owner performs its own cleanup. (+6 more)

### Community 83 - "test_backfill_embeddings.py"
Cohesion: 0.06
Nodes (93): _acquire_corpus_mutation_lock(), _acquire_corpus_sync_run_lock(), _append_cache(), _arguments(), _backfill_database(), _bundle_passages(), _cache_batch_values(), _cache_file_lock() (+85 more)

### Community 84 - "PostgresIdentityRepository"
Cohesion: 0.13
Nodes (9): PostgresIdentityRepository, AsyncEngine, ConversationSummary, date, datetime, MockUser, QuestionResponse, UUID (+1 more)

### Community 85 - "run_experiment_0043_v1_v2_compare.py"
Cohesion: 0.43
Nodes (7): _answerer_for(), load_cases(), main(), 0043 범위 4: D-10 최대 3문항에 대해 v1(build_messages)과 v2(build_messages_v2) 답변을 동일 검색…, _router(), run_one(), _with_retry()

### Community 86 - "test_prepared_update.py"
Cohesion: 0.12
Nodes (12): _Connection, _ConnectionContext, _document(), _Engine, asyncio, Path, _Repository, _Result (+4 more)

### Community 87 - "PostgresExperimentDBackend"
Cohesion: 0.11
Nodes (10): PostgresExperimentDBackend, Backend holding one transaction-scoped shared lock for the evaluation., _ConnectionContext, _LockConnection, _LockEngine, _ScalarResult, test_postgres_backend_busy_xact_lock_does_not_enter_reader(), test_postgres_backend_uses_one_transaction_and_shared_mutation_key_for_lock() (+2 more)

### Community 88 - "AgentState"
Cohesion: 0.18
Nodes (16): _blocked_node(), build_graph(), Any, _route_branch(), build_search_node(), search_node(), AgentState, append_turn() (+8 more)

### Community 89 - "_node"
Cohesion: 0.27
Nodes (13): _FakeEmbedder, _FakeVectorStore, _node(), asyncio, TextNode, test_search_applies_limit_after_temporal_post_filtering(), test_search_excludes_nodes_with_incomplete_metadata(), test_search_excludes_provision_closed_on_requested_date() (+5 more)

### Community 90 - "NvidiaNimQuestionRouter"
Cohesion: 0.07
Nodes (30): NvidiaNimQuestionRouter, Any, BaseModel, Question router backed by one structured NVIDIA NIM request., Release the process-owned NVIDIA HTTP client., _RouteJudgmentSchema, Protocol, QuestionRouter (+22 more)

### Community 91 - "Experiment D-10 Gold review draft"
Cohesion: 0.10
Nodes (21): Clarification required cases, Corpus of 3,066 provisions, Repeatable read, read-only DB, Experiment D-10 Gold review draft, Zero embedding, search, and model calls, 30,660 relevance judgments, Partially answerable cases, Pending user review (+13 more)

### Community 92 - "Evaluation and Experiment Reading"
Cohesion: 0.14
Nodes (21): Advisory lock coordination, As-of populations, Atomic evaluation result publication, Date-independent content snapshot identity, Corpus, query, qrels, and reference contract, D-10-R1 calibration reranking, D-10 unanswerable pilot, Evaluation and Experiment Reading (+13 more)

### Community 93 - "test_layperson_prompt_v2.py"
Cohesion: 0.20
Nodes (19): build_messages_v2(), 0043: 법률을 처음 접하는 사용자를 위한 문체 규칙을 추가한 v2 프롬프트. 인용·근거·action 안전 규칙은…, _hits(), v1 has "적용 여부를 추정하지 않는다" right after the summary/결론 guidance; v2 must carry the…, v1 ends its limitations guidance with "limitations에 새로운 법률 주장을 추가하지 않는다." v2…, _request(), test_v1_prompt_text_is_unchanged_by_v2_addition(), test_v2_system_prompt_caps_limitations_and_splits_confirmed_vs_unconfirmed() (+11 more)

### Community 94 - "experiment_d_10_context_assembly.py"
Cohesion: 0.21
Nodes (19): article_key(), assemble_variant_a(), assemble_variant_b(), AssembledArticle, Candidate, CorpusRecord, evaluate_combo(), load_context_verdicts() (+11 more)

### Community 95 - "CorpusTemporalState"
Cohesion: 0.13
Nodes (25): korea_today(), date, ValueError, Dynamic temporal contract for the currently searchable legal corpus. The…, Return the product's legal-current date, independent of server timezone., Raised when a request falls outside the current dynamic corpus bounds., Return a supported date or fail before quota and provider work begins., require_supported_corpus_date() (+17 more)

### Community 96 - "실행 계획 0008: 4단계 검색, 1초 지연 목표, RAG 디버깅"
Cohesion: 0.11
Nodes (22): 1초 지연 목표와 측정 경계, 1단계 모든 핵심어 일치, 3단계 필수 앵커 검증, 핵심어 정규화, 직접 조문 경로 검색, 4단계 근거 부족, 2단계 최소 2개 후보 풀, 검색 절대 deadline 1,000ms (+14 more)

### Community 97 - "LegalRepository"
Cohesion: 0.14
Nodes (8): v1 위임 저장소와 v2 검색 의존성을 연결한다., Compatibility facade for callers that still provide a repository object., _requires_legacy_query_embedding(), LegalRepository, date, datetime, Protocol, UUID

### Community 98 - "corpus_preflight.py"
Cohesion: 0.07
Nodes (30): _all(), _async_url(), CorpusPreflightError, _json_value(), _mapping(), _one(), preflight_current_corpus(), Any (+22 more)

### Community 99 - "contracts.ts"
Cohesion: 0.13
Nodes (14): CitationCard(), citation, SafeText(), Citation, ConversationPage, ConversationSummary, ConversationTurnPage, QuestionResponse (+6 more)

### Community 100 - "Evidence-First Retrieval and Answers"
Cohesion: 0.16
Nodes (19): Embedding profile lineage, Candidate grouping and five-context budget, Citation IDs and structured output, Cosine similarity, Deterministic citation gate, Direct statutory path query, Evidence-First Retrieval and Answers, Evidence-first RAG boundary (+11 more)

### Community 101 - "전기사업법 제12조 허가 취소 등"
Cohesion: 0.14
Nodes (19): 전기사업법 제10조 양수·분할·합병 인가, 전기사업법 제11조 사업 승계, 전기사업법 제12조 허가 취소 등, 전기사업법 제34조 차액계약, 전기사업법 제53조 전기위원회, 전기사업법 제61조 공사계획 인가, 전기사업법 제7조 사업의 허가, 전기사업법 제8조 결격사유 (+11 more)

### Community 102 - "test_question_cancellation.py"
Cohesion: 0.51
Nodes (9): _allow_quota(), _LegalRouter, asyncio, _request(), test_active_generation_is_cancelled(), test_active_search_is_cancelled_and_registry_is_cleaned(), test_cancelled_answer_generation_stage_is_not_logged_as_succeeded(), test_unknown_and_completed_request_ids_cannot_be_cancelled() (+1 more)

### Community 103 - "main.py"
Cohesion: 0.05
Nodes (82): main_module(), Resolve the composition entry lazily to retain monkeypatch compatibility., cancel_question_execution(), _capability_hash(), _execution_capability(), _not_ready_error(), prepare_question_execution(), _prepared_execution_response() (+74 more)

### Community 104 - "RouteDecision"
Cohesion: 0.19
Nodes (12): build_route_node(), route_node(), BaseModel, RouteDecision, FakeStructuredLLM, asyncio, RouteDecision, test_route_node_passes_question_text_to_llm() (+4 more)

### Community 105 - "generation-retry.ts"
Cohesion: 0.18
Nodes (15): QuestionInput, askQuestionWithRetry(), AskQuestionWithRetryDeps, cancelWithBound(), GENERATION_ATTEMPT_TIMEOUT_MS, GENERATION_CANCEL_TIMEOUT_MS, GENERATION_MAX_ATTEMPTS, GENERATION_OVERALL_TIMEOUT_MS (+7 more)

### Community 106 - "0053 LlamaIndex v2 Retrieval Pipeline"
Cohesion: 0.12
Nodes (18): Citation Law-Type Code, Law API Type Fields, Law-Type Pass-Through Columns, 0041 Law Type Classification Parsing, Source-Kind Identity Column, Hash-Skipping Ingestion, LlamaIndex Legal Repository Adapter, LlamaIndex v2 Retrieval Pipeline (+10 more)

### Community 107 - "Clarification Loop Handling Plan"
Cohesion: 0.18
Nodes (18): Answered Field Deduplication, Clarification Loop Handling Plan, Clarification Regression Tests, Clarification Required Action, Clarification Round Limit, Conversation Context, LangGraph State Graph, Unanswered Field Finalization (+10 more)

### Community 108 - "Law Corpus Lifecycle"
Cohesion: 0.18
Nodes (18): Abolished versus source-deleted state, Lineage catalog with HNSW exclusion, Content fingerprint and snapshot ID, Law Corpus Lifecycle, Effective-date half-open interval, As-of eligible provision population, JSON-first XML schema fallback, LegalDocumentRecord (+10 more)

### Community 109 - "User, Privacy, and Failure Safety"
Cohesion: 0.18
Nodes (16): AbortController versus distributed cancellation, AI failure search-only fallback, Separate generation and embedding provider ports, Anonymous question non-persistence, Authentication epoch and late-response discard, Checklist export and accessible citation controls, User, Privacy, and Failure Safety, Google identity provider (+8 more)

### Community 110 - "코퍼스 운영·롤백 런북"
Cohesion: 0.13
Nodes (15): Prepared Transaction Gate 반영, 코퍼스 검색 게이트, SHA 벡터 재사용 캐시, 고정 출구 IP 수동 실행, 예약 실행 없음, Prepare Current Bundle, 롤백·검색 전용 유지, 롤백 (+7 more)

### Community 111 - "ExecutionPhase"
Cohesion: 0.12
Nodes (21): CapacityLeaseStore, Lease, MemoryConcurrencyLimiter, _MemoryLease, PostgresCapacityLeaseStore, PostgresConcurrencyLimiter, _PostgresLease, AsyncEngine (+13 more)

### Community 112 - "실행 계획 0025: 승인 질문에서 근거 기반 AI 답변까지"
Cohesion: 0.05
Nodes (37): D-full 50문항 pilot, D-full 재활성화 시 실행 순서, D-full 전체 1,000문항, E0 — 외부 호출 없는 결정적 검사, M0 — 질문 승인과 상태 감사, M1.5 — D-10 수동 진단, M1 완료 증거 — 2026-08-04, M1 — 운영 DB 반영 전 corpus 게시 검증 (+29 more)

### Community 113 - "OpenAI Vector embeddings"
Cohesion: 0.12
Nodes (16): Embedding anomaly detection, Embedding classification, Embedding input and output ownership, dimensions parameter, Embeddings API, Embedding pricing by input tokens, Embedding vector, Model knowledge cutoff September 2021 (+8 more)

### Community 114 - "일반 사용자형 에너지 질문 의도 설계"
Cohesion: 0.11
Nodes (19): 일반 사용자형 에너지 질문 의도 설계, 에너지바우처 FAQ, 2026년 공용 완속충전시설 설치 안내서, 무공해차 통합누리집, 독립 검토 Gold와 Qrels, 한전 분산형 전원 계통연계 절차, 한전 전기사용 신청·계약 안내, 한전 전력서비스 헌장 (+11 more)

### Community 115 - "Nemotron 3 Embed 1B"
Cohesion: 0.12
Nodes (18): NIM Embedding API 계약, Hosted Free Endpoint Trial 경계, L2 재정규화, 임베딩 모델·차원·버전 분리, 34개 언어 다국어 임베딩, Native 2048차원 출력, Nemotron 3 Embed 1B, 첫 512차원 Prefix Slice (+10 more)

### Community 116 - "check_docs.py"
Cohesion: 0.19
Nodes (16): check_d010_active_experiment_contract(), check_d010_current_contract_docs(), check_d010_routing_contract(), check_d010_superseded_designs(), check_freshness(), check_links(), main(), markdown_files() (+8 more)

### Community 117 - "v1/answering.py"
Cohesion: 0.05
Nodes (70): _answering_http_error(), cancel_question(), _handle_question(), HTTPException, post, QuestionResponse, QuestionStageTimingOutcome, Request (+62 more)

### Community 118 - "사용 중·조건부 추천 상세"
Cohesion: 0.06
Nodes (32): LlamaIndex Python Framework Module Guides와 law-rag v2, 개념 예시: 동일한 retrieval 결과에 대해서만 보조 평가한다., 공식 문서 탐색 범위, 사용 중·조건부 추천 상세, 실제 사용 코드와 참조, 실제 사용 코드와 참조, 실제 사용 코드와 참조, 실제 사용 코드와 참조 (+24 more)

### Community 119 - "Database schema"
Cohesion: 0.11
Nodes (22): active_retrieval_release pointer, checklist_exports table, conversations table, corpus_snapshots table, Database schema, document_versions table, embedding_profiles table, history_retention_runs table (+14 more)

### Community 120 - "Alembic autogenerate"
Cohesion: 0.12
Nodes (16): Alembic autogenerate, alembic check, Candidate migration, Type and server-default comparison, Database schema comparison, env.py, EnvironmentContext.configure, include_name filter hook (+8 more)

### Community 121 - "Energy Business Legal Chat"
Cohesion: 0.15
Nodes (18): corpus_unready, Cursor-paginated conversation history, 24,576-token context rollover, Anonymous history policy, Checklist Markdown CSV PDF export, Product corpus_unready state, Grounded legal QA decision records, Product deterministic citation gate (+10 more)

### Community 122 - "D-10 수동 검색·문맥 진단"
Cohesion: 0.12
Nodes (16): 프로젝트 1000문항·200 Scenario Family 설계, 30660개 사용자 검토 Judgment, Annotation·Adjudication 계약, 현재 3066개 Provision 코퍼스, D-10 Gold 사용자 검토 Workflow, D-full 1000문항 설계, Pending User Review 상태, 직접 답변 가능성 판정 라벨 (+8 more)

### Community 123 - "PlanRecord"
Cohesion: 0.16
Nodes (20): _atomic_replace(), main(), _parser(), _print_validation_errors(), ArgumentParser, Path, Render the generated roadmap from execution-plan index metadata., Validate the registry and atomically regenerate ``docs/ROADMAP.md``. (+12 more)

### Community 124 - "test_v2_search.py"
Cohesion: 0.21
Nodes (15): client(), asyncio, fixture, MonkeyPatch, parametrize, TestClient, test_v2_readiness_closes_when_marker_connection_or_migration_is_unavailable(), test_v2_readiness_depends_on_the_active_generation_pointer() (+7 more)

### Community 125 - "V2 LlamaIndex 검색(Retrieval) 파이프라인 구현 계획"
Cohesion: 0.11
Nodes (19): Self-Review Notes(계획 작성자를 위한 것이며 태스크가 아님), Staging 가동 검증 (2026-08-18, 사용자 승인 하에 실제 운영 DB 대상 실행), Task 10: `apps/api`의 `LlamaIndexLegalRepository` 어댑터, Task 11: `/v2/search` 엔드포인트, Task 12: `/v2/questions` 엔드포인트(v1의 답변 파이프라인 재사용), Task 13: `apps/web` — `/v2/questions`로 전환, Task 14: 저장소 문서 업데이트 및 계획 마무리, Task 1: `law-rag-llamaindex` 워크스페이스 앱 스캐폴딩 (+11 more)

### Community 126 - "LegalDocumentRecord"
Cohesion: 0.23
Nodes (6): CollectorRepository, Any, date, Protocol, Backward-compatible short alias for internal callers., LegalDocumentRecord

### Community 127 - "derive_answer_action"
Cohesion: 0.29
Nodes (10): AnswerAction, derive_answer_action(), derive_fallback_action(), ChecklistItem, _item(), ChecklistItem, test_all_required_or_not_applicable_is_fully_answerable(), test_any_check_status_is_clarification_required() (+2 more)

### Community 128 - "query/retriever.py"
Cohesion: 0.22
Nodes (16): Active-generation query resources and temporal retrieval adapters., _as_of_filter(), _filter_hits(), _is_current_on(), _over_fetch_limit(), Any, date, Temporal retrieval adapters for the v2 vector index. (+8 more)

### Community 129 - "Security and Privacy"
Cohesion: 0.18
Nodes (15): GitHub Issue and PR Workflow, No Sensitive Data in Issues or PRs, PR Quality Contract, One Verifiable Outcome per Issue, Safe Use without Sensitive Case Data, Reliability and Operations: C, Request and Trace Observability, AI and Search-Only Rate Limits (+7 more)

### Community 130 - "New User Onboarding"
Cohesion: 0.13
Nodes (20): Evidence citation UI, Legal-advice disclaimer, Product Specifications Index, Approved grounded legal QA specification, Onboarding assumption draft, Product specifications catalog, User-observable product spec rules, Anonymous question no-history policy (+12 more)

### Community 131 - "select_generation_hits"
Cohesion: 0.50
Nodes (8): Keep at most one ranked leaf per article within the provider input budget., select_generation_hits(), _hit(), test_budget_keeps_one_oversized_top_provision(), test_budget_keeps_whole_ranked_provisions(), test_flat_body_paths_are_not_collapsed_into_one_article(), test_generation_context_is_limited_to_five_articles(), test_generation_context_keeps_only_highest_ranked_leaf_per_article()

### Community 132 - "MemoryQuestionExecutionRepository"
Cohesion: 0.16
Nodes (17): MemoryQuestionExecutionRepository, datetime, ExecutionStatus, UUID, Persist a phase result and every public event under one lock. A provider call…, In-memory reference implementation of the authoritative execution contract., ExecutionSnapshot, InvalidExecutionTransition (+9 more)

### Community 133 - "test_prepared_publisher_postgres.py"
Cohesion: 0.23
Nodes (13): fixture, repository(), _assert_writer_locks_released(), _async_url(), _complete(), _isolated_repository(), _no_sleep(), asyncio (+5 more)

### Community 134 - "GenerationResult"
Cohesion: 0.33
Nodes (10): build_generate_node(), _format_evidence(), generate_node(), GenerationResult, FakeStructuredLLM, asyncio, test_generate_node_ignores_citation_ids_outside_search_hits_range(), test_generate_node_maps_citation_ids_to_search_hits() (+2 more)

### Community 137 - "System Map and Execution Boundaries"
Cohesion: 0.14
Nodes (20): Collector execution boundary, Domain-to-adapter dependency direction, System Map and Execution Boundaries, FastAPI API, Fixed-IP Windows collector, law-rag core domain, National Law Information Open API, Next.js Web (+12 more)

### Community 138 - "Discord Error Ledger"
Cohesion: 0.20
Nodes (14): Active plan index mismatch incident, Python CI import-path incident, Conversation-first lock order, History deletion deadlock incident, Discord incident ledger scope, Discord Error Ledger, Duplicate clone incident, External reviewer access incident (+6 more)

### Community 139 - "Repository Rules (AGENTS.md)"
Cohesion: 0.17
Nodes (13): Pull request template, Pull request security checklist, Pull request verification checklist, Repository Rules (AGENTS.md), Domain and data invariants, Evidence, citations, and source-version traceability, JSON-first XML-fallback ingestion, Privacy-safe logging and secret handling (+5 more)

### Community 140 - "test_experiment_d_manual_review_results.py"
Cohesion: 0.37
Nodes (11): create_review_template(), _canonical_sha256(), _judgment(), MonkeyPatch, Path, _result(), test_cli_resolves_relative_artifact_paths_from_repository_root(), test_confirmed_review_computes_only_manual_diagnostics() (+3 more)

### Community 143 - "V2: LlamaIndex 프레임워크 파이프라인 개편 설계"
Cohesion: 0.06
Nodes (31): 10. v1 호환성과 전환, 11. 검증 계약, 12. 구현계획에서만 정할 세부값, 13. 결정 기록, 1. 목적, 2.1 이번 구현 목표, 2.2 명시적인 다음 목표, 2. 현재 목표와 다음 목표 (+23 more)

### Community 144 - "test_graph.py"
Cohesion: 0.36
Nodes (11): fake_generate(), fake_route_legal_search(), fake_search(), fake_validate(), _initial_state(), asyncio, _recording_node(), test_graph_restores_state_from_memory_checkpointer_for_same_thread() (+3 more)

### Community 145 - "test_api_factory_composition.py"
Cohesion: 0.10
Nodes (17): _Connection, _Engine, _FactoryRepository, asyncio, date, MonkeyPatch, Regression coverage for factory-scoped transport dependencies and seams., Fail if the v1 route bypasses a patched app.main._answer_question seam. (+9 more)

### Community 146 - "ExperimentDBackend"
Cohesion: 0.13
Nodes (12): _configure_search_path(), ExperimentDBackend, _load_retrieval_state(), LockedDenseReader, _PostgresLockedDenseReader, Any, AsyncConnection, date (+4 more)

### Community 147 - "실행 계획 0020: 실험 D — 검색 문맥 구성"
Cohesion: 0.12
Nodes (21): 조·항·호·목 계층 복원, Article Recall, 실험 D 검색 문맥 구성, corpus 정확성 우선, corpus validator, dense-only 최종 기준선, 직접 근거 1~5개, evidence closure (+13 more)

### Community 148 - "RAG 평가 방법 공식 자료"
Cohesion: 0.11
Nodes (18): 미주석 질문 초안, 답변 Faithfulness·Groundedness 지표, BEIR, BEIR Annotation Hole·Pooling Bias, ID·Path·SHA 결정적 검색 지표, Ground Truth 기반 정확도 벤치마크, 독립 Graded Qrels·Adjudication, Labelled RAG Dataset (+10 more)

### Community 149 - "scripts"
Cohesion: 0.15
Nodes (12): name, packageManager, private, scripts, build, build:web, dev:web, lint:web (+4 more)

### Community 150 - "RetrievalGeneration"
Cohesion: 0.08
Nodes (39): Generation catalog models, persistence and publication policy., generation_source_records(), generation_table_name(), GenerationSource, provision_fingerprint(), UUID, Pure generation catalog values and transformation fingerprints., Fingerprint the transformation contract that defines vector compatibility. (+31 more)

### Community 151 - "sse.py"
Cohesion: 0.27
Nodes (13): core_question_execution(), finalize_question_execution(), alias, Header, post, Request, StreamingResponse, UUID (+5 more)

### Community 152 - "PostgresGenerationRepository"
Cohesion: 0.06
Nodes (28): PostgresGenerationRepository, AsyncEngine, UUID, Read the stored lineage required to select safe vector copies., Switch active pointer only if the candidate has been verified., Persist generation transitions using short, caller-owned transactions., Record a failed candidate while retaining the current active pointer., Atomically restore an explicitly retained rollback generation. (+20 more)

### Community 153 - "실행 계획 0017: 실험 B — NVIDIA NIM 두 문장 임베딩과 코사인 유사도"
Cohesion: 0.08
Nodes (30): 2048차원 NIM과 기존 512차원 계약 연결, 코사인 유사도, 512차원 embed 계약, L2 재정규화, live API 반복성 관찰, 2048→512 첫 prefix slicing, nvidia/nemotron-3-embed-1b, query·passage 입력 유형 (+22 more)

### Community 154 - "cli.py"
Cohesion: 0.13
Nodes (18): main(), _parser(), ArgumentParser, Path, _run(), CorpusPreflightSettings, BaseSettings, The preflight intentionally needs only a direct PostgreSQL session URL. (+10 more)

### Community 155 - "checklist-export.ts"
Cohesion: 0.26
Nodes (10): exportChecklist(), ChecklistExportInput, csvCell(), downloadBlob(), downloadText(), ExportFormat, renderCsv(), renderMarkdown() (+2 more)

### Community 156 - "Product Sense"
Cohesion: 0.20
Nodes (12): Citation Context Preservation, Product Design Principles, Evidence Path First, Source, Date, Jurisdiction, and Document-Type Hierarchy, Citation-to-Source Follow-Up, Product Sense, Relevant Evidence, Explicit Uncertainty Disclosure (+4 more)

### Community 157 - "fetch_provisions"
Cohesion: 0.16
Nodes (9): fetch_provisions(), AsyncEngine, ProvisionRecord, Return all provisions in the canonical corpus snapshot., Load canonical provisions and normalize database values at the boundary., Backward-compatible provision-reader import., asyncio, test_fetch_provisions_returns_expected_fields() (+1 more)

### Community 158 - "Production retrieval debug revision 0004"
Cohesion: 0.17
Nodes (12): All-keywords path, Direct article path, Nine documents, Eight retrieval contracts passed, Zero embeddings, Zero evaluation runs, Keyword-only search, Not a recall baseline (+4 more)

### Community 159 - "Operational vector index build report"
Cohesion: 0.17
Nodes (12): Corpus as-of range 2026-06-03 to 2026-08-03, Zero missing or stale vectors, Current runtime ignores retrieval catalog, Exhaustive exact cosine, Hybrid and RRF DB functions absent, Historical HNSW index, Operational vector index build report, Embedding profile active true (+4 more)

### Community 160 - "실험 C Dense 검색 후보 관찰"
Cohesion: 0.15
Nodes (14): pgvector HNSW 영구 제외, 후보에서 직접 근거로 가는 문맥 파이프라인, 실험 D 검색 문맥 구성, Corpus SHA·검색 실행 스냅샷, 실험 D 실제 결과, Article Candidates, 후보는 최종 근거가 아님, Dense-only 기준선 (+6 more)

### Community 161 - "2026-07-19 사건"
Cohesion: 0.14
Nodes (13): 1. 기존 checkout에 대한 중복 clone 시도, 2026-07-19 사건, 2. 활성 실행 계획 index와 실제 파일 불일치, 3. 로컬 Git 작성자 설정 누락, 4. `main` Python CI의 전 테스트 수집 실패, 5. 임시 PostgreSQL 검증 harness 실행 실패, 6. 외부 Claude 독립 review 시작 실패, 7. Retention과 새 질문 저장의 conversation 경합 (+5 more)

### Community 162 - "bootstrap.py"
Cohesion: 0.07
Nodes (40): Reject a publishable core summary that names evidence it did not receive., validate_core_draft(), Protocol, QueryEmbeddingCapability, Declare whether this retrieval path needs an application query vector., All collaborator ports for a single v2 service instance. The composition root…, V2ExecutionDependencies, AppDependencies (+32 more)

### Community 163 - "test_non_model_endpoint_latency.py"
Cohesion: 0.33
Nodes (9): assert_under_one_second(), _headers(), _login(), MonkeyPatch, Response, TestClient, _seed_question(), test_every_non_model_endpoint_responds_within_one_second() (+1 more)

### Community 164 - "test_mock_auth_history.py"
Cohesion: 0.32
Nodes (9): _ask(), _login(), test_anonymous_question_is_not_saved_but_authenticated_question_is(), test_conversation_is_owner_scoped_and_delete_cascades_legacy_history(), test_conversation_summary_and_turn_cursors_do_not_duplicate_items(), test_history_is_private_and_owner_can_delete_it(), test_invalid_or_wrong_cursor_kind_is_rejected(), test_logout_invalidates_session_and_account_delete_cascades() (+1 more)

### Community 165 - "Reliability"
Cohesion: 0.22
Nodes (11): WCAG 2.2 AA, Frontend Architecture, Question, Answer, Citation, and Source Flow, Question State Machine, Response Mode Synchronization, Safe Source Rendering, Search-Only Feature Disabled by Default, Reliability (+3 more)

### Community 166 - "Dense article-level search baseline"
Cohesion: 0.18
Nodes (11): Exhaustive exact cosine search, Legacy HNSW index excluded, Independent keyword fallback, Article MRR equals 1.0, Article Recall at 3, 5, and 10 equals 1.0, Candidate k equals 10, Dense article-level search baseline, Evidence Recall at 3, 5, and 10 equals 1.0 (+3 more)

### Community 167 - "Experiment D search context safety gate"
Cohesion: 0.20
Nodes (10): Electricity Business Act Article 7, Electricity Business Act Article 7 absent, Experiment D search context safety gate, Five in-scope runs ready, Governing provision outside corpus, One out-of-scope run insufficient evidence, In-scope success 5 of 5, Required evidence terms contract (+2 more)

### Community 168 - "R1 plus A"
Cohesion: 0.20
Nodes (11): Assembly A: one best leaf per article, Assembly B: parent and sibling expansion, Zero budget-exceeded cases, Calibration-only result, 60,000 character budget, Direct evidence hit, Experiment D-10 M4 context assembly summary, Maximum five provisions (+3 more)

### Community 169 - "Reciprocal Rank Fusion"
Cohesion: 0.15
Nodes (14): Retrieval catalog v1, retrieval_index_builds table, retrieval_profiles table, Condorcet Fuse, FIPS 180-4 Secure Hash Standard, Hash computation, Message integrity, LETOR 3 dataset (+6 more)

### Community 170 - "test_security_boundaries.py"
Cohesion: 0.08
Nodes (32): is_allowed_source_url(), 브라우저에 노출 가능한 국가법령정보 원문 URL만 허용한다., emit_execution_phase(), emit_question_outcome(), emit_route_outcome(), ExecutionPhaseEvent, fallback_reason_metrics_snapshot(), BaseModel (+24 more)

### Community 171 - "QuestionTaskRegistry"
Cohesion: 0.13
Nodes (11): Task, UUID, QuestionTaskRegistry, Process-local active question tasks, scoped by a non-secret owner key., Regression coverage for the public route registration boundary., All existing public URL and operation identifiers remain registered., Routes without explicit models and the CORS policy keep their original…, Registration keeps documented response models and browser request permissions. (+3 more)

### Community 172 - "test_experiment_d_local_rerank.py"
Cohesion: 0.44
Nodes (9): _candidate(), _canonical_sha256(), _case(), Path, test_rerank_does_not_overwrite_existing_output(), test_rerank_moves_target_evidence_to_top3_and_reduces_known_noise(), test_rerank_rejects_unconfirmed_review_without_output(), test_rerank_uses_case_text_without_relevance_labels() (+1 more)

### Community 173 - "Traffic Routing Calibration Review"
Cohesion: 0.33
Nodes (10): Authenticated Diagnostics History, D-010 Router Calibration, Fail-Closed Routing Observability, Fallback Reason Metrics Snapshot, Historical Tier Dictionary, Route Metrics Snapshot, Route and Reason-Code Policy, Single Question Router (+2 more)

### Community 174 - "V2 Chunking Ablation"
Cohesion: 0.36
Nodes (10): Chunker-Only Experimental Variable, V2 Chunking Ablation Plan, Current Provision TextNode Baseline, D-10 Sealed Calibration Gold, Fixed V2 Retrieval Pipeline, Isolated Experiment Vector Tables, LlamaIndex Subchunk Candidate, Provision Traceability (+2 more)

### Community 175 - "V2 Dynamic Today Date Bound Plan"
Cohesion: 0.38
Nodes (10): API and Web Date Contract, Clock Injection Boundary Tests, F-005 Temporal Adapter Boundary, Future-Date 422 Guard, Supported As-Of Start, Supported As-Of Through, Temporal Effective Interval, Asia Seoul Today Provider (+2 more)

### Community 176 - "Output 512 dimensions"
Cohesion: 0.13
Nodes (16): Cosine similarity, Embedding repeatability unresolved, Exact 512-float vector comparison, Experiment B embedding results, Native 2048 dimensions, Normalized embedding vector, nvidia/nemotron-3-embed-1b, NVIDIA NIM (+8 more)

### Community 177 - "Project Roadmap"
Cohesion: 0.24
Nodes (10): Execution Plan Operations, Execution Plan Lifecycle, Todo, Picked Up, Blocked, and Done Statuses, Task Management Metadata Contract, 52/55/60-Second Question Timeout Budget, DOC-001 Task Metadata and Thin Roadmap, Project Roadmap, F-002 Distributed Question Cancellation (+2 more)

### Community 178 - "Qwen3:4b 연결 준비사항"
Cohesion: 0.12
Nodes (16): GTX 1650·Windows 10 로컬 프로필, Nemotron 3 Nano 4B, NIM on WSL2 지원 하드웨어 경계, Qwen3:4b·Ollama 로컬 후보, Qwen 입력 예산 24576 토큰, Ollama OpenAI 호환 경로, 생성 출력 예약 4096 토큰, Qwen3-4B Native Context 32768 (+8 more)

### Community 179 - "FrozenCitation"
Cohesion: 0.18
Nodes (18): FinalAnswer, FinalAnswerCoordinator, Choose one authoritative terminal response from already verified content., VerifiedAnswer, CitationRegistry, FrozenCitation, GroundedSection, GroundedSentence (+10 more)

### Community 180 - "실험 D — 검색 문맥 안전 게이트 평가"
Cohesion: 0.29
Nodes (4): 결과, 실험 D — 검색 문맥 안전 게이트 평가, 판정, 한계

### Community 181 - "legal_search_router"
Cohesion: 0.33
Nodes (8): legal_search_router(), fixture, MonkeyPatch, Let non-temporal API tests exercise their own downstream concern., Exercise legacy search-only contracts only when the feature is explicitly…, Keep normal AI-flow tests on the post-routing legal-search path., ready_corpus_temporal_state(), search_only_enabled()

### Community 182 - "ActiveGenerationIndexProvider"
Cohesion: 0.14
Nodes (10): Backward-compatible imports for the active-generation query cache., ActiveGenerationIndexProvider, ActiveIndex, Request-safe cache for indexes opened from the active generation pointer., One index paired with the immutable generation it reads., Cache one index per active generation without changing prior pins., Resolve the current pointer once and return an immutable request pin., Release the caller-owned database engines, if this provider owns them. (+2 more)

### Community 184 - "validate_node"
Cohesion: 0.39
Nodes (7): _citation_matches_hit(), _citations_from_search_hits(), validate_node(), test_validate_node_blocks_citation_that_does_not_match_retrieved_evidence(), test_validate_node_blocks_uncited_claims(), test_validate_node_passes_through_answer_with_citations(), test_validate_node_suppresses_unanswerable_arbitrary_legal_claim()

### Community 185 - "Corpus Support Range"
Cohesion: 0.25
Nodes (9): apply-prepared Atomic Publish, Corpus Search-Ready Gate, Dynamic Corpus Snapshot Identity, Corpus Support Range, corpus_unready HTTP 503, Dynamic Runtime Snapshot, Lifecycle and Source States, Searchable Version (+1 more)

### Community 186 - "Exhaustive Exact Dense Search"
Cohesion: 0.22
Nodes (9): BM25 Retriever, Experiment D Exhaustive Exact Cosine, Exhaustive Exact Dense Search, HNSW Permanent Exclusion, PGroonga Keyword Fallback, LangGraph v3, LlamaIndex v2, pgvector and PGroonga (+1 more)

### Community 187 - "law-rag-agent Workspace"
Cohesion: 0.25
Nodes (9): Agent State, Node-Level SSE Stream, Postgres LangGraph Checkpointer, v3 Thread Run API, F-001 v3 Foundation Plan, law-rag-agent Workspace, Postgres Checkpointer Task, StateGraph Implementation Tasks (+1 more)

### Community 188 - "실행 계획 0006: 예시 질문 기반 답변 품질 평가"
Cohesion: 0.13
Nodes (17): 답변 품질 평가, 생성 초안 인용 grounding gate, 기대 근거 계약, 근거 없음 차단, Recall@10, 대표 에너지 법령 질문, 근거 기반 검색 전용 응답, 검증 및 롤백 (+9 more)

### Community 189 - "질문 이력 보존 정리 작업 실행 계획"
Cohesion: 0.15
Nodes (17): advisory transaction lock, checklist_exports FK cascade, 대화 재집계와 빈 대화 삭제, expires_at cutoff, 질문 이력 1년 보존, history_retention_runs 감사, pg_cron scheduler 등록 보류, SECURITY DEFINER 정리 함수 (+9 more)

### Community 190 - "실행 계획 0021: 프로덕션을 근거 우선 실험 설계와 정렬"
Cohesion: 0.14
Nodes (18): collector 활성화 validator, 조 단위 후보 중복 제거, dense-only 프로덕션 검색, 생성 문맥 최대 5개 조문, 독립 keyword fallback, RRF·BM25·reranker 미도입, 프로덕션 인용 게이트, 프로덕션 근거 우선 설계 (+10 more)

### Community 191 - "0034 Web Auth Rehydration Throttle"
Cohesion: 0.25
Nodes (9): Auth Event Action, Auth Rehydration Control, Browser Network Verification, 0034 Web Auth Rehydration Throttle, No Refocus Rehydration, 0040 Production Auth Rehydration Verification, Production Auth Deployment Check, Session-State Guard (+1 more)

### Community 192 - "Distributed Question Cancellation Plan"
Cohesion: 0.36
Nodes (9): Cancel API Status Contract, Distributed Question Cancellation Plan, Memory Coordinator Adapter, NVIDIA Hosted NIM Cancel Capability, Cancellation Owner Isolation, Persistent Cancellation Coordinator, Cancellation Polling Watcher, Production Migration Approval Gate (+1 more)

### Community 193 - "Todo Execution Plans Index"
Cohesion: 0.33
Nodes (9): Approved Question Bank, D-10 Calibration Gold, D-Full Gold On Demand Plan, D-Full Gold Scope, Generalization and Release Gate, Gold Preflight, QREL and Reference Artifacts, Todo Execution Plans Index (+1 more)

### Community 194 - "Evaluation Harness Consolidation Plan"
Cohesion: 0.36
Nodes (9): Agent Context Diet, Evaluation Conflict Detector, Rubric Counterexample Fixtures, Decision Record Normalization, Evaluation Harness Consolidation Plan, Evaluation State YAML, Exact Token Calculation, Machine-Readable Relevance Rubric (+1 more)

### Community 195 - "Live Search Reranking Plan"
Cohesion: 0.36
Nodes (9): D-10 Rerank Evaluation, Evidence Quality Gate Boundary, Generation Hit Selection, Heading and Directness Score, Live Search Reranking Plan, Live Search With Trace, Offline Rerank Case, Source Kind Signal (+1 more)

### Community 196 - "Provider-Neutral Answer Model Selection Plan"
Cohesion: 0.39
Nodes (9): Allowed Model Profiles, Compatibility Migration Telemetry, Provider Model Failure Contract, Provider Model Registry, Provider-Neutral Answer Intent, Provider-Neutral Answer Model Selection Plan, Provider-Neutral Public Request Schema, Search-Only Fallback (+1 more)

### Community 197 - "R1 local rerank"
Cohesion: 0.22
Nodes (9): Experiment D-10-R1 local rerank results, Held-out validation required, R1 hit at 10 equals 7 of 10, R1 hit at 3 equals 7 of 10, R1 hit at 5 equals 7 of 10, Manual direct evidence, Parent-heading directness v1 scoring profile, R1 local rerank (+1 more)

### Community 198 - "Experiment D-10 manual diagnostic"
Cohesion: 0.22
Nodes (9): Codex-user agreement 10 of 10, Experiment D-10 manual diagnostic, Manual hit at 10 equals 7 of 10, Manual hit at 1 equals 6 of 10, Manual hit at 3 equals 6 of 10, Manual hit at 5 equals 6 of 10, Three cases without direct evidence, Top-five irrelevant candidates 28 (+1 more)

### Community 199 - "RAG 검색·근거 선택 패턴"
Cohesion: 0.22
Nodes (9): 검색 후보와 직접 근거 분리, 입력 문서 품질 경계, Hybrid·Reranker·Graph 평가 채택 게이트, Local·Global GraphRAG 검색, Reciprocal Rank Fusion, RAG 검색·근거 선택 패턴, 인용 가능한 Context Package, 직접 근거 선택 (+1 more)

### Community 200 - "검색 성능·관측 공식 자료"
Cohesion: 0.22
Nodes (9): PGroonga 전문 검색, PostgreSQL EXPLAIN 측정, Prepared Statement Cache 0, 원격 DB 왕복 예산, 검색 지연·후보 관측 메트릭, 검색 성능·관측 공식 자료, 4단계 순차 검색 완화, Supavisor Transaction Mode (+1 more)

### Community 201 - "vercel.json"
Cohesion: 0.25
Nodes (7): excludeFiles, maxDuration, functions, app/main.py, regions, $schema, icn1

### Community 202 - "answer-mode.ts"
Cohesion: 0.31
Nodes (7): openHistory(), AI_UNAVAILABLE_NOTICE, AnswerModeResolution, AnswerPreference, isTerraAvailabilityFailure(), resolveResponseAnswerMode(), TERRA_FALLBACK_NOTICE

### Community 203 - "Embedding Profile"
Cohesion: 0.25
Nodes (8): Embedding Profile, Legal Provision Passage Contract, Retrieval Lineage Catalog 0011, HnswIndexManager CLI, Native-Dimension NIM Embedding, v2 Passage Template, Provisions Input Projection, v2 PGVector Physical Table

### Community 204 - "실행 계획 0001: MVP 기반 확정"
Cohesion: 0.13
Nodes (18): 인용 검증 게이트, Google OAuth, 독립 collector, JSON 우선·XML 폴백, 법률 RAG MVP, 문서 우선 모듈형 모놀리스, 국가법령정보 공동활용 Open API, 질문 이력 1년 보존 (+10 more)

### Community 205 - "실행 계획 0016: 실험 A — 일반 텍스트 조문 청킹 관찰"
Cohesion: 0.11
Nodes (22): 조문 전체 단위 청크, Markdown·JSON 원자 저장, law_json.parse_legal_document, 실험 A 일반 텍스트 청킹, ProvisionRecord, 텍스트 입력 어댑터, UI 잔여 줄 제거, 검증 및 롤백 (+14 more)

### Community 206 - "Harness Engineering 적용 메모"
Cohesion: 0.14
Nodes (11): AGENTS 작업 지도·계약, 아키텍처 경계와 의존성 방향, 문서 자동화·구조 테스트 부채, Harness Engineering 적용 메모, 점진적으로 읽는 분류 문서, 품질·보안·신뢰성 독립 문서, 아직 적용하지 않은 내용, 이 저장소에 적용한 내용 (+3 more)

### Community 207 - "route.ts"
Cohesion: 0.71
Nodes (4): GET(), authErrorPath(), callbackBaseUrl(), safeAuthNextPath()

### Community 208 - "post_edit_lint.py"
Cohesion: 0.52
Nodes (6): build_command(), main(), Path, read_hook_input(), resolve_file_path(), to_repo_relative()

### Community 209 - "LangGraph StateGraph"
Cohesion: 0.29
Nodes (7): Conditional Blocking Edge, Future Interrupt and Web Search, generate Node, route Node, LangGraph StateGraph, validate Node, v3 Design Status Proposed

### Community 210 - "실행 계획 0003: 채팅 중심 웹 경험"
Cohesion: 0.14
Nodes (15): 익명 질문 비저장, 채팅 중심 반응형 셸, 로그인 대화 이력, 검색 전용 모드, gpt-5.6-terra 생성 모델, 검증과 롤백, 결과와 잔여 작업, 결정 로그 (+7 more)

### Community 211 - "학습 노트 통합 실행 계획"
Cohesion: 0.11
Nodes (24): HNSW 영구 제외, 승인 gold 미실행 상태, 법령 코퍼스 생애주기, 현재 dense-only 계약, 평가와 실험 읽기, 근거 우선 검색과 답변, 5개 장 학습 구조, HNSW 영구 제외 (+16 more)

### Community 212 - "Article 12 license cancellation"
Cohesion: 0.38
Nodes (7): Article 10 transfer, split, and merger, Article 11 succession, Article 12 license cancellation, Article 53 electricity commission, Article 7 business license, Article 8 disqualification, Article 9 installation and start duty

### Community 213 - "account.py"
Cohesion: 0.08
Nodes (54): conversation_turns(), conversations(), current_user(), _decode_conversation_cursor(), _decode_cursor(), _decode_turn_cursor(), delete_account(), delete_conversation() (+46 more)

### Community 215 - "0034: 웹 프런트 탭 포커스 시 불필요한 인증·이력 재조회 억제"
Cohesion: 0.08
Nodes (23): 0034: 웹 프런트 탭 포커스 시 불필요한 인증·이력 재조회 억제, 범위, 비범위, 설계 (2026-08-08 확정, 미구현), 승격 조건, 완료 조건, 원인, 진행 기록 (+15 more)

### Community 216 - "Application Trust Boundary"
Cohesion: 0.40
Nodes (6): Citation Integrity Gate, Untrusted External Law Document, Prompt Injection, Rate-Limit Abuse, Stale or Partial Corpus, Application Trust Boundary

### Community 217 - "v2 Dense Retriever"
Cohesion: 0.33
Nodes (6): v2 Dense Retriever, v2 Ingestion Readiness Marker, SearchHit Mapping, search Node, v2 Retriever Reuse, Independent v3 Agent

### Community 218 - "E-10 Base Execution"
Cohesion: 0.33
Nodes (6): D-10 Gold Set, E-001 E-10 Experiment Plan, E-10 Base Execution, Historical Tier Routing, Maximum Twelve NVIDIA Calls, TD-011 Answer Quality Evaluation

### Community 219 - "Active Execution Plan Index"
Cohesion: 0.40
Nodes (5): Active Execution Plan Index, E-001 Todo, F-001 Todo, F-005 Picked Up, Roadmap Authority

### Community 220 - "0059 Task Management Metadata and Roadmap"
Cohesion: 0.40
Nodes (6): Execution-Plan Lifecycle, Manual GitHub Label Mapping, Single Picked-Up Constraint, 0059 Task Management Metadata and Roadmap, Task Metadata Contract, Thin Roadmap Status Index

### Community 221 - "Experiment A chunking results"
Cohesion: 0.33
Nodes (6): Electric Utility Act chapter 2 fixture, Experiment A chunking results, Local user-provided experiment, parse_legal_document parser, Parser schema version 2, Six article chunks

### Community 222 - "실제 터미널 출력"
Cohesion: 0.08
Nodes (23): 반복 실행 비교, 벡터 지문, 비교 목적, 실제 터미널 출력, 실행 1, 실행 10, 실행 11, 실행 12 (+15 more)

### Community 223 - "v2-execution.ts"
Cohesion: 0.15
Nodes (20): cancelExecution(), followExecution(), isPreparedExecution(), isQuestionResponse(), isRecord(), json(), KNOWN_ACTIONS, parseFrame() (+12 more)

### Community 224 - "Quality Scorecard"
Cohesion: 0.33
Nodes (6): Quality Scorecard, Mock Evaluation Limitation, Quality Scorecard Assessment, Search Quality: B, Search Availability SLI/SLO: 99.9%, E-001 AI Answer Evaluation E-10

### Community 225 - "로드맵 정본·컨텍스트 절약 설계"
Cohesion: 0.15
Nodes (12): 검사와 훅, 검증, 권위 관계, 로드맵 정본·컨텍스트 절약 설계, 목적, 비범위, 상태와 파일 lifecycle, 생성되는 로드맵 (+4 more)

### Community 226 - "4. 평가와 실험 읽기"
Cohesion: 0.04
Nodes (43): gold 평가셋으로 승격하는 절차, 결정 기록, 독립 주석과 blind 평가, 목적, 분할과 지표 계산 계약, 실험 D 일반 사용자 질문은행과 gold 주석 경계, 왜 질문과 정답을 동시에 자동 생성하지 않는가, 평가 자료의 관계 (+35 more)

### Community 227 - "Vercel·Supabase 운영 전환 설계"
Cohesion: 0.09
Nodes (23): API Vercel Project, FastAPI Vercel 배포 준비 조건, Terra 준비 상태의 의미, Vercel·Supabase 운영 전환 설계, Web·API 연결과 Preview CORS, Web Vercel Project, 결정 기록, 데이터베이스 연결 (+15 more)

### Community 228 - "dialog-focus.ts"
Cohesion: 0.70
Nodes (3): dialogKeyAction, focusInitial(), restoreFocus()

### Community 229 - "web/proxy.ts"
Cohesion: 0.60
Nodes (3): updateSession(), config, proxy()

### Community 230 - "Current State Session Start Pointer"
Cohesion: 0.70
Nodes (5): Authoritative Question Execution, Current State Session Start Pointer, Generation Indexing, Sentence-Level Grounding SSE, V2 LlamaIndex Framework Pipeline

### Community 233 - "Execution-Plan Metadata Contract"
Cohesion: 0.40
Nodes (5): Execution-Plan Metadata Contract, GitHub Type Labels, Picked Up Singleton, Plan Artifact Lifecycle, Thin Roadmap Index

### Community 234 - "Effective-Date Half-Open Interval"
Cohesion: 0.40
Nodes (5): as_of_date, Document Versions Natural Key, Effective-Date Half-Open Interval, unsupported_corpus_date HTTP 422, TD-027 v2 Date Gate

### Community 235 - "Korean translation materials"
Cohesion: 0.40
Nodes (5): Alembic autogenerate translation, Korean translation materials, OpenAI Vector embeddings translation, Research and standards excerpts translation, Source term preservation

### Community 236 - "실행 계획 0018: 실험 C — 지정 장·조 로컬 벡터 검색"
Cohesion: 0.11
Nodes (23): 로컬 corpus 원자 교체, 저작권법, 전기사업법, exhaustive cosine Top 3, LawOpenApiClient, 실험 C 지정 장·조 로컬 벡터 검색, NVIDIA passage embedding, 신재생에너지법 (+15 more)

### Community 237 - "참고 자료 카탈로그"
Cohesion: 0.40
Nodes (5): 외부 참고 자료와 법률 권위의 경계, Harness Engineering 메모, NVIDIA 로컬 추론·Vercel 연결 검토, 참고 자료 카탈로그, 안정적 링크·확인일·라이선스 메모

### Community 238 - "Expired Question-History Purge"
Cohesion: 0.40
Nodes (5): Advisory-Lock Idempotency, Expired Question-History Purge, D-009 Production Question-History Scheduler, Account-Deletion Propagation, One-Year Question-History Retention

### Community 239 - "law-rag-api"
Cohesion: 0.40
Nodes (5): law-rag-agent, law-rag-api, law-rag-collector, law-rag-core, law-rag-llamaindex

### Community 244 - "test_history_retention_migration.py"
Cohesion: 0.83
Nodes (3): load_migration(), test_retention_migration_is_serialized_idempotent_and_scheduler_neutral(), test_retention_migration_records_auditable_cleanup()

### Community 245 - "test_v3_thread_migration.py"
Cohesion: 0.83
Nodes (3): load_migration(), test_v3_thread_migration_downgrade_drops_index_before_table(), test_v3_thread_migration_has_expected_revision_and_schema()

### Community 246 - "0036 Account Modal Model Label"
Cohesion: 0.50
Nodes (4): AI Mode Status Copy, Citation-Verified Answer Badge, 0036 Account Modal Model Label, Provider-Neutral UI Copy

### Community 247 - "0037 Account Quota Toggle"
Cohesion: 0.50
Nodes (4): Account Quota Toggle, 0037 Account Quota Toggle, Quota Re-Enable Contract, Unlimited Account Mode

### Community 248 - "0056 Python Docstrings and Ruff D"
Cohesion: 0.50
Nodes (4): Pre-Existing Documentation Debt, 0056 Python Docstrings and Ruff D, Public API Docstrings, Ruff PEP 257 Docstring Policy

### Community 249 - "Electricity permit sentence A"
Cohesion: 0.50
Nodes (4): Electricity permit sentence A, Electricity permit paraphrase sentence B, Punctuation variant sentence, Identical question sentence

### Community 250 - "lay-energy-0346 rerank case"
Cohesion: 0.50
Nodes (4): lay-energy-0346, lay-energy-0346 rerank case, Direct evidence rank 8 to 2, lay-energy-0346 direct evidence rank 8

### Community 252 - "Bug issue form"
Cohesion: 0.67
Nodes (3): Bug issue form, Bug-report privacy notice, Bug reproduction and sanitized evidence

### Community 253 - "GitHub CI workflow"
Cohesion: 0.67
Nodes (3): Documentation checker, Web and Python quality checks, GitHub CI workflow

### Community 269 - "LlamaIndexLegalRepository"
Cohesion: 0.67
Nodes (3): LlamaIndexLegalRepository, v1 Answer Pipeline Reuse, v2 Search and Question Endpoints

### Community 270 - "Completed Execution Plans Index"
Cohesion: 0.67
Nodes (3): Verified Completed Plan Archive, Completed Execution Plans Index, Project Roadmap

### Community 271 - "실행 계획 0026: 실험 D-10 수동 검색·문맥 진단"
Cohesion: 0.20
Nodes (10): 검증과 롤백, 결정 로그, 구현 순서, 목적과 사용자 결과, 미결정과 차단 요소, 범위와 비범위, 실행 계획 0026: 실험 D-10 수동 검색·문맥 진단, 완료 조건 (+2 more)

### Community 272 - "NVIDIA 로컬 추론과 Vercel 연결 검토"
Cohesion: 0.12
Nodes (17): 1순위: outbound 작업 중계, 2026-07-19 Hosted NIM 결정, 2순위: NVIDIA-hosted NIM endpoint, 3순위: 인증된 reverse tunnel/gateway, NVIDIA 공식 참고자료, NVIDIA 로컬 추론과 Vercel 연결 검토, “NVIDIA가 최근 무료 배포했다”는 주장 확인, Qwen3:4b 대안 가능성 (+9 more)

### Community 273 - "RLS and auth.uid ownership"
Cohesion: 0.67
Nodes (3): RLS and auth.uid ownership, user_consents table, user_profiles table

### Community 285 - "audiovisual-rights-transfer-presumption"
Cohesion: 0.17
Nodes (12): 10. 전기사업법 제57조 — 0.15805304733422365, 1. 저작권법 제100조 — 0.7614980371908396, 2. 저작권법 제101조 — 0.6668837848915818, 3. 저작권법 제99조 — 0.4998693372642797, 4. 저작권법 제2조 — 0.41026333610016275, 5. 저작권법 제1조 — 0.2715532718591162, 6. 저작권법 제2조의2 — 0.2492213766100656, 7. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제2조 — 0.21182166799675062 (+4 more)

### Community 286 - "copyright-act-purpose"
Cohesion: 0.17
Nodes (12): 10. 전기사업법 제2조 — 0.2766948448417783, 1. 저작권법 제1조 — 0.5629934141372378, 2. 저작권법 제2조 — 0.4045600310166265, 3. 전기사업법 제1조 — 0.37251101323177055, 4. 저작권법 제2조의2 — 0.34489272951672617, 5. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제1조 — 0.3350023948818371, 6. 저작권법 제99조 — 0.3324521568968159, 7. 저작권법 제101조 — 0.33225848150341186 (+4 more)

### Community 287 - "electricity-commission-functions"
Cohesion: 0.17
Nodes (12): 10. 전기사업법 제4조 — 0.30802484840776917, 1. 전기사업법 제56조 — 0.5993898499225545, 2. 전기사업법 제53조 — 0.5397218095759785, 3. 전기사업법 제60조 — 0.4215336780686214, 4. 전기사업법 제58조 — 0.41961285029610973, 5. 전기사업법 제59조 — 0.4140941628501188, 6. 전기사업법 제57조 — 0.40659137809432, 7. 전기사업법 제54조 — 0.3755989344636726 (+4 more)

### Community 288 - "renewable-basic-plan-cycle"
Cohesion: 0.17
Nodes (12): 10. 저작권법 제2조의2 — 0.15088479230342758, 1. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제5조 — 0.736244584773862, 2. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제2조 — 0.3803033352176514, 3. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제4조 — 0.36815712382772947, 4. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제1조 — 0.33046360551694104, 5. 전기사업법 제3조 — 0.23903635322044742, 6. 전기사업법 제56조 — 0.17746305450754618, 7. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제3조 — 0.17728691209978362 (+4 more)

### Community 289 - "solar-is-renewable-energy"
Cohesion: 0.17
Nodes (12): 10. 전기사업법 제1조 — 0.16401504036431777, 1. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제2조 — 0.5738374923043102, 2. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제1조 — 0.390636921368038, 3. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제4조 — 0.37135226166757596, 4. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제5조 — 0.34012211395544883, 5. 전기사업법 제2조 — 0.2423786341266909, 6. 저작권법 제2조 — 0.24182255022059052, 7. 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 제3조 — 0.22048617126397796 (+4 more)

### Community 309 - ".write_nodes"
Cohesion: 0.25
Nodes (5): Any, TextNode, Persist transformed nodes in the newly allocated generation table., Copy unchanged source vectors and verify their lineage count., Run the physical-table verifier before the catalog transition.

### Community 358 - "0060: V2 기준일 지원 상한을 한국 날짜 today로 동적 계산"
Cohesion: 0.25
Nodes (8): 0060: V2 기준일 지원 상한을 한국 날짜 today로 동적 계산, 목표, 문제 상황·원인·해결, 배경, 비범위, 승격 조건, 완료 조건, 포함 범위

### Community 359 - "V3 LangGraph 에이전트 기본 골격 구현 계획"
Cohesion: 0.10
Nodes (20): Self-Review Notes(계획 작성자를 위한 것이며 태스크가 아님), Task 10: 그래프 조립, Task 11: `(user_id, thread_id)` 인덱스 마이그레이션, Task 12: `POST /v3/threads`, `POST /v3/threads/{id}/runs`, Task 13: `POST /v3/threads/{id}/runs/stream` (SSE), Task 14: `GET /v3/threads/{id}/state`, Task 15: 로그인 사용자의 `(user_id, thread_id)` 기록, Task 16: 문서 마무리 (+12 more)

### Community 360 - "실행 계획 0019: 실험 C — 검색 후보 관찰·기록·평가"
Cohesion: 0.12
Nodes (19): 조 단위 후보 10개, 최고 하위 청크 cosine 조 점수, candidate_k 기본 10, dense-only 기준선, 실험 D 문맥 구성 입력, 로컬 Markdown·JSON 실행 이력, raw 청크 후보 10개, Law@1·Recall·MRR 지표 (+11 more)

### Community 361 - "0028: 검색 전 질문 라우팅과 조건부 query 보강"
Cohesion: 0.10
Nodes (20): 0028: 검색 전 질문 라우팅과 조건부 query 보강, active 승격 조건, tier 1 사전 확장 — v1 질문은행(1,000문항) 전수 분석, tier 2 구현 방식(확정, 2026-08-08), 결론과 확정 사항, 결정 기록, 계획 검증 사례, 공인 문헌 조사 (+12 more)

### Community 362 - "0030: D-10 전수 qrel과 사용자 adjudication"
Cohesion: 0.10
Nodes (20): 0030: D-10 전수 qrel과 사용자 adjudication, M0 — 계약·preflight, M1 — corpus와 judgment 작업표, M2 — annotation 초안, M3 — 사용자 review와 adjudication, M4 — Gold 봉인 — 완료, v3 추가 기록 — 2026-08-07 (완료 이후 정정), 검증 (+12 more)

### Community 363 - "작업 관리 메타데이터와 얇은 로드맵"
Cohesion: 0.11
Nodes (17): GitHub 라벨 매핑, 검증, 결정 기록, 로드맵과 실행계획의 역할, 메타데이터 계약, 목적, 상태 전이와 이행, 작업 관리 메타데이터와 얇은 로드맵 (+9 more)

### Community 364 - "실행 계획 0004: Google 인증과 계정 수명주기"
Cohesion: 0.13
Nodes (18): 계정 삭제 cascade, 익명 질문 비소급 저장, 약관·개인정보 동의 버전 기록, Supabase Google OAuth PKCE, 내부 사용자 ID 매핑, OAuth state·nonce·redirect allowlist, 질문 이력 사용자별 RLS, Supabase JWT·세션 검증 (+10 more)

### Community 365 - "분산 취소·검색 문법·로컬 AI·부채 감사"
Cohesion: 0.12
Nodes (18): Agent별 단계, 분산 취소 공유 저장소, 임베딩 공급자 결정, 한글 수사·복수 항·범위 파서, 로컬 NVIDIA 모델 하드웨어 제약, outbound queue 로컬 모델 연결 대안, prompt 신뢰 경계, sticky routing 배제 (+10 more)

### Community 366 - "Discord 에이전트 오버레이"
Cohesion: 0.18
Nodes (11): Discord 에이전트 오버레이, TODO와 위임, 보고 내용, 보고 시점, 오류 Ledger, 완료 체크리스트, 작업 시작 계약, 적용 범위와 우선순위 (+3 more)

### Community 367 - "NVIDIA Hosted NIM 생성 모델 연결"
Cohesion: 0.14
Nodes (18): provider-neutral 생성 adapter, AI 비활성 검색 전용 fallback, DraftAnswer JSON schema, nvidia/nemotron-3-ultra-550b-a55b, NVIDIA hosted NIM, NVIDIA Hosted NIM 생성 모델 연결, 공급자 중립 생성 경계, 초기 reasoning 비활성 (+10 more)

### Community 368 - "v2 설계"
Cohesion: 0.12
Nodes (17): API (`apps/api`), v1 요약 (참고용, 변경 없음), V2: LlamaIndex 기반 검색 파이프라인 (Phase 1) 설계, v2 설계, Web (`apps/web`), 결정 기록, 데이터 모델과 Ingestion, 목표 (+9 more)

### Community 369 - "실행 계획 0005: 로그인·익명 사용자 전체 흐름 엣지케이스"
Cohesion: 0.14
Nodes (16): 익명 흐름 비저장, 인증 사용자 이력 소유권, 가짜 사용자 ID 테스트 경계, 로그아웃 UI·민감 대화 초기화, OAuth callback 입력 검증, quota·빈 결과 엣지케이스, 검증 및 롤백, 결과와 잔여 작업 (+8 more)

### Community 370 - "0039: 구조화된 에러 detail이 "[object Object]"로 표출됨"
Cohesion: 0.12
Nodes (15): 0035: 기준일 선택 범위를 오늘까지로 제한, 구현 결과 (2026-08-09), 비범위, 설계 (미착수, 방향만), 승격 조건, 완료 조건, 원인, 0039: 구조화된 에러 detail이 "[object Object]"로 표출됨 (+7 more)

### Community 371 - "실행 계획 0027: 실험 D-10-R1 로컬 재정렬"
Cohesion: 0.20
Nodes (9): 검증과 롤백, 결정 로그, 목적과 사용자 결과, 미결정과 차단 요소, 범위와 비범위, 실행 계획 0027: 실험 D-10-R1 로컬 재정렬, 완료 조건, 작업 TODO (+1 more)

### Community 372 - "실행 계획 0009: 연속 대화, 이력 페이지네이션, 인증 지연 개선"
Cohesion: 0.16
Nodes (15): AbortController 요청 취소, conversation·turn 저장 계약, cursor 페이지네이션, 대화 상세 지연 로딩, 400 메시지 rollover, 400 메시지 경계 폐기, 가정과 완료 조건, 검증 및 롤백 (+7 more)

### Community 373 - "NVIDIA RAG 및 이벤트 기반 취소 실행 계획"
Cohesion: 0.16
Nodes (15): Broadcast 깨우기 신호, DB 권위 취소 상태, 이벤트 기반 분산 취소, 기존 512차원 임베딩 공간, Supabase Free Realtime 보호 한도, 생성 근거 문자 예산, NVIDIA Nemotron 생성, NVIDIA RAG 및 이벤트 기반 취소 실행 계획 (+7 more)

### Community 374 - "단계 구조"
Cohesion: 0.12
Nodes (16): 2026-08-28 milestone sequencing decision, Plan self-review, Task 10: Whole-workspace verification and completion, Task 1: Generation·execution persistence migration, Task 2: Generation-aware ingestion and atomic publish, Task 3: Pinned active index and router/query-engine adapter, Task 4: Pure execution domain, grounding and final-answer contract, Task 5: Execution repository and global capacity lease (+8 more)

### Community 375 - "Auto Generating Migrations"
Cohesion: 0.12
Nodes (16): Affecting the Rendering of Types Themselves, Applying Post Processing and Python Code Formatters to Generated Revisions, Auto Generating Migrations, Autogenerating Multiple MetaData collections, Basic Post Processor Configuration, Comparing and Rendering Types, Comparing Types, Controlling the Module Prefix (+8 more)

### Community 376 - "AnswerEvent"
Cohesion: 0.07
Nodes (44): _admit_v2_provider_phase(), Acquire provider capacity before sending an SSE response when work will start., PhaseResult, datetime, QuestionPhaseCoordinator, Authoritative, replay-safe v2 phase coordination. Provider work is supplied as…, Start exactly one phase or return its persisted authoritative replay., AnswerEvent (+36 more)

### Community 377 - "실행 계획 0007: Production 자연어 검색과 단계별 관측"
Cohesion: 0.15
Nodes (14): 한국어 자연어 검색, NFTC 기술기준 청킹, PGroonga 단계형 완화 검색, 검색 전용 독립 동작, 공유 질의 정규화, 검증 및 롤백, 결정 로그, 목적과 사용자 결과 (+6 more)

### Community 378 - "Vector embeddings(벡터 임베딩)"
Cohesion: 0.13
Nodes (12): Can I share my embeddings online?, Do V3 embedding models know about recent events?, Embedding models, FAQ, How can I retrieve K nearest embedding vectors quickly?, How can I tell how many tokens a string has before I embed it?, How to get embeddings, New embedding models (+4 more)

### Community 379 - "v1 to LangChain/LangGraph/LlamaIndex Evolution"
Cohesion: 0.23
Nodes (15): _answer_question, Delegated v1 repository methods, v1 to LangChain/LangGraph/LlamaIndex Evolution, Experimental exposure guard, LangGraph route/search/generate/validate nodes, LlamaIndexLegalRepository, NvidiaNimAnswerer, Parallel version operation (+7 more)

### Community 380 - "Google OAuth·Supabase Auth 연결 설계"
Cohesion: 0.14
Nodes (14): Google Cloud → Google 인증 플랫폼 → 클라이언트 → `law-rag-web`, Google OAuth·Supabase Auth 연결 설계, Production 결정, Supabase Dashboard → Authentication → Sign In / Providers → Google, Supabase Dashboard → Authentication → URL Configuration, 결정 기록, 공식 참고, 대표 오류 (+6 more)

### Community 381 - "분산 질문 취소 실행 계획"
Cohesion: 0.14
Nodes (14): Agent API/runtime, Agent DB/coordinator, Agent Web/UX, Agent 운영 검증, Agent별 실행 TODO, 검증 명령, 롤백, 목적과 사용자 결과 (+6 more)

### Community 383 - "에너지 법령 RAG 아키텍처"
Cohesion: 0.15
Nodes (13): 검색 품질 검증 (실험 D), 결정 기록, 공개 API, 답변 안전 게이트, 모듈 경계, 목적, 문서 지도, 배포와 데이터 흐름 (+5 more)

### Community 384 - "[역사 문서] terra 모드에서 search_only 폴백 제거 (always-generate)"
Cohesion: 0.15
Nodes (13): 1. `validate_draft` 완화 ([openai_answerer.py:289](../../apps/api/app/adapters/openai_answerer.py#L289)), 2. 검색 후 0건 경로 ([main.py:515-533](../../apps/api/app/main.py#L515)), 3. 사전 라우팅 차단 경로 ([main.py:417-425](../../apps/api/app/main.py#L417)), 4. 생성 후 발견되는 clarification_required, 5. 관측성, 검증, 결과, 결정 (+5 more)

### Community 385 - "검색 인덱스와 임베딩 계보 설계"
Cohesion: 0.15
Nodes (13): BM25 확장 경계, passage 입력 계약, 검색 계보 catalog (`0011`), 검색 인덱스와 임베딩 계보 설계, 결론, 결정 기록, 물리 인덱스 존재와 현재 평가 계약은 다르다, 부분 corpus와 낡은 벡터 노출 방지 (+5 more)

### Community 386 - "v3 설계"
Cohesion: 0.15
Nodes (13): API (`apps/api`), State와 영속화, V3: LangGraph 에이전트 기본 골격 설계, v3 설계, 결정 기록, 노드 설계, 목표, 미결정 (+5 more)

### Community 387 - "일반인 답변 계약 v2 설계"
Cohesion: 0.17
Nodes (12): 1. 프롬프트 v2 (신규 함수, 기존 함수 보존), 2. Generation Profile 분리, 3. 가독성 평가 계약, 4. 원문 링크 (UI, 0043 범위 확장분), 5. 후속 todo로 분리: 실제(hosted) v1·v2 비교 실행, 검증, 결과, 결정 (+4 more)

### Community 388 - "V2 준비 상태와 HNSW 구현 계획"
Cohesion: 0.15
Nodes (12): Task 1: ingestion 실행 lifecycle, Task 2: v2 HNSW 인덱스 운영 모듈, Task 3: API 지연 초기화, Task 4: 정책·설계·전체 검증, V2 준비 상태와 HNSW 구현 계획, 결과 및 커밋, 결과 및 커밋, 결과 및 커밋 (+4 more)

### Community 389 - "Use cases"
Cohesion: 0.15
Nodes (13): Classification using the embedding features, Clustering, Code search using embeddings, Data visualization in 2D, Embedding as a text feature encoder for ML algorithms, Obtaining the embeddings, Obtaining user and product embeddings for cold-start recommendation, Question answering using embeddings-based search (+5 more)

### Community 390 - "Matryoshka Representation Learning"
Cohesion: 0.15
Nodes (12): 1. INTRODUCTION, Abstract, ABSTRACT, Coarse-to-fine representation, FIPS 180-4 — Secure Hash Standard (SHS), Flexible representation, Focus to learn more, Matryoshka Representation Learning (+4 more)

### Community 391 - "근거 우선 검색 품질 설계"
Cohesion: 0.17
Nodes (12): 검색 알고리즘 결정, 결론, 결정 기록, 구조 표지가 실제 제1조를 덮어쓴 문제, 그래프 RAG를 지금 쓰지 않는 이유, 근거 우선 검색 품질 설계, 다른 RAG 시스템과의 비교, 발견한 두 가지 corpus 결함 (+4 more)

### Community 392 - "install_git_hooks.py"
Cohesion: 0.26
Nodes (14): discover_repo_root(), _git_dir(), _git_output(), install(), _is_managed_hook(), main(), _parser(), ArgumentParser (+6 more)

### Community 393 - "국가법령정보 Open API 수집 계약"
Cohesion: 0.17
Nodes (12): Parser schema v3와 조문 식별자, 결정 기록, 국가법령정보 Open API 수집 계약, 로컬 cache의 SHA 재사용, 버전 식별과 효력 기간, 범위, 삭제 이력 동기화 계약, 수집 잠금과 벡터 활성화 경계 (+4 more)

### Community 394 - "0032: 실험 E-10 — AI 답변 소표본 평가 (0025 M6)"
Cohesion: 0.17
Nodes (12): 0032: 실험 E-10 — AI 답변 소표본 평가 (0025 M6), active 승격 조건, 결정 기록, 목적과 사용자 결과, 범위, 비범위, 역사적 E-10 실행 기록 (2026-08-08; D-010으로 대체됨), 완료 조건 (+4 more)

### Community 395 - "2. 법령 코퍼스의 생애주기"
Cohesion: 0.12
Nodes (16): 2. 법령 코퍼스의 생애주기, JSON 우선, XML은 스키마 폴백, raw Storage와 PostgreSQL을 둘 다 쓰는 이유, 게시 전 검사는 왜 읽기 전용이어야 하는가, 계보와 세대 이름, 시간은 `[from, to)`로 읽는다, 왜 검색 준비 게이트가 두 개인가, 잠금은 원자성과 역할이 다르다 (+8 more)

### Community 396 - "3. 근거 우선 검색과 답변"
Cohesion: 0.17
Nodes (12): 3. 근거 우선 검색과 답변, RAG의 목적은 그럴듯한 문장이 아니다, 검색 실패를 디버깅하는 순서, 검색 후보와 답변 문맥은 다르다, 검색 후처리기를 정답 판정기로 오해하지 않는다, 구조화 출력과 인용 gate, 먼저 구조 질의와 자연어 질의를 나눈다, 임베딩과 코사인을 최소한으로 이해하기 (+4 more)

### Community 397 - "5. 사용자·개인정보·장애 안전"
Cohesion: 0.17
Nodes (12): 5. 사용자·개인정보·장애 안전, AI provider와 폴백, rate limit은 신뢰 경계다, 결과 없음·장애·갱신 중을 나눈다, 관측 가능성과 로그 최소화, 보존과 삭제는 실제 DB 작업이다, 안전은 답변 뒤가 아니라 요청 전체에 있다, 익명 질문과 대화 이력 (+4 more)

### Community 398 - "Target File Structure"
Cohesion: 0.25
Nodes (7): F-005 V2 가독성 중심 리팩터링 구현 계획, Global Constraints, Target File Structure, Task 1: LlamaIndex generation·ingestion·query 패키지 분리, Task 2: API composition root와 v2 application service 추출, Task 3: v1/v2 HTTP router 분리와 slim application entry point, Task 4: Whole-repository verification and documentation

### Community 399 - "분산 질문 취소 설계"
Cohesion: 0.18
Nodes (11): 결정, 결정 기록, 목적, 보안, 분산 질문 취소 설계, 영속 상태, 왜 LISTEN/NOTIFY만 사용하지 않는가, 제한과 관측 (+3 more)

### Community 400 - "실험 D-10 전수 qrel과 사용자 adjudication"
Cohesion: 0.18
Nodes (11): 0251·0521 필수 답변 요소의 위치와 의미, 검증과 seal, 결정 기록, 고정 계약, 목적, 사용자 검토 방법, 실제 실행 결과, 실험 D-10 전수 qrel과 사용자 adjudication (+3 more)

### Community 401 - "Python docstring 정책"
Cohesion: 0.18
Nodes (9): Python docstring 정책, 결정 기록, 규칙, 목적, 자동 검사와 적용 범위, Python Docstrings and Ruff D Implementation Plan, 검증 증거, 결과 (+1 more)

### Community 402 - "terra 모드 search_only 폴백 제거 (always-generate) Implementation Plan"
Cohesion: 0.18
Nodes (10): Global Constraints, Task 1: `validate_draft` 근거 0건 게이트 완화, Task 2: `build_messages_v2`에 빈 근거 지시 추가, Task 3: 라우팅 차단 전용 프롬프트 + `NvidiaNimAnswerer.answer_blocked_route`, Task 4: 검색 후 근거 0건 분기가 항상 생성 단계로 진행하게 배선, Task 5: 사전 라우팅 차단 분기를 LLM 생성으로 배선, Task 6: 문서 정합성 확인 (완료), Task 7: 0046 파이프라인 지도와 활성 계획 목록 정합성 (+2 more)

### Community 403 - "청크"
Cohesion: 0.18
Nodes (10): 1. 제7조 — 사업의 허가, 2. 제8조 — 결격사유, 3. 제9조 — 전기설비의 설치 및 사업의 개시 의무, 4. 제10조 — 사업의 양수 및 법인의 분할ㆍ합병 등, 5. 제11조 — 사업의 승계 등, 6. 제12조 — 사업허가의 취소 등, 결과 요약, 실험 A — 기존 법령 파서 청킹 결과 (+2 more)

### Community 404 - "electricity-business-license-out-of-scope"
Cohesion: 0.18
Nodes (11): 10. 전기사업법 제53조 — 0.3242885585903023, 1. 전기사업법 제2조 — 0.43838407437171883, 2. 전기사업법 제56조 — 0.41453919634781433, 3. 전기사업법 제3조 — 0.41296463018223795, 4. 전기사업법 제1조 — 0.39412790458183994, 5. 전기사업법 제4조 — 0.36911421789713295, 6. 전기사업법 제57조 — 0.36783245840749795, 7. 전기사업법 제5조 — 0.3656175938561748 (+3 more)

### Community 405 - "실험 D-10 수동 검색·문맥 진단"
Cohesion: 0.18
Nodes (10): Codex·AI의 1차 확인사항, D-10 완료 조건과 다음 단계, 고정 입력과 결과 위치, 다른 실험과의 경계, 목적, 사용자 확인 뒤 계산하는 진단값, 사용자의 최종 확인사항, 실행 순서 (+2 more)

### Community 406 - "0024 점검 모드 기반 코퍼스 원자 반영"
Cohesion: 0.20
Nodes (9): 0024 점검 모드 기반 코퍼스 원자 반영, TODO와 담당, 검증, 검증 결과, 고정 데이터 흐름, 목표, 범위와 제외, 커밋 단위 (+1 more)

### Community 407 - "0066: 로드맵 정본·컨텍스트 절약 구현 계획"
Cohesion: 0.14
Nodes (13): 0066: 로드맵 정본·컨텍스트 절약 구현 계획, File Structure, Global Constraints, Plan Self-Review, Spec Coverage Review, Task 1: Shared index-header registry and deterministic rendering data, Task 2: Generated roadmap writer and read-only checker, Task 3: Normalize current plan headers and remove duplicate status indexes (+5 more)

### Community 408 - "파일 구조"
Cohesion: 0.20
Nodes (10): Global Constraints, Task 1: `build_messages_v2()` 프롬프트 함수, Task 2: v2 Generation Profile, Task 3: `NvidiaNimAnswerer`에 `message_builder` 주입, Task 4: 근거 카드에 원문 링크 (UI), Task 5: 문서 갱신과 상태 전이, 완료 조건 (설계 문서 기준), 원본 todo 배경 (+2 more)

### Community 409 - "Web 기준일 선택 상한을 한국 오늘으로 동적 유지 Implementation Plan"
Cohesion: 0.18
Nodes (10): API Alignment Amendment, Global Constraints, Task 0: 요구사항별 API 계약 회귀 검증, Task 1: 날짜 입력 상한의 TDD 구현, Task 2: V2 기준일 전달 회귀 테스트, Task 3: 전체 검증과 완료 기록, Web 기준일 선택 상한을 한국 오늘으로 동적 유지 Implementation Plan, 계획 본문 (+2 more)

### Community 410 - "Task 3 실행 보고서: v1/v2 HTTP router 분리"
Cohesion: 0.25
Nodes (7): Fix round 1 (review 반영), Graphify, Task 3 실행 보고서: v1/v2 HTTP router 분리, TDD 및 회귀, 검증, 경계 결정, 범위

### Community 411 - "v1 to v2 to v3 Pipeline Diagram"
Cohesion: 0.36
Nodes (10): v1 to v2 to v3 Pipeline Diagram, Node-level SSE streaming, Postgres checkpointer state snapshots, v1 operating lane, v2 LlamaIndex lane, v2 search replacement, v3 LangGraph lane, v3 reused v2 search (+2 more)

### Community 413 - "Global Constraints"
Cohesion: 0.29
Nodes (6): API main 모듈화 Implementation Plan, Completion, Global Constraints, Task 1: API registration boundary, Task 2: API quality verification, Task 3: Plan lifecycle

### Community 414 - "평가 전략"
Cohesion: 0.22
Nodes (9): Production 검색 디버깅 시드, 결과 기록, 결정 기록, 결정적 답변 계약 시드, 릴리스 게이트 초안, 원칙, 지표, 평가 전략 (+1 more)

### Community 415 - "검토한 선택지"
Cohesion: 0.22
Nodes (9): 1. 질문 키워드로 법률을 직접 지정, 2. 로컬 lexical 검색과 dense 검색을 RRF로 결합, 3. production PGroonga 재사용, 4. 외부 reranker 사용, 검토한 선택지, 결론, 결정 기록, 실험 C — 키워드 결합 검색 보류 설계 (+1 more)

### Community 416 - "실험 D-full 1,000문항 평가 설계"
Cohesion: 0.22
Nodes (9): gold 불변조건, gold의 날짜와 콘텐츠 스냅샷, 결정 기록, 권위 입력, 목적, 실행 경계, 실험 D-full 1,000문항 평가 설계, 지표 (+1 more)

### Community 417 - "이전 finding 확인"
Cohesion: 0.14
Nodes (13): Finding count, P1 — acceptance tests의 lifecycle/cardinality/actionability/body 경계 누락: 해결, P1 — headerless todo/active 누락: 해결, P1 — staged reference의 worktree fallback: 해결, P1 — `다음 행동` 한 문장: 해결, P1 — 전체 plan 본문 materialization: 해결, P2 — loose header grammar: 해결, P2 — 불필요한 compatibility alias surface: 해결 (+5 more)

### Community 418 - "기술 스택 ADR"
Cohesion: 0.22
Nodes (9): 검색·AI 사용 원칙, 결정 기록, 구성과 데이터 흐름, 근거 파일, 기술 스택 ADR, 목적과 기준, 버전별 프레임워크 경계, 의도적으로 하지 않는 선택 (+1 more)

### Community 419 - "test_postgres_identity.py"
Cohesion: 0.45
Nodes (11): _existing(), FakeEngine, _identity(), asyncio, test_delete_history_locks_conversation_before_deleting_question(), test_existing_consented_profile_does_not_require_headers_again(), test_existing_profile_can_record_missing_current_consent_once(), test_existing_profile_without_consent_is_rejected() (+3 more)

### Community 420 - "D-010 Single-Stage Router and Safe Routing-Unavailable Response Implementation Plan"
Cohesion: 0.25
Nodes (8): D-010 Single-Stage Router and Safe Routing-Unavailable Response Implementation Plan, File Structure, Global Constraints, Plan Self-Review, Task 1: Replace the tiered router with a single typed router, Task 2: Make router failure a no-search AI response with named stages, Task 3: Align documentation, lifecycle records, and final verification, Task 3 progress — 2026-08-25

### Community 421 - "운영 벡터 인덱스 구축 결과"
Cohesion: 0.22
Nodes (8): 과거 인덱스 준비와 실행 계획 감사, 실제 결과, 실행 명령, 운영 검색 확인, 운영 벡터 인덱스 구축 결과, 재실행 해석, 현재 corpus 기준일 계약, 후속 retrieval catalog와 이 기록의 관계

### Community 422 - "FakeResult"
Cohesion: 0.14
Nodes (3): FakeConnection, FakeResult, TransactionContext

### Community 423 - "보안 및 개인정보"
Cohesion: 0.22
Nodes (9): 개인정보 원칙, 관리형 플랫폼과 애플리케이션 책임, 기본 통제, 보안 및 개인정보, 보호 대상, 익명 rate-limit IP 신뢰 경계, 주요 위협, 출시 전 필수 검토 (+1 more)

### Community 424 - "Task 3 실행 보고서: v2 API 리소스 지연 초기화"
Cohesion: 0.22
Nodes (8): Fix round 1: 리소스 factory 초기화 실패의 stable 503 변환, Task 3 실행 보고서: v2 API 리소스 지연 초기화, TDD 및 수정, TDD 진행, 검증, 구현 내용, 원인, 작업 범위

### Community 425 - "completed/README.md"
Cohesion: 0.05
Nodes (33): 0036: 계정 및 모델 정책 모달의 모델명 하드코딩 문구 정리, 구현 결과 (2026-08-09), 비범위, 승격 조건, 완료 조건, 원인, 재개 사유와 진행 기록 (2026-08-09), 확정 설계 (+25 more)

### Community 426 - "답변 근거 검증 설계 (validate_draft)"
Cohesion: 0.25
Nodes (8): action 필드와 검증 강도 분기, unanswerable도 침묵하지 않는다, 검증 계약: 왜 텍스트 추측이 아니라 모델의 명시적 신호인가, 결정 기록, 답변 근거 검증 설계 (validate_draft), 목표, 발견하고 고친 오탐 두 가지, 재검증 비용 문제와 replay 도구

### Community 427 - "RAG 파이프라인 설계"
Cohesion: 0.22
Nodes (9): RAG 파이프라인 설계, 검색 단계, 결정 기록, 답변 계약, 목표, 문서 모델, 실패 모드, 캐시와 재현성 (+1 more)

### Community 428 - "실험 D-10 수동 검색·문맥 진단"
Cohesion: 0.25
Nodes (8): 결정 기록, 고정 입력, 목적, 수동 검토와 진단값, 실행 계약, 실험 C·D-10·D-full 경계, 실험 D-10 수동 검색·문맥 진단, 완료와 다음 단계

### Community 429 - "단일 단계 라우터와 라우터 불가 응답"
Cohesion: 0.25
Nodes (8): 결정 기록, 단일 단계 라우터와 라우터 불가 응답, 단일 라우터 계약, 라우터 불가 경로, 목적, 범위 밖, 외부 응답과 관측, 정상 법령 답변 경로

### Community 430 - "0041: 법제처 API의 법종구분코드를 실제로 파싱해 저장·응답에 반영"
Cohesion: 0.25
Nodes (8): 0041: 법제처 API의 법종구분코드를 실제로 파싱해 저장·응답에 반영, 결정 사항 (사용자, 2026-08-08), 구현 결과 (2026-08-09), 비범위, 승격 조건, 완료 조건, 확인된 사실, 후속 결정: `source_kind`·`law_type_code` 통합 보류 (2026-08-09)

### Community 431 - "프론트엔드 아키텍처"
Cohesion: 0.25
Nodes (7): 결정 기록, 경계, 상태 모델, 책임, 테스트, 프론트엔드 아키텍처, 화면 구조

### Community 432 - "0058: v2 청킹 ablation — 현재 조문 노드 vs LlamaIndex 하위 청킹"
Cohesion: 0.08
Nodes (21): 0047: 추가 정보 재질문 루프 중복 제거 및 미답변 처리, 목표, 비범위, 승격 조건, 완료 조건, 포함 범위, 0050: 질의 형식 엣지케이스 조사 및 회귀 테스트 뱅크 구축, 목표 (+13 more)

### Community 433 - "에너지 사업 법령 채팅"
Cohesion: 0.10
Nodes (17): MVP 허용 목록, 결정 기록, 비목표, 사용자와 문제, 에너지 사업 법령 채팅, 완료 기준, 핵심 여정, 후속 TODO — 프런트 기준일 차단 (+9 more)

### Community 434 - "NVIDIA Nemotron 3 Embed 1B 조사"
Cohesion: 0.25
Nodes (7): NVIDIA Nemotron 3 Embed 1B 조사, 결론, 공식 출처, 왜 L2 재정규화하는가, 왜 첫 512개인가, 적용 판단, 확인된 계약

### Community 435 - "신뢰성"
Cohesion: 0.25
Nodes (8): 관측 가능성, 사용자 관점의 핵심 기능, 성능 저하 전략, 신뢰성, 운영 준비 체크, 조정된 질문 timeout 예산 (0045), 질문 이력 보존 작업, 초기 SLI/SLO 제안

### Community 436 - "0046 기준 질문 파이프라인 지도 갱신 설계"
Cohesion: 0.25
Nodes (7): 0046 기준 질문 파이프라인 지도 갱신 설계, 검증, 결정 기록, 목적, 범위, 비범위, 표현 방식

### Community 437 - "실험 D — 검색 문맥 구성"
Cohesion: 0.25
Nodes (8): 2026-08-03 실제 결과, 목적, 실행 CLI, 실험 A에서 재사용한 기록 원칙, 실험 D — 검색 문맥 구성, 완료 조건, 입력 계약, 출력 계약

### Community 438 - "PhaseDeadline"
Cohesion: 0.52
Nodes (3): PhaseDeadline, datetime, test_repair_and_detail_share_one_fifty_five_second_budget()

### Community 439 - "Law RAG Collector"
Cohesion: 0.29
Nodes (7): Law RAG Collector, 게시 전 읽기 전용 사전검사, 기존 명령, 실패 복구, 예약 실행, 정기 운영 경로, 환경변수

### Community 440 - "ADR-NNNN: 결정 제목"
Cohesion: 0.29
Nodes (6): ADR-NNNN: 결정 제목, 검증, 결과, 결정, 대안, 맥락

### Community 441 - "실험 D-10 M2 동결과 M3 소표본 calibration"
Cohesion: 0.29
Nodes (7): D-full을 다시 여는 조건, M2 — 10문항 계약 동결, M3 — 진행 방법, 결정, 결정 기록, 실험 D-10 M2 동결과 M3 소표본 calibration, 판정과 다음 단계

### Community 442 - "시간 효력 모델"
Cohesion: 0.29
Nodes (7): 결정 기록, 날짜 구간, 마이그레이션과 검증, 버전 식별자, 법적 효력 구간과 corpus 지원 범위는 다르다, 서로 다른 세 가지 상태, 시간 효력 모델

### Community 443 - "6. v1에서 LangChain/LangGraph/LlamaIndex 버전으로: 로직이 어떻게 바뀌었나"
Cohesion: 0.22
Nodes (9): 6. v1에서 LangChain/LangGraph/LlamaIndex 버전으로: 로직이 어떻게 바뀌었나, v1: 한 함수 안의 순차 파이프라인, v2: 검색 한 칸만 새로 짜기, v3: 노드 단위로 다시 짜고 대화를 영속화하기 (설계 단계, 아직 미구현), 상세 자료를 찾는 곳, 세 버전 비교표, 왜 세 버전이 동시에 존재하는가, 읽을 때 지킬 구분 (+1 more)

### Community 444 - "0033: 트래픽 축적 후 라우팅·관측 재검토 묶음"
Cohesion: 0.29
Nodes (7): 0033: 트래픽 축적 후 라우팅·관측 재검토 묶음, A. (역사 기록) tier 1 사전 확장 재검토, B. 인증·비인증 사용자 이력 검토, 승격 조건, 완료 조건, 왜 묶었는가, 포함 항목

### Community 445 - "F-006 대화형 clarification workflow 설계"
Cohesion: 0.22
Nodes (8): F-006 대화형 clarification workflow 설계, V2 API와 workflow, 답변과 결정론적 grounding, 대화·질문 포맷 계약, 목적, 실패·보안·완료 조건, 작업 구조, 정본 상태와 LlamaIndex 경계

### Community 446 - "실험 D-10-R1 부모 표제·직접성 로컬 재정렬"
Cohesion: 0.25
Nodes (7): 결정 기록, 목적, 비교값, 성공 판정, 실험 D-10-R1 부모 표제·직접성 로컬 재정렬, 입력과 불변조건, 직접성 규칙 v1

### Community 448 - "Task 2 실행 보고서: 관리형 v2 HNSW 인덱스"
Cohesion: 0.29
Nodes (6): Fix round 1: P1 v2 테이블 경계 및 import 안전성, Task 2 실행 보고서: 관리형 v2 HNSW 인덱스, TDD 진행, 검증, 구현 내용, 작업 범위

### Community 449 - "D-010 Task 3 Report"
Cohesion: 0.29
Nodes (6): Commit record, D-010 Task 3 Report, Failure diagnosis and resolution, Files and contract alignment, Status, Verification evidence

### Community 450 - "1. 시스템 지도와 실행 경계"
Cohesion: 0.25
Nodes (8): 1. 시스템 지도와 실행 경계, 런타임과 재현성, 모노레포지만 실행 단위는 다르다, 사용자 질문 한 건의 큰 흐름, 어디가 권위 문서인가, 직접 확인, 한 문장 지도, 핵심 확인

### Community 451 - "0046 기준 질문 파이프라인 지도 설계"
Cohesion: 0.25
Nodes (8): 버전 관리 실행 계획, Clarification Missing Information, Legal Search Terra 경로, 0046 기준 질문 파이프라인 지도 설계, 사전 차단 질문 전용 LLM 경로, Terra Always-generate 계약, 빈 근거 Unanswerable 응답, Insufficient Evidence 판정

### Community 453 - "제품 감각"
Cohesion: 0.29
Nodes (6): 성공 신호(초안), 우리가 해결하려는 문제, 우선할 사용자 가치, 제품 감각, 판단 질문, 피해야 할 대리지표

### Community 454 - "단계"
Cohesion: 0.33
Nodes (6): 1. 제품 범위 결정, 2. 데이터 적법성과 품질 확인, 3. 기술 결정, 4. 수직 슬라이스 구현, 5. 검증과 운영 준비, 단계

### Community 455 - "실행 순서와 에이전트별 TODO"
Cohesion: 0.33
Nodes (6): Agent A — 공용 계약과 프로젝트 경계, Agent A 또는 루트 — 통합·회귀, Agent B — 독립 collector와 전체 연혁, Agent C — 목업 API, 로그인 이력, Terra 폴백, Agent D — 목업 로그인과 워크벤치 UI, 실행 순서와 에이전트별 TODO

### Community 456 - "에이전트별 TODO"
Cohesion: 0.33
Nodes (6): DB·마이그레이션 에이전트, Vercel·배포 에이전트, Web 통합 에이전트, 사용자가 해야 할 일, 에이전트별 TODO, 현재 집중 범위와 역할

### Community 457 - "검색 계약"
Cohesion: 0.33
Nodes (6): 1단계: 모든 핵심어 일치, 2단계: 최소 2개 핵심어 후보 풀, 3단계: 필수 앵커와 나머지 핵심어, 4단계: 근거 부족, 검색 계약, 공통 전처리

### Community 459 - "실험 C — Dense 검색 후보 관찰"
Cohesion: 0.29
Nodes (7): corpus 범위, 고정 평가, 실패 동작, 실험 C — Dense 검색 후보 관찰, 질문, 후보 10개와 자동 기록, 현재 하지 않는 것, 환경변수와 준비

### Community 460 - "실행 계획 운영법"
Cohesion: 0.33
Nodes (5): 기존 계획의 섹션 형식 (repository-specific metadata), 실행 계획 운영법, 위치, 작업 관리 메타데이터, 작업 상태 계약

### Community 461 - "검색 성능과 관측 공식 자료"
Cohesion: 0.33
Nodes (5): PGroonga, PostgreSQL, Supabase와 Vercel, 검색 성능과 관측 공식 자료, 이 프로젝트에 적용하는 결론

### Community 462 - "PULL_REQUEST_TEMPLATE.md"
Cohesion: 0.33
Nodes (5): 검증, 근거·데이터·보안, 목적, 문서와 운영, 변경

### Community 464 - "phase_service.py"
Cohesion: 0.09
Nodes (29): citations_for_hits(), execution_generation_hits(), execution_request_and_hits(), freeze_citations(), Any, Citation, datetime, Frozen-evidence mapping helpers for the v2 execution flow. (+21 more)

### Community 465 - "제품 디자인 원칙"
Cohesion: 0.33
Nodes (5): 목표, 원칙, 접근성, 제품 디자인 원칙, 핵심 화면(초안)

### Community 467 - "2026-07-14 병렬 품질 강화 TODO"
Cohesion: 0.40
Nodes (5): 2026-07-14 병렬 품질 강화 TODO, Agent B — 주간 수집과 즉시 승격 안전성, Agent C — 인용 의미 게이트와 API 보안, Agent D — 워크벤치 근거 탐색과 접근성, Root — 통합, 위협 모델, 완료 판정

### Community 468 - "단계"
Cohesion: 0.40
Nodes (5): Google OAuth와 사용자 경계, Supabase와 데이터 수명주기, Vercel Web/FastAPI 배포와 운영, 단계, 생성 provider와 품질 게이트

### Community 469 - "RAG 디버깅 보고서 계약"
Cohesion: 0.40
Nodes (5): 1. 실패 상황과 버전 고정, 2. Retrieve 검증, 3. Query 변환과 하이브리드 검증, 4. 생성과 검색 원인 분리, RAG 디버깅 보고서 계약

### Community 470 - "Agent별 TODO"
Cohesion: 0.40
Nodes (5): Agent별 TODO, RAG 감사 Agent — 읽기 전용, 부채 감사 Agent — 읽기 전용, 주 Agent — 코드·통합, 취소 조사 Agent — 읽기 전용

### Community 471 - "실험 D-10-R1 부모 표제·직접성 로컬 재정렬 결과"
Cohesion: 0.40
Nodes (4): 결과, 실험 D-10-R1 부모 표제·직접성 로컬 재정렬 결과, 입력 결박, 해석 한계

### Community 472 - "실험 D-10 사용자 확인 수동 진단"
Cohesion: 0.40
Nodes (4): 다음 결정, 실행 결박, 실험 D-10 사용자 확인 수동 진단, 확정 진단값

### Community 473 - "Production 검색 디버깅 결과: DB revision 0004"
Cohesion: 0.40
Nodes (4): Production 검색 디버깅 결과: DB revision 0004, 질문별 결과, 해석 제한, 환경

### Community 474 - "0045: Web/API 질문 timeout 예산 정렬 Implementation Plan"
Cohesion: 0.15
Nodes (13): 0045: Web/API 질문 timeout 예산 정렬 Implementation Plan, Completion conditions, Decision log, File map, Global Constraints, Rollback, Task 1: API 요청 예산과 설정 계약, Task 2: Apply the shared budget to the API pipeline (+5 more)

### Community 476 - "Findings"
Cohesion: 0.15
Nodes (12): Finding count, Findings, P1 — metadata가 전혀 없는 todo/active 계획이 조용히 registry에서 사라진다, P1 — staged 검증이 index에 없는 reference를 worktree에서 허용한다, P1 — tests가 요구한 lifecycle/cardinality/actionability/body-boundary 사례를 실제로 증명하지 않는다, P1 — `다음 행동`의 “한 문장” 계약을 검증하지 않는다, P1 — 전체 plan 본문을 실제로 읽고 materialize 한다, P2 — header grammar가 strict하지 않고 header 외 preamble text를 무시한다 (+4 more)

### Community 477 - "단계별 구조화 관측"
Cohesion: 0.50
Nodes (4): 질문 진단 JSONB, 단계별 구조화 관측, 4단계 검색 완화 파이프라인, 단계별 검색 trace

### Community 478 - "실제 후보"
Cohesion: 0.50
Nodes (4): 실제 후보, 실험 C — Dense 조 단위 검색 평가, 지표, 질문별 결과

### Community 479 - "Task 4 report: Scoped pre-commit installation and CI enforcement"
Cohesion: 0.15
Nodes (12): Commit, Documentation and graphify notes, Fix, Fix commit, Fix round 1, Green evidence, Green evidence, Implemented behavior (+4 more)

### Community 480 - "품질 점수표"
Cohesion: 0.50
Nodes (3): 갱신 규칙, 품질 점수표, 현재 평가 해석

### Community 481 - "실험 A — 기존 법령 파서 청킹 관찰"
Cohesion: 0.50
Nodes (3): 실패와 재실행, 실행, 실험 A — 기존 법령 파서 청킹 관찰

### Community 482 - "위협 모델"
Cohesion: 0.33
Nodes (6): 개인정보 흐름, 검증과 승인 조건, 결정 기록, 범위와 신뢰 경계, 위협 모델, 주요 위협과 통제

### Community 485 - "범위와 비범위"
Cohesion: 0.67
Nodes (3): 범위, 범위와 비범위, 비범위

### Community 486 - "TODO와 에이전트 배정"
Cohesion: 0.67
Nodes (3): TODO와 에이전트 배정, 주 에이전트, 하위 에이전트

### Community 491 - "계획 본문"
Cohesion: 0.40
Nodes (4): Task 1: 내보내기 UI와 클라이언트 코드 제거, Task 2: 검증과 완료 기록, 계획 본문, 체크리스트 내보내기 프런트 제거 Implementation Plan

### Community 497 - "GitHub 이슈와 PR 운영"
Cohesion: 0.40
Nodes (4): GitHub 이슈와 PR 운영, PR, 이슈, 프로젝트 보드

### Community 499 - "질문 사전 라우팅 설계 (0028, 대체됨)"
Cohesion: 0.50
Nodes (4): 0028 결정 기록 (역사), 0028의 문제 정의와 역사적 근거, 질문 사전 라우팅 설계 (0028, 대체됨), 현재 계약 (D-010)

### Community 503 - "check_roadmap.py"
Cohesion: 0.26
Nodes (11): _display_line(), _first_difference(), main(), _mismatch_message(), _parser(), _print_errors(), ArgumentParser, Path (+3 more)

### Community 504 - "Task 2 구현·self-review 보고서"
Cohesion: 0.17
Nodes (11): Concerns, Red — entry point 부재, Red — Windows byte newline 회귀, Task 2 구현·self-review 보고서, TDD 증거, 검증, 구현 결과, 범위 (+3 more)

### Community 507 - "0066 final whole-branch review"
Cohesion: 0.20
Nodes (9): 0066 final whole-branch review, Completion-gate resolution (2026-09-03), Final closure — 2026-09-03, Five-task and global-constraint audit, Initial blocking findings — 2026-09-03 (historical), Initial evidence — 2026-09-03 (historical), Initial verdict — 2026-09-03 (historical), Review scope (+1 more)

### Community 508 - "Task 1 구현·self-review 보고서"
Cohesion: 0.20
Nodes (9): Fix round 1 evidence, Green, Red, Self-review 및 concerns, Task 1 구현·self-review 보고서, TDD 증거, 범위, 변경 파일 (+1 more)

### Community 509 - "Task 5 report: Minimal-reading operator workflow and project documentation"
Cohesion: 0.20
Nodes (9): Commit, Green, Implemented contract, Red, Review fix (2026-09-03), Scope decision, Task 5 report: Minimal-reading operator workflow and project documentation, TDD evidence (+1 more)

### Community 512 - "Task 3 report: Normalize current plan headers and remove duplicate status indexes"
Cohesion: 0.22
Nodes (8): Commit, Concerns, Documentation check, Generated roadmap, Green evidence, Modified paths, Red evidence, Task 3 report: Normalize current plan headers and remove duplicate status indexes

### Community 513 - "Task 4 fix-round 재리뷰 — scoped roadmap pre-commit hook"
Cohesion: 0.22
Nodes (8): Finding count, P1 — Git-quoted non-ASCII staged path가 필터를 우회: 해결, P1 — staged-path discovery fail-open: 해결, Regression sweep, Task 4 fix-round 재리뷰 — scoped roadmap pre-commit hook, Verdict, 범위와 검증, 이전 finding 확인

### Community 514 - "Task 5 fix-round re-review — minimal-reading operator workflow"
Cohesion: 0.22
Nodes (8): Finding count, P1 — unbounded startup read of `CURRENT_STATE.md`: resolved, P2 — stale six-field header description: resolved, Previous findings, Regression sweep, Scope, Task 5 fix-round re-review — minimal-reading operator workflow, Verdict

### Community 515 - "Task 5 review — minimal-reading operator workflow"
Cohesion: 0.22
Nodes (8): Evidence, Findings, [P1] The normal startup instructions still require the whole current-state document, [P2] `docs/PLANS.md` still calls the expanded header a six-field header, Review scope and read-range record, Scope assessment, Task 5 review — minimal-reading operator workflow, Verdict

### Community 516 - "Roadmap Operator"
Cohesion: 0.25
Nodes (7): Roadmap Operator, 개요, 검증 명령, 네 가지 읽기 범위 (순서 고정), 빠른 참조, 상태 전이, 흔한 오류

### Community 519 - "Task 3 review: Normalize current plan headers and remove duplicate status indexes"
Cohesion: 0.29
Nodes (6): Documentation freshness check, Registry boundary change, Specification and scope, Task 3 review: Normalize current plan headers and remove duplicate status indexes, Verdict, Verification evidence

### Community 524 - "Task 2 independent review"
Cohesion: 0.33
Nodes (5): Deferred repository ROADMAP, Evidence, Findings, Task 2 independent review, Verdicts

### Community 527 - "Task 4 review — changes requested"
Cohesion: 0.40
Nodes (4): Confirmed, Findings, Task 4 review — changes requested, Verification note

### Community 529 - "SDD ledger — current plan: `docs/exec-plans/completed/0066-roadmap-registry-and-context-diet.md`"
Cohesion: 0.50
Nodes (3): Pre-flight interface scan, SDD ledger — current plan: `docs/exec-plans/completed/0066-roadmap-registry-and-context-diet.md`, Task consistency scan

## Ambiguous Edges - Review These
- `routing_unavailable` → `HNSW Excluded from v2`  [AMBIGUOUS]
  docs/design-docs/single-stage-router-and-failure-response.md · relation: semantically_similar_to
- `Qwen3:4b 연결 준비` → `요청 ID 기반 서버 취소 endpoint`  [AMBIGUOUS]
  docs/exec-plans/completed/0010-token-context-cancellation-and-search-coverage.md · relation: conceptually_related_to

## Knowledge Gaps
- **2075 isolated node(s):** `EmbeddingProfile`, `Theme`, `$schema`, `icn1`, `maxDuration` (+2070 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **84 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `routing_unavailable` and `HNSW Excluded from v2`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **What is the exact relationship between `Qwen3:4b 연결 준비` and `요청 ID 기반 서버 취소 endpoint`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `PostgresLegalRepository` connect `PostgresLegalRepository` to `bootstrap.py`, `evaluate_experiment_d_gold.py`, `CorpusSearchStatus`, `postgres_repository.py`, `corpus.py`, `search_only_answer`, `SearchTrace`, `ExperimentDBackend`, `test_backfill_embeddings.py`, `SourceKind`, `preflight_experiment_d_gold.py`, `PostgresExperimentDBackend`, `get_settings`, `LegalDocumentRecord`, `CorpusTemporalState`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `main_module()` connect `main.py` to `MemoryLegalRepository`, `test_question_timeout_budget.py`, `test_api_factory_composition.py`, `sse.py`, `SearchHit`, `bootstrap.py`, `law_rag_core/domain/schemas.py`, `test_security_boundaries.py`, `legal_search_router`, `RouteJudgment`, `api/dependencies.py`, `LlamaIndexLegalRepository`, `corpus.py`, `account.py`, `CorpusTemporalState`, `test_question_cancellation.py`, `v1/answering.py`, `AnswerEvent`, `test_v2_search.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `SourceKind` connect `SourceKind` to `experiment_search.py`, `publish_prepared_bundle`, `law_json.py`, `RawResponse`, `postgres_repository.py`, `corpus_update_bundle.py`, `MemoryLegalRepository`, `test_question_timeout_budget.py`, `test_api_factory_composition.py`, `LawOpenApiClient`, `SearchHit`, `PostgresLegalRepository`, `DeletionRecord`, `law_rag_core/domain/schemas.py`, `test_security_boundaries.py`, `QuestionRequest`, `RouteJudgment`, `law_rag_collector/service.py`, `law_rag_core/domain/catalog.py`, `LlamaIndexLegalRepository`, `search_only_answer`, `test_backfill_embeddings.py`, `account.py`, `test_prepared_update.py`, `test_layperson_prompt_v2.py`, `test_question_cancellation.py`, `main.py`, `AnswerEvent`, `LegalDocumentRecord`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 98 inferred relationships involving `SourceKind` (e.g. with `PostgresLegalRepository` and `._hit()`) actually correct?**
  _`SourceKind` has 98 INFERRED edges - model-reasoned connections that need verification._
- **Are the 57 inferred relationships involving `main_module()` (e.g. with `legal_search_router()` and `ready_corpus_temporal_state()`) actually correct?**
  _`main_module()` has 57 INFERRED edges - model-reasoned connections that need verification._
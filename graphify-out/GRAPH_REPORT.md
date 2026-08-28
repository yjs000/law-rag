> Token-accounting note: host-agent semantic extraction ran in Codex; platform token usage is not available to Graphify, so cost.json records 0 and must not be read as zero actual usage.

# Graph Report - law-rag  (2026-08-28)

## Corpus Check
- Large corpus: 512 files · ~453,689 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 5236 nodes · 11308 edges · 357 communities (277 shown, 80 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 982 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 155
- Community 156
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 164
- Community 165
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
- Community 173
- Community 174
- Community 175
- Community 176
- Community 177
- Community 178
- Community 179
- Community 180
- Community 181
- Community 182
- Community 184
- Community 185
- Community 186
- Community 187
- Community 188
- Community 189
- Community 190
- Community 191
- Community 192
- Community 193
- Community 194
- Community 195
- Community 196
- Community 197
- Community 198
- Community 199
- Community 200
- Community 201
- Community 202
- Community 203
- Community 204
- Community 205
- Community 206
- Community 207
- Community 208
- Community 209
- Community 210
- Community 211
- Community 212
- Community 213
- Community 214
- Community 215
- Community 216
- Community 217
- Community 218
- Community 219
- Community 220
- Community 221
- Community 222
- Community 223
- Community 224
- Community 225
- Community 226
- Community 227
- Community 228
- Community 229
- Community 230
- Community 231
- Community 232
- Community 233
- Community 234
- Community 235
- Community 236
- Community 237
- Community 238
- Community 239
- Community 240
- Community 241
- Community 242
- Community 243
- Community 244
- Community 245
- Community 246
- Community 247
- Community 248
- Community 249
- Community 250
- Community 251
- Community 252
- Community 253
- Community 268
- Community 269
- Community 270
- Community 271
- Community 272
- Community 273
- Community 274
- Community 275
- Community 276
- Community 277
- Community 278
- Community 279
- Community 281
- Community 282
- Community 283
- Community 284
- Community 285
- Community 286
- Community 287
- Community 288
- Community 289
- Community 290
- Community 291
- Community 292
- Community 293
- Community 294
- Community 295
- Community 296
- Community 297
- Community 298
- Community 308
- Community 309
- Community 310
- Community 311
- Community 312
- Community 313
- Community 314
- Community 315
- Community 316
- Community 317
- Community 318
- Community 319
- Community 320
- Community 321
- Community 322
- Community 323
- Community 324
- Community 325
- Community 326
- Community 327
- Community 328
- Community 329
- Community 330
- Community 331
- Community 332
- Community 333
- Community 334
- Community 335
- Community 336
- Community 337
- Community 338
- Community 339
- Community 340
- Community 341
- Community 342
- Community 343
- Community 344
- Community 345
- Community 346
- Community 347
- Community 348
- Community 349
- Community 350
- Community 351
- Community 352
- Community 353
- Community 354

## God Nodes (most connected - your core abstractions)
1. `SourceKind` - 108 edges
2. `PostgresLegalRepository` - 80 edges
3. `SearchHit` - 69 edges
4. `MemoryLegalRepository` - 60 edges
5. `QuestionRequest` - 58 edges
6. `RawResponse` - 53 edges
7. `LegalDocumentRecord` - 47 edges
8. `_answer_question()` - 43 edges
9. `audit_gold_dataset()` - 40 edges
10. `GoldRunError` - 38 edges

## Surprising Connections (you probably didn't know these)
- `Concurrent HNSW DDL` --semantically_similar_to--> `Operator-only v2 HNSW exception`  [INFERRED] [semantically similar]
  .superpowers/sdd/0054-v2-readiness-and-hnsw/task-2-report.md → ARCHITECTURE.md
- `Single-stage NVIDIA QuestionRouter` --semantically_similar_to--> `Single-stage NVIDIA QuestionRouter`  [INFERRED] [semantically similar]
  .superpowers/sdd/0057-single-stage-router-and-failure-response/task-3-report.md → ARCHITECTURE.md
- `routing_unavailable no-search failure` --semantically_similar_to--> `routing_unavailable no-search safety route`  [INFERRED] [semantically similar]
  .superpowers/sdd/0057-single-stage-router-and-failure-response/task-3-report.md → ARCHITECTURE.md
- `Search-ready publication gate` --semantically_similar_to--> `Atomic corpus publication gate`  [INFERRED] [semantically similar]
  apps/collector/README.md → ARCHITECTURE.md
- `Frozen D-10 calibration contract` --semantically_similar_to--> `D-10 search-quality calibration`  [INFERRED] [semantically similar]
  README.md → ARCHITECTURE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Grounded question pipeline** — architecture_question_router, architecture_answer_safety_gate, architecture_routing_unavailable [EXTRACTED 1.00]
- **Prepared collector publication flow** — apps_collector_readme_prepare_current, apps_collector_readme_generate_cache, apps_collector_readme_apply_prepared [EXTRACTED 1.00]
- **CI quality and documentation gate** — _github_workflows_ci_workflow, _github_workflows_ci_quality_gate, _github_workflows_ci_docs_checker [EXTRACTED 1.00]
- **Grounded Legal Answer Experience** — docs_product_sense_verifiable_investigation_starting_point, docs_design_evidence_path_first, docs_frontend_question_answer_citation_flow, docs_reliability_core_user_journey [INFERRED 0.75]
- **Safe Legal Data Boundary** — docs_security_protected_data_and_assets, docs_frontend_safe_source_rendering, docs_security_input_validation, docs_reliability_request_trace_observability [INFERRED 0.75]
- **근거 우선 검색·답변 경로** — docs_design_docs_open_law_api_ingestion_open_api_allowlist, docs_design_docs_evidence_first_retrieval_quality_corpus_validator, docs_design_docs_evidence_first_retrieval_quality_dense_only_retrieval, docs_design_docs_evidence_first_retrieval_quality_insufficient_evidence_gate, docs_design_docs_answer_grounding_validation_validate_draft [INFERRED 0.85]
- **독립 Gold 평가 계약** — docs_design_docs_experiment_d_layperson_question_bank_approved_question_set, docs_design_docs_experiment_d_layperson_question_bank_independent_gold_annotation, docs_design_docs_experiment_d_10_gold_adjudication_qrels, docs_design_docs_experiment_d_1000_evaluation_approved_gold, docs_design_docs_evaluation_strategy_evaluation_metrics [INFERRED 0.85]
- **인증·분산 취소 경계** — docs_design_docs_google_oauth_supabase_flow_supabase_auth, docs_design_docs_google_oauth_supabase_flow_fastapi_jwt_rls, docs_design_docs_distributed_question_cancellation_execution_state, docs_design_docs_distributed_question_cancellation_cancel_watcher, docs_design_docs_distributed_question_cancellation_cancel_endpoint_contract [INFERRED 0.75]
- **Retrieval Readiness and Exact Search Contract** — docs_design_docs_retrieval_index_storage_exhaustive_exact_dense, docs_design_docs_retrieval_index_storage_embedding_profile, docs_design_docs_retrieval_index_storage_corpus_search_ready, docs_design_docs_retrieval_index_storage_dynamic_corpus_snapshot [EXTRACTED 1.00]
- **v2 Grounded Execution Contract** — docs_design_docs_v2_llamaindex_framework_redesign_question_execution, docs_design_docs_v2_llamaindex_framework_redesign_frozen_citation_registry, docs_design_docs_v2_llamaindex_framework_redesign_grounded_sentence_verifier, docs_design_docs_v2_llamaindex_framework_redesign_final_answer_coordinator [EXTRACTED 1.00]
- **v3 StateGraph Workflow** — docs_design_docs_v3_langgraph_agent_foundation_design_state_graph, docs_design_docs_v3_langgraph_agent_foundation_design_route_node, docs_design_docs_v3_langgraph_agent_foundation_design_search_node, docs_design_docs_v3_langgraph_agent_foundation_design_generate_node, docs_design_docs_v3_langgraph_agent_foundation_design_validate_node, docs_design_docs_v3_langgraph_agent_foundation_design_postgres_checkpointer [EXTRACTED 1.00]
- **4단계 검색 완화 파이프라인** — docs_exec_plans_completed_0008_four_stage_retrieval_latency_and_debugging_all_keywords_match, docs_exec_plans_completed_0008_four_stage_retrieval_latency_and_debugging_pairwise_candidate_pool, docs_exec_plans_completed_0008_four_stage_retrieval_latency_and_debugging_anchor_validation, docs_exec_plans_completed_0008_four_stage_retrieval_latency_and_debugging_insufficient_evidence_stage [EXTRACTED 1.00]
- **근거 문맥 안전 체인** — docs_exec_plans_completed_0020_experiment_d_search_context_corpus_validator, docs_exec_plans_completed_0020_experiment_d_search_context_article_hierarchy_restoration, docs_exec_plans_completed_0020_experiment_d_search_context_direct_evidence_1_to_5, docs_exec_plans_completed_0020_experiment_d_search_context_insufficient_evidence_gate [EXTRACTED 1.00]
- **승인 Gold 평가 계보** — docs_exec_plans_completed_0022_retrieval_index_and_experiment_d_1000_question_approval_manifest, docs_exec_plans_completed_0022_retrieval_index_and_experiment_d_1000_approved_gold, docs_exec_plans_completed_0022_retrieval_index_and_experiment_d_1000_gold_adjudication_manifest, docs_exec_plans_completed_0022_retrieval_index_and_experiment_d_1000_experiment_d_runner [EXTRACTED 1.00]
- **D-10 Calibration Evaluation Flow** — docs_exec_plans_completed_0025_approved_questions_to_grounded_answer_roadmap_d10_calibration, docs_exec_plans_completed_0026_experiment_d_10_manual_review_d10_manual_review, docs_exec_plans_completed_0027_experiment_d_10_local_rerank_d10_r1_local_rerank, docs_exec_plans_completed_0030_d_10_full_corpus_qrels_adjudication_d10_gold_v3, docs_exec_plans_completed_0028_pre_retrieval_question_routing_route_fixture_v1 [INFERRED 0.85]
- **Answer Generation Safety Flow** — docs_exec_plans_completed_0043_layperson_answer_contract_v2_layperson_prompt_v2, docs_exec_plans_completed_0045_coordinated_question_timeout_budget_coordinated_question_timeout, docs_exec_plans_completed_0046_terra_always_generate_terra_always_generate, docs_exec_plans_completed_0057_single_stage_router_and_failure_response_routing_unavailable [INFERRED 0.75]
- **v2 Retrieval Operations** — docs_exec_plans_completed_0053_v2_llamaindex_retrieval_pipeline_llamaindex_v2_retrieval_pipeline, docs_exec_plans_completed_0054_v2_readiness_and_hnsw_v2_ingestion_readiness, docs_exec_plans_completed_0054_v2_readiness_and_hnsw_v2_hnsw_operator_control, docs_exec_plans_completed_0054_v2_readiness_and_hnsw_v2_lazy_resource_initialization [INFERRED 0.85]
- **Evaluation Gold, Rubric, Fixtures, and Metrics** — docs_exec_plans_todo_0029_d_full_gold_on_demand_d10_calibration_gold, docs_exec_plans_todo_0031_eval_harness_consolidation_machine_readable_relevance_rubric, docs_exec_plans_todo_0050_query_format_edge_case_regression_bank_regression_fixture_bank, docs_exec_plans_todo_0058_v2_chunking_ablation_d10_recall_at_k_mrr10 [INFERRED 0.75]
- **Runtime Clarification and Request Guards** — docs_exec_plans_todo_0047_clarification_loop_dedup_and_unanswered_handling_conversation_context, docs_exec_plans_todo_0050_query_format_edge_case_regression_bank_followup_conversation_context, docs_exec_plans_todo_0060_v2_dynamic_today_date_bound_future_date_422_guard [INFERRED 0.65]
- **Corpus, embedding, retrieval, and release lineage** — docs_generated_db_schema_corpus_snapshots, docs_generated_db_schema_embedding_profiles, docs_generated_db_schema_provision_embeddings, docs_generated_db_schema_retrieval_profiles, docs_generated_db_schema_retrieval_releases [EXTRACTED 1.00]
- **D-10 ranking and context calibration** — docs_generated_experiment_d_10_m3_calibration_summary_r1_local_rerank, docs_generated_experiment_d_10_m4_context_assembly_summary_r1_plus_a, docs_generated_experiment_d_10_local_rerank_parent_heading_directness_v1 [EXTRACTED 1.00]
- **Embedding-to-search pipeline** — docs_generated_experiment_b_embedding_results_output_512_dimensions, docs_generated_experiment_c_retrieval_evaluation_dense_article_search_baseline, docs_generated_law_rag_question_pipeline_map_vector_dense_search [INFERRED 0.85]
- **Validated corpus to grounded answer** — docs_learning_02_corpus_lifecycle_validated_corpus_generation, docs_learning_03_evidence_first_retrieval_evidence_first_rag, docs_product_specs_grounded_legal_qa_evidence_citation_ui [INFERRED 0.85]
- **Retrieval, evaluation, and safety contract** — docs_learning_03_evidence_first_retrieval_deterministic_citation_gate, docs_learning_04_evaluation_multi_stage_rag_evaluation, docs_learning_05_product_safety_product_safety_contract [INFERRED 0.85]
- **Versioned pipeline evolution** — docs_learning_06_v1_to_langchain_evolution_v1_sequential_pipeline, docs_learning_06_v1_to_langchain_evolution_v2_llamaindex_search, docs_learning_06_v1_to_langchain_evolution_v3_langgraph_design [EXTRACTED 1.00]
- **D-10 후보·근거·Gold 검토 흐름** — experiments_search_readme_article_candidates, experiments_context_readme_direct_evidence_selection, experiments_d_manual_readme_d10_manual_diagnostic, experiments_d_gold_10_readme_d10_gold_workflow [INFERRED 0.85]
- **NVIDIA 임베딩·512차원 검색 프로필** — docs_references_nvidia_nemotron_3_embed_1b_2026_07_23_nemotron_3_embed_1b, experiments_embeddings_readme_nvidia_512_output_contract, experiments_search_readme_nvidia_query_embedding, experiments_d_manual_readme_nvidia_512_profile [INFERRED 0.85]
- **생성 폴백·코퍼스 게이트·운영 경계** — docs_references_operations_runbook_corpus_search_gate, docs_references_operations_runbook_rollback_search_only, docs_references_qwen3_4b_integration_search_only_fallback, docs_superpowers_specs_2026_08_10_pipeline_map_0046_design_search_only_fallback [INFERRED 0.85]

## Communities (357 total, 80 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (111): _article_chunks(), _atomic_write_many(), _build(), build_context_package(), _candidate_rank(), ContextRecordingError, _evidence_case(), _load_context_runs() (+103 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (95): _acquire_corpus_mutation_lock(), _acquire_corpus_sync_run_lock(), _append_cache(), _arguments(), _backfill_database(), _bundle_passages(), _cache_batch_values(), _cache_file_lock() (+87 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (58): apply_migration(), drop_database_objects(), load_migration(), asyncio, reset_database(), test_retention_avoids_delete_deadlock_and_counts_actual_export_deletes(), test_retention_is_safe_during_concurrent_turn_save_and_has_strict_acl(), _apply_prepared_transaction() (+50 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (59): asyncio, test_domain_alias_finds_formal_renewable_energy_title(), test_future_version_is_excluded_before_effective_date(), TextNode, _chunk_payload(), _display_path(), ExperimentRunError, main() (+51 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (62): 코사인 유사도, 512차원 embed 계약, L2 재정규화, live API 반복성 관찰, 2048→512 첫 prefix slicing, nvidia/nemotron-3-embed-1b, 실행 계획 0017: 실험 B — NVIDIA NIM 두 문장 임베딩과 코사인 유사도, query·passage 입력 유형 (+54 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (45): RawResponse, plan_provision_sync(), ProvisionRecord, raw_object_path(), _corpus_gate_call_indices(), _deletion_repository(), _DeletionConnection, _document() (+37 more)

### Community 6 - "Community 6"
Cohesion: 0.10
Nodes (53): ConsentRequiredError, Exception, _ai_unavailable_error(), _authenticated_user(), _bearer_token(), changes(), _check_quota(), conversation_turns() (+45 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (46): _arguments(), _atomic_publish(), _audit_or_raise(), _candidate_record(), _canonical_json_bytes(), _capture_query_plans(), _current_code_provenance(), _embed_all_questions() (+38 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (48): _arguments(), _article_contexts(), _article_root(), _atomic_publish_run(), _atomic_write_query_cache(), _cache_file_sha256(), _cache_key(), _canonical_json_bytes() (+40 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (30): _async_url(), _corpus_items(), _corpus_search_status(), _corpus_temporal_population_statement(), _corpus_temporal_state(), _dense_search_parameters(), _dense_search_statement(), _elapsed_ms() (+22 more)

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (46): embedding_text_sha256(), EmbeddingProfile, legal_provision_embedding_text(), Build the versioned passage text used for provision embeddings., SourceProvision, canonical_gold_corpus_snapshot_id(), canonical_gold_dataset_sha256(), Hash unique content populations; evaluation dates are sealed separately. (+38 more)

### Community 11 - "Community 11"
Cohesion: 0.06
Nodes (49): exhaustive exact cosine, 고정 공인 IP Windows collector, Google OAuth, HNSW 검색 경로 제외, Matryoshka Representation Learning, OpenAI embedding model 발표, pgvector 공식 문서, 실행 계획 0002: 실제 서비스 연결 (+41 more)

### Community 12 - "Community 12"
Cohesion: 0.11
Nodes (45): test_content_snapshot_identity_does_not_include_the_calendar_date(), BundleState, _atomic_write(), _build_manifest(), canonical_corpus_population_fingerprint(), canonical_corpus_publish_snapshot_id(), canonical_corpus_snapshot_id(), _canonical_json() (+37 more)

### Community 13 - "Community 13"
Cohesion: 0.09
Nodes (32): _date_or_none(), MemoryLegalRepository, date, Path, UUID, test_quota_resets_on_next_day(), asyncio, Path (+24 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (46): Apply Prepared Transaction, Atomic Corpus Publication, Base Snapshot Fingerprint, Embedding Cache Generation, 0024 Maintenance Corpus Publish, Prepare Current Bundle, Search Ready Gate, Corpus-First Answer Roadmap (+38 more)

### Community 15 - "Community 15"
Cohesion: 0.08
Nodes (31): BaseModel, _RouteJudgmentSchema, A provider judgment for one of the four provider-resolvable routes., RouteDecision, RouteJudgment, _allow_quota(), client(), _hit() (+23 more)

### Community 16 - "Community 16"
Cohesion: 0.12
Nodes (26): CancelSignalResult, ExecutionNotOwnedError, ExecutionStatus, InvalidExecutionTransitionError, MemoryQuestionCancellationCoordinator, _now(), datetime, Exception (+18 more)

### Community 17 - "Community 17"
Cohesion: 0.10
Nodes (35): _elapsed_ms(), _match_score(), _natural_trace(), datetime, Keep the highest-ranked leaf for each document/article pair., _stage_trace(), _unique_article_hits(), _row_matching_terms() (+27 more)

### Community 18 - "Community 18"
Cohesion: 0.10
Nodes (32): GenerationProfile, 0025 M5 item 4: model/prompt/schema/context/sampling settings, versioned…, _atomic_write(), _code_fence(), _display_float(), Embedder, _embedding_digest(), _load_runs() (+24 more)

### Community 19 - "Community 19"
Cohesion: 0.14
Nodes (41): _arguments(), _artifact_name(), atomic_write_worklist(), build_pilot_worklist(), create_pilot_worklist(), _file_sha256(), _load_json_object(), main() (+33 more)

### Community 20 - "Community 20"
Cohesion: 0.12
Nodes (42): canonical_gold_case_payload_sha256(), ExperimentDGoldCase, ExperimentDGoldDataset, GoldMetricProtocol, Hash one complete validated gold-case payload using canonical JSON., _append_direct_supported_facet(), _case(), _corpus_snapshot() (+34 more)

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (24): _async_url(), _batches(), _embedding_eligible_version(), _mark_corpus_search_unready(), _ordered_ids(), ProvisionSyncPlan, AsyncEngine, date (+16 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (26): _compact_date(), LawOpenApiClient, LawOpenApiError, ParsedResponse, AsyncClient, date, RuntimeError, T (+18 more)

### Community 23 - "Community 23"
Cohesion: 0.05
Nodes (42): Clarification-required control, Nine-document energy corpus, Lay energy question approval review v1, Thirty-five high-risk questions, Fifteen intents, lay-energy-0201 approval case, not_annotated status, 1,000-question bank (+34 more)

### Community 24 - "Community 24"
Cohesion: 0.12
Nodes (39): _answerability_diagnostic_report(), _case_metrics(), _control_pair_diagnostics(), _dcg(), evaluate_dense_retrieval(), _family_bootstrap_confidence_intervals(), _family_macro_average(), _family_primary_report() (+31 more)

### Community 25 - "Community 25"
Cohesion: 0.08
Nodes (41): _answer_question, Delegated v1 repository methods, v1 to LangChain/LangGraph/LlamaIndex Evolution, Experimental exposure guard, LangGraph route/search/generate/validate nodes, LlamaIndexLegalRepository, NvidiaNimAnswerer, Parallel version operation (+33 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (27): BaseSettings, model_validator, Settings, main(), 0025 M5 item 6: bounded hosted smoke test for real NVIDIA answer generation.…, DenyingPostgresIdentity, MonkeyPatch, consume_quota always denies, so a passing test proves the toggle controls it. (+19 more)

### Community 27 - "Community 27"
Cohesion: 0.05
Nodes (39): dependencies, next, react, react-dom, @supabase/ssr, @supabase/supabase-js, devDependencies, eslint (+31 more)

### Community 28 - "Community 28"
Cohesion: 0.14
Nodes (36): DraftAnswer, BaseModel, 구조 검증만 한다: 인용 ID가 실제 제공된 근거를 가리키는지, action별로 요구되는 필드가 채워졌는지. 문장 내용이 근거와 의미적으로…, validate_draft(), _draft_from_dict(), _hit_from_dict(), main(), 검증기(validate_draft) 코드를 고친 뒤 실제 근거·draft로 재검증한다 - 새 NVIDIA 호출 0회. 2026-08-08… (+28 more)

### Community 29 - "Community 29"
Cohesion: 0.09
Nodes (29): Frozen corpus context recorded with the approved Experiment D question bank.…, _canonical_sha256(), question_scope_payload(), question_scope_set_sha256(), question_scope_sha256(), Canonical identities for the Experiment D layperson question bank., Return the fields a user approves as one question's text and scope., _arguments() (+21 more)

### Community 30 - "Community 30"
Cohesion: 0.16
Nodes (31): PostgresLegalRepository, _ConnectionContext, _document(), _FakeConnection, _FakeEngine, asyncio, parametrize, _row() (+23 more)

### Community 31 - "Community 31"
Cohesion: 0.09
Nodes (23): ApprovalManifestSourceBank, ApprovedQuestion, canonical_provision_id_set_sha256(), ExperimentDGoldAdjudicationManifest, GoldAdjudicatedCase, GoldAnnotationProtocol, GoldAnnotationReview, GoldAsOfPopulation (+15 more)

### Community 32 - "Community 32"
Cohesion: 0.05
Nodes (38): Answer Generation, Answer Validation, Blocked Answer Generation, Blocked Fallback, Blocked Response Validation, Evidence Retrieval, Evidence Source Validation, legal_search Route (+30 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (35): _arguments(), atomic_write_manifest(), build_question_approval_manifest(), _canonical_sha256(), create_question_approval(), load_question_bank(), main(), parse_approved_at() (+27 more)

### Community 34 - "Community 34"
Cohesion: 0.21
Nodes (32): run_and_publish_approved_gold(), FakeBackend, FakeEmbedder, _fixed_clock(), gold_bundle(), GoldFixtureBundle, PublisherSpy, asyncio (+24 more)

### Community 35 - "Community 35"
Cohesion: 0.09
Nodes (21): HnswIndexManager, AsyncEngine, Manage the optional v2 HNSW index without coupling it to ingestion., Return whether the exact v2 index exists in the public catalog., Create the index if it is absent and report whether creation was requested., Create the v2 cosine HNSW index using a non-transactional connection., Drop the v2 HNSW index using a non-transactional connection., _validate_table_name() (+13 more)

### Community 36 - "Community 36"
Cohesion: 0.12
Nodes (32): build_nodes(), changed_provision_ids(), delete_nodes(), existing_hashes(), _finish_ingestion_run(), IngestionResult, AsyncEngine, ProvisionRecord (+24 more)

### Community 37 - "Community 37"
Cohesion: 0.13
Nodes (27): DeletionKind, _clean(), _date(), DeletionPage, DeletionRecord, _first(), _json_records(), parse_deletions_json() (+19 more)

### Community 38 - "Community 38"
Cohesion: 0.09
Nodes (31): AiFailureCategory, AiFallbackReason, AiRuntimeState, AnswerMode, ChangeItem, ChecklistExportFormat, Citation, ConversationPage (+23 more)

### Community 39 - "Community 39"
Cohesion: 0.14
Nodes (31): _arguments(), ArtifactBinding, ArtifactBindings, FrozenCase, FrozenD10ContractError, FrozenD10EvaluationContract, FrozenRunBinding, load_frozen_contract() (+23 more)

### Community 40 - "Community 40"
Cohesion: 0.09
Nodes (28): get_settings(), BaseSettings, v2 LlamaIndex 검색 구성 값을 제공한다., 환경 변수에서 읽는 v2 색인 및 임베딩 구성이다., 프로세스 동안 재사용할 v2 구성 값을 반환한다., Settings, build_embedder(), Settings (+20 more)

### Community 41 - "Community 41"
Cohesion: 0.08
Nodes (34): Task 2 HNSW execution report, Concurrent HNSW DDL, HnswIndexManager, Task 3 v2 API execution report, Lazy v2 resource initialization, Stable v2 not-ready 503, D-010 verification evidence, D-010 Task 3 report (+26 more)

### Community 42 - "Community 42"
Cohesion: 0.11
Nodes (17): _ConnectionContext, _Embedder, _Engine, _ExistingTableFailingQueryConnection, _LifecycleConnection, _LifecycleEngine, _MissingTableConnection, _provisions() (+9 more)

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (30): stopGeneration(), submit(), cancelQuestion(), appendPendingTurn(), AssistantChatMessage, ChatMessage, ChatSession, completedConversationTurns() (+22 more)

### Community 44 - "Community 44"
Cohesion: 0.16
Nodes (27): NvidiaNimAnswerer, QuestionRoute, NVIDIA hosted NIM adapter with a schema-validated legal answer boundary., 0046: 사전 라우팅이 legal_search 밖으로 걸러낸 질문(embedding·검색 없음)에 근거 없이 LLM을 호출한다 -…, build_blocked_route_messages(), QuestionRoute, 0046: 사전 라우팅이 legal_search 밖으로 걸러낸 질문(embedding·검색을 아예 하지 않는 경로)에 근거 없이 LLM을…, _answerer() (+19 more)

### Community 45 - "Community 45"
Cohesion: 0.09
Nodes (33): clarification_resubmission_summary(), post_generation_clarification_answer(), QuestionResponse, 0028 "비용 최소화 결정"의 재제출 템플릿. route_guidance_fallback(사전 라우팅)와…, 2026-08-08: DraftAnswer.action == "clarification_required"일 때 쓴다 - 사전 라우팅이 못 잡고…, Build the deterministic AI-mode fallback for a route without evidence.…, route_guidance_fallback(), _ai_unavailable_reason() (+25 more)

### Community 46 - "Community 46"
Cohesion: 0.14
Nodes (23): ActivationMetadata, _clean(), _json_values(), _markers(), Any, date, 활성 manifest에 들어가기 전에 문서 단위 불변조건을 모두 확인한다., 검색·임베딩 전에 원문 위치와 부모 관계를 결정적으로 검증한다. (+15 more)

### Community 47 - "Community 47"
Cohesion: 0.06
Nodes (32): Ownership Checks and RLS, Privacy-Safe Logs, DB TTL Capacity Lease, FinalAnswerCoordinator, Frozen CitationRegistry, Grounded Sentence Verifier, Pipeline Issue Ledger, Authoritative question_execution (+24 more)

### Community 48 - "Community 48"
Cohesion: 0.15
Nodes (30): _active_concepts(), _arguments(), _article_path(), _atomic_publish(), build_comparison(), _canonical_json_bytes(), _cli_path(), _concept_matches() (+22 more)

### Community 49 - "Community 49"
Cohesion: 0.14
Nodes (29): ApprovalReviewError, _arguments(), _canonical_sha256(), _cell(), load_question_bank(), main(), _mapping(), Namespace (+21 more)

### Community 50 - "Community 50"
Cohesion: 0.07
Nodes (31): As-of Date Clamping, Future-Date Boundary, Korea-Date Picker Limit, 0035 As-of Date Future Limit, Single-Connection Corpus Overview, Non-Model Endpoint One-Second SLA, One-Second Latency Test, 0038 Non-Model Endpoint Latency (+23 more)

### Community 51 - "Community 51"
Cohesion: 0.13
Nodes (12): MockIdentityRepository, MockSession, _one_year_after(), ConversationSummary, datetime, MockUser, QuestionResponse, UUID (+4 more)

### Community 52 - "Community 52"
Cohesion: 0.09
Nodes (25): load_provisions(), load_provisions_from_connection(), AsyncConnection, Current-parser corpus records used by Experiment D validation and retrieval., _arguments(), as_of_population_fingerprints(), AsOfPopulationFingerprint, _declared_as_of_populations() (+17 more)

### Community 53 - "Community 53"
Cohesion: 0.13
Nodes (28): parametrize, test_admin_rule_json_sections_get_stable_article_paths(), test_chapter_marker_does_not_replace_first_article(), test_exact_allowlist_title_is_enforced(), test_flat_json_subitems_are_restored_under_their_numbered_items(), test_flat_json_subitems_skip_deleted_numbered_item_when_counts_match(), test_flat_json_subitems_use_order_when_parent_text_has_no_each_subitem_phrase(), test_json_and_xml_normalize_to_equivalent_core_document() (+20 more)

### Community 54 - "Community 54"
Cohesion: 0.11
Nodes (24): emit_question_outcome(), emit_question_stage_timing(), emit_route_outcome(), fallback_reason_metrics_snapshot(), BaseModel, QuestionStageTimingOutcome, RouteDecision, question_metrics_snapshot() (+16 more)

### Community 55 - "Community 55"
Cohesion: 0.11
Nodes (24): AnnotationProposal, ArtifactBinding, CorpusBinding, D10GoldWorkflowContract, ProposedCase, ProposedFacet, ProposedPositiveJudgment, ProposedReferenceResponse (+16 more)

### Community 56 - "Community 56"
Cohesion: 0.12
Nodes (21): NvidiaNimQuestionRouter, Question router backed by one structured NVIDIA NIM request., Protocol, QuestionRouter, Single-stage question routing before evidence retrieval., route_question(), _build_router(), evaluate() (+13 more)

### Community 57 - "Community 57"
Cohesion: 0.11
Nodes (22): get_settings(), do_run_migrations(), run_async_migrations(), _arguments(), Namespace, 계정 질문 이력의 검색 단계별 진단을 읽기 전용 JSON으로 출력한다., _run(), _arguments() (+14 more)

### Community 58 - "Community 58"
Cohesion: 0.26
Nodes (27): _arguments(), _atomic_publish_directory(), build_draft(), _canonical_bytes(), D10GoldReviewError, export_corpus(), _iso(), _jsonl_bytes() (+19 more)

### Community 59 - "Community 59"
Cohesion: 0.16
Nodes (25): ExperimentD10QuestionInput, _file_sha256(), FrozenQuestionIdentity, load_manual_pilot_artifacts(), ManualPilotInputError, BaseModel, model_validator, Path (+17 more)

### Community 60 - "Community 60"
Cohesion: 0.08
Nodes (6): _DeletionEngine, _FakeEngine, _FakeResult, _RunLockConnection, _RunLockEngine, _TransactionContext

### Community 61 - "Community 61"
Cohesion: 0.15
Nodes (24): accessToken(), ApiError, askQuestion(), authHeaders(), deleteAccount(), deleteConversation(), deleteQuestionHistory(), downloadPdf() (+16 more)

### Community 62 - "Community 62"
Cohesion: 0.23
Nodes (18): CorpusSnapshot, _candidates(), _code_provenance(), FakeBackend, FakeEmbedder, FakeLockedReader, _provision(), _provisions() (+10 more)

### Community 63 - "Community 63"
Cohesion: 0.14
Nodes (24): CurrentEmbeddingSource, PreparedUpdateRepository, preview_has_corpus_changes(), preview_source_deletions(), Protocol, UUID, Read-only helpers used while preparing a maintenance corpus bundle., Read the full searchable passage and target-profile vector provenance. (+16 more)

### Community 64 - "Community 64"
Cohesion: 0.07
Nodes (26): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+18 more)

### Community 65 - "Community 65"
Cohesion: 0.15
Nodes (22): build_messages(), _contains_normative_assertion(), _evidence_for_citations(), 근거와 겹치는 용어 비율(>=50%)을 요구해 무근거 주장을 막는다. 2026-08-08: `unanswerable` action의…, 신뢰하지 않는 질문·원문을 system 지시와 분리한 모델 입력., _strip_epistemic_hedges(), _terms(), _text_matches_evidence() (+14 more)

### Community 66 - "Community 66"
Cohesion: 0.14
Nodes (12): MockUser, SupabaseIdentity, FakePostgresIdentity, FakeSupabaseAuth, _headers(), fixture, MockUser, UUID (+4 more)

### Community 67 - "Community 67"
Cohesion: 0.15
Nodes (14): _existing(), FakeConnection, FakeEngine, FakeResult, _identity(), asyncio, test_delete_history_locks_conversation_before_deleting_question(), test_existing_consented_profile_does_not_require_headers_again() (+6 more)

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (11): _Connection, _ConnectionContext, _document(), _Engine, asyncio, Path, _Repository, _Result (+3 more)

### Community 69 - "Community 69"
Cohesion: 0.19
Nodes (24): _arguments(), _atomic_create_json(), _canonical_json_bytes(), _cli_path(), CompletedJudgment, _final_judgment(), finalize_confirmed_review(), main() (+16 more)

### Community 70 - "Community 70"
Cohesion: 0.15
Nodes (20): canonical_pilot_worklist_payload_sha256(), ExperimentDPilotAnnotationWorklist, PilotQuestion, PilotQuestionApprovalBinding, PilotSelection, PilotSourceBankBinding, BaseModel, model_validator (+12 more)

### Community 71 - "Community 71"
Cohesion: 0.12
Nodes (14): AccountDialog(), AnswerView(), AuthDocument, AuthStatus, AuthView, IconName, MODEL_LABELS, ConsumedQuestionDraft (+6 more)

### Community 72 - "Community 72"
Cohesion: 0.12
Nodes (25): AbortController 요청 취소, conversation·turn 저장 계약, cursor 페이지네이션, 대화 상세 지연 로딩, 400 메시지 rollover, 실행 계획 0009: 연속 대화, 이력 페이지네이션, 인증 지연 개선, 400 메시지 경계 폐기, 입력 토큰 예산 24,576 (+17 more)

### Community 73 - "Community 73"
Cohesion: 0.08
Nodes (25): ACCOUNT_QUOTA_ENABLED, answer_generation stage, _answer_question, answer_validation stage, Authenticated and consented storage, Blocked-route generation, Citation source_kind, clarification_required action (+17 more)

### Community 74 - "Community 74"
Cohesion: 0.19
Nodes (14): _iso(), MockCorpusRepository, Any, date, Path, 첫 실행은 8일, 이후에는 마지막 성공일 하루 전부터 겹쳐 조회한다., Open API 레코드 삭제를 법적 폐지와 분리해 기록하고 체크포인트를 전진한다., Supabase 연결 전 사용하는 원자적 파일 기반 목업 저장소. (+6 more)

### Community 75 - "Community 75"
Cohesion: 0.09
Nodes (24): 생성 실패 시 검색 전용 폴백, Outbound 추론 작업 큐, Provider-neutral Answerer 포트, Qwen 장애 시 검색 전용 폴백, 구조화 출력·Grounding 검증, 대화 컨텍스트 중복 제거, 분산 취소 Tombstone 검증, 정확 조문 경로 매칭 (+16 more)

### Community 76 - "Community 76"
Cohesion: 0.13
Nodes (15): LlamaIndexLegalRepository, datetime, UUID, v2 LlamaIndex 검색과 v1 저장소 위임을 결합한다., Corpus 검색 상태 조회를 v1 저장소에 위임한다., 마지막 corpus 동기화 시각 조회를 v1 저장소에 위임한다., v2 검색기는 사용하고 나머지 저장소 계약은 v1에 위임한다., 문서 upsert를 v1 저장소에 위임한다. (+7 more)

### Community 77 - "Community 77"
Cohesion: 0.20
Nodes (16): AsyncClient, Exception, UUID, SupabaseAuth, SupabaseAuthError, SupabaseAuthUnavailableError, asyncio, parametrize (+8 more)

### Community 78 - "Community 78"
Cohesion: 0.19
Nodes (17): search_only_answer(), citation_quality(), enforce_quality(), main(), _answer_text(), _assert_terms(), _hits(), parametrize (+9 more)

### Community 79 - "Community 79"
Cohesion: 0.14
Nodes (20): _compact(), _document_title(), _korean_number(), _normalize_korean_provision_numbers(), _number_value(), parse_provision_reference(), parse_provision_references(), ProvisionQuery (+12 more)

### Community 80 - "Community 80"
Cohesion: 0.23
Nodes (21): _clean_text(), _raw_article_events(), parametrize, test_open_api_error_is_not_treated_as_empty_search(), ProvisionRecord, clean_text(), direct_text(), element_text() (+13 more)

### Community 81 - "Community 81"
Cohesion: 0.17
Nodes (18): _configure_ai(), _FailingRouter, _hit(), _payload_json(), _ProviderTimeoutRouter, asyncio, _SlowRouter, test_legal_search_runs_generation_and_validation_after_retrieval() (+10 more)

### Community 82 - "Community 82"
Cohesion: 0.12
Nodes (17): authEventAction(), clampAsOfDate(), Home(), handleDeleteAccount(), handleGoogleAuth(), handleLogout(), jumpToCitation(), loadOlderTurns() (+9 more)

### Community 83 - "Community 83"
Cohesion: 0.23
Nodes (18): _bundle(), test_title_change_requires_vectors_for_current_and_historical_versions(), PreparedDocumentRecord, PreparedRawRecord, Backward-compatible short alias for internal callers., LegalDocumentRecord, _document(), _publish_base_row() (+10 more)

### Community 84 - "Community 84"
Cohesion: 0.15
Nodes (7): PostgresIdentityRepository, AsyncEngine, ConversationSummary, date, datetime, QuestionResponse, UUID

### Community 85 - "Community 85"
Cohesion: 0.13
Nodes (20): is_allowed_source_url(), 브라우저에 노출 가능한 국가법령정보 원문 URL만 허용한다., _ai_available(), corpus_status(), _corpus_unready_http_error(), _current_korea_date(), _load_corpus_temporal_state(), provision() (+12 more)

### Community 86 - "Community 86"
Cohesion: 0.13
Nodes (8): DenseCandidate, LockedDenseReader, date, _candidate(), FakeLockedReader, date, Any, FakeBackend

### Community 87 - "Community 87"
Cohesion: 0.12
Nodes (8): _ConnectionContext, _LockConnection, _LockEngine, _ScalarResult, test_postgres_backend_busy_xact_lock_does_not_enter_reader(), test_postgres_backend_uses_one_transaction_and_shared_mutation_key_for_lock(), _TransactionContext, _TransactionContext

### Community 88 - "Community 88"
Cohesion: 0.18
Nodes (16): _blocked_node(), build_graph(), Any, _route_branch(), build_search_node(), search_node(), AgentState, append_turn() (+8 more)

### Community 89 - "Community 89"
Cohesion: 0.20
Nodes (15): date, v2 벡터 검색에서 기준일에 유효한 법령 조문만 반환한다., 질문 임베딩으로 검색하고 요청 기준일에 유효한 결과만 반환한다. 후보를 넉넉히 가져온 뒤 시행일 범위로 다시 걸러, 벡터 저장소의…, search(), _FakeEmbedder, _FakeVectorStore, _node(), asyncio (+7 more)

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (21): 결정론적 검증, 원문 추적성, corpus validator, 근거 우선 검색 품질 설계, GraphRAG 보류, insufficient_evidence 안전 게이트, 법률 계층 복원, parser v3 provision ID 게이트 (+13 more)

### Community 91 - "Community 91"
Cohesion: 0.10
Nodes (21): Clarification required cases, Corpus of 3,066 provisions, Repeatable read, read-only DB, Experiment D-10 Gold review draft, Zero embedding, search, and model calls, 30,660 relevance judgments, Partially answerable cases, Pending user review (+13 more)

### Community 92 - "Community 92"
Cohesion: 0.14
Nodes (21): Advisory lock coordination, As-of populations, Atomic evaluation result publication, Date-independent content snapshot identity, Corpus, query, qrels, and reference contract, D-10-R1 calibration reranking, D-10 unanswerable pilot, Evaluation and Experiment Reading (+13 more)

### Community 93 - "Community 93"
Cohesion: 0.20
Nodes (19): build_messages_v2(), 0043: 법률을 처음 접하는 사용자를 위한 문체 규칙을 추가한 v2 프롬프트. 인용·근거·action 안전 규칙은…, _hits(), v1 has "적용 여부를 추정하지 않는다" right after the summary/결론 guidance; v2 must carry the…, v1 ends its limitations guidance with "limitations에 새로운 법률 주장을 추가하지 않는다." v2…, _request(), test_v1_prompt_text_is_unchanged_by_v2_addition(), test_v2_system_prompt_caps_limitations_and_splits_confirmed_vs_unconfirmed() (+11 more)

### Community 94 - "Community 94"
Cohesion: 0.21
Nodes (19): article_key(), assemble_variant_a(), assemble_variant_b(), AssembledArticle, Candidate, CorpusRecord, evaluate_combo(), load_context_verdicts() (+11 more)

### Community 95 - "Community 95"
Cohesion: 0.21
Nodes (16): _BoundaryOnlyRepository, date, MonkeyPatch, parametrize, _ready_state(), test_content_snapshot_identity_rejects_invalid_population_contracts(), test_corpus_status_exposes_dynamic_supported_date_window(), test_corpus_status_exposes_null_identity_when_current_population_is_unready() (+8 more)

### Community 96 - "Community 96"
Cohesion: 0.15
Nodes (20): 한국어 자연어 검색, NFTC 기술기준 청킹, PGroonga 단계형 완화 검색, 실행 계획 0007: Production 자연어 검색과 단계별 관측, 질문 진단 JSONB, 검색 전용 독립 동작, 공유 질의 정규화, 단계별 구조화 관측 (+12 more)

### Community 97 - "Community 97"
Cohesion: 0.15
Nodes (6): v1 위임 저장소와 v2 검색 의존성을 연결한다., LegalRepository, date, datetime, Protocol, UUID

### Community 98 - "Community 98"
Cohesion: 0.15
Nodes (9): _Connection, _Context, _Engine, _publish_row(), parametrize, _query_results(), test_preflight_fails_closed_on_invalid_state(), test_preflight_uses_one_read_only_transaction_and_selects_only() (+1 more)

### Community 99 - "Community 99"
Cohesion: 0.18
Nodes (11): CitationCard(), citation, SafeText(), Citation, ConversationPage, ConversationSummary, ConversationTurnPage, citationDocumentKind() (+3 more)

### Community 100 - "Community 100"
Cohesion: 0.16
Nodes (19): Embedding profile lineage, Candidate grouping and five-context budget, Citation IDs and structured output, Cosine similarity, Deterministic citation gate, Direct statutory path query, Evidence-First Retrieval and Answers, Evidence-first RAG boundary (+11 more)

### Community 101 - "Community 101"
Cohesion: 0.14
Nodes (19): 전기사업법 제10조 양수·분할·합병 인가, 전기사업법 제11조 사업 승계, 전기사업법 제12조 허가 취소 등, 전기사업법 제34조 차액계약, 전기사업법 제53조 전기위원회, 전기사업법 제61조 공사계획 인가, 전기사업법 제7조 사업의 허가, 전기사업법 제8조 결격사유 (+11 more)

### Community 102 - "Community 102"
Cohesion: 0.25
Nodes (17): cancel_question(), lifespan(), question(), 애플리케이션 종료 시 선택적 외부 인증 리소스를 정리한다., v1 검색 저장소로 법령 질문에 응답한다., 같은 요청 소유자가 실행 중인 질문을 취소한다., _allow_quota(), _LegalRouter (+9 more)

### Community 103 - "Community 103"
Cohesion: 0.19
Nodes (14): BillingFailure, FailingAnswerer, Exception, parametrize, QuotaFailure, test_all_generation_failures_fall_back_without_another_model(), test_billing_or_quota_failure_disables_terra_for_later_requests(), test_disabled_ai_reports_safe_reason_without_calling_openai() (+6 more)

### Community 104 - "Community 104"
Cohesion: 0.19
Nodes (12): build_route_node(), route_node(), BaseModel, RouteDecision, FakeStructuredLLM, asyncio, RouteDecision, test_route_node_passes_question_text_to_llm() (+4 more)

### Community 105 - "Community 105"
Cohesion: 0.18
Nodes (15): QuestionInput, askQuestionWithRetry(), AskQuestionWithRetryDeps, cancelWithBound(), GENERATION_ATTEMPT_TIMEOUT_MS, GENERATION_CANCEL_TIMEOUT_MS, GENERATION_MAX_ATTEMPTS, GENERATION_OVERALL_TIMEOUT_MS (+7 more)

### Community 106 - "Community 106"
Cohesion: 0.12
Nodes (18): Citation Law-Type Code, Law API Type Fields, Law-Type Pass-Through Columns, 0041 Law Type Classification Parsing, Source-Kind Identity Column, Hash-Skipping Ingestion, LlamaIndex Legal Repository Adapter, LlamaIndex v2 Retrieval Pipeline (+10 more)

### Community 107 - "Community 107"
Cohesion: 0.18
Nodes (18): Answered Field Deduplication, Clarification Loop Handling Plan, Clarification Regression Tests, Clarification Required Action, Clarification Round Limit, Conversation Context, LangGraph State Graph, Unanswered Field Finalization (+10 more)

### Community 108 - "Community 108"
Cohesion: 0.18
Nodes (18): Abolished versus source-deleted state, Lineage catalog with HNSW exclusion, Content fingerprint and snapshot ID, Law Corpus Lifecycle, Effective-date half-open interval, As-of eligible provision population, JSON-first XML schema fallback, LegalDocumentRecord (+10 more)

### Community 109 - "Community 109"
Cohesion: 0.16
Nodes (18): AbortController versus distributed cancellation, AI failure search-only fallback, Separate generation and embedding provider ports, Anonymous question non-persistence, Authentication epoch and late-response discard, Checklist export and accessible citation controls, Cursor-paginated conversation history, User, Privacy, and Failure Safety (+10 more)

### Community 110 - "Community 110"
Cohesion: 0.11
Nodes (18): AGENTS 작업 지도·계약, 아키텍처 경계와 의존성 방향, 문서 자동화·구조 테스트 부채, Harness Engineering 적용 메모, 점진적으로 읽는 분류 문서, 품질·보안·신뢰성 독립 문서, Prepared Transaction Gate 반영, 코퍼스 운영·롤백 런북 (+10 more)

### Community 111 - "Community 111"
Cohesion: 0.25
Nodes (15): alias, _markdown_item(), _minimal_unicode_pdf(), ChecklistItem, 외부 PDF 엔진 없이 만드는 표지·브랜딩 없는 단순 텍스트 출력본., render_csv(), render_markdown(), render_pdf() (+7 more)

### Community 112 - "Community 112"
Cohesion: 0.22
Nodes (13): build_checkpointer_context(), _psycopg_database_url(), Settings, get_settings(), BaseSettings, Settings, test_build_checkpointer_context_normalizes_url_and_returns_context_manager(), test_build_checkpointer_context_requires_database_url() (+5 more)

### Community 113 - "Community 113"
Cohesion: 0.12
Nodes (17): Embedding anomaly detection, Embedding classification, Embedding clustering, Embedding input and output ownership, dimensions parameter, Embeddings API, Embedding pricing by input tokens, Embedding vector (+9 more)

### Community 114 - "Community 114"
Cohesion: 0.12
Nodes (17): 일반 사용자형 에너지 질문 의도 설계, 에너지바우처 FAQ, 2026년 공용 완속충전시설 설치 안내서, 무공해차 통합누리집, 한전 분산형 전원 계통연계 절차, 한전 전기사용 신청·계약 안내, 한전 전력서비스 헌장, 한국전기안전공사 사용전검사 안내 (+9 more)

### Community 115 - "Community 115"
Cohesion: 0.13
Nodes (17): NIM Embedding API 계약, Hosted Free Endpoint Trial 경계, L2 재정규화, 임베딩 모델·차원·버전 분리, 34개 언어 다국어 임베딩, Native 2048차원 출력, Nemotron 3 Embed 1B, 첫 512차원 Prefix Slice (+9 more)

### Community 116 - "Community 116"
Cohesion: 0.19
Nodes (16): check_d010_active_experiment_contract(), check_d010_current_contract_docs(), check_d010_routing_contract(), check_d010_superseded_designs(), check_freshness(), check_links(), main(), markdown_files() (+8 more)

### Community 117 - "Community 117"
Cohesion: 0.29
Nodes (9): T, RequestBudget, StageTimeoutError, asyncio, test_run_converts_asyncio_timeout_to_stage_timeout(), test_run_preserves_provider_timeout_error(), test_stage_timeout_rejects_work_when_only_response_reserve_remains(), test_stage_timeout_uses_smaller_of_cap_and_remaining_work_budget() (+1 more)

### Community 118 - "Community 118"
Cohesion: 0.33
Nodes (8): 국가법령정보 Open API 전용 독립 수집기., T, resolve(), CollectorService, Exception, _safe_detail(), IngestionResult, CatalogEntry

### Community 119 - "Community 119"
Cohesion: 0.16
Nodes (16): active_retrieval_release pointer, corpus_snapshots table, Database schema, document_versions table, embedding_profiles table, history_retention_runs table, LlamaIndex ingestion runs table, Document lifecycle state (+8 more)

### Community 120 - "Community 120"
Cohesion: 0.12
Nodes (16): Alembic autogenerate, alembic check, Candidate migration, Type and server-default comparison, Database schema comparison, env.py, EnvironmentContext.configure, include_name filter hook (+8 more)

### Community 121 - "Community 121"
Cohesion: 0.17
Nodes (16): corpus_unready, Anonymous history policy, Checklist Markdown CSV PDF export, Product corpus_unready state, Grounded legal QA decision records, Product deterministic citation gate, Energy Business Legal Chat, Dynamic corpus date support (+8 more)

### Community 122 - "Community 122"
Cohesion: 0.12
Nodes (16): 프로젝트 1000문항·200 Scenario Family 설계, 30660개 사용자 검토 Judgment, Annotation·Adjudication 계약, 현재 3066개 Provision 코퍼스, D-10 Gold 사용자 검토 Workflow, D-full 1000문항 설계, Pending User Review 상태, 직접 답변 가능성 판정 라벨 (+8 more)

### Community 123 - "Community 123"
Cohesion: 0.25
Nodes (10): NvidiaNimEmbedder, NVIDIA hosted NIM embedding adapter with the existing batch contract., _embedder(), asyncio, parametrize, test_embedder_empty_batch_does_not_call_provider(), test_embedder_preserves_indexes_slices_and_l2_normalizes(), test_embedder_rejects_invalid_provider_vectors() (+2 more)

### Community 124 - "Community 124"
Cohesion: 0.23
Nodes (13): client(), asyncio, fixture, LogCaptureFixture, MonkeyPatch, parametrize, TestClient, test_v2_readiness_closes_when_marker_connection_or_migration_is_unavailable() (+5 more)

### Community 125 - "Community 125"
Cohesion: 0.30
Nodes (13): _date(), effective_periods(), EffectiveVersion, HistoryVersion, parse_history_json(), parse_history_xml(), Any, 시행일 오름차순으로 ``[시행일, 다음 시행일)`` 효력 기간을 계산한다. (+5 more)

### Community 126 - "Community 126"
Cohesion: 0.14
Nodes (15): NVIDIA 오류 시 원문 검색 유지, clarification_required 응답, terra 모드 always-generate 역사 설계, 빈 근거 validate_draft 계약, search_only 폴백, terra AI 요청 always-generate, unanswerable 응답, DraftAnswer action (+7 more)

### Community 127 - "Community 127"
Cohesion: 0.13
Nodes (15): 결정적 답변 계약 시드, 평가 전략, 평가 지표, 평가셋, Production 검색 디버깅 시드, 릴리스 게이트, Evidence Recall, RRF 보류 (+7 more)

### Community 128 - "Community 128"
Cohesion: 0.14
Nodes (15): dense-only 검색, dense-only 기준선, D-full exhaustive exact cosine, bulk negative 검토, 실험 D-10 전수 qrel과 사용자 adjudication, 필수 facet과 기준 응답, relevance 0·1·2 판정, 사용자 adjudication (+7 more)

### Community 129 - "Community 129"
Cohesion: 0.18
Nodes (15): GitHub Issue and PR Workflow, No Sensitive Data in Issues or PRs, PR Quality Contract, One Verifiable Outcome per Issue, Safe Use without Sensitive Case Data, Reliability and Operations: C, Request and Trace Observability, AI and Search-Only Rate Limits (+7 more)

### Community 130 - "Community 130"
Cohesion: 0.18
Nodes (15): Evidence citation UI, Legal-advice disclaimer, Anonymous question no-history policy, Assumption-based onboarding draft, Avoid case-identifying information, Beta AI and search quotas, First-answer citation verification, New User Onboarding (+7 more)

### Community 131 - "Community 131"
Cohesion: 0.23
Nodes (10): CorpusSearchUnavailableError, RuntimeError, Raised when the current corpus generation is not safe to search., MonkeyPatch, test_anonymous_question_search_failure_returns_safe_temporary_error(), test_closed_corpus_is_not_reported_as_no_matching_evidence(), test_direct_search_failure_returns_the_same_safe_temporary_error(), test_provision_returns_corpus_unready_instead_of_not_found() (+2 more)

### Community 132 - "Community 132"
Cohesion: 0.21
Nodes (8): _configure_search_path(), PostgresExperimentDBackend, _PostgresLockedDenseReader, AsyncConnection, Backend holding one transaction-scoped shared lock for the evaluation., _set_read_committed_read_only(), _set_repeatable_read_only(), _snapshot_on_connection()

### Community 133 - "Community 133"
Cohesion: 0.26
Nodes (11): _assert_writer_locks_released(), _async_url(), _complete(), _isolated_repository(), _no_sleep(), asyncio, parametrize, Opt-in transaction test for a dedicated empty PostgreSQL database. (+3 more)

### Community 134 - "Community 134"
Cohesion: 0.33
Nodes (10): build_generate_node(), _format_evidence(), generate_node(), GenerationResult, FakeStructuredLLM, asyncio, test_generate_node_ignores_citation_ids_outside_search_hits_range(), test_generate_node_maps_citation_ids_to_search_hits() (+2 more)

### Community 135 - "Community 135"
Cohesion: 0.18
Nodes (14): 인용 게이트, 차단 라우트 답변 생성, validate_draft, 프롬프트 v2, corpus.search_ready 게이트, blocked_response_validation, 질문 사전 라우팅 역사 설계, grounded sequence (+6 more)

### Community 136 - "Community 136"
Cohesion: 0.19
Nodes (14): 취소 endpoint 상태 계약, 취소 신호 watcher, 분산 질문 취소 설계, 질문 실행 영속 상태, owner HMAC, pending_registration tombstone, question_executions 테이블, Google OAuth·Supabase Auth 연결 (+6 more)

### Community 137 - "Community 137"
Cohesion: 0.23
Nodes (14): Collector execution boundary, Domain-to-adapter dependency direction, System Map and Execution Boundaries, FastAPI API, Fixed-IP Windows collector, law-rag core domain, National Law Information Open API, Next.js Web (+6 more)

### Community 138 - "Community 138"
Cohesion: 0.20
Nodes (14): Active plan index mismatch incident, Python CI import-path incident, Conversation-first lock order, History deletion deadlock incident, Discord incident ledger scope, Discord Error Ledger, Duplicate clone incident, External reviewer access incident (+6 more)

### Community 139 - "Community 139"
Cohesion: 0.17
Nodes (13): Pull request template, Pull request security checklist, Pull request verification checklist, Repository Rules (AGENTS.md), Domain and data invariants, Evidence, citations, and source-version traceability, JSON-first XML-fallback ingestion, Privacy-safe logging and secret handling (+5 more)

### Community 140 - "Community 140"
Cohesion: 0.37
Nodes (11): create_review_template(), _canonical_sha256(), _judgment(), MonkeyPatch, Path, _result(), test_cli_resolves_relative_artifact_paths_from_repository_root(), test_confirmed_review_computes_only_manual_diagnostics() (+3 more)

### Community 141 - "Community 141"
Cohesion: 0.32
Nodes (9): _ask(), _login(), test_anonymous_question_is_not_saved_but_authenticated_question_is(), test_conversation_is_owner_scoped_and_delete_cascades_legacy_history(), test_conversation_summary_and_turn_cursors_do_not_duplicate_items(), test_history_is_private_and_owner_can_delete_it(), test_invalid_or_wrong_cursor_kind_is_rejected(), test_logout_invalidates_session_and_account_delete_cascades() (+1 more)

### Community 142 - "Community 142"
Cohesion: 0.31
Nodes (12): client(), fixture, LogCaptureFixture, MonkeyPatch, TestClient, test_v2_questions_returns_503_when_index_is_not_ready(), test_v2_questions_returns_503_when_not_configured(), test_v2_questions_returns_503_when_resource_factory_fails() (+4 more)

### Community 143 - "Community 143"
Cohesion: 0.26
Nodes (12): _all(), CorpusPreflightError, _json_value(), _mapping(), _one(), Any, AsyncConnection, RuntimeError (+4 more)

### Community 144 - "Community 144"
Cohesion: 0.36
Nodes (11): fake_generate(), fake_route_legal_search(), fake_search(), fake_validate(), _initial_state(), asyncio, _recording_node(), test_graph_restores_state_from_memory_checkpointer_for_same_thread() (+3 more)

### Community 145 - "Community 145"
Cohesion: 0.26
Nodes (10): openHistory(), AI_UNAVAILABLE_NOTICE, AnswerModeResolution, AnswerPreference, isTerraAvailabilityFailure(), isTerraUnavailable(), resolveCorpusAnswerMode(), resolveResponseAnswerMode() (+2 more)

### Community 146 - "Community 146"
Cohesion: 0.18
Nodes (13): gold adjudication manifest, approved_gold 평가셋, 실험 D-full 1,000문항 평가, held-out test split, 기준일별 content snapshot identity, D-10 qrels, 승인된 질문 집합, 실험 D 일반 사용자 질문은행 (+5 more)

### Community 147 - "Community 147"
Cohesion: 0.26
Nodes (13): 조·항·호·목 계층 복원, Article Recall, 실험 D 검색 문맥 구성, corpus 정확성 우선, corpus validator, dense-only 최종 기준선, 직접 근거 1~5개, evidence closure (+5 more)

### Community 148 - "Community 148"
Cohesion: 0.17
Nodes (13): 독립 검토 Gold와 Qrels, 미주석 질문 초안, 답변 Faithfulness·Groundedness 지표, BEIR Annotation Hole·Pooling Bias, ID·Path·SHA 결정적 검색 지표, Ground Truth 기반 정확도 벤치마크, 독립 Graded Qrels·Adjudication, Labelled RAG Dataset (+5 more)

### Community 149 - "Community 149"
Cohesion: 0.15
Nodes (12): name, packageManager, private, scripts, build, build:web, dev:web, lint:web (+4 more)

### Community 150 - "Community 150"
Cohesion: 0.29
Nodes (10): AnswerAction, derive_answer_action(), derive_fallback_action(), ChecklistItem, _item(), ChecklistItem, test_all_required_or_not_applicable_is_fully_answerable(), test_any_check_status_is_clarification_required() (+2 more)

### Community 151 - "Community 151"
Cohesion: 0.27
Nodes (10): anonymous_rate_limit_subject(), _canonical_ip(), daily_subject_hash(), date, Return a canonical, non-persisted subject for anonymous quota hashing. Vercel…, test_daily_subject_hash_hides_and_rotates_ip(), test_forwarded_chain_and_invalid_ip_fail_closed_to_one_subject(), test_ipv4_mapped_ipv6_cannot_create_a_second_subject() (+2 more)

### Community 152 - "Community 152"
Cohesion: 0.24
Nodes (10): main(), _parser(), ArgumentParser, Path, _run(), CorpusPreflightSettings, BaseSettings, The preflight intentionally needs only a direct PostgreSQL session URL. (+2 more)

### Community 153 - "Community 153"
Cohesion: 0.24
Nodes (5): CollectorRepository, Any, date, Protocol, date

### Community 154 - "Community 154"
Cohesion: 0.24
Nodes (8): CollectorSettings, BaseSettings, model_validator, test_complete_supabase_configuration_enables_repository(), test_env_local_is_loaded_and_overrides_env(), test_partial_supabase_configuration_is_rejected(), test_process_environment_overrides_env_local(), test_transaction_pooler_url_cannot_replace_collector_direct_url()

### Community 155 - "Community 155"
Cohesion: 0.26
Nodes (10): exportChecklist(), ChecklistExportInput, csvCell(), downloadBlob(), downloadText(), ExportFormat, renderCsv(), renderMarkdown() (+2 more)

### Community 156 - "Community 156"
Cohesion: 0.20
Nodes (12): Citation Context Preservation, Product Design Principles, Evidence Path First, Source, Date, Jurisdiction, and Document-Type Hierarchy, Citation-to-Source Follow-Up, Product Sense, Relevant Evidence, Explicit Uncertainty Disclosure (+4 more)

### Community 157 - "Community 157"
Cohesion: 0.23
Nodes (12): 봉인된 calibration artifact, R1 calibration 진단, 실험 D-10-R1 로컬 재정렬, 로컬 재정렬 profile v1, 부모 표제·직접성 규칙, raw top 10 후보 집합, M3 baseline 순위, diagnostic-only calibration (+4 more)

### Community 158 - "Community 158"
Cohesion: 0.17
Nodes (12): All-keywords path, Direct article path, Nine documents, Eight retrieval contracts passed, Zero embeddings, Zero evaluation runs, Keyword-only search, Not a recall baseline (+4 more)

### Community 159 - "Community 159"
Cohesion: 0.17
Nodes (12): Corpus as-of range 2026-06-03 to 2026-08-03, Zero missing or stale vectors, Current runtime ignores retrieval catalog, Exhaustive exact cosine, Hybrid and RRF DB functions absent, Historical HNSW index, Operational vector index build report, Embedding profile active true (+4 more)

### Community 160 - "Community 160"
Cohesion: 0.18
Nodes (12): 후보에서 직접 근거로 가는 문맥 파이프라인, 실험 D 검색 문맥 구성, Corpus SHA·검색 실행 스냅샷, 실험 D 실제 결과, Article Candidates, 후보는 최종 근거가 아님, 역사적 205청크 코퍼스, 실험 C Dense 검색 후보 관찰 (+4 more)

### Community 161 - "Community 161"
Cohesion: 0.27
Nodes (9): korea_today(), date, ValueError, Dynamic temporal contract for the currently searchable legal corpus. The…, Return the product's legal-current date, independent of server timezone., Raised when a request falls outside the current dynamic corpus bounds., Return a supported date or fail before quota and provider work begins., require_supported_corpus_date() (+1 more)

### Community 162 - "Community 162"
Cohesion: 0.18
Nodes (11): _build_llamaindex_resources(), _llamaindex_resources(), v2 검색에 필요한 리소스를 모두 구성하거나 미구성 상태를 반환한다. 데이터베이스 URL 또는 NVIDIA 키가 없으면 외부 초기화를 시도하지…, 테스트 주입 리소스를 보존하며 v2 리소스를 반환한다. 구성 또는 초기화에 실패하면 호출자가 준비되지 않은 v2 상태로 처리하도록…, 가장 최근 v2 색인 작업의 완료 상태를 fail-closed 방식으로 확인한다., 준비 표지 접근 실패 시 fail-closed로 v2 준비 상태를 확인한다., 준비된 v2 인덱스에서 허용된 법령 검색 결과만 반환한다. 리소스 또는 색인 준비 상태를 확인할 수 없으면 검색 결과 대신 503을 반환한다., search_v2() (+3 more)

### Community 163 - "Community 163"
Cohesion: 0.33
Nodes (9): assert_under_one_second(), _headers(), _login(), MonkeyPatch, Response, TestClient, _seed_question(), test_every_non_model_endpoint_responds_within_one_second() (+1 more)

### Community 164 - "Community 164"
Cohesion: 0.20
Nodes (11): AI 차별화와 안전 설계, 사업 단계 법률 체크리스트, 기준일·버전 근거, 경계 검증, 인용은 제품 계약, 핵심 신념, 교체 가능한 모델 어댑터, 검색 실패를 생성으로 감추지 않음 (+3 more)

### Community 165 - "Community 165"
Cohesion: 0.22
Nodes (11): WCAG 2.2 AA, Frontend Architecture, Question, Answer, Citation, and Source Flow, Question State Machine, Response Mode Synchronization, Safe Source Rendering, Search-Only Feature Disabled by Default, Reliability (+3 more)

### Community 166 - "Community 166"
Cohesion: 0.18
Nodes (11): Exhaustive exact cosine search, Legacy HNSW index excluded, Independent keyword fallback, Article MRR equals 1.0, Article Recall at 3, 5, and 10 equals 1.0, Candidate k equals 10, Dense article-level search baseline, Evidence Recall at 3, 5, and 10 equals 1.0 (+3 more)

### Community 167 - "Community 167"
Cohesion: 0.18
Nodes (11): Electricity Business Act Article 7, electricity-business-license-out-of-scope case, Electricity Business Act Article 7 absent, Experiment D search context safety gate, Five in-scope runs ready, Governing provision outside corpus, One out-of-scope run insufficient evidence, In-scope success 5 of 5 (+3 more)

### Community 168 - "Community 168"
Cohesion: 0.20
Nodes (11): Assembly A: one best leaf per article, Assembly B: parent and sibling expansion, Zero budget-exceeded cases, Calibration-only result, 60,000 character budget, Direct evidence hit, Experiment D-10 M4 context assembly summary, Maximum five provisions (+3 more)

### Community 169 - "Community 169"
Cohesion: 0.18
Nodes (11): Coarse-to-fine representation, FIPS 180-4 Secure Hash Standard, Flexible representation, Hash computation, Message integrity, Matryoshka Representation Learning, Message digest, MRL, FIPS 180-4, and RRF excerpts (+3 more)

### Community 170 - "Community 170"
Cohesion: 0.27
Nodes (4): PreparedProvisionRecord, model_validator, ProvisionRecord, Self

### Community 171 - "Community 171"
Cohesion: 0.29
Nodes (4): Task, UUID, QuestionTaskRegistry, Process-local active question tasks, scoped by a non-secret owner key.

### Community 172 - "Community 172"
Cohesion: 0.44
Nodes (9): _candidate(), _canonical_sha256(), _case(), Path, test_rerank_does_not_overwrite_existing_output(), test_rerank_moves_target_evidence_to_top3_and_reduces_known_noise(), test_rerank_rejects_unconfirmed_review_without_output(), test_rerank_uses_case_text_without_relevance_labels() (+1 more)

### Community 173 - "Community 173"
Cohesion: 0.33
Nodes (10): Authenticated Diagnostics History, D-010 Router Calibration, Fail-Closed Routing Observability, Fallback Reason Metrics Snapshot, Historical Tier Dictionary, Route Metrics Snapshot, Route and Reason-Code Policy, Single Question Router (+2 more)

### Community 174 - "Community 174"
Cohesion: 0.36
Nodes (10): Chunker-Only Experimental Variable, V2 Chunking Ablation Plan, Current Provision TextNode Baseline, D-10 Sealed Calibration Gold, Fixed V2 Retrieval Pipeline, Isolated Experiment Vector Tables, LlamaIndex Subchunk Candidate, Provision Traceability (+2 more)

### Community 175 - "Community 175"
Cohesion: 0.38
Nodes (10): API and Web Date Contract, Clock Injection Boundary Tests, F-005 Temporal Adapter Boundary, Future-Date 422 Guard, Supported As-Of Start, Supported As-Of Through, Temporal Effective Interval, Asia Seoul Today Provider (+2 more)

### Community 176 - "Community 176"
Cohesion: 0.22
Nodes (10): Cosine similarity, Normalized embedding vector, Output 512 dimensions, Cosine similarity, Normalized OpenAI vectors, Embedding dimension reduction, Up to fourteen-times retrieval speed-up, 2,956 checkpoint vectors reused (+2 more)

### Community 177 - "Community 177"
Cohesion: 0.24
Nodes (10): Execution Plan Operations, Execution Plan Lifecycle, Todo, Picked Up, Blocked, and Done Statuses, Task Management Metadata Contract, 52/55/60-Second Question Timeout Budget, DOC-001 Task Metadata and Thin Roadmap, Project Roadmap, F-002 Distributed Question Cancellation (+2 more)

### Community 178 - "Community 178"
Cohesion: 0.20
Nodes (10): GTX 1650·Windows 10 로컬 프로필, Nemotron 3 Nano 4B, NIM on WSL2 지원 하드웨어 경계, Qwen3:4b·Ollama 로컬 후보, Qwen 입력 예산 24576 토큰, Ollama OpenAI 호환 경로, 생성 출력 예약 4096 토큰, Qwen3-4B Native Context 32768 (+2 more)

### Community 179 - "Community 179"
Cohesion: 0.25
Nodes (5): date, Corpus 기준일 범위 상태 조회를 v1 저장소에 위임한다., v2 검색 결과만 반환하고 검색 추적 정보는 숨긴다., v2 dense 검색 결과와 관측용 검색 추적 정보를 반환한다. 호출자가 제공한 v1 임베딩 인자는 사용하지 않는다. v2 검색기가 자체…, 사용량 한도 소비를 v1 저장소에 위임한다.

### Community 180 - "Community 180"
Cohesion: 0.50
Nodes (8): Keep at most one ranked leaf per article within the provider input budget., select_generation_hits(), _hit(), test_budget_keeps_one_oversized_top_provision(), test_budget_keeps_whole_ranked_provisions(), test_flat_body_paths_are_not_collapsed_into_one_article(), test_generation_context_is_limited_to_five_articles(), test_generation_context_keeps_only_highest_ranked_leaf_per_article()

### Community 181 - "Community 181"
Cohesion: 0.33
Nodes (8): legal_search_router(), fixture, MonkeyPatch, Let non-temporal API tests exercise their own downstream concern., Exercise legacy search-only contracts only when the feature is explicitly…, Keep normal AI-flow tests on the post-routing legal-search path., ready_corpus_temporal_state(), search_only_enabled()

### Community 184 - "Community 184"
Cohesion: 0.39
Nodes (7): _citation_matches_hit(), _citations_from_search_hits(), validate_node(), test_validate_node_blocks_citation_that_does_not_match_retrieved_evidence(), test_validate_node_blocks_uncited_claims(), test_validate_node_passes_through_answer_with_citations(), test_validate_node_suppresses_unanswerable_arbitrary_legal_claim()

### Community 185 - "Community 185"
Cohesion: 0.25
Nodes (9): apply-prepared Atomic Publish, Corpus Search-Ready Gate, Dynamic Corpus Snapshot Identity, Corpus Support Range, corpus_unready HTTP 503, Dynamic Runtime Snapshot, Lifecycle and Source States, Searchable Version (+1 more)

### Community 186 - "Community 186"
Cohesion: 0.22
Nodes (9): BM25 Retriever, Experiment D Exhaustive Exact Cosine, Exhaustive Exact Dense Search, HNSW Permanent Exclusion, PGroonga Keyword Fallback, LangGraph v3, LlamaIndex v2, pgvector and PGroonga (+1 more)

### Community 187 - "Community 187"
Cohesion: 0.25
Nodes (9): Agent State, Node-Level SSE Stream, Postgres LangGraph Checkpointer, v3 Thread Run API, F-001 v3 Foundation Plan, law-rag-agent Workspace, Postgres Checkpointer Task, StateGraph Implementation Tasks (+1 more)

### Community 188 - "Community 188"
Cohesion: 0.31
Nodes (9): 인용 검증 게이트, 답변 품질 평가, 생성 초안 인용 grounding gate, 기대 근거 계약, 근거 없음 차단, 실행 계획 0006: 예시 질문 기반 답변 품질 평가, Recall@10, 대표 에너지 법령 질문 (+1 more)

### Community 189 - "Community 189"
Cohesion: 0.39
Nodes (9): advisory transaction lock, checklist_exports FK cascade, 대화 재집계와 빈 대화 삭제, expires_at cutoff, 질문 이력 1년 보존, history_retention_runs 감사, pg_cron scheduler 등록 보류, 질문 이력 보존 정리 작업 실행 계획 (+1 more)

### Community 190 - "Community 190"
Cohesion: 0.39
Nodes (9): collector 활성화 validator, 조 단위 후보 중복 제거, dense-only 프로덕션 검색, 생성 문맥 최대 5개 조문, 독립 keyword fallback, RRF·BM25·reranker 미도입, 실행 계획 0021: 프로덕션을 근거 우선 실험 설계와 정렬, 프로덕션 인용 게이트 (+1 more)

### Community 191 - "Community 191"
Cohesion: 0.25
Nodes (9): Auth Event Action, Auth Rehydration Control, Browser Network Verification, 0034 Web Auth Rehydration Throttle, No Refocus Rehydration, 0040 Production Auth Rehydration Verification, Production Auth Deployment Check, Session-State Guard (+1 more)

### Community 192 - "Community 192"
Cohesion: 0.36
Nodes (9): Cancel API Status Contract, Distributed Question Cancellation Plan, Memory Coordinator Adapter, NVIDIA Hosted NIM Cancel Capability, Cancellation Owner Isolation, Persistent Cancellation Coordinator, Cancellation Polling Watcher, Production Migration Approval Gate (+1 more)

### Community 193 - "Community 193"
Cohesion: 0.33
Nodes (9): Approved Question Bank, D-10 Calibration Gold, D-Full Gold On Demand Plan, D-Full Gold Scope, Generalization and Release Gate, Gold Preflight, QREL and Reference Artifacts, Todo Execution Plans Index (+1 more)

### Community 194 - "Community 194"
Cohesion: 0.36
Nodes (9): Agent Context Diet, Evaluation Conflict Detector, Rubric Counterexample Fixtures, Decision Record Normalization, Evaluation Harness Consolidation Plan, Evaluation State YAML, Exact Token Calculation, Machine-Readable Relevance Rubric (+1 more)

### Community 195 - "Community 195"
Cohesion: 0.36
Nodes (9): D-10 Rerank Evaluation, Evidence Quality Gate Boundary, Generation Hit Selection, Heading and Directness Score, Live Search Reranking Plan, Live Search With Trace, Offline Rerank Case, Source Kind Signal (+1 more)

### Community 196 - "Community 196"
Cohesion: 0.39
Nodes (9): Allowed Model Profiles, Compatibility Migration Telemetry, Provider Model Failure Contract, Provider Model Registry, Provider-Neutral Answer Intent, Provider-Neutral Answer Model Selection Plan, Provider-Neutral Public Request Schema, Search-Only Fallback (+1 more)

### Community 197 - "Community 197"
Cohesion: 0.22
Nodes (9): Experiment D-10-R1 local rerank results, Held-out validation required, R1 hit at 10 equals 7 of 10, R1 hit at 3 equals 7 of 10, R1 hit at 5 equals 7 of 10, Manual direct evidence, Parent-heading directness v1 scoring profile, R1 local rerank (+1 more)

### Community 198 - "Community 198"
Cohesion: 0.22
Nodes (9): Codex-user agreement 10 of 10, Experiment D-10 manual diagnostic, Manual hit at 10 equals 7 of 10, Manual hit at 1 equals 6 of 10, Manual hit at 3 equals 6 of 10, Manual hit at 5 equals 6 of 10, Three cases without direct evidence, Top-five irrelevant candidates 28 (+1 more)

### Community 199 - "Community 199"
Cohesion: 0.22
Nodes (9): 검색 후보와 직접 근거 분리, 입력 문서 품질 경계, Hybrid·Reranker·Graph 평가 채택 게이트, Local·Global GraphRAG 검색, Reciprocal Rank Fusion, RAG 검색·근거 선택 패턴, 인용 가능한 Context Package, 직접 근거 선택 (+1 more)

### Community 200 - "Community 200"
Cohesion: 0.22
Nodes (9): PGroonga 전문 검색, PostgreSQL EXPLAIN 측정, Prepared Statement Cache 0, 원격 DB 왕복 예산, 검색 지연·후보 관측 메트릭, 검색 성능·관측 공식 자료, 4단계 순차 검색 완화, Supavisor Transaction Mode (+1 more)

### Community 201 - "Community 201"
Cohesion: 0.25
Nodes (7): excludeFiles, maxDuration, functions, app/main.py, regions, $schema, icn1

### Community 202 - "Community 202"
Cohesion: 0.32
Nodes (8): _async_url(), preflight_current_corpus(), AsyncEngine, date, Path, Inspect production corpus state without locks, writes, or external APIs., _validated_report(), test_preflight_requires_direct_url()

### Community 203 - "Community 203"
Cohesion: 0.25
Nodes (8): Embedding Profile, Legal Provision Passage Contract, Retrieval Lineage Catalog 0011, HnswIndexManager CLI, Native-Dimension NIM Embedding, v2 Passage Template, Provisions Input Projection, v2 PGVector Physical Table

### Community 204 - "Community 204"
Cohesion: 0.36
Nodes (8): Google OAuth, 독립 collector, JSON 우선·XML 폴백, 법률 RAG MVP, 문서 우선 모듈형 모놀리스, 국가법령정보 공동활용 Open API, 실행 계획 0001: MVP 기반 확정, 질문 이력 1년 보존

### Community 205 - "Community 205"
Cohesion: 0.43
Nodes (8): 조문 전체 단위 청크, Markdown·JSON 원자 저장, law_json.parse_legal_document, 실험 A 일반 텍스트 청킹, 실행 계획 0016: 실험 A — 일반 텍스트 조문 청킹 관찰, ProvisionRecord, 텍스트 입력 어댑터, UI 잔여 줄 제거

### Community 206 - "Community 206"
Cohesion: 0.25
Nodes (8): 버전 관리 실행 계획, Clarification Missing Information, Legal Search Terra 경로, 0046 기준 질문 파이프라인 지도 설계, 사전 차단 질문 전용 LLM 경로, Terra Always-generate 계약, 빈 근거 Unanswerable 응답, Insufficient Evidence 판정

### Community 207 - "Community 207"
Cohesion: 0.71
Nodes (4): GET(), authErrorPath(), callbackBaseUrl(), safeAuthNextPath()

### Community 208 - "Community 208"
Cohesion: 0.52
Nodes (6): build_command(), main(), Path, read_hook_input(), resolve_file_path(), to_repo_relative()

### Community 209 - "Community 209"
Cohesion: 0.29
Nodes (7): Conditional Blocking Edge, Future Interrupt and Web Search, generate Node, route Node, LangGraph StateGraph, validate Node, v3 Design Status Proposed

### Community 210 - "Community 210"
Cohesion: 0.38
Nodes (7): Terra 검색 전용 폴백, 익명 질문 비저장, 채팅 중심 반응형 셸, 실행 계획 0003: 채팅 중심 웹 경험, 로그인 대화 이력, 검색 전용 모드, gpt-5.6-terra 생성 모델

### Community 211 - "Community 211"
Cohesion: 0.33
Nodes (7): Retrieval catalog v1, retrieval_index_builds table, retrieval_profiles table, Condorcet Fuse, LETOR 3 dataset, Rank fusion, Reciprocal Rank Fusion

### Community 212 - "Community 212"
Cohesion: 0.38
Nodes (7): Article 10 transfer, split, and merger, Article 11 succession, Article 12 license cancellation, Article 53 electricity commission, Article 7 business license, Article 8 disqualification, Article 9 installation and start duty

### Community 213 - "Community 213"
Cohesion: 0.47
Nodes (5): MockGoogleLoginRequest, MockLoginResponse, BaseModel, mock_google_login(), 비운영 환경에서 목업 Google 로그인 세션을 발급한다.

### Community 214 - "Community 214"
Cohesion: 0.33
Nodes (6): _async_database_url(), main(), SQLAlchemy's async engine requires an async driver in the URL scheme.…, CLI entrypoint: `python -m law_rag_llamaindex.ingest`. Reads…, test_async_database_url_adds_asyncpg_driver_to_plain_postgresql_url(), test_async_database_url_leaves_asyncpg_url_unchanged()

### Community 215 - "Community 215"
Cohesion: 0.47
Nodes (3): QuestionResponse, EmptyResultMessage, getEmptyResultMessage()

### Community 216 - "Community 216"
Cohesion: 0.40
Nodes (6): Citation Integrity Gate, Untrusted External Law Document, Prompt Injection, Rate-Limit Abuse, Stale or Partial Corpus, Application Trust Boundary

### Community 217 - "Community 217"
Cohesion: 0.33
Nodes (6): v2 Dense Retriever, v2 Ingestion Readiness Marker, SearchHit Mapping, search Node, v2 Retriever Reuse, Independent v3 Agent

### Community 218 - "Community 218"
Cohesion: 0.33
Nodes (6): D-10 Gold Set, E-001 E-10 Experiment Plan, E-10 Base Execution, Historical Tier Routing, Maximum Twelve NVIDIA Calls, TD-011 Answer Quality Evaluation

### Community 219 - "Community 219"
Cohesion: 0.33
Nodes (6): F-005 Picked Up Status, Active Execution Plan Index, E-001 Todo, F-001 Todo, F-005 Picked Up, Roadmap Authority

### Community 220 - "Community 220"
Cohesion: 0.40
Nodes (6): Execution-Plan Lifecycle, Manual GitHub Label Mapping, Single Picked-Up Constraint, 0059 Task Management Metadata and Roadmap, Task Metadata Contract, Thin Roadmap Status Index

### Community 221 - "Community 221"
Cohesion: 0.33
Nodes (6): Electric Utility Act chapter 2 fixture, Experiment A chunking results, Local user-provided experiment, parse_legal_document parser, Parser schema version 2, Six article chunks

### Community 222 - "Community 222"
Cohesion: 0.33
Nodes (6): Embedding repeatability unresolved, Exact 512-float vector comparison, Experiment B embedding results, Native 2048 dimensions, nvidia/nemotron-3-embed-1b, NVIDIA NIM

### Community 223 - "Community 223"
Cohesion: 0.33
Nodes (6): Authoritative design and product documents, Current behavior contract, law-rag Learning Course Index, Current learning course, Pending, excluded, and unvalidated distinctions, Six-part reading sequence

### Community 224 - "Community 224"
Cohesion: 0.33
Nodes (6): Quality Scorecard, Mock Evaluation Limitation, Quality Scorecard Assessment, Search Quality: B, Search Availability SLI/SLO: 99.9%, E-001 AI Answer Evaluation E-10

### Community 227 - "Community 227"
Cohesion: 0.60
Nodes (3): claimAnonymousLoginPrompt(), LOGIN_PROMPT_KEY, SessionStorage

### Community 228 - "Community 228"
Cohesion: 0.70
Nodes (3): dialogKeyAction, focusInitial(), restoreFocus()

### Community 229 - "Community 229"
Cohesion: 0.60
Nodes (3): updateSession(), config, proxy()

### Community 230 - "Community 230"
Cohesion: 0.70
Nodes (5): Authoritative Question Execution, Current State Session Start Pointer, Generation Indexing, Sentence-Level Grounding SSE, V2 LlamaIndex Framework Pipeline

### Community 231 - "Community 231"
Cohesion: 0.40
Nodes (5): 조문 경로 보존, 답변 근거 검증 설계, 인식론적 겸양 필터, missing_information, grounding 검증 replay

### Community 232 - "Community 232"
Cohesion: 0.40
Nodes (5): 복잡한 내부 경계 docstring, Python docstring 정책, 점진적 적용 범위, 공개 API docstring, Ruff D 규칙

### Community 233 - "Community 233"
Cohesion: 0.40
Nodes (5): Execution-Plan Metadata Contract, GitHub Type Labels, Picked Up Singleton, Plan Artifact Lifecycle, Thin Roadmap Index

### Community 234 - "Community 234"
Cohesion: 0.40
Nodes (5): as_of_date, Document Versions Natural Key, Effective-Date Half-Open Interval, unsupported_corpus_date HTTP 422, TD-027 v2 Date Gate

### Community 235 - "Community 235"
Cohesion: 0.40
Nodes (5): Alembic autogenerate translation, Korean translation materials, OpenAI Vector embeddings translation, Research and standards excerpts translation, Source term preservation

### Community 236 - "Community 236"
Cohesion: 0.50
Nodes (5): Product Specifications Index, Approved grounded legal QA specification, Onboarding assumption draft, Product specifications catalog, User-observable product spec rules

### Community 237 - "Community 237"
Cohesion: 0.40
Nodes (5): 외부 참고 자료와 법률 권위의 경계, Harness Engineering 메모, NVIDIA 로컬 추론·Vercel 연결 검토, 참고 자료 카탈로그, 안정적 링크·확인일·라이선스 메모

### Community 238 - "Community 238"
Cohesion: 0.40
Nodes (5): Advisory-Lock Idempotency, Expired Question-History Purge, D-009 Production Question-History Scheduler, Account-Deletion Propagation, One-Year Question-History Retention

### Community 239 - "Community 239"
Cohesion: 0.40
Nodes (5): law-rag-agent, law-rag-api, law-rag-collector, law-rag-core, law-rag-llamaindex

### Community 244 - "Community 244"
Cohesion: 0.83
Nodes (3): load_migration(), test_retention_migration_is_serialized_idempotent_and_scheduler_neutral(), test_retention_migration_records_auditable_cleanup()

### Community 245 - "Community 245"
Cohesion: 0.83
Nodes (3): load_migration(), test_v3_thread_migration_downgrade_drops_index_before_table(), test_v3_thread_migration_has_expected_revision_and_schema()

### Community 246 - "Community 246"
Cohesion: 0.50
Nodes (4): AI Mode Status Copy, Citation-Verified Answer Badge, 0036 Account Modal Model Label, Provider-Neutral UI Copy

### Community 247 - "Community 247"
Cohesion: 0.50
Nodes (4): Account Quota Toggle, 0037 Account Quota Toggle, Quota Re-Enable Contract, Unlimited Account Mode

### Community 248 - "Community 248"
Cohesion: 0.50
Nodes (4): Pre-Existing Documentation Debt, 0056 Python Docstrings and Ruff D, Public API Docstrings, Ruff PEP 257 Docstring Policy

### Community 249 - "Community 249"
Cohesion: 0.50
Nodes (4): Electricity permit sentence A, Electricity permit paraphrase sentence B, Punctuation variant sentence, Identical question sentence

### Community 250 - "Community 250"
Cohesion: 0.50
Nodes (4): lay-energy-0346, lay-energy-0346 rerank case, Direct evidence rank 8 to 2, lay-energy-0346 direct evidence rank 8

### Community 252 - "Community 252"
Cohesion: 0.67
Nodes (3): Bug issue form, Bug-report privacy notice, Bug reproduction and sanitized evidence

### Community 253 - "Community 253"
Cohesion: 0.67
Nodes (3): Documentation checker, Web and Python quality checks, GitHub CI workflow

### Community 269 - "Community 269"
Cohesion: 0.67
Nodes (3): LlamaIndexLegalRepository, v1 Answer Pipeline Reuse, v2 Search and Question Endpoints

### Community 270 - "Community 270"
Cohesion: 0.67
Nodes (3): Verified Completed Plan Archive, Completed Execution Plans Index, Project Roadmap

### Community 271 - "Community 271"
Cohesion: 0.67
Nodes (3): checklist_exports table, conversations table, question_history table

### Community 272 - "Community 272"
Cohesion: 0.67
Nodes (3): law_type_code, legal_documents table, National law information Open API

### Community 273 - "Community 273"
Cohesion: 0.67
Nodes (3): RLS and auth.uid ownership, user_consents table, user_profiles table

## Ambiguous Edges - Review These
- `routing_unavailable` → `HNSW Excluded from v2`  [AMBIGUOUS]
  docs/design-docs/single-stage-router-and-failure-response.md · relation: semantically_similar_to
- `요청 ID 기반 서버 취소 endpoint` → `Qwen3:4b 연결 준비`  [AMBIGUOUS]
  docs/exec-plans/completed/0010-token-context-cancellation-and-search-coverage.md · relation: conceptually_related_to

## Knowledge Gaps
- **619 isolated node(s):** `EmbeddingProfile`, `Theme`, `$schema`, `icn1`, `maxDuration` (+614 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **80 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `routing_unavailable` and `HNSW Excluded from v2`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **What is the exact relationship between `요청 ID 기반 서버 취소 endpoint` and `Qwen3:4b 연결 준비`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `PostgresLegalRepository` connect `Community 30` to `Community 1`, `Community 132`, `Community 6`, `Community 7`, `Community 9`, `Community 78`, `Community 17`, `Community 83`, `Community 52`, `Community 53`, `Community 85`, `Community 57`, `Community 95`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `SourceKind` connect `Community 53` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 9`, `Community 12`, `Community 13`, `Community 15`, `Community 22`, `Community 28`, `Community 30`, `Community 37`, `Community 38`, `Community 44`, `Community 46`, `Community 63`, `Community 68`, `Community 74`, `Community 76`, `Community 78`, `Community 80`, `Community 81`, `Community 83`, `Community 85`, `Community 93`, `Community 102`, `Community 103`, `Community 111`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `build_embedder()` connect `Community 40` to `Community 112`, `Community 36`, `Community 214`, `Community 142`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 96 inferred relationships involving `SourceKind` (e.g. with `PostgresLegalRepository` and `._hit()`) actually correct?**
  _`SourceKind` has 96 INFERRED edges - model-reasoned connections that need verification._
- **Are the 42 inferred relationships involving `PostgresLegalRepository` (e.g. with `SearchStageTrace` and `SearchTrace`) actually correct?**
  _`PostgresLegalRepository` has 42 INFERRED edges - model-reasoned connections that need verification._
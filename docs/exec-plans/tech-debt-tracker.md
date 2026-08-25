# 기술 부채 추적기

## 등급

- P0: 보안, 데이터 손실, 법률적으로 오해를 유발할 수 있는 즉시 위험
- P1: 다음 릴리스 전 해결해야 할 신뢰성/품질 위험
- P2: 계획된 유지보수에서 해결할 생산성/일관성 문제
- P3: 기회가 있을 때 개선할 항목

## 열린 항목

| ID | 등급 | 영역 | 내용 | 종료 조건 | 소유자 |
|---|---|---|---|---|---|
| TD-006 | P0 | 배포 | Vercel·Supabase·Google OAuth·현재 코퍼스 연결은 완료했으나 실제 Terra를 포함한 공개 URL 통합 종단 증거가 없음 | 공개 URL에서 로그인→Terra/검색 전용→인용 원문→이력→내보내기 흐름 통과 | 미지정 |
| TD-007 | P1 | 시간성 | `delHst` 실응답은 확인했고 법적 폐지와 출처 삭제를 분리했으나 운영 코퍼스 격리 전파는 미검증 | 실제 주간 실행에서 출처 삭제 격리·경고 종단 테스트 통과 | 미지정 |
| TD-008 | P1 | 운영 | 독립 collector와 Windows 스케줄러 스크립트는 구현됐으나 클라우드 고정 IP 운영 검증이 필요 | 예약·수동 수집 및 IP 변경 경고 검증 | 미지정 |
| TD-009 | P1 | 신뢰성 | AI quota 플래그가 프로세스 메모리에만 존재 | `runtime_flags` 영속 폴백 테스트 통과 | 미지정 |
| TD-010 | P2 | 제품 | Markdown/CSV/PDF 체크리스트 내보내기는 목업 구현됐으나 변경 비교·관계 그래프가 미완료 | 승인된 제품 흐름 종단 테스트 통과 | 미지정 |
| TD-011 | P1 | 답변 품질 | 5개 목업 질문 계약과 결정적 근거 게이트는 통과했으나 실제 코퍼스·Terra·법률 전문가 평가는 미실행 | 버전 고정 코퍼스 Recall/MRR, Terra 오탐·미탐, 전문가 블라인드 표본 결과 기록 | 미지정 |
| TD-012 | P0 | 개인정보 | 1년 만료 이력 정리 함수는 있으나 운영 scheduler가 없음 | 정리 job·감사 메트릭·실제 만료 삭제 통합 테스트 | 미지정 |
| TD-013 | P1 | 취소 | 분산 coordinator는 설계·memory mock만 있고 운영은 process-local | Supabase migration과 2인스턴스 종단 취소·상태 UX 통과 | 미지정 |
| TD-014 | P1 | AI 공급자 | NVIDIA hosted NIM adapter와 schema mock은 구현됐으나 실제 key·법률 평가·Trial→Production 계약이 미검증 | hosted smoke, 고정 평가셋, 운영 endpoint 계약 통과 | 미지정 |
| TD-015 | P1 | 임베딩 | 조문 벡터 backfill 운영 경로와 모델·차원·버전 검색 필터가 없음 | backfill CLI, DB 함수 필터, 벡터 개수·Recall 검증 | 미지정 |
| TD-016 | P1 | 컨텍스트 | 실제 tokenizer 기반 전체 prompt/output 예산 게이트가 없음 | server tokenizer와 근거 trimming 경계 테스트 | 미지정 |
| TD-017 | P1 | 로컬 추론 | Vercel→PC 직접 경로는 없고 outbound inference worker가 미구현 | 인증 queue worker·TTL·동시성·fallback 종단 테스트 | 미지정 |
| TD-018 | P1 | 운영 | AI quota 플래그·메트릭이 인스턴스 메모리에 남음 | runtime_flags와 중앙 관측·복구 테스트 | 미지정 |
| TD-019 | P0 | AI 개인정보 | NVIDIA hosted 전송의 보존·학습·국외 이전·Trial 약관이 미검증 | 정책 검토와 개인정보처리방침 반영 전 공개 AI 비활성 | 사용자 |
| TD-020 | P1 | 임베딩 검색 | hybrid SQL이 embedding model·dimensions·version을 필터하지 않아 혼합 가능 | 벡터 값 유지, 함수 인자·필터 migration 및 혼합 회귀 테스트 | 미지정 |
| TD-021 | P2 | 취소 UX | 취소 API 실패도 즉시 중지 완료처럼 표시될 수 있음 | 접수·확정·이미 완료·503 재시도 상태 UI 테스트 | 미지정 |
| TD-022 | P2 | 벡터 저장 | HNSW는 영구 제외했지만 적용된 migration `0008`, 기존 물리 인덱스와 `hnsw_ready` 레거시 진단이 남아 있음 | 별도 additive cleanup migration으로 기존·신규 환경의 HNSW 인덱스와 전용 진단을 제거하고 exhaustive exact cosine 회귀 검증 통과 | 미지정 |
| TD-023 | P2 | AI 답변 품질 | `temperature=0.3`·`answer_timeout_seconds=40`(현재 설정; 60초는 역사적 E-10/구 배포 기록이며 현재 계약이 아님)과 `derive_answer_action()`의 checklist→action 매핑 규칙이 실측 D-10 실행으로 검증된 적이 없음 | [0032](active/0032-experiment-e-10-ai-answer-evaluation.md) 역사 실행 기록과 현재 단일-stage timing을 대조해 재현성·latency·gold 일치율을 확인하고 값을 확정 | 미지정 |
| TD-024 | P2 | 단일 라우터 정책 | 역사적 route-fixture-v1 실행에서 provider route judgment가 일부 질문을 `external_document_required`로 잘못 차단한 사례가 남아 있다. 이는 현재 tier2 runtime을 전제하지 않으며, D-010 단일 `QuestionRouter`의 route/reason_code calibration 필요성을 보여주는 제한된 역사 증거다 | [0033](todo/0033-traffic-based-routing-calibration-review.md) 트래픽 축적 후 단일-router 정책·reason_code calibration을 승인받아 재검토 | 미지정 |
| TD-025 | P1 | 배포 | 2026-08-08 실제 프로덕션 응답에서 `fallback_reason:"generation_error"`가 확인됐으나, 현재 `ANSWER_TIMEOUT_SECONDS=40` 설정과 D-010 fail-closed 계약의 배포 반영 여부가 미검증이다. 60초 값은 역사적 기록이며 현재 기준이 아니다 | Vercel API 프로젝트가 최신 커밋으로 재배포됐는지, `ANSWER_TIMEOUT_SECONDS` 환경변수가 현재 40초 계약과 일치하는지 확인 | 사용자 |
| TD-027 | P2 | v2 검색 | `/v2/search`·`/v2/questions`가 v1의 `_require_supported_as_of_date`(기준일이 corpus 지원 범위 밖이면 `422 unsupported_corpus_date`로 차단)에 해당하는 v2 전용 게이트가 없음 — 범위 밖 날짜에 조용히 빈 결과를 반환할 수 있음. [0053](completed/0053-v2-llamaindex-retrieval-pipeline.md) 전체 브랜치 리뷰에서 발견(2026-08-18) | v2 corpus의 지원 기준일 범위(예: ingestion된 provision들의 최소 `effective_from`)를 계산해 v1과 동일한 방식으로 범위 밖 요청을 사전에 거부 | 미지정 |
| TD-026 | P2 | 데이터 모델 | [0041](completed/0041-parse-law-type-classification-code.md) 완료 뒤 `source_kind`와 `law_type_code`가 의미상 겹친다고 확인됨(둘 다 쓰는 코드 4곳 존재, 대체된 사용처는 없음). `source_kind`는 `legal_documents`의 `UNIQUE(source_kind, source_id)`·upsert `ON CONFLICT` 키·`corpus-publish-base-v1` drift 계약·population fingerprint에 걸친 identity 컬럼이라 통합 시 재설계 범위가 크므로 지금은 병합하지 않기로 결정(2026-08-09) | 두 값이 실제로 어긋나는 사례가 발견되거나 identity/drift 계약을 다른 이유로 재설계할 기회가 생기면 `law_type_code → source_kind` 도출 방식으로 통합 재검토 | 미지정 |

## 종료된 항목

| ID | 종료일 | 결과 |
|---|---|---|
| TD-001 | 2026-07-13 | 일반 사용자·에너지 사업·MVP 법령 9개로 제품 명세 승인 |
| TD-002 | 2026-07-13 | 국가법령정보 공동활용 Open API 단일 출처와 실응답 계약 검증 |
| TD-004 | 2026-07-13 | 실제 MVP 9개 수집 산출물 기반 검색 평가 9/9 통과, Recall@10 1.0 기록 |
| TD-003 | 2026-07-14 | Markdown 로컬 링크와 핵심 문서 45일 신선도 검사를 CI·로컬 검증에 도입 |
| TD-005 | 2026-07-14 | 주장별 핵심용어·규범어·숫자 인용 게이트와 무관 근거 폴백 테스트, 인용 존재·원문 일치 100% 평가 통과 |

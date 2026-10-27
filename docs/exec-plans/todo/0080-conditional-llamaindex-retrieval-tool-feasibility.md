> 작업 ID: `E-007`
> 상태: `Todo`
> 우선순위: `P3`
> 유형: `Experiment`
> 보조 라벨: `Performance`, `UX`, `Evaluation`
> 선행 조건: 실제 모델 tool-calling 평가는 NVIDIA 개발 credential·network 실행 승인과 읽기 전용 검색 DB 접근 승인이 필요하다.
> 다음 행동: 현재 conditional search 기준선과 단일 retrieval tool의 입력·출력·호출 금지 계약을 먼저 고정한다.
> 참고 범위:
> - `apps/api/app/api/v2/executions.py` L81-L93 — 현재 V2 pinned index 검색 호출 경계
> - `apps/api/app/application/v2/phase_service.py` L752-L780 — legal_search에서만 근거 검색을 실행하는 현재 조건부 분기
> - `apps/law-rag-llamaindex/src/law_rag_llamaindex/query/retriever.py` L1-L113 — query embedding·vector query·기준일 필터·SearchHit 변환 흐름

# LlamaIndex 임베딩·검색 단일 tool화와 선택 호출 가능성 검증

**Goal:** LlamaIndex의 질의 임베딩부터 기준일 검색·`SearchHit` 반환까지를 하나의 안전한 tool로 묶을 수 있는지, 그리고 에이전트가 일상 대화에서는 이 tool을 호출하지 않고 법률 근거가 필요할 때만 호출하도록 만들 수 있는지 검증한다.

**Important baseline:** 현재 V2 서비스도 typed route가 `legal_search`일 때만 근거 검색을 실행하므로 다른 route에서는 이미 embedding을 건너뛴다. V3는 F-001 Dropped에 따라 2026-10-27 소스를 제거했으므로 비교 기준으로 사용하지 않는다. 이번 실험은 단순히 embedding 호출 수를 줄이는 것이 아니라, 일상 대화 응답을 새로 허용하면서도 법률 주장은 반드시 검색 tool과 인용을 거치게 할 수 있는지, 기존 route 방식보다 실제 이점이 있는지를 비교한다.

**Non-goal:** 이 실험에서 운영 그래프를 tool-calling 방식으로 전환하거나 기존 안전 라우터를 제거하지 않는다. 결과는 `채택`, `기존 route와 병행`, `기각` 중 하나의 근거 있는 결론과 후속 구현 범위다.

### Task 1: 단일 retrieval tool 계약과 기준선 고정

- **결과:** tool이 소유할 입력·출력·오류·관측 경계와, tool을 호출하면 안 되는 일상 대화 및 반드시 호출해야 하는 법률 질문 기준이 문서와 테스트 fixture로 고정된다.
- **대상:** `apps/api/app/api/v2/executions.py` L81-L93 및 `apps/law-rag-llamaindex/src/law_rag_llamaindex/query/retriever.py` L1-L113 검토, tool 계약 설계 문서 새 파일 약 100줄, 평가 fixture 새 파일 약 80줄, 합계 약 180줄.
- **실행 절차:** tool 입력을 질문·기준일·결과 수로 제한하고 내부에서 query embedding, vector query, 시간 유효성 필터, 공식 출처 metadata 검증, `SearchHit` 직렬화를 소유하도록 경계를 정의한다. 일상 인사·잡담·글쓰기 요청, 명백한 법률 질문, 법률처럼 보이는 애매한 질문, 대화 후속 질문을 균형 있게 고정한다. 기존 V2 조건부 분기에서 embedding·retrieval 호출 횟수와 답변 경로를 fake embedder/vector store로 측정한다. API 경계는 `..\..\scripts\run_python.ps1 -m pytest -p no:cacheprovider tests/test_v2_question_executions.py`를 `apps/api`에서 실행한다. 검색 adapter는 `..\..\scripts\run_python.ps1 -m pytest -p no:cacheprovider tests/test_retriever.py`를 `apps/law-rag-llamaindex`에서 별도로 실행한다.
- **완료 증거:** tool 하나의 타입 계약, fail-closed 오류 계약, 관측 event, 호출/비호출 평가셋과 현재 V2 조건부 분기의 embedding 호출 기준선이 재현 가능하게 남는다.
- **의존성:** 없음.

### Task 2: 운영 비활성 tool-calling prototype 비교

- **결과:** 운영 경로를 바꾸지 않는 prototype에서 일상 대화는 embedding 0회, 법률 질문은 retrieval tool 1회와 인용 가능한 `SearchHit`를 만드는지 검증된다.
- **대상:** 기존 `experiments/search/` 아래 실험용 tool adapter·harness 새 파일 합계 약 140줄, 관련 단위 테스트 새 파일 약 120줄, V2 조건부 분기 비교 테스트 새 파일 약 40줄, 합계 약 300줄. 폐기한 V3 package는 다시 만들지 않는다.
- **실행 절차:** 현재 `retriever.search`를 다시 구현하지 않고 typed tool adapter로 감싼다. fake model을 사용해 일상 대화에서 tool 0회, 법률 질문에서 정확히 1회, tool 오류·빈 결과·잘못된 인자에서 안전 종료, tool을 쓰지 않은 응답에 실질적 법률 주장이 없음을 먼저 테스트한다. 대화 문맥에 앞선 법률 질문이 있더라도 새 일상 대화가 불필요하게 검색을 타지 않는지, 반대로 짧은 후속 법률 질문이 검색 없이 답변되지 않는지 검증한다. 기존 route 방식과 tool-calling prototype의 노드 수·provider 호출 수·embedding 호출 수·지연 예산을 같은 fixture로 비교한다.
- **완료 증거:** prototype이 검색 구현을 복제하지 않고 단일 tool 경계를 사용하며, 호출 필요 여부별 기대 횟수와 법률 주장 안전 조건을 모두 통과한다.
- **의존성:** Task 1의 tool 계약과 평가 fixture.

### Task 3: 실제 모델 소표본 판정과 채택 결정

- **결과:** 실제 모델이 tool을 빠뜨리거나 남용하는 비율, 비용·지연 변화, 기존 typed route 대비 안전성이 측정되어 채택 여부가 결정된다.
- **대상:** Task 1 평가 fixture 결과 artifact 새 파일 약 120줄, `docs/design-docs/conditional-retrieval-tool-feasibility.md` 새 파일 약 140줄, `ARCHITECTURE.md` 결정 기록 추가 약 6줄, 이 계획 결과 기록 약 12줄, `docs/ROADMAP.md` renderer 생성 변경.
- **실행 절차:** 승인된 NVIDIA 개발 환경과 읽기 전용 DB에서 고정 fixture를 기존 route와 tool-calling prototype에 동일하게 실행한다. 일상 대화 tool 오호출률, 법률 질문 tool 미호출률, 질문당 embedding 횟수, 첫 응답 지연, 검색된 근거·인용 가능성을 비교한다. 법률 질문의 tool 미호출은 일반 품질 실패가 아니라 안전 실패로 분류한다. 모델이나 SDK가 안정적인 tool calling을 지원하지 않거나 typed route보다 안전성이 낮으면 기각 또는 병행 결론을 낸다. 결과를 설계 문서와 결정 기록에 남기고 계획을 `completed/`로 이동한 뒤 roadmap renderer와 checker를 실행한다.
- **완료 증거:** `채택`, `기존 route와 병행`, `기각` 중 하나가 수치와 실패 사례로 뒷받침되고, 채택 시에도 “실질적 법률 주장은 검색 tool 결과와 인용이 있어야 한다”는 불변조건과 후속 구현 범위가 명확하다.
- **의존성:** Task 1과 Task 2 완료, NVIDIA 개발 credential·network 실행 승인, 읽기 전용 검색 DB 접근 승인.

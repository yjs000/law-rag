> 작업 ID: `E-005`
> 상태: `Todo`
> 유형: `Experiment`
> 보조 라벨: `Data`, `Evaluation`
> 선행 조건: parser·chunk_size·overlap·호출 비용 상한·실험 DB 권한을 확정하고 입력 artifact와 운영 색인 격리 경로를 검증해야 한다.
> 다음 행동: 동일 v2 snapshot에서 청킹별 top-k Recall을 비교
> 참고 범위:
> - `docs/design-docs/v2-llamaindex-retrieval-pipeline-design.md` L105-L118 — v2 ingestion 입력과 원본 metadata 보존 계약
> - `docs/design-docs/experiment-d-10-gold-adjudication.md` L9-L14 — D-10 calibration Gold의 10문항 범위와 D-full 분리

# 0058: v2 청킹 ablation — 현재 조문 노드 vs LlamaIndex 하위 청킹

## 계획 본문

상태: `제안됨 (2026-08-25)`

제안 출처: 사용자가 v1/v2 파이프라인을 검토한 뒤, 운영 검색을 바꾸기 전에 **v2 내부에서
청킹만** 현재 조문 단위와 새 LlamaIndex 청킹으로 바꿔 비교하라고 요청했다.

## 목표

현재 v2의 `조문 1개 = TextNode 1개` 기준선과, 같은 조문을 LlamaIndex node parser로 하위
청킹하는 후보를 A/B ablation으로 비교한다. 이 실험은 청킹 이후의 모든 단계를 v2로 고정해,
top-k 검색 결과의 Recall 계열 수치 차이만 청킹 선택의 근거로 사용한다.

## 고정 조건

- **공통 입력:** 동일한 v2 corpus snapshot과 동일한 10개 D-10 sealed calibration Gold 질문·기준일·qrel을 사용한다.
- **공통 후속 과정:** 두 arm 모두 LlamaIndex NVIDIA embedding, v2 native 2048차원 벡터,
  LlamaIndex PGVectorStore, 동일 metadata/시행일 필터, 동일 top-k와 동일 `SearchHit` 매핑을 사용한다.
- **실험 변수 하나:** ingestion의 node builder/chunker만 DI로 주입해 바꾼다.
  - A 기준선: 현행 `provision` 하나를 `TextNode` 하나로 만드는 방식.
  - B 후보: LlamaIndex node parser가 같은 provision에서 만든 하위 노드 방식.
- **추적성:** B의 모든 하위 노드는 원 `provision_id`, 원 조문 경로, 원문 SHA와 하위 범위를 보존한다.
  이 실험은 검색 순위만 평가하지만, 법률 근거의 출처·인용 위치를 잃는 노드는 생성하지 않는다.

## 범위

1. v2 ingestion 경계에 `node_builder` 또는 동등한 chunker 의존성을 주입할 수 있게 만들고,
   A/B arm이 같은 provision 입력에서 서로 다른 노드 집합만 생성하게 한다.
2. 각 arm을 서로 격리된 실험용 v2 vector table/run manifest에 적재한다. 기존 운영
   `data_law_rag_llamaindex`, v1 `provision_embeddings`, 원문·조문 테이블은 변경하지 않는다.
3. sealed D-10 calibration Gold의 확정된 10문항으로 각 arm의 raw top-k 결과를 생성한다.
4. 동일 qrel을 기준으로 Recall@1/3/5/10과 MRR@10을 계산하고, 질문별·전체 집계 결과와
   corpus snapshot, chunker 설정, 코드/입력 SHA를 재현 가능한 artifact로 기록한다.

## 비범위

- v1 검색, v1 임베딩, v1 snapshot 또는 v1 평가 harness를 비교 대상에 넣는 것
- 임베딩 모델·차원·벡터 저장소·HNSW 설정·검색 필터·reranking·keyword fallback·답변 생성의 변경
- latency, 비용, 주관적 답변 품질, 새로운 사람 판정, D-full 일반화 또는 운영 release 판단
- 실험 결과만으로 운영 v2 청킹이나 사용자 트래픽을 바꾸는 것

## 평가·판정 규칙

- 평가는 기존 sealed D-10 calibration Gold의 확정 10문항만 사용한다.
- 같은 질문·기준일에 대해 두 arm의 top-k를 qrel과 대조하고 Recall@k와 MRR@10만 비교한다.
- 수치가 어느 한 arm의 우월성을 보여도 이는 **D-10 calibration 범위의 청킹 비교 결과**일 뿐,
  held-out 성능·일반화·운영 채택 근거로 표현하지 않는다.
- 동률 또는 개선이 불명확하면 현재 조문 단위 기준선을 유지한다. 운영 변경은 별도 TODO와 사용자
  승인 없이는 수행하지 않는다.

## 완료 조건

- A/B가 같은 v2 snapshot과 같은 10개 질문을 사용했다는 manifest 검증이 통과한다.
- 두 arm에서 chunker 이외 v2 retrieval 설정이 동일함을 자동 검사한다.
- B의 모든 노드가 원 provision 추적 필드를 가지며, 누락·중복·범위 오류가 없음을 테스트한다.
- 각 arm의 질문별 top-1/3/5/10, Recall@1/3/5/10, MRR@10과 전체 집계가 생성·재실행 가능하다.
- 결과 문서가 비교 범위를 “청킹 ablation, D-10 calibration only”로 명시한다.

## active 승격 조건

- 사용자가 이 TODO의 착수를 명시한다.
- 실험할 LlamaIndex node parser와 `chunk_size`·`chunk_overlap` 값, NVIDIA 임베딩 호출 비용 상한,
  실험용 원격 DB table 생성 권한을 사용자와 함께 확정한다.
- 실행 전 현재 v2 ingestion과 D-10 Gold artifact가 읽기 가능하며, 실험 결과를 운영 색인과
  물리적으로 격리할 경로가 검증된다.

## 결정 기록

- 2026-08-25: 청킹 효과만 분리하기 위해 v1을 대조군으로 쓰지 않고, snapshot·임베딩·벡터 저장소·검색과
  평가를 모두 v2로 고정한다.
- 2026-08-25: 현재 조문 단위와 LlamaIndex 하위 청킹을 DI로 교체한다. 청킹 이후 retrieval 과정은
  두 arm에서 같아야 한다.
- 2026-08-25: sealed D-10의 확정 10문항을 사용하며, top-k Recall 계열 수치로만 청킹을 판단한다.

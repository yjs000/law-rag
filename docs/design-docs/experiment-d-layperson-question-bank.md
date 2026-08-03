# 실험 D 일반 사용자 질문은행과 gold 주석 경계

상태: 질문 검토 초안
작성일: 2026-08-03

## 목적

기존 실험 D v3는 운영 corpus의 원문 근거를 먼저 고르고 질문을 역으로 만들어 정답 라벨과 qrels를 정적으로 생성한 검토 전 초안이다. 검색 결과에서 정답을 추론하지 않는 장점이 있지만, 아직 사용자 질문 검토와 corpus 재동기화를 거친 승인 gold는 아니다. 또한 법률명·조문 경로를 아는 질문이 많아 일반 사용자의 표현 분포를 충분히 대표하지 못한다.

별도의 일반 사용자 질문은행은 “태양광 사업을 시작하려면 무엇을 준비해야 하나요?”처럼 상황과 목적부터 말하는 질문을 수집한다. 이 은행은 기존 v3를 교체하지 않으며, 취소된 v2 전체 검토본과도 관계없는 새 산출물이다.

## 현재 산출물의 역할

`experiment-d-lay-energy-query-bank-v1-draft.json`은 질문을 검토하기 위한 후보 은행이다.

- 1,000개 질문만 포함한다.
- 공공기관 FAQ·절차 안내에서는 질문 주제만 참고하고 문구와 답을 복사하지 않는다.
- 실제 사용자 로그나 질문 빈도 자료라고 주장하지 않는다.
- 모든 문항은 `evaluation_annotation_status=not_annotated`이다. 이는 평가 정답 라벨인 answerability·qrels·reference response가 없다는 뜻이며, 질문을 만든 주제·기술·표현 방식 같은 생성 메타데이터가 없다는 뜻은 아니다.
- 사용자 유형·사업 단계·현재 corpus의 답변 가능성을 문항별 라벨로 미리 붙이지 않는다. 주제 수준의 후보 정보만 남긴다.
- 출처 연결도 질문별 근거가 아니라 연구 주제 수준의 영감 출처로만 기록한다.
- 정답, qrels, 기대 법령·조문과 검색 결과를 포함하지 않는다.
- `catalog_title_set_sha256`은 검토 대상 법령명 목록이 바뀌었는지만 확인한다. parser가 만든 조문 ID와 본문을 고정하는 corpus fingerprint가 아니다.
- `question_set_sha256`은 질문 ID와 문구를, `question_scope_set_sha256`은 여기에 상황 묶음·의도·기술·질문 변형을 더해 고정한다. 사용자 승인 뒤에는 어느 쪽도 다시 계산해 덮어쓰지 않는다.
- 사용자 질문 승인 전에는 검색·임베딩 평가에 입력하지 않는다.

이 상태로 확인할 수 있는 것은 질문 수, 범위, 자연스러움, 중복, 법률식 표현 혼입 여부다. Recall·MRR·nDCG나 최종 답변 정확도는 평가할 수 없다.

질문은 200개 상황과 상황별 5개 질문 변형(`query_variants_per_scenario`)으로 구성한다. 여기서 변형은 질문 말투·관점이며, gold의 필수 답변 요소(`required_answer_facets`)와 다른 개념이다. 처음에는 큰 주제마다 공통 후속문을 붙였지만, 검사 신청·계량기 고장·계약 분쟁처럼 서로 다른 상황에서 의미 충돌이 발견됐다. 이후 상황을 더 작은 호환 묶음으로 나누고, 문항별 사용자 유형·단계·scope 자동 배정을 제거했다. 정적 중복 검사와 별도로 전체 문장 읽기 검토를 수행한다.

## 왜 질문과 정답을 동시에 자동 생성하지 않는가

질문을 만든 직후 현재 검색기의 상위 결과를 정답으로 저장하면 검색기가 자기 결과로 자신을 채점하게 된다. 잘못 검색된 조문이 gold로 굳어지고 Recall이 실제보다 높아질 수 있다. FAQ 페이지의 답도 이 프로젝트가 허용한 법률 corpus의 직접 근거가 아니므로 qrels로 대신 사용할 수 없다.

따라서 질문 확정과 gold 주석을 분리한다. 정답이 없는 편이 평가에 더 좋은 것이 아니라, 잘못된 정답을 조기에 고정하지 않기 위한 임시 단계다.

## gold 평가셋으로 승격하는 절차

여기서 gold는 검색기가 낸 결과와 독립적으로 사람이 공식 원문·버전을 확인해 정답 근거를 확정한 평가 자료다. 검색 정답은 `qrels`, 최종 동작과 기준 문구는 `reference_response`로 역할을 나눈다.

질문이 승인되면 별도 `experiment-d-lay-energy-gold-v1.json`을 만든다. 질문은행 원문은 고정하고 다음 필드를 독립적으로 주석한다.

실행 가능한 필드·상태·불변조건은 `apps/api/scripts/experiment_d_gold_contract.py`의 Pydantic 계약이 권위 원본이다. 문서 설명만 통과하고 코드 계약을 통과하지 못한 파일은 gold로 취급하지 않는다.

1. `evaluation_status`: 사람 검토와 승인 완료 전에는 `draft_for_review`, 완료 후에만 `approved_gold`
2. `source_bank`: 질문은행 버전과 승인된 전체 질문 문구 SHA-256·범위 SHA-256, 외부 승인 manifest SHA-256
3. `approval_manifest`: 사용자가 승인한 질문 ID·질문 SHA-256·질문 범위 SHA-256과 승인 시각을 질문은행과 별도 파일로 고정
4. `corpus_snapshot`: parser 계약 버전, 기준일, 실제 provision ID+본문 SHA 기반 corpus fingerprint와 검색 단위
5. `question_review_status`: gold에는 `approved` 문항만 포함하고 승인한 질문 SHA-256을 보존
6. `split`: 같은 scenario family를 나누지 않는 `calibration | test`
7. `answerability`: `fully_answerable | partially_answerable | clarification_required | unanswerable`
8. `required_answer_facets`: 허가, 부지, 계통연계, 검사처럼 답에 꼭 필요한 요소와 `supported | unsupported | needs_clarification` 상태
9. `qrels`: 각 요소를 직접 뒷받침하는 문서·버전·조문 ID, 경로, 본문 SHA-256, `facet_ids`와 관련성 등급
10. `reference_contexts`: qrel 원문 또는 content-addressed snapshot 위치. 이후 corpus가 바뀌어도 당시 기준문맥을 재현한다.
11. `reference_response`: 답변·부분 답변·추가 질문·근거 부족 중 기대 동작과 기준 문구, 인용 qrel ID
12. `insufficient_reason`: corpus 밖, 기준일 밖, 사실관계 부족 또는 직접 근거 부족
13. `annotation_review`: 작성자·검토자·판정 상태와 불일치 해결 기록

관련성 `2`는 하나 이상의 필수 답변 요소를 직접 뒷받침하는 원문, `1`은 그 직접 근거를 이해하는 데 필요한 문맥이다. 관련성 `0`인 오답 후보는 qrels에 넣지 않고 별도 distractor 목록에 둔다.

다음 불변조건을 적용한다.

- `fully_answerable`: 모든 필수 요소가 supported이고 요소마다 relevance 2 근거가 하나 이상 있다.
- `partially_answerable`: supported와 unsupported 요소가 모두 있다.
- `clarification_required`: 하나 이상의 요소가 `needs_clarification`이면 다른 상태보다 우선한다. 답을 정하려면 부족한 사용자 사실과 기준 추가 질문을 명시한다.
- `unanswerable`: qrels가 비어 있고 `insufficient_reason`이 필수다.
- reference response가 인용한 qrel은 반드시 같은 문항에 속해야 한다.
- 질문 문구가 바뀌면 질문은행 버전과 해시를 바꾸고 다시 승인한다.

`expected_action`은 위 상태와 일대일로 고정한다.

| answerability | expected_action | 기준 응답 |
|---|---|---|
| fully_answerable | answer | 직접 근거를 인용한 답 |
| partially_answerable | partial_answer_with_limits | 확인 가능한 부분과 확인 불가능한 부분을 구분한 답 |
| clarification_required | ask_clarifying_question | 필요한 사용자 사실을 묻는 질문 |
| unanswerable | insufficient_evidence | 근거 부족 사유를 밝힌 답변 보류 |

검색 결과는 근거 후보를 찾는 보조 수단으로 사용할 수 있지만, 그 결과 자체를 gold로 확정하지 않는다. 전체 corpus 확인, 출처·버전·원문 해시 검증과 사람의 직접 근거 판단을 거친다. 넓은 질문은 하나의 조문이 아니라 필수 답변 요소별 여러 qrels를 가질 수 있다.

평가 실행 전에는 `scripts.preflight_experiment_d_gold`가 다음을 읽기 전용으로 확인한다.

- `evaluation_status=approved_gold`
- 별도 승인 manifest, 질문은행, gold의 질문 ID·문구·범위·SHA-256 일치
- gold가 고정한 corpus fingerprint와 현재 searchable corpus의 일치
- 모든 qrel의 provision ID, document/version ID, path와 본문 SHA-256의 일치
- answerability와 qrels 유무의 일관성

이 독립 명령은 아직 평가 runner와 연결되지 않았고 검사 뒤 DB 잠금을 해제한다. 따라서 최종 runner는 같은 프로세스에서 corpus mutation 공유 잠금을 획득하고, 잠금 안에서 preflight를 다시 실행한 뒤 전체 검색이 끝날 때까지 잠금을 유지해야 한다. 그 연결이 구현되기 전에는 “검사를 통과했으니 검색도 같은 corpus를 봤다”고 주장하지 않는다.

## 독립 주석과 blind 평가

검색 결과를 그대로 정답으로 쓰지는 않지만 3,066개 조문 전체를 매번 눈으로 읽는 것도 재현 가능한 방법이 아니다. 따라서 직접 법률 경로 확인과 서로 다른 후보 수집 방법을 합친 pool을 만들고, 후보마다 직접 근거·보조 문맥·무관을 판정한다. 한 검색기의 결과만으로 pool을 만들지 않는다.

- 각 후보 수집 방법, 설정 SHA-256과 top-k를 기록한다.
- 문항별 판정 후보 provision ID 전체와 정렬된 후보 집합 SHA-256을 gold 안에 직접 고정한다. 이 inline 목록이 권위 원본이며, qrels와 distractor의 합집합은 정확히 이 목록과 같아야 한다.
- 후보 존재 여부는 생성기의 “정답 근거로 쓰기 좋은 조문” 휴리스틱이 아니라 실제 검색 가능한 provision 전체와 대조한다. 검색기가 반환할 수 있는 장·절 표지나 짧은 행도 distractor로 판정·기록할 수 있어야 한다.
- 주석자에게 어떤 검색 시스템이 후보를 냈는지 숨긴다.
- pool의 모든 후보를 판정하고 대체 가능한 직접 근거가 더 있는지 별도로 확인한다.
- 작성자와 다른 검토자가 불일치를 해결한 문항만 `adjudicated`로 둔다.
- test qrels는 검색 설정 조정에 사용하지 않고 봉인한다. 조정은 calibration 200개만 사용한다.
- frozen benchmark에서는 미판정 문서를 nonrelevant로 취급하므로 pool 완전성 한계를 결과에 함께 보고한다.

## 분할과 지표 계산 계약

같은 상황의 다섯 질문 변형은 반드시 같은 split에 둔다. 200개 scenario family 중 사람이 확정한 40개 family, 즉 200문항을 calibration으로, 나머지 160개 family, 즉 800문항을 test로 고정한다. 현 계약은 검증하지 않는 `stratified`라는 이름이나 seed를 주장하지 않고, 실제 family별 배정 목록과 그 SHA-256을 동결한다. gold 완성 뒤 intent·technology·answerability·필수 요소 수의 두 split 분포를 별도 보고해 심한 불균형을 사람이 검토한다.

- Recall@k·MRR·nDCG의 모집단은 `fully_answerable` 문항으로만 고정한다. partial·clarification·unanswerable을 같은 평균에 섞지 않는다.
- Recall@k와 MRR의 정답은 relevance `2` 직접 근거만 인정한다. relevance `1` 보조 문맥만 찾으면 성공이 아니다.
- nDCG@k는 직접 근거 `2`, 보조 문맥 `1`의 등급을 사용한다.
- 기본 검색 단위는 raw `provision_id`다. 부모·자식 조각은 자동으로 같은 정답으로 간주하지 않고, 필요한 계층 문맥을 qrels의 explicit evidence closure로 모두 기록한다.
- `facet_recall@k`의 분모는 corpus가 지원하는 필수 요소만 사용한다. corpus가 지원하지 않는 요소까지 포함한 전체 범위 충족률은 별도 `corpus_coverage`로 보고한다.
- 질문별 facet recall을 먼저 계산한 뒤 macro 평균한다. 한 질문의 요소 수가 많다는 이유로 전체 점수를 지배하게 하지 않는다.
- `all_required_facets_covered@k`는 fully answerable 문항에서 모든 필수 요소의 relevance 2 근거가 후보 안에 있을 때만 1이다.
- partial·clarification·unanswerable은 retrieval Recall 평균과 섞지 않고, 부분 근거 회수율·추가 질문 정확도·답변 보류 정확도·무관 근거 false-positive를 별도로 보고한다.
- 일반인 gold와 기존 synthetic control suite의 점수는 한 평균으로 합치지 않는다.

## 평가에서 두 자료의 관계

| 자료 | 강점 | 사용하는 평가 |
|---|---|---|
| 기존 실험 D v3 | 원문 기반 정답 라벨과 qrels를 정적으로 생성한 검토 전 초안 | 사용자 승인 뒤 결정적 검색 회귀, 경계·대조군 |
| 일반 사용자 질문은행 초안 | 자연어 범위와 사용자 상황이 넓음 | 질문 품질·범위 검토만 가능 |
| 향후 일반 사용자 gold | 자연스러운 질문과 독립 검증 근거를 함께 보유 | 현실적 Recall·MRR·nDCG와 답변 평가 |

질문 가족별 표현 변형은 나중에 calibration과 test 양쪽으로 나누지 않는다. 같은 `scenario_family_id`는 한 분할에만 배정해 표현 누출로 점수가 부풀려지는 것을 막는다.

일반 Recall·MRR·nDCG와 함께 넓은 질문은 `facet_recall@k`와 `all_required_facets_covered@k`를 측정한다. partial·clarification·unanswerable 문항은 이 평균에서 빼고, 부분 근거 회수율·무관 근거를 정답처럼 제시한 비율·올바른 답변 보류·추가 질문 비율을 각각 별도로 측정한다. 특정 별도 모집단이 0개면 0점이 아니라 `not_applicable`로 기록한다.

## 현재 제한

- 현재 corpus는 에너지 법령·기술기준 9종으로 제한돼 있어 토지, 건축, 농지, 세금, 금융, 지원 공고, 소비자 계약 질문 상당수는 범위 밖일 수 있다.
- 지원금, 요금, 신청기한처럼 변하는 값은 기준일과 당시 공식 자료 없이는 고정 답으로 만들지 않는다.
- broad question은 “관련 조문 하나가 포함됐는가”만으로 정답 처리할 수 없다. 필수 답변 요소 전체에 대한 evidence coverage를 별도로 검토해야 한다.

## 결정 기록

- 2026-08-03: 일반 사용자 질문은행은 기존 v3 정답셋을 대체하지 않는 별도 초안으로 만든다.
- 2026-08-03: `not_annotated` 상태는 최종 평가 방식이 아니라 질문 승인 전 중간 단계로 한정한다.
- 2026-08-03: Recall 계산에는 답변 문장보다 먼저 독립적으로 검증한 qrels가 필요하며, 생성 답변 평가는 reference response까지 주석한 뒤 수행한다.
- 2026-08-03: 넓은 질문의 answerability는 boolean으로 축약하지 않고 full·partial·clarification·unanswerable로 나누며, qrels를 필수 답변 요소와 연결한다.
- 2026-08-03: 질문은행·질문·corpus 해시를 gold에 고정해 질문 또는 근거 변경을 감지한다.
- 2026-08-03: 법령명 목록 해시와 parser corpus fingerprint를 분리한다. 기존 v3 qrels는 parser v3 전환 뒤 고유 ID 1,624개가 모두 현재 corpus에 없어 평가 입력으로 사용할 수 없다.
- 2026-08-03: 미승인 draft, 질문 변경, corpus 변경, qrel ID·본문 변경을 검색 전에 차단하는 읽기 전용 preflight를 도입한다.
- 2026-08-03: 취소된 v2 12문항 전체본은 생성하거나 수정하지 않는다.

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
- 모든 문항은 `evaluation_annotation_status=not_annotated`이다. 이는 평가 정답 라벨인 answerability·qrels·reference answer가 없다는 뜻이며, 질문을 만든 주제·기술·표현 방식 같은 생성 메타데이터가 없다는 뜻은 아니다.
- 사용자 유형·사업 단계·현재 corpus의 답변 가능성을 문항별 라벨로 미리 붙이지 않는다. 주제 수준의 후보 정보만 남긴다.
- 출처 연결도 질문별 근거가 아니라 연구 주제 수준의 영감 출처로만 기록한다.
- 정답, qrels, 기대 법령·조문과 검색 결과를 포함하지 않는다.
- 사용자 질문 승인 전에는 검색·임베딩 평가에 입력하지 않는다.

이 상태로 확인할 수 있는 것은 질문 수, 범위, 자연스러움, 중복, 법률식 표현 혼입 여부다. Recall·MRR·nDCG나 최종 답변 정확도는 평가할 수 없다.

질문은 200개 상황과 상황별 5개 질문 관점으로 구성한다. 처음에는 큰 주제마다 공통 후속문을 붙였지만, 검사 신청·계량기 고장·계약 분쟁처럼 서로 다른 상황에서 의미 충돌이 발견됐다. 이후 상황을 더 작은 호환 묶음으로 나누고, 문항별 사용자 유형·단계·scope 자동 배정을 제거했다. 정적 중복 검사와 별도로 전체 문장 읽기 검토를 수행한다.

## 왜 질문과 정답을 동시에 자동 생성하지 않는가

질문을 만든 직후 현재 검색기의 상위 결과를 정답으로 저장하면 검색기가 자기 결과로 자신을 채점하게 된다. 잘못 검색된 조문이 gold로 굳어지고 Recall이 실제보다 높아질 수 있다. FAQ 페이지의 답도 이 프로젝트가 허용한 법률 corpus의 직접 근거가 아니므로 qrels로 대신 사용할 수 없다.

따라서 질문 확정과 gold 주석을 분리한다. 정답이 없는 편이 평가에 더 좋은 것이 아니라, 잘못된 정답을 조기에 고정하지 않기 위한 임시 단계다.

## gold 평가셋으로 승격하는 절차

여기서 gold는 검색기가 낸 결과와 독립적으로 사람이 공식 원문·버전을 확인해 정답 근거를 확정한 평가 자료다. 검색 정답은 `qrels`, 답변 정답은 `reference_answer`로 역할을 나눈다.

질문이 승인되면 별도 `experiment-d-lay-energy-gold-v1.json`을 만든다. 질문은행 원문은 고정하고 다음 필드를 독립적으로 주석한다.

1. `source_bank`: 질문은행 버전과 전체 질문 SHA-256
2. `corpus_snapshot`: 기준일, corpus fingerprint와 검색 단위
3. `question_review_status`: `approved | revise | reject`와 승인한 질문 SHA-256
4. `split`: 같은 scenario family를 나누지 않는 `calibration | test`
5. `answerability`: `fully_answerable | partially_answerable | clarification_required | unanswerable`
6. `required_answer_facets`: 허가, 부지, 계통연계, 검사처럼 답에 꼭 필요한 요소와 `supported | unsupported | needs_clarification` 상태
7. `qrels`: 각 요소를 직접 뒷받침하는 문서·버전·조문 ID, 경로, 본문 SHA-256, `facet_ids`와 관련성 등급
8. `reference_answer`: qrels의 원문만으로 작성하고 qrel 인용 ID가 고정된 기준 답변
9. `insufficient_reason`: corpus 밖, 기준일 밖, 사실관계 부족 또는 직접 근거 부족
10. `annotation_review`: 작성자·검토자·판정 상태와 불일치 해결 기록

관련성 `2`는 하나 이상의 필수 답변 요소를 직접 뒷받침하는 원문, `1`은 그 직접 근거를 이해하는 데 필요한 문맥이다. 관련성 `0`인 오답 후보는 qrels에 넣지 않고 별도 distractor 목록에 둔다.

다음 불변조건을 적용한다.

- `fully_answerable`: 모든 필수 요소가 supported이고 요소마다 relevance 2 근거가 하나 이상 있다.
- `partially_answerable`: supported와 unsupported 요소가 모두 있다.
- `clarification_required`: 답을 정하려면 부족한 사용자 사실이 무엇인지 명시한다.
- `unanswerable`: qrels가 비어 있고 `insufficient_reason`이 필수다.
- reference answer가 인용한 qrel은 반드시 같은 문항에 속해야 한다.
- 질문 문구가 바뀌면 질문은행 버전과 해시를 바꾸고 다시 승인한다.

검색 결과는 근거 후보를 찾는 보조 수단으로 사용할 수 있지만, 그 결과 자체를 gold로 확정하지 않는다. 전체 corpus 확인, 출처·버전·원문 해시 검증과 사람의 직접 근거 판단을 거친다. 넓은 질문은 하나의 조문이 아니라 필수 답변 요소별 여러 qrels를 가질 수 있다.

## 평가에서 두 자료의 관계

| 자료 | 강점 | 사용하는 평가 |
|---|---|---|
| 기존 실험 D v3 | 원문 기반 정답 라벨과 qrels를 정적으로 생성한 검토 전 초안 | 사용자 승인 뒤 결정적 검색 회귀, 경계·대조군 |
| 일반 사용자 질문은행 초안 | 자연어 범위와 사용자 상황이 넓음 | 질문 품질·범위 검토만 가능 |
| 향후 일반 사용자 gold | 자연스러운 질문과 독립 검증 근거를 함께 보유 | 현실적 Recall·MRR·nDCG와 답변 평가 |

질문 가족별 표현 변형은 나중에 calibration과 test 양쪽으로 나누지 않는다. 같은 `scenario_family_id`는 한 분할에만 배정해 표현 누출로 점수가 부풀려지는 것을 막는다.

일반 Recall·MRR·nDCG와 함께 넓은 질문은 `facet_recall@k`와 `all_required_facets_covered@k`를 측정한다. unanswerable·clarification 문항은 Recall 평균에서 빼고, 무관 근거를 정답처럼 제시한 비율과 올바른 답변 보류·추가 질문 비율을 별도로 측정한다.

## 현재 제한

- 현재 corpus는 에너지 법령·기술기준 9종으로 제한돼 있어 토지, 건축, 농지, 세금, 금융, 지원 공고, 소비자 계약 질문 상당수는 범위 밖일 수 있다.
- 지원금, 요금, 신청기한처럼 변하는 값은 기준일과 당시 공식 자료 없이는 고정 답으로 만들지 않는다.
- broad question은 “관련 조문 하나가 포함됐는가”만으로 정답 처리할 수 없다. 필수 답변 요소 전체에 대한 evidence coverage를 별도로 검토해야 한다.

## 결정 기록

- 2026-08-03: 일반 사용자 질문은행은 기존 v3 정답셋을 대체하지 않는 별도 초안으로 만든다.
- 2026-08-03: `not_annotated` 상태는 최종 평가 방식이 아니라 질문 승인 전 중간 단계로 한정한다.
- 2026-08-03: Recall 계산에는 답변 문장보다 먼저 독립적으로 검증한 qrels가 필요하며, 생성 답변 평가는 reference answer까지 주석한 뒤 수행한다.
- 2026-08-03: 넓은 질문의 answerability는 boolean으로 축약하지 않고 full·partial·clarification·unanswerable로 나누며, qrels를 필수 답변 요소와 연결한다.
- 2026-08-03: 질문은행·질문·corpus 해시를 gold에 고정해 질문 또는 근거 변경을 감지한다.
- 2026-08-03: 취소된 v2 12문항 전체본은 생성하거나 수정하지 않는다.

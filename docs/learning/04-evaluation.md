# 4. 평가와 실험 읽기

## RAG에는 하나의 총점이 없다

좋은 답이 나오기까지 서로 다른 단계가 실패할 수 있다.

```text
원문과 정답표가 정확한가
→ 검색기가 정답 근거를 후보에 넣었는가
→ 직접 근거만 답변 문맥으로 골랐는가
→ 답변이 질문에 맞고 근거를 벗어나지 않았는가
→ 주장별 인용이 실제 원문을 지지하는가
→ 근거가 없을 때 안전하게 거부했는가
```

검색 Recall이 높아도 잡음이 많으면 생성이 흔들릴 수 있다. Faithfulness가 높아도 틀린 문맥에 충실한
답일 수 있다. Answer correctness가 높아도 모델 기억으로 우연히 맞고 인용은 틀릴 수 있다. 따라서
변경한 단계에 맞는 지표와 실패 사례를 함께 본다.

## 평가 데이터의 네 요소

검색 지표를 계산하려면 질문 목록만으로는 부족하다.

| 요소 | 뜻 | 법률 RAG에서 함께 고정할 것 |
|---|---|---|
| corpus | 검색 대상 전체 | 문항 기준일별 eligible count·content fingerprint, 고유 population 집합의 날짜 독립 snapshot ID, 문서·버전·조문 ID |
| query | 평가 질문 | 질문 ID, 문구, 기준일, scenario family, split |
| qrels | 질문별 관련성 정답표 | provision ID, 직접 근거 2·보조 문맥 1, 본문 SHA |
| reference | 기준 문맥과 답변 | 원문 위치, 허용 답변·한계·추가 질문 |

`qrels`는 query relevance judgments의 줄임말이다. 현재 검색 결과를 그대로 qrels로 복사하면 검색기가
낸 답을 같은 검색기의 정답으로 삼는 순환 평가가 된다. 여러 검색 방법과 직접 원문 검토로 후보 pool을
만들 수는 있지만, 관련성 판정은 공식 원문을 사람이 독립적으로 확인해야 한다.

정답 없는 질문은행은 쓸모없지 않다. 말투가 자연스러운지, 범위와 중복이 적절한지 검토하는 자료다.
다만 Recall·Precision·MRR·nDCG를 계산할 gold는 아니다.

## 질문 승인과 gold 승인은 다르다

실험 D의 일반 사용자 질문은행이 실제 평가 입력이 되려면 다음 순서를 거친다.

```text
질문은행 초안
→ 사용자가 문구·범위를 승인
→ 공식 원문에서 후보 수집·전수 판정
→ 독립 검토와 불일치 해결
→ qrels + reference contexts + reference response
→ adjudication manifest가 전체와 문항별 canonical SHA-256 봉인
→ approved gold
```

질문 approval manifest는 승인 후 질문을 몰래 바꾸지 않았다는 증거다. qrels가 정확하다는 승인은 아니다.
gold adjudication은 독립 annotation review 이후여야 하며, 질문 승인·검토·gold 승인 시각도 그 순서를
지켜야 한다.

질문 승인 범위는 질문 ID·문구와 scenario family·intent·technology·질문 변형 같은 질문 범위
메타데이터까지다. corpus snapshot, `as_of_date`, qrels, reference response와 검색 결과는 승인하지 않는다.
그래서 gold의 시간·근거 계약을 바꿔도 승인된 질문 문구와 범위가 같다면 question approval manifest를
다시 만들지 않는다.

넓은 질문은 `required_answer_facets`로 필수 답변 요소를 나눈다. 예를 들어 허가·검사·계통연계 중
허가 근거 하나만 찾았다면 HitRate는 성공할 수 있어도 전체 Recall과 facet coverage는 낮아야 한다.

## 날짜와 content snapshot을 따로 고정하는 이유

평가 질문의 기준일은 검색할 법령 버전을 선택한다. gold는 각 `case.as_of_date`에 유효한 provision만
모은 뒤 그 수와 content fingerprint를 `as_of_populations`에 기록한다. `snapshot_id`는 날짜 문자열이나
NVIDIA embedding profile이 아니라 이 목록에 등장하는 고유한 content population identity 집합에서
계산한다. 여러 날짜의 population이 다르면 그 여러 identity를 함께 봉인하고, population이 같으면 날짜만
다른 중복 identity는 하나로 본다.

```text
8월 3일 eligible ID·검색 콘텐츠 = 8월 4일 eligible ID·검색 콘텐츠
→ content snapshot ID는 같음
→ 날짜와 fingerprint 대응은 gold dataset·adjudication SHA에 각각 남음
```

따라서 날짜 독립 ID는 “언제 질문했는지 무시한다”는 뜻이 아니다. 같은 본문 상태를 여러 달력 날짜 이름으로
중복 식별하지 않는다는 뜻이다. 문항 날짜를 바꾸면 `as_of_populations` 대응과 dataset·adjudication
canonical SHA-256이 달라진다.

미래 시행 버전을 미리 저장하거나 기존 버전의 `effective_to`를 그 미래 시행일로 닫아도 과거 기준일의
유효 ID와 검색 콘텐츠가 같다면 과거 snapshot을 무효화하지 않는다. 새 버전이 실제로 시행되어 유효
population이 바뀌거나 본문·경로 등 검색 콘텐츠가 바뀌면 fingerprint가 달라져 preflight가 실패한다.
qrel source도 현재 corpus에서 문항 기준일에 실제로 유효해야 한다. 기록된 qrel ID와 본문 SHA가 맞아도
그 날짜에 효력이 없으면 정답 근거로 사용할 수 없다.

운영 API의 snapshot은 이 gold 계약과 용도가 다르다. 운영은 한국 날짜의 오늘에 유효한 population 하나로
현재 상태 ID를 계산하고, 지원 시작일은 오늘 이하인 수집·현재 parser·검색 가능 버전의 전역 최소
`effective_from`, 종료일은 한국 날짜의 오늘로 노출한다. gold는 과거를 포함한 문항 기준일별 population을
따로 검증한다. 운영의 오늘 ID를 과거 gold 대신 쓰거나, gold가 있다는 이유로 운영의 법률별 timeline
gap·overlap이 모두 검증됐다고 보지 않는다.

embedding profile은 별도 retrieval contract다. 같은 corpus라도 모델·query/passage 입력·차원·축약·정규화가
다르면 검색 실험은 달라지므로 실행 입력과 결과에 기록한다. 그러나 이를 content snapshot ID에 섞으면
원문은 그대로인데 검색 모델만 바꿔도 corpus가 바뀐 것처럼 보이므로 분리한다. HNSW는 이 프로젝트의
현재와 미래 retrieval contract에서 제외한다.

## 검색 지표를 하나의 예로 이해하기

한 질문의 직접 근거가 A와 B 두 개이고 검색 결과가 `A, X, B, Y, Z`라고 하자.

- `Recall@3 = 2/2 = 1`: 찾아야 할 직접 근거를 top 3에서 모두 찾았다.
- `HitRate@1 = 1`: top 1에 직접 근거가 하나라도 있다.
- `Direct Precision@5 = 2/5`: top 5 중 직접 근거는 두 개다.
- `MRR@10 = 1`: 첫 직접 근거가 1위다.

직접 근거 A가 3위이고 보조 문맥 B가 1위라면 모든 관련 문서를 top 3에서 찾았어도 핵심 근거의 순위는
좋지 않다. `nDCG@K`는 relevance 등급과 뒤 순위 할인으로 이 차이를 반영한다.

```text
DCG@K = Σ (2^relevance_i - 1) / log2(rank_i + 1)
nDCG@K = 실제 DCG@K / 이상적인 순서의 DCG@K
```

현재 실험 D 검색 계약은 다음처럼 읽는다.

- Recall·HitRate·nDCG·facet cutoff: `1, 3, 5, 10`
- MRR: 첫 grade 2 직접 근거의 `@10`
- Precision@5: grade 1 보조 문맥과 grade 2 직접 근거 모두
- Direct Precision@5: grade 2 직접 근거만
- facet recall: 찾은 직접 qrel이 지원한 필수 요소 비율
- all required facets covered: 지원 가능한 필수 요소를 모두 찾았는지

질문마다 직접 근거가 하나뿐이면 Recall과 HitRate가 같아 보인다. 직접 근거가 여러 개인 질문에서는
하나만 찾아도 HitRate는 1이지만 Recall은 1보다 작으므로 둘을 같은 이름으로 기록하지 않는다.

## 검색·문맥·답변 지표를 구분한다

| 단계 | 우선 지표 | 답하는 질문 |
|---|---|---|
| 후보 검색 | Recall@K, HitRate@K, MRR@10, nDCG@K | 직접 근거를 놓치지 않고 앞에 놓았는가? |
| 최종 문맥 | Context/Evidence Recall, Context/Evidence Precision | 답할 정보가 충분하고 잡음이 적은가? |
| 생성 답변 | Faithfulness, Response Relevancy, Answer Correctness | 근거 안에서 질문에 맞는 사실을 말했는가? |
| 인용 | Citation Correctness/Coverage, source integrity | 각 주장의 인용이 실제 원문·버전과 맞는가? |
| 근거 부족 | 오답 생성률, 잘못된 거부율 | 답할 수 없을 때 멈추고, 답할 수 있을 때 과도하게 막지 않는가? |

Context Recall과 Faithfulness 같은 의미 기반 지표는 LLM judge를 쓸 수 있다. judge는 사람처럼 의미를
읽을 수 있지만 모델·프롬프트·샘플링과 호출 실패에 따라 값이 달라진다. judge 모델과 평가기 version,
입력한 문항 기준일별 content population snapshot, 실패·NaN 개수를 기록하고 결정적 ID 기반 지표와 같은 종류의 숫자로 섞지 않는다.

Evidence Recall은 프로덕션의 모든 새 질문마다 실행하는 “정답 확인 단계”가 아니다. Recall은 찾아야 할
정답 근거의 전체 집합을 분모로 써야 하므로, 독립 qrels가 있는 오프라인 평가에서만 계산할 수 있다.
사용자가 처음 묻는 질문은 정답 근거를 찾는 중이므로 그 자리에서 Evidence Recall을 알 수 없다. 실제
제품에서는 넉넉한 후보 검색, 직접 근거 선택, 결정적 인용 gate와 근거 부족 상태로 안전을 관리하고,
그 설계가 잘 작동하는지는 별도의 gold 질문셋에서 Recall·Precision과 오류 사례로 검증한다. 지표 출처와
세부 적용은 [RAG 평가 방법 참고 자료](../references/rag-evaluation-methods-2026-08-03.md)에 있다.

## 실험 D가 production과 다른 이유

production은 사용자 편의를 위해 직접 조문 조회, dense 결과 0건의 keyword fallback과 조 단위 grouping을
사용한다. 실험 D는 현재 embedding의 dense 기준선만 분리해 측정한다.

```text
질문 query embedding
→ 기준일 유효 raw provision 전체와 exact cosine
→ raw score 내림차순, 동점이면 provision ID
→ top 10과 qrels 비교
```

평가 시에는 10개가 아니라 11개를 검색한다. 10위와 11위 raw cosine 점수가 같으면 어떤 문서를 top
10에 넣을지가 tie-break에 좌우되므로 `unresolved_cutoff_tie`로 실행을 실패시킨다. keyword와 article
grouping을 섞지 않아 “근거 찾기”와 다른 효과를 분리한다. HNSW는 현재 실험에서만 뺀 비교 후보가
아니라 미래 실험과 운영에서도 영구 제외한 방식이다.

같은 상황을 다른 말로 표현한 여러 질문은 서로 완전히 독립인 표본이 아니다. 그래서 primary 집계는
질문별 값을 scenario family 안에서 먼저 평균하고 family마다 같은 가중치를 준다. 신뢰구간도 family를
단위로 결정적 bootstrap 2,000회를 수행한다.

retrieval 설정을 조정한 calibration 결과는 diagnostic이고, 조정 중 보지 않은 held-out `test`의
`fully_answerable` 결과가 primary다. partial·clarification·unanswerable은 core 평균에 섞지 않고 별도
모집단으로 보고한다.

## 왜 preflight와 잠금이 필요한가

평가 숫자는 같은 입력과 상태에서 다시 설명할 수 있어야 한다.

1. artifact 계약, 승인 manifest, critical code provenance와 초기 DB 상태를 검사한다.
2. 이 단계가 통과한 뒤에만 외부 비용이 드는 질문 embedding을 만든다.
3. embedding 중 corpus가 바뀔 수 있으므로 별도 read-only transaction에서 corpus mutation shared lock을
   첫 snapshot-taking statement로 획득한다.
4. 잠금 안에서 gold·corpus·vector profile·coverage·norm과 DB planner 상태를 다시 검사한다.
5. 기준일별 대표 exact query의 `EXPLAIN` plan과 SHA-256을 기록한다.
6. 같은 연결과 잠금을 마지막 검색까지 유지한다.
7. 모든 검색과 지표 계산이 성공한 완성 payload만 새 파일로 원자 게시한다.

실패한 실행은 일부 결과를 정상 run JSON으로 남기지 않는다. 성공 결과에는 dataset·code·corpus·vector,
query plan, 실제 순위, embedding batch와 PostgreSQL/pgvector 설정을 역추적할 지문이 포함된다.

## 현재 상태를 오해하지 않기

approved-gold-only runner와 합성 fixture 검증은 구현돼 있다. 일반 사용자 질문은행 1,000개의 문구와
범위는 2026-08-04 승인됐지만, 이 승인은 정답 승인이 아니다. 독립 qrels·reference 주석과 gold
adjudication은 아직 완료하지 않았다. 따라서 실제 1,000문항의 NVIDIA query embedding, DB 검색,
Recall·HitRate·Precision·MRR·nDCG·facet 결과는 아직 실행하거나 기록하지 않았다.

작은 과거 실험의 높은 점수는 해당 질문과 제한 corpus에서 코드 경로를 확인한 역사적 결과다. 현재
1,000문항의 일반 검색 품질로 확대 해석하지 않는다. HNSW 물리 인덱스가 존재했던 기록도 검색 품질
증명이 아니며 현재 실험 D 입력이 아니다.

## 정답 없는 D-10에서 말할 수 있는 것

D-10은 정답 없는 질문 10개를 현재 DB에서 검색하고 raw 후보와 조문 문맥을 사람이 직접 읽는 pilot이다.
실행 전 qrels를 넣지 않으므로 자동 Recall은 계산할 수 없다. Codex가 직접 근거와 경계 판정을 먼저 쓰고
사용자가 10개를 모두 승인·수정한 뒤에야 `수동 확인 직접 근거 hit@K`와 첫 근거 순위 같은 진단값을
계산한다. 이 숫자의 분모는 독립 gold가 아니라 확인된 10문항이므로 정식 Evidence Recall이라고 부르지 않는다.

실제 run ID도 재현 가능한 결과 경로 계약의 일부다. D-10은 UTC 시각과 무작위 suffix를 소문자
`d10-<timestamp>-<suffix>`로 만들고 동일한 경로 안전 정규식으로 검증한다. 생성기와 검증기의 문자 집합이
다르면 DB·embedding 호출 전에 모든 실행이 실패하므로 자동 생성 ID 자체를 경계 테스트로 고정한다. 검토
CLI의 상대 artifact 경로는 `uv --directory`의 작업 디렉터리 변경과 무관하게 저장소 루트를 기준으로
해석하여 검색 실행기가 출력한 `.data/experiments/d-manual/` 경로를 그대로 이어서 사용한다.

과거 실험 C는 저작권법과 과거 전기사업법을 포함한 로컬 205청크의 후보 관찰이었다. D-10은 현재 DB의
검색 준비 완료 corpus와 활성 NVIDIA 512차원 vector를 읽는다. 실행 기록 방식은 참고할 수 있지만 corpus와
질문·판정 계약이 다르므로 C를 D로 바꾸거나 두 결과 수치를 비교하면 안 된다.

D-10의 실제 순서는 `입력 검증 → DB/profile preflight → query cache 조회 → cache miss 한 batch embedding
→ shared lock 안의 snapshot 재검증 → raw top 11/동점 검사 → top 10 조문 계층 복원 → run 원자 게시`다.
그 뒤 run에 결박된 `manual-review.json`을 만들고 Codex 판정과 사용자 확인을 기록한다. `on_hold`가 하나라도
남아 있거나 사용자 수정 override가 불완전하면 `confirmed-diagnostics.json`을 만들지 않는다. query cache는
질문 SHA·profile·snapshot이 모두 같을 때만 재사용하므로 corpus가 바뀐 재실행을 같은 관측으로 오인하지
않는다.

## 직접 확인

외부 credential 없이 gold 계약의 합성 fixture를 검증한다.

```powershell
$env:PYTHONPATH = 'apps/api'
uv run --project apps/api pytest apps/api/tests/test_experiment_d_gold_preflight.py -q
```

실제 runner 실행 전에는 [실험 D 설계](../design-docs/experiment-d-1000-evaluation.md)와
[일반 사용자 질문은행 경계](../design-docs/experiment-d-layperson-question-bank.md)를 읽는다.

## 핵심 확인

1. 정답 없는 질문은행으로 Recall을 계산할 수 없는 이유는 무엇인가?
2. Recall@K와 HitRate@K가 여러 직접 근거에서 어떻게 달라지는가?
3. 실험 D가 production의 keyword fallback과 grouping을 일부러 사용하지 않는 이유는 무엇인가?

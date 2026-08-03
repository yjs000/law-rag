# 실험 D 1,000문항 평가 설계

상태: 데이터셋 v3 검토 초안 생성, 사용자 질문 확인·검색 측정 전
확정일: 2026-08-03

## 선택한 방식

NVIDIA의 검색/답변 분리와 BEIR qrels, LlamaIndex의 labelled RAG dataset을 결합해 법률 corpus에 맞게 조정했다.

- NVIDIA 방식: retrieval과 answer generation을 분리하고 Recall@k·nDCG@k, context recall/precision, faithfulness, answer correctness를 각각 측정한다.
- BEIR 방식: corpus, query, qrels를 분리해 검색기를 같은 정답 집합으로 비교한다.
- LlamaIndex 방식: query와 reference context/reference answer를 가진 라벨 데이터셋으로 RAG 기준선을 반복 비교한다.
- 법률용 보강: 모든 근거를 DB의 document/version/provision ID, path, 원문 SHA-256으로 고정하고 기준일·근거 부족 사례를 포함한다.

공식 자료와 확인 내용은 [RAG 평가 방법 공식 자료](../references/rag-evaluation-methods-2026-08-03.md)에 기록했다.

## 정답을 정하는 방법

정답을 질문에서 추론하지 않는다. 먼저 운영 corpus의 조·항·호·목 하나를 선택하고, 그 원문을 `reference`와 primary qrel로 고정한 뒤 해당 근거를 묻는 질문을 역으로 만든다. primary evidence에는 document/version/provision ID, path와 원문 SHA-256을 저장한다. 조 전체 문맥이 필요한 경우 같은 조의 부모·자식 조각을 relevance 1, 직접 답 조각을 relevance 2로 둔다.

시행일 전·corpus 밖 음성 질문은 `answerable=false`, 빈 qrels, “현재 corpus와 기준일에서는 직접 근거를 찾을 수 없습니다”를 기준 응답으로 가진다. 모델 기억으로 정답을 보완하지 않는다.

## 왜 LLM이 1,000개 정답을 쓰게 하지 않았는가

생성 모델이 자연스러운 질문을 만들 수는 있지만 원문에 없는 법률 요건을 추가하거나 정답 범위를 바꿀 수 있다. 이번 v3 초안은 정답 신뢰성을 우선해 질문을 결정적 템플릿으로 만들고 reference는 원문 그대로 사용했다.

LlamaIndex의 질문과 reference를 가진 labelled dataset 구조는 따르되, 법률 답은 LLM 생성문이 아니라 원문 조각으로 고정했다. 의미 질문은 원문 전체를 의문형으로 복사하지 않고 조 표제와 `허가·신고·의무·금지·허용` 행위 유형을 결합한다. 조 표제가 없는 조각은 의미 질문 후보에서 제외한다.

장점은 재생성해도 같은 문항이 나오고 정답 환각이 없다는 것이다. 한계는 자연스러운 질문인지까지 템플릿만으로 보장할 수 없다는 것이다. 현재 10개 수동 검토와 전체 읽기용 검토본을 제공하며, 후속 human-authored holdout으로 보완한다.

의미 질문은 법령명·조 표제·행위 유형에 행위 주체 역할명(`전기사업자`, `장관`, `공급의무자` 등)을 선택적으로 결합한다. 같은 질문 문자열을 만드는 후보 조각이 둘 이상이면 어느 조각이 정답인지 고정할 수 없으므로 모두 의미 질문 후보에서 제외한다. 현재 corpus에서는 이러한 후보 212개가 제외됐고, 남은 후보에서 200개 의미 질문과 100개 hard contrast를 구성했다.

`다음 각 호` 또는 `다음 각 목`을 여는 조각은 그 문장만으로 목록 내용을 다 담지 못한다. 이 경우 primary evidence와 그 하위 호·목을 `subtree` evidence closure로 묶는다. primary 조각은 relevance 2, 답을 완성하는 하위 조각은 relevance 1이며, `reference`와 `reference_contexts`에도 함께 들어간다. 짧아서 질문 후보가 될 수 없는 호·목도 삭제·구조 표지가 아니라면 근거 문맥에는 포함한다.

## 1,000문항 구성

| 범주 | 수 | 목적 |
|---|---:|---|
| exact path control | 200 | 법률명·조문 번호 직접 조회 기준선 |
| heading lexical control | 200 | 정확한 법률명·표제·조문 표현 대조군 |
| semantic paraphrase | 200 | 조 표제와 의무·허가·신고·금지·허용 유형을 결합한 의미 질문 |
| hierarchy child | 150 | 조→항→호→목 경로 복원과 하위 근거 확인 |
| hard contrast | 100 | 같은 법령 버전에서 본문이 가장 유사한 다른 조문을 distractor로 둔 구분 능력 |
| temporal before effective | 75 | 첫 수록 버전 시행 전 기준일의 근거 부족 |
| outside corpus | 75 | corpus 밖 실제 법률 질문 60개와 존재하지 않는 조문 극단 경계 15개 |

전체 중 850개는 answerable, 150개는 unanswerable이다. 각 범주에서 20%를 calibration으로 배정해 top-k·후속 임계값 후보를 관찰하고, 나머지 800개 test는 결정 후 최종 비교에 사용한다. test 결과를 보고 calibration 규칙을 바꾸지 않는다.

## 경계값·대조·비교군

### 경계값

- `Recall@1/3/5/10`: 후보 수를 늘릴 때 직접 근거가 언제 들어오는지 본다.
- HNSW exact 대조: indexed search가 exact cosine 순위에서 얼마나 근거를 놓치는지 본다.
- 근거 부족: 시행 전 75개, corpus 밖 실제 법률 60개, 존재하지 않는 조문 15개의 false-positive rate를 본다.
- 생성 문맥: 후보 10개와 생성 최대 5개 조문의 Evidence Recall/Precision 변화를 분리한다.

고정 similarity cutoff는 아직 채택하지 않는다. calibration 200개의 positive/negative 점수 분포가 분리되는지 관찰할 뿐이며, 직접 근거 판정을 코사인 점수 하나로 대체하지 않는다.

### 대조군

- exact path/heading 400개: lexical하게 쉬운 양성 대조군
- semantic 200개: 원문 전체를 복사하지 않은 조문 주제·행위 유형 질문
- hard contrast 100개: 정답과 본문 유사도 0.30 이상인 다른 조문 distractor가 있는 어려운 양성군
- negative 150개: 결과가 없어야 하는 안전 대조군

### 향후 검색기 비교

현재 dense-only를 baseline으로 저장한다. BM25를 추가하면 dense와 BM25를 독립 실행해 같은 qrels로 비교한다. RRF는 두 독립 결과가 서로 다른 실패를 보완한다는 증거가 있을 때만 세 번째 구성으로 실험한다.

## 데이터 형식

현재 사용자 검토 대상은 [experiment-d-v3-1000.json](../../apps/api/evaluation/experiment-d-v3-1000.json)이다. `draft` 버전이며 질문 확인 전에는 검색 실험 입력으로 사용하지 않는다. 각 문항은 다음을 가진다.

- `user_input`, `as_of_date`, `answerable`
- 원문 기반 `reference`, `reference_contexts`
- `document_id`, `version_id`, `provision_id`, `path`, `content_sha256`
- 관련 조각과 relevance 등급인 `qrels`
- hard contrast의 `distractor_provision_ids`
- 생성 템플릿, `evidence_scope`와 사람 검토 상태

BEIR 호환 `corpus.jsonl`, `queries.jsonl`, calibration/test qrels는 `.data/experiments/context/beir-v3/`에 로컬 생성한다. 전체 법률 원문 corpus는 실행 산출물이므로 Git에 넣지 않는다.

## 자동 검증과 사람 검토

자동 검사는 다음을 보장한다.

- 정확히 1,000문항
- ID와 질문 중복 없음
- 850 positive / 150 negative
- positive는 qrels와 relevance 2의 primary evidence 보유
- negative는 qrels가 비어 있음
- qrel의 provision ID와 원문 SHA-256 일치
- calibration 200 / test 800과 범주별 고정 수량
- 장·절 구조 표지와 삭제 조문이 양성 reference에 없음
- semantic 질문과 reference의 문자열 유사도 0.80 미만
- hard contrast distractor가 qrel과 겹치지 않고 정답과 본문 유사도 0.30 이상
- outside-corpus가 실제 corpus 밖 법률 60개와 극단 조문 경계 15개로 구성됨
- 같은 의미 질문 문자열이 정확히 하나의 근거 후보만 가리킴
- `다음 각 호·목`을 여는 subtree 근거에 실제 하위 조각이 있으면 qrels와 기준 문맥에 포함됨

표제가 없거나 근거가 매우 짧고 교차참조 중심인 문항은 자동 통과로 숨기지 않는다. 현재 10개를 [사람이 직접 확인할 문항](../generated/experiment-d-v3-review.md)에 질문·기준 답·이유와 함께 분리했다. 범주별 대표 질문과 전체 1,000문항은 [전체 질문 검토본](../generated/experiment-d-v3-question-review.md)에 있다.

v2 정적 감사에서는 장·절 표지가 정답인 7개, 삭제 조문 32개, reference와 문자열 유사도 0.80 이상인 의미 질문 116개를 발견했다. v3 초안에서는 세 항목이 모두 0개다. 운영 corpus는 이후 parser v3로 재수집해 구조 표지와 실제 조문 계층을 분리했고 벡터도 다시 생성했다.

운영 corpus와 벡터는 이후 parser v3로 재구축됐지만 이 파일의 qrels는 재생성하지 않았다. 현재 searchable corpus와 대조한 결과 고유 qrel ID 1,624개 중 1,624개가 모두 누락된다. 따라서 JSON 내부 정적 검사가 통과하더라도 이 draft를 검색 평가에 사용할 수 없으며, 질문 승인 후 현재 parser v3 ID와 직접 근거로 다시 주석해야 한다.

실제 읽기 전용 검사값과 실패 이유는 [실험 D gold 사전검사 보고](../generated/experiment-d-gold-preflight-report.md)에 기록한다.

## 아직 측정하지 않은 것

이 문서는 질문 초안 생성 결과이지 검색 품질 결과가 아니다. 사용자 질문 확인과 corpus 재수집이 끝난 뒤에만 다음을 실제 실행값으로 별도 기록한다.

실행 직전에는 다음 명령이 `approved_gold` 상태, 승인 질문·범위 해시, 현재 corpus fingerprint와 모든 qrel 메타데이터를 통과해야 한다. 이 명령은 임베딩이나 검색을 호출하지 않는다.

`uv run --directory apps/api python -m scripts.preflight_experiment_d_gold --dataset evaluation/experiment-d-lay-energy-gold-v1.json`

현재 명령은 독립적인 읽기 전용 검사다. 아직 1,000문항 평가 runner와 연결되지 않았으므로 그 자체가 검색 실행 전체를 잠그는 원자적 게이트는 아니다. 평가 runner를 구현할 때는 동일 프로세스에서 corpus mutation 공유 잠금을 먼저 얻고, 잠금 안에서 이 검사를 다시 수행한 뒤 마지막 검색까지 잠금을 유지해야 한다. 질문 승인 전에는 runner를 실행하지 않는다.

과거 v3 draft의 stale qrels를 재현해서 확인할 때만 보고서에 적힌 별도 명령처럼 `evaluation/experiment-d-v3-1000.json`을 명시한다. 이 파일은 통과 대상 gold가 아니다.

- Recall@1/3/5/10, MRR, nDCG@3/5/10
- answerable 범주의 Article/Evidence Recall
- unanswerable false-positive rate
- HNSW 대 exact recall과 latency
- 생성 답변의 faithfulness·answer correctness·citation correctness

LLM judge를 쓰는 지표는 모델·프롬프트·실패/NaN 수를 함께 기록하고, ID·원문 기반 결정적 지표와 분리한다.

## 결정 기록

- 2026-08-03: 1,000문항을 850 positive와 150 negative, calibration 200과 test 800으로 고정했다.
- 2026-08-03: 법률 정답은 생성 모델 문장이 아니라 원문 reference와 qrels로 고정했다.
- 2026-08-03: v2 semantic 문항은 법적 의미를 보존하는 제한된 종결 변형으로 만들었으나 근접 복사가 많아 v3에서 대체했다.
- 2026-08-03: v2의 12개 모호 문항은 별도 검토 큐로 공개했고, v3 재생성 후 11개로 갱신했다.
- 2026-08-03: v2 정적 감사 결과를 반영해 구조 표지·삭제 조문을 제외하고, 의미 질문을 조 표제·행위 유형 기반으로 바꾼 v3 검토 초안을 생성했다.
- 2026-08-03: hard distractor는 같은 법령 버전의 다른 조문 중 가장 유사한 본문으로 선택하고 최소 유사도 0.30을 요구한다.
- 2026-08-03: outside-corpus는 corpus 밖 실제 법률 질문 60개와 존재하지 않는 조문 15개로 분리했다.
- 2026-08-03: 의미 질문에 행위 주체 역할명을 추가하고, 동일 질문이 복수 근거 후보를 가리키는 212개 후보는 제외했다.
- 2026-08-03: 목록 도입 조각의 답을 완성하는 짧은 하위 호·목까지 subtree evidence closure와 qrels에 포함했다.

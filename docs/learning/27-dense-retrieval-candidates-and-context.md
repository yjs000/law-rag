# Dense 검색 후보와 답변 문맥은 왜 분리해야 하는가

## 핵심

검색의 목적은 정답일 가능성이 있는 조문을 놓치지 않는 것이고, 문맥 구성의 목적은 그중 답변을 직접
뒷받침하는 근거만 남기는 것이다. 그래서 `top K 검색 후보`와 `답변에 넣을 근거 수`는 같은 값일 필요가
없다.

실험 C에서는 모든 청크와 query embedding의 코사인 유사도를 계산한다. raw 청크를 그대로 보면 같은
조의 항·호가 여러 순위를 차지할 수 있으므로, 같은 조에 속한 청크를 묶고 가장 높은 청크 점수를 그 조의
대표 점수로 쓴다.

```text
raw chunk candidates 최대 10개
-> article root로 그룹화
-> article score = 그 조에 속한 chunk score의 최댓값
-> article candidates 최대 10개
```

최댓값은 조 전체가 정답이라는 증명이 아니다. 어느 한 하위 청크가 질문과 가까워 후보로 관찰할 가치가
있다는 뜻이다. 따라서 실제 본문을 읽고 직접 관련성을 확인해야 한다.

## top 3, top 5, top 10의 실제 차이

2026-07-23 고정 평가의 범위 내 5문항 결과는 다음과 같았다.

- Law@1: `1.0`
- Article Recall@3: `0.8`
- Article Recall@5: `0.8`
- Article Recall@10: `1.0`
- Article MRR: `0.82`

저작권법 목적 질문의 기대 조문 제1조는 10위였다. top 3을 top 5로만 늘려도 찾지 못하고, 후보를 10개
관찰해야 복구됐다. 반면 태양광 질문에서는 신재생에너지법 제2조가 1위였고, 무관한 전기사업법 제2조는
5위였다. 후보 수를 늘리면 recall은 좋아질 수 있지만 무관한 내용도 함께 들어온다.

따라서 당시 실험 C는 후보 10개를 관찰하고, 후속 문맥 실험은 그중 직접 근거만 별도로 고르는 방향을
검토했다. 현재 1,000문항 실험 D의 core runner는 문맥을 1~5개로 고르는 실험이 아니라 raw provision
top 10 검색을 승인 qrels와 비교하는 단계다. `top 10`은 AI에 그대로 넘길 문서 수가 아니다.

## 반복 가능성과 관련성은 다르다

같은 질문을 여러 번 실행해 순위와 점수가 같다는 것은 provider와 계산 경로가 재현 가능하다는 뜻이다.
그 결과가 법적으로 관련 있다는 뜻은 아니다. 검색 품질은 기대 법률·조문을 가진 고정 질문으로 Law@1,
Recall@K, MRR을 측정하고 실제 본문을 확인해야 한다.

실험 C는 성공한 `ask`의 실제 stdout, 실행 시각, corpus SHA-256, stdout SHA-256을 로컬 JSON과 Markdown에
자동 기록한다. 이 기록으로 다음을 구분할 수 있다.

- 같은 corpus와 질문에서 결과가 반복되는가
- corpus나 모델이 바뀌었는가
- 순위는 안정적이지만 관련성이 낮은가

## 다음 개선 순서

1. 승인 gold에서 dense-only 기준선을 고정한다.
2. 같은 gold로 BM25 같은 lexical 검색기를 dense와 독립 비교한다.
3. 두 독립 검색기가 서로 다른 실패를 실제로 보완할 때만 결합 실험을 추가한다.
4. 검색 후보 평가와 직접 근거·답변 문맥 선택을 분리한다.
5. 근거 부족이면 답변 생성을 중단한다.

키워드를 보고 특정 법률을 직접 지정하는 규칙은 평가 질문을 외운 구현이 되기 쉽다. 현재 구현은
dense-only이며 결과가 0건일 때만 keyword fallback을 독립 실행한다. BM25·hybrid·RRF는 채택하지 않았다.
향후에는 lexical 순위와 dense 순위를 각각 같은 qrels에서 먼저 비교하고, 결합이 실제로 개선된다는
증거가 있을 때만 RRF를 세 번째 실험으로 검토한다.

## 직접 확인

```powershell
uv run --directory apps/api python -m scripts.experiment_search ask `
  --question "태양광 발전에 사용하는 태양에너지는 신에너지와 재생에너지 중 어디에 해당하나요?"

uv run --directory apps/api python -m scripts.experiment_search evaluate
```

실행과 산출물은 [실험 C 안내](../../experiments/search/README.md), 실제 기준선은
[평가 문서](../generated/experiment-c-retrieval-evaluation.md), 다음 문맥 단계는
[실험 D 안내](../../experiments/context/README.md)를 참고한다.

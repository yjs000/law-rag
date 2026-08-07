# 실험 D-10 Gold review draft 요약

생성 명령:

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_gold_review build-draft --export .data/experiments/d-gold-10/d10-gold-20260807t040448957688z --proposal experiments/d_gold_10/experiment-d-10-gold-annotation-proposal-v1.json
```

기준 시점: 2026-08-05

생성일: 2026-08-07

상태: `pending_user_review` · `sealed=false`

## 결과

- 질문: 10개
- corpus: 3,066 provision
- 전체 판정: 30,660개
- relevance 2: 35개
- relevance 1: 3개
- relevance 0: 30,622개
- 사용자 승인 대기: 10개
- DB 접근: `REPEATABLE READ, READ ONLY`
- query/passsage embedding·검색·모델 호출: 0회
- candidate set SHA-256: `74b9520a87cba41a0e54bb61326671b40c59471964dc7be2a2674cc4cfdd6d84`
- annotation draft SHA-256: `6b465ed031d3a9ea7f524d6ec8acc0c24a3fc94c17810c3a937df57e2996b253`
- judgments JSONL SHA-256: `f549782c3bfbbd293269c4bfa20c24bc29d769d24b6251cc9ef93bc4acf80929`
- adjudication draft SHA-256: `28f65cf1e01164716c1a5fa3f2896c6567fc0da6732f3d05224153b54434350f`

| 질문 | 제안 answerability | rel 2 | rel 1 | rel 0 |
| --- | --- | ---: | ---: | ---: |
| lay-energy-0201 | partially_answerable | 8 | 0 | 3,058 |
| lay-energy-0251 | clarification_required | 7 | 0 | 3,059 |
| lay-energy-0521 | partially_answerable | 6 | 0 | 3,060 |
| lay-energy-0601 | partially_answerable | 2 | 0 | 3,064 |
| lay-energy-0111 | clarification_required | 5 | 0 | 3,061 |
| lay-energy-0346 | partially_answerable | 1 | 2 | 3,063 |
| lay-energy-0561 | partially_answerable | 6 | 1 | 3,059 |
| lay-energy-0605 | unanswerable | 0 | 0 | 3,066 |
| lay-energy-0836 | unanswerable | 0 | 0 | 3,066 |
| lay-energy-0943 | unanswerable | 0 | 0 | 3,066 |

이 문서는 결과 요약이며 Gold 승인이 아니다. 실제 원문·qrel·기준 응답과 사용자 입력은
`.data/experiments/d-gold-10/d10-gold-20260807t040448957688z/review/`에 있다. 모든 문항이 사용자
adjudication을 통과하기 전에는 `approved_gold`, Evidence Recall 또는 release gate를 계산하지 않는다.

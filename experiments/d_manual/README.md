# 실험 D-10 고정 입력

이 디렉터리는 승인된 1,000문항에서 선택한 D-10 질문 identity만 보관한다. 질문 원문은 기존 권위
질문은행에서 읽으며 이 입력에는 답변, 기대 법률·조문, qrel 또는 검색 후보를 넣지 않는다.

- 입력: `experiment-d-10-questions.json`
- 질문은행: `apps/api/evaluation/experiment-d-lay-energy-query-bank-v1-draft.json`
- 질문 승인: `apps/api/evaluation/experiment-d-lay-energy-question-approval-v1.json`
- 실제 run: Git에서 제외되는 `.data/experiments/d-manual/`

입력 검증만 실행하려면 다음 명령을 사용한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_manual_review validate-input
```

실험 C의 로컬 corpus를 준비하거나 읽지 않는다. 실제 D-10 검색 명령은 runner 구현 문서에 추가한다.

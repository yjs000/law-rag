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

실제 검색은 사용자가 후속으로 다음 명령을 실행한다. `DIRECT_URL`과 `NVIDIA_API_KEY`가 필요하며 DB write,
Open API 수집과 passage embedding은 수행하지 않는다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_manual_review run
```

성공 stdout은 run ID와 JSON·Markdown 경로, corpus snapshot, profile, query cache hit/miss를 출력한다.
실험 C의 로컬 corpus를 준비하거나 읽지 않는다.

run 뒤 Codex가 검토할 JSON template은 다음처럼 만든다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_manual_review_results create-review `
  --result .data/experiments/d-manual/runs/<run-id>/result.json
```

Codex 1차 판정과 사용자 승인·수정이 10/10 끝난 뒤 `manual-review.json`의 상태를 `confirmed`로 바꾸고
다음 명령을 실행한다. 하나라도 `on_hold`이거나 판정이 비어 있으면 출력 파일을 만들지 않는다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_manual_review_results finalize `
  --result .data/experiments/d-manual/runs/<run-id>/result.json `
  --review .data/experiments/d-manual/runs/<run-id>/manual-review.json
```

생성되는 `confirmed-diagnostics.json`은 D-10 수동 진단이며 정식 Evidence Recall이나 gold가 아니다.

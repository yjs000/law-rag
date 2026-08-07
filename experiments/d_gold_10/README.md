# D-10 Gold 사용자 검토 workflow

이 디렉터리는 D-10 10문항만 현재 3,066개 provision 전체와 대조하는 annotation·adjudication 계약을
보관한다. 1,000문항 D-full과 기존 D-10 top-10 진단 artifact를 변경하지 않는다.

## 명령

무호출 계약 검사:

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_gold_review preflight-contract
```

현재 DB corpus 읽기 전용 export:

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_gold_review export-corpus
```

qrel·adjudication draft 생성:

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_gold_review build-draft `
  --export .data/experiments/d-gold-10/<draft-id> `
  --proposal experiments/d_gold_10/experiment-d-10-gold-annotation-proposal-v1.json
```

사용자 검토 전후 preflight:

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_gold_review preflight-draft `
  --review .data/experiments/d-gold-10/<draft-id>/review
```

현재 검토 대상은 `d10-gold-20260807t040448957688z`다. 자세한 판정·수정·seal 절차는
[설계 문서](../../docs/design-docs/experiment-d-10-gold-adjudication.md)를 따른다.

법률 원문, 30,660개 judgment와 사용자 입력은 `.data/`에 두며 Git에 커밋하지 않는다. 사용자 승인 전
상태는 `pending_user_review`이고 정식 Gold 지표를 계산하지 않는다.

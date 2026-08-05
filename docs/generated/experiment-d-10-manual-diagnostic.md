# 실험 D-10 사용자 확인 수동 진단

> 생성 근거 명령: `uv run --directory apps/api python -m scripts.experiment_d_manual_review_results finalize --result .data/experiments/d-manual/runs/d10-20260805t065001773007z-442bef4a327b/result.json --review .data/experiments/d-manual/runs/d10-20260805t065001773007z-442bef4a327b/manual-review.json`
>
> 기준 시점: 2026-08-05 · 사용자 10/10 승인 · 정식 Evidence Recall 또는 gold가 아닌 수동 진단

## 실행 결박

- run: `d10-20260805t065001773007z-442bef4a327b`
- corpus: `corpus-sha256:605b1f53b4fbe3edff19000796e56d906415e7648e7e6ae6119a46f5fc8d9578`
- embedding profile: `nvidia-nemotron-3-embed-1b-512-v1`
- 질문 입력 SHA-256: `0bb1e6a01c3a7b7f592cd4df907450afa5ad172d8a6dd7dcc7c79c9937bc9e1c`
- result file SHA-256: `8beb359333ee94ddf614693b4735688dbc213d96bd4207753e6341ea945a74e6`
- review file SHA-256: `f3e3f72e44215c626512994f59514f394d46c9d7c5875331ee1766f520d4fa96`
- confirmed diagnostics SHA-256: `def38f046c16ef9f018d7e1ffed1ad252714bf07040d7512e1df58e6704e5d0a`

원본 result, review와 confirmed diagnostics는 Git에서 제외되는 `.data/experiments/d-manual/runs/`에
보존한다. 이 문서는 확정 artifact의 간단한 projection이며 원문 후보를 복제하지 않는다.

## 확정 진단값

| 진단 | 결과 |
|---|---:|
| 수동 직접 근거 hit@1 | 6/10 (0.6) |
| 수동 직접 근거 hit@3 | 6/10 (0.6) |
| 수동 직접 근거 hit@5 | 6/10 (0.6) |
| 수동 직접 근거 hit@10 | 7/10 (0.7) |
| top 5 무관 후보 | 28개 |
| 문맥 충분 | 1개 |
| 문맥 부족 | 6개 |
| 문맥 차단 | 3개 |
| Codex·사용자 최종 판정 일치 | 10/10 |
| 추가 질문·corpus 부족 경계 구분 일치 | 5/5 |

문항별 첫 직접 근거 순위는 여섯 문항이 1위, `lay-energy-0346`이 8위, 세 문항은 현재 corpus에 직접
근거가 없었다. 특히 `lay-energy-0346`은 raw top 5가 모두 무관했지만 직접 근거가 8위에 있어 상위 후보
순도와 뒤 순위 할인을 별도로 개선할 필요가 확인됐다.

## 다음 결정

원본 D-10을 덮어쓰지 않고 저장된 동일 top 10을 입력으로 부모 조문 표제와 일반 직접성 규칙을 적용한
무호출 로컬 재정렬 진단을 별도 artifact로 실행한다. 목표에 맞추기 위한 문항별 정답 규칙은 넣지 않으며,
`lay-energy-0346`의 직접 근거가 top 3에 드는지와 사용자 확인 top 5 무관 후보 수가 감소하는지를 비교한다.

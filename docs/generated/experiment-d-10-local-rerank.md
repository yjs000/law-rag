# 실험 D-10-R1 부모 표제·직접성 로컬 재정렬 결과

> 생성 명령: `uv run --directory apps/api python -m scripts.experiment_d_local_rerank --result .data/experiments/d-manual/runs/d10-20260805t065001773007z-442bef4a327b/result.json`
>
> 기준 시점: 2026-08-05 · 외부 호출 0회 · 같은 10문항 calibration 진단

## 입력 결박

- D-10 run: `d10-20260805t065001773007z-442bef4a327b`
- scoring profile: `d10-parent-heading-directness-v1`
- profile SHA-256: `a7f59257e9ce7baf3bc91341e9928a1b17c7b39e428573e37b0385e8ba57cf38`
- comparison JSON SHA-256: `80b4493b40fc42c778373f94b981e86b47f14f951760db40d6db8d8b8eaccf76`
- comparison payload SHA-256: `2f77b77c8fe012fa31e6ead9b908e58f2a6290ad3a9e329a1fd58f2bd06c361b`

원본 raw candidate ID·cosine·rank와 10×10 후보 집합은 모두 보존됐다. 점수 계산은 질문, 법령명, 복원된
부모 조문 표제, raw provision 본문과 문항 내부 raw cosine 위치만 사용했다. 사용자 확인 direct/irrelevant
라벨은 재정렬 뒤 비교에만 사용했다.

## 결과

| 값 | raw dense | 로컬 재정렬 |
|---|---:|---:|
| 수동 직접 근거 hit@1 | 6/10 | 6/10 |
| 수동 직접 근거 hit@3 | 6/10 | 7/10 |
| 수동 직접 근거 hit@5 | 6/10 | 7/10 |
| 수동 직접 근거 hit@10 | 7/10 | 7/10 |
| confirmed known irrelevant@5 | 28 | 18 |

`lay-energy-0346`의 유일한 직접 근거는 raw 8위에서 rerank 2위로 이동해 top 3 목표를 통과했다. 이
문항의 기존 top 5는 모두 사용자 확인 무관 후보였고, 재정렬 뒤 직접 근거가 들어오면서 확정 무관 후보가
5개에서 4개로 감소했다. 새 top 5가 모두 기존 top 5 또는 확정 직접 근거이므로 이 문항에는 새 미판정
후보가 없다.

## 해석 한계

전체 `28 → 18`은 원래 확인된 무관 ID가 새 top 5에 남은 수다. 원래 6~10위였던 후보 9개가 여러 문항의
새 top 5에 들어왔지만 D-10 검토 계약상 이들은 전수 무관 판정을 받지 않았다. 따라서 실제 전체 무관
후보가 10개 줄었다고 해석하지 않는다.

이 profile은 같은 10문항을 보며 설계한 calibration 규칙이다. `0346` 개선은 재현됐지만 운영 채택이나
일반 성능 개선의 증거는 아니다. 질문 ID별 예외 없이 동작하더라도 별도 held-out gold에서 direct
Precision@5, MRR과 nDCG를 검증하기 전에는 운영 검색 순서를 바꾸지 않는다.

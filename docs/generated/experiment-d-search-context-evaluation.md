# 실험 D — 검색 문맥 안전 게이트 평가

> 생성 명령: `uv run --directory apps/api python -m scripts.experiment_context build --run <20..25>`
> 기준 시점: `2026-08-03T04:55:00Z`
> corpus SHA-256: `86fbfe0af0df4c308d46a910e2ba8ff3f102c3c8534c41f9777758b75054f3da`
> 입력 검색 실행: `20`~`25`

이 문서는 로컬 `.data/experiments/context/context-runs.json`에 기록된 실제 실행 6개의 요약이다. 질문과
근거 본문을 포함한 stdout 전체는 Git에 넣지 않고 로컬 실행 기록에 보존한다.

## 결과

| D 실행 | C 실행 | 근거 계약 | 상태 | 이유 | 기대 조문 rank | 근거 묶음 | stdout SHA-256 |
|---:|---:|---|---|---|---:|---:|---|
| 1 | 20 | solar-is-renewable-energy | ready | - | 1 | 1 | `9feb4a295a42ad456065a142bbf6bbf07f520dd397c0e6a891fb9b67237639af` |
| 2 | 21 | electricity-commission-functions | ready | - | 1 | 1 | `acb3f66bd59f78a4f752d335faacc062c4d22b45f849dd01875546aa459f8705` |
| 3 | 22 | audiovisual-rights-transfer-presumption | ready | - | 1 | 1 | `5863f4af2563ac2d6685fa299fee828853e37340d6cdc030d11ea3ddc45bfbe8` |
| 4 | 23 | renewable-basic-plan-cycle | ready | - | 1 | 1 | `f19ef200812ef0644e34367e9caae3e3fbd288459fc963c7bd94fd9f8212fdf1` |
| 5 | 24 | copyright-act-purpose | ready | - | 1 | 1 | `a7fc271f0de32d89b4a8fa98c4bd8307c07dc6574e53eae731ce58eb64b41465` |
| 6 | 25 | electricity-business-license-out-of-scope | insufficient_evidence | governing_provision_outside_corpus | - | 0 | `1b160eeb063a10f7d84d95677dba00a37d4f0dba2e3ccab459caa5d4349ced9b` |

## 판정

- 범위 내 성공률: `5/5`
- 범위 내 기대 조문 rank 1: `5/5`
- 범위 밖 안전 차단: `1/1`
- 범위 밖 질문에 잘못 전달된 근거 묶음: `0`

전기사업법 제7조는 현재 실험 corpus에 없다. dense 검색이 제2조의 “허가받은 자” 같은 관련 문장을
찾더라도 D는 이를 허가권자의 직접 근거로 사용하지 않고 답변 생성을 차단했다.

## 한계

현재 직접 근거 판정은 고정 평가 질문의 `required_evidence_terms` 계약을 사용한다. 임의 자연어 질문의
근거 충분성을 의미적으로 판정하는 범용 시스템은 아니며, 그 단계는 후속 reranker 또는 답변 검증
실험에서 별도로 평가해야 한다.

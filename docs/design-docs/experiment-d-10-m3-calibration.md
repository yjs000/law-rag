# 실험 D-10 M2 동결과 M3 소표본 calibration

상태: M2 계약·preflight 완료, M3 실행 전

결정일: 2026-08-07

## 결정

승인된 1,000문항 전체를 지금 Gold로 승격하지 않는다. 질문은행과 승인 manifest, D-full Gold schema와
runner는 삭제하지 않고 보존하며, 정식 회귀 범위나 일반화 근거가 실제로 필요할 때 대상 질문을 다시
원문 검토한 뒤 answerability·qrels·reference answer를 붙인다.

현재는 사용자 확인이 끝난 D-10의 10문항만 다음 단계에 사용한다. 이 자료는 독립 주석·corpus 전수 qrels·
held-out split이 없으므로 `full gold`, `Evidence Recall`, `held-out 성능`, `운영 release gate`로 부르지 않는다.

## M2 — 10문항 계약 동결

동결 파일은 `experiments/d_manual/experiment-d-10-m3-frozen-contract.json`이다. 다음 항목을 고정한다.

- 질문 ID·질문 SHA·범위 SHA 10개와 원래 질문 승인 manifest
- 2026-08-05 D-10 run, 3,066 provision corpus snapshot과 NVIDIA 512차원 profile
- 사용자 확정 answerability와 문맥 판정
- 원래 raw top 10 안에서 확인한 직접 근거 provision ID
- 원래 raw top 5에서 확인한 무관 provision ID
- 원본 result·review·diagnostics와 R1 comparison 파일 SHA-256
- 허용 진단값과 금지할 일반화 주장

질문 원문, 정답 문장과 법률 원문 전문은 동결 manifest에 복제하지 않는다. 원본 검색 산출물은 Git에서
제외된 `.data/experiments/d-manual/`에 보존하고 manifest는 경로와 SHA만 결박한다.

다음 preflight는 파일을 쓰거나 DB·NVIDIA를 호출하지 않는다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_frozen_contract preflight
```

preflight는 질문 identity, contract payload SHA, 다섯 artifact SHA, run·snapshot·profile, 사용자 확정
판정과 raw 후보 내 라벨 범위를 검사한다. 하나라도 바뀌거나 로컬 원본 artifact가 없으면 M3를 시작하지
않는다.

## M3 — 진행 방법

M3의 이름은 `D-10-M3 calibration`이다. 새 검색 성능 실험이 아니라 저장된 동일 10문항 결과로 현재
기준선과 로컬 재정렬의 효과·결함을 정리하는 소표본 분석이다.

1. 위 M2 preflight를 먼저 통과한다.
2. 원본 D-10 raw top 10과 cosine 순서를 baseline으로 읽는다. 새 query embedding과 DB 검색을 하지 않는다.
3. 사용자 확정 직접 근거 라벨로 다음 값만 계산한다.
   - manual direct-evidence hit@1/3/5/10
   - 첫 직접 근거 순위와 manual reciprocal rank@10
   - 확인된 무관 top 5 수
   - `sufficient | insufficient | blocked` 문맥 수
4. 같은 후보 집합의 R1 순서를 비교한다. `0346`의 8위→2위, hit@3/5 변화와 순위 하락 사례를 모두 본다.
5. R1로 새 top 5에 들어온 원래 6~10위 후보는 미판정일 수 있다. 실제 무관 top 5 감소나
   direct Precision@5를 주장하기 전에 해당 후보를 Codex가 원문 검토하고 사용자가 최종 확인한다.
6. 질문별로 baseline 유지, R1 사용 후보, 라우팅 우선, 추가 문맥 필요 중 하나를 기록한다.
7. 결과는 새 원자 JSON과 `docs/generated/` 요약에 기록하되 기존 D-10/R1 artifact를 덮어쓰지 않는다.

M3에서 HNSW, hybrid, RRF, 모델 reranker, similarity cutoff, passage 재임베딩과 답변 생성은 하지 않는다.

## 판정과 다음 단계

M3 완료는 10문항 안에서 직접 근거 순위와 알려진 잡음의 변화를 설명하고, 새 top 5 후보의 사용자 확인이
끝난 상태다. 표본이 작고 같은 문항으로 R1을 설계했으므로 운영 검색 순서를 자동 변경하지 않는다.

M3 다음에는 동일 10문항으로 M4 문맥 조립을 비교한다. 이후 0028 검색 전 라우팅을 구현하고, 그 결과가
부족한 법령 질문에만 query 보강을 검토한다. NVIDIA 답변 생성은 이 문맥·라우팅 계약 뒤에 시작한다.

## D-full을 다시 여는 조건

다음 중 하나가 실제로 필요할 때만 예정 작업 0029를 active로 승격한다.

- 10문항 밖으로 검색·재정렬 품질을 일반화해야 함
- 운영 release gate나 회귀 임계값에 통계적 근거가 필요함
- 새로운 질문 유형·법령·corpus 변경의 영향을 자동 평가해야 함
- 10문항에서 비교한 두 방법의 차이가 작거나 상충해 결정을 내릴 수 없음

이때는 1,000문항에 기존 판정을 복사하지 않는다. 현재 corpus와 기준일을 다시 검사하고 필요한 문항에만
독립 answerability·qrels·reference를 작성한 뒤 새 manifest로 봉인한다.

## 결정 기록

- 2026-08-07: 비용과 현재 의사결정에 필요한 증거 범위를 줄이기 위해 1,000문항 Gold를 필수 선행조건에서
  제거했다. D-10 10문항의 사용자 확정 top-10 라벨만 M3 calibration에 사용하며, 정식 Gold와 일반화
  성능 주장은 금지한다.

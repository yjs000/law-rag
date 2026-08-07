# 실험 D-10 수동 검색·문맥 진단

## 목적

D-10은 승인된 일반 사용자 질문 1,000개 중 정답을 미리 붙이지 않은 10개를 현재 PostgreSQL의 확정
에너지 법령 corpus에서 검색하는 저비용 진단 실험이다. 검색 후보가 질문에 직접 답하는 법률 근거인지,
그 후보를 조 단위로 복원했을 때 향후 AI 답변에 제공할 문맥으로 충분한지를 사람이 확인한다.

이 실험은 AI 답변을 생성하거나 답변 품질을 평가하지 않는다. 검색 결과와 문맥 품질을 먼저 확정한 뒤에만
후속 답변 생성 구현을 시작하기 위한 선행 gate다.

## 다른 실험과의 경계

- 실험 C는 저작권법과 과거 전기사업법을 포함한 로컬 205청크의 역사적 후보 관찰 실험이다. D-10으로
  이름을 바꾸거나 현재 결과와 수치를 비교하지 않는다.
- D-10은 정답 없이 시작해 사용자 확인을 마친 10문항 수동 진단이다. 2026-08-07부터 이 10문항의
  top-10 한정 판정만 M3 calibration 계약으로 동결하며 정식 Evidence Recall로 부르지 않는다.
- D-full은 독립 qrels·reference·adjudication을 갖춘 기존 1,000문항 정식 평가 설계다. 질문은행, 승인
  manifest와 Gold 계약은 보존하되 일반화·운영 회귀가 실제로 필요할 때만 다시 검사해 Gold를 작성한다.
- 실험 A·B는 corpus 검색 실험이 아니므로 기존 기록을 그대로 유지한다.

## 고정 입력과 결과 위치

이 디렉터리는 선택한 D-10 질문 identity만 보관한다. 질문 원문은 기존 권위 질문은행에서 읽으며 입력에는
답변, 기대 법률·조문, qrel 또는 검색 후보를 넣지 않는다.

- 입력: `experiment-d-10-questions.json`
- 질문은행: `apps/api/evaluation/experiment-d-lay-energy-query-bank-v1-draft.json`
- 질문 승인: `apps/api/evaluation/experiment-d-lay-energy-question-approval-v1.json`
- 실제 run: Git에서 제외되는 `.data/experiments/d-manual/`

## 자동으로 검증하는 사항

실행기는 다음 조건을 모두 통과해야 검색 결과를 게시한다.

1. 정확히 10개의 질문 ID·질문 SHA·범위 SHA가 승인 manifest와 일치한다.
2. 현재 DB가 검색 준비 상태이고 활성 embedding profile이 NVIDIA 512차원 계약과 일치한다.
3. 검색 가능한 provision과 활성 passage vector가 전부 대응하고 vector가 L2 정규화돼 있다.
4. DB 점검과 검색은 읽기 전용 transaction에서 수행되고 corpus mutation shared lock 안에서 상태를 다시
   확인한다.
5. 초기 점검과 실제 검색 사이에 corpus snapshot이나 vector profile이 바뀌면 전체 실행을 실패시킨다.
6. 같은 질문 SHA·profile·snapshot의 query vector만 cache에서 재사용한다. cache miss는 최대 10개를
   NVIDIA query embedding 한 batch로 요청한다.
7. 질문마다 exhaustive exact cosine으로 raw 후보 11개를 조회하고 10위와 11위 점수가 같으면 실행을
   실패시킨다.
8. raw top 10 원문과 점수를 기록하고 같은 조의 부모 조문·항·호·목을 원문 순서로 복원한다.
9. 10문항이 모두 성공한 경우에만 JSON과 Markdown을 새 run 디렉터리에 원자 게시하며 기존 run을
   덮어쓰지 않는다.
10. 결과에는 질문·corpus snapshot·embedding profile·query cache hit/miss·raw 점수·조문 문맥·코드와
    입력 해시·실제 stdout SHA-256을 남긴다.

실행 중 DB write, Open API 수집, 로컬 corpus 생성, passage embedding, answer 생성, HNSW, hybrid, RRF,
reranker는 수행하지 않는다.

## 실행 순서

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

검토 CLI의 상대경로는 `uv --directory apps/api`가 바꾸는 process working directory가 아니라 저장소 루트를
기준으로 해석한다. 따라서 위 `.data/...` 경로를 저장소 루트 PowerShell에서 그대로 사용한다.

Codex 1차 판정과 사용자 승인·수정이 10/10 끝난 뒤 `manual-review.json`의 상태를 `confirmed`로 바꾸고
다음 명령을 실행한다. 하나라도 `on_hold`이거나 판정이 비어 있으면 출력 파일을 만들지 않는다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_manual_review_results finalize `
  --result .data/experiments/d-manual/runs/<run-id>/result.json `
  --review .data/experiments/d-manual/runs/<run-id>/manual-review.json
```

생성되는 `confirmed-diagnostics.json`은 D-10 수동 진단이며 정식 Evidence Recall이나 gold가 아니다.

확정된 동일 top 10에 부모 표제·직접성 로컬 재정렬을 별도 적용하려면 다음 명령을 사용한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_local_rerank `
  --result .data/experiments/d-manual/runs/<run-id>/result.json
```

기본 출력은 원본을 덮어쓰지 않는 `runs/<run-id>/rerank/d10-parent-heading-directness-v1/`이다. DB,
embedding, 외부 API와 모델 reranker를 호출하지 않는다. 같은 10문항 calibration 결과이므로 운영 채택
근거가 아니며, 새 top 5에 진입한 과거 6~10위 후보는 별도 판정 전까지 관련 후보로 간주하지 않는다.

사용자 확인 10문항과 원본 run·R1을 M3 입력으로 사용하기 전에는 다음 무호출 preflight를 실행한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_frozen_contract preflight
```

이 명령은 `experiment-d-10-m3-frozen-contract.json`의 payload와 질문·result·review·diagnostics·R1
artifact SHA, corpus snapshot, embedding profile과 판정 범위를 검증한다. `.data` 원본이 없거나 하나라도
달라지면 실패하며 파일을 생성하거나 DB·NVIDIA를 호출하지 않는다.

## Codex·AI의 1차 확인사항

Codex는 자동 출력된 실제 원문만 읽고 문항마다 다음 항목을 작성한다. 모델 기억으로 법률 조항이나 정답을
보완하지 않으며, 이 단계에서 사용자에게 보여 줄 최종 법률 답변을 생성하지 않는다.

- 질문에 직접 답하는 raw provision ID와 순위
- 판정:
  `directly_answerable | partially_answerable | clarification_required | not_answerable_from_current_corpus`
- 후보 원문에서 확인되는 답변 요소
- 사용자 사실, 계약, 현장 자료, 실시간 정보 또는 corpus 범위 때문에 확인할 수 없는 요소
- 조문 단위 복원 문맥 판정: `sufficient | insufficient | blocked`
- raw top 5 중 질문과 무관한 후보
- 판정 이유와 사용자가 특히 다시 확인해야 할 경계

`clarification_required`는 현재 법령 근거가 없다는 뜻이 아니라 답변 전에 사용자 사실이 더 필요하다는
뜻이다. `not_answerable_from_current_corpus`는 질문에 필요한 실시간 상태·가격·예산·계약·지방 규정 또는
다른 출처가 현재 corpus에 없다는 뜻이다. Codex는 이 둘을 분리해 판단한다.

## 사용자의 최종 확인사항

사용자는 Codex의 1차 판정을 참고해 각 문항을 다음 기준으로 확인한다.

- 선택된 직접 근거가 실제로 질문에 답하는 조문인지
- 직접 답 가능·부분 답 가능·추가 질문 필요·현재 corpus로 답변 불가 판정이 맞는지
- 근거가 있는 답변 요소와 없는 요소가 정확히 분리됐는지
- 복원된 조문 문맥을 AI에 보내도 충분한지, 부족하거나 생성이 차단돼야 하는지
- top 5 무관 후보 표시가 맞는지
- Codex 판정을 그대로 승인할지, 수정할지, 보류할지

문항별 사용자 상태는 다음과 같다.

- `approved`: Codex 판정을 그대로 확정
- `modified`: 사용자가 직접 근거·판정·이유·문맥 상태를 override해 확정
- `on_hold`: 추가 확인이 필요하며 D-10 완료 판정에서 제외

10문항 중 하나라도 `on_hold`이거나 Codex 판정·사용자 수정값이 비어 있으면 진단 집계를 생성하지 않는다.

## 사용자 확인 뒤 계산하는 진단값

10문항이 모두 승인 또는 수정된 경우에만 다음 값을 계산한다.

- 수동 확인 직접 근거 hit@1/3/5/10
- 문항별 첫 직접 근거 순위
- 문항별·전체 top 5 무관 후보 수
- 문맥 `sufficient | insufficient | blocked` 건수
- Codex 판정과 사용자 최종 판정 일치 건수
- Codex가 추가 질문 필요와 현재 corpus 근거 부족을 최종 판정과 같게 구분한 건수

이 값의 모집단은 사용자 확인을 마친 10문항뿐이다. 검색기의 일반 성능, 정식 Gold 지표 또는 D-full의
Evidence Recall로 확대 해석하지 않는다.

## D-10 완료 조건과 다음 단계

D-10은 코드 구현이나 검색 실행만으로 완료되지 않는다. 다음 조건을 모두 만족해야 완료로 판정한다.

1. 실제 DB/NVIDIA query embedding 검색 run이 성공한다.
2. raw top 10과 복원 조문 문맥이 10문항 모두 기록된다.
3. Codex가 10문항의 1차 검토를 작성한다.
4. 사용자가 10문항을 모두 승인 또는 수정한다.
5. 확인된 수동 진단값이 생성되고 남은 검색·문맥 결함이 기록된다.
6. 문맥 구성 수정이 필요한지 여부를 결정한다.

완료 뒤에는 확정된 결과 요약만 `docs/generated/`에 남긴다. 검색·문맥 결함이 있으면 먼저 수정하고 다시
확인한다. M3에서는 같은 10문항의 raw baseline과 R1을 비교하고 새 top 5 미판정 후보를 사용자 확인한다.
그 다음 M4 문맥 구성, 검색 전 라우팅, AI 답변 생성 순서로 진행한다. D-full 1,000문항 Gold 설계는
별도 예정 작업으로 보존하며 10문항 밖 일반화나 운영 회귀가 필요할 때만 착수한다.

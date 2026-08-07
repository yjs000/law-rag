# 0030: D-10 전수 qrel과 사용자 adjudication

상태: `진행 중 · draft 생성 완료 · 사용자 adjudication 대기`

착수일: 2026-08-07

제안 출처: 사용자가 D-10 10문항의 정식 Gold 요건을 보완하기 위해 전 후보 qrel과 adjudication을
작성하고 사용자 검토까지 진행하도록 요청했다.

## 목적과 사용자 결과

기존 D-10의 top-10 한정 사용자 판정을 정식 Gold로 이름만 바꾸지 않는다. 동일한 질문 10개와 현재
3,066개 provision snapshot을 별도 annotation 입력으로 고정하고, 검색 점수·순위를 숨긴 전 후보 판정,
독립 검토와 사용자 adjudication을 거쳐 `D-10 Gold v1`을 만들 수 있는 재현 가능한 작업 흐름을 제공한다.

이번 작업이 생성하는 최초 산출물은 `pending_user_review`다. 사용자가 qrel·answerability·필수 요소·기준
응답과 충돌 항목을 확인한 뒤에만 별도 명령으로 `approved_gold`와 adjudication manifest를 봉인한다.

## 범위

- D-10 질문 ID·질문 SHA·범위 SHA 10개와 승인 manifest 재검증
- 2026-08-05 기준 현재 D-10 corpus snapshot의 3,066개 provision 읽기 전용 export
- 질문별 3,066개, 총 30,660개 candidate judgment 작업표 생성
- relevance `0 | 1 | 2`, facet 연결, 판정 근거와 annotator 상태 기록
- answerability·필수 답변 요소·reference context·reference response 초안
- 사용자 adjudication 검토표와 승인·수정·보류 입력 계약
- 초안 preflight와 승인 후 seal preflight, 원자적 산출물 기록
- 설계·학습·운영 로드맵 갱신과 테스트

## 비범위

- 나머지 990문항 Gold 주석 또는 D-full 실행
- 기존 D-10, R1, frozen contract artifact 수정·덮어쓰기
- 사용자 승인 전 `approved_gold`, held-out 성능, 일반화, 운영 release gate 주장
- 새 passage embedding, query embedding, DB 검색, HNSW, hybrid/RRF, 답변 모델 호출
- 운영 검색 순서·문맥 조립·AI 생성 동작 변경

## 역할과 독립성

- `annotation_draft`: Codex가 검색 점수·rank·기존 top-10 판정 필드를 입력에서 제외한 canonical corpus
  순서로 1차 판정을 작성한다. 이 단계는 제안이며 Gold 승인이 아니다.
- `review`: 사용자가 질문별 positive qrel, 경계 후보, 일괄 relevance-0 판정 범위와 필수 답변 요소를
  승인·수정·보류한다.
- `adjudication`: 사용자 확인 결과를 별도 manifest에 반영한다. draft annotator와 reviewer ID는 달라야
  하고, adjudication 시각은 모든 review 시각보다 늦어야 한다.
- 기존 D-10 사용자 판정은 비교·충돌 탐지에만 사용하며 독립 annotation의 정답 입력으로 복사하지 않는다.

Codex가 기존 결과를 이미 본 한계는 provenance에 기록한다. 따라서 사용자가 법령 원문과 후보 판정을
직접 확인하기 전에는 독립 human Gold라고 주장하지 않는다.

## 산출물

추적 파일:

- `experiments/d_gold_10/experiment-d-10-gold-contract.json`
- `apps/api/scripts/experiment_d_10_gold_review.py`
- `apps/api/tests/test_experiment_d_10_gold_review.py`
- 관련 설계·학습 문서

로컬 비추적 파일:

- `.data/experiments/d-gold-10/<draft-id>/corpus.jsonl`
- `.data/experiments/d-gold-10/<draft-id>/judgments.jsonl`
- `.data/experiments/d-gold-10/<draft-id>/annotation-draft.json`
- `.data/experiments/d-gold-10/<draft-id>/adjudication-review.md`
- `.data/experiments/d-gold-10/<draft-id>/user-adjudication.json`
- 승인 후 `.data/experiments/d-gold-10/<draft-id>/sealed/`

법령 원문 전문과 30,660개 판정은 Git에 커밋하지 않는다. 추적 contract와 승인 후 요약은 artifact SHA와
corpus identity만 기록한다.

## 마일스톤과 체크리스트

### M0 — 계약·preflight

- [x] 1,000문항 보류와 D-10 전용 범위를 분리한다.
- [x] 사용자 승인 전 상태를 `pending_user_review`로 고정한다.
- [x] 질문·snapshot·profile·corpus count·출력 경로를 추적 contract로 봉인한다.

### M1 — corpus와 judgment 작업표

- [x] 읽기 전용 transaction에서 현재 parser의 provision을 canonical 순서로 export한다.
- [x] D-10 frozen snapshot/count/fingerprint와 일치하지 않으면 아무 산출물도 게시하지 않는다.
- [x] 질문마다 정확히 3,066개 candidate를 만들고 검색 점수·rank 필드가 없음을 검사한다.
- [x] 총 30,660개 judgment의 ID 집합과 SHA-256을 기록한다.

### M2 — annotation 초안

- [x] relevance 0/1/2, facet, 판정 이유를 모든 candidate에 기록한다.
- [x] positive와 경계 후보의 원문·메타데이터를 사용자 검토표에 표시한다.
- [x] relevance-0 일괄 판정은 규칙·범위·예외와 개수를 표시하고 사용자 승인 대상으로 둔다.
- [x] answerability·필수 답변 요소·reference context·reference response 초안을 작성한다.
- [x] 기존 D-10 판정과 다른 핵심 항목을 사용자 검토 문서에 표시한다.

### M3 — 사용자 review와 adjudication

- [ ] 사용자가 문항별 `승인 | 수정 | 보류`와 수정 qrel/facet/reason을 기록한다.
- [ ] 보류 또는 미판정 candidate가 하나라도 있으면 seal을 차단한다.
- [ ] 사용자 확정 payload로 새 adjudication manifest를 만든다.
- [ ] annotator/reviewer 분리와 `질문 승인 < annotation review < adjudication`을 검사한다.

### M4 — Gold 봉인

- [ ] 10문항 각각 3,066개 판정과 positive/distractor 완전 분할을 검증한다.
- [ ] qrel의 provision/version/content/effective-date identity를 corpus export와 재검증한다.
- [ ] dataset·case·judgment-set SHA를 adjudication manifest에 봉인한다.
- [ ] 최종 상태를 `approved_gold`로 바꾸고 D-10 calibration Gold임을 명시한다.
- [ ] 기존 10문항에 이미 조정한 검색기는 held-out으로 평가하지 않는다.

## 완료 조건

- 10개 질문 모두 현재 고정 corpus의 후보 수와 판정 수가 정확히 3,066개다.
- 모든 후보가 relevance 0/1/2 중 하나이며 positive와 distractor가 겹치지 않는다.
- 필수 답변 요소, qrel, reference context·response가 provision identity와 해시로 결박된다.
- 사용자 review가 10문항 모두 승인되고 보류·충돌·미판정이 0개다.
- adjudication manifest와 sealed Gold preflight가 통과한다.
- 결과는 calibration Gold이며 held-out·1,000문항 일반화로 표현되지 않는다.

## 검증

```powershell
uv run --directory apps/api python -m pytest tests/test_experiment_d_10_gold_review.py -q
uv run --directory apps/api python -m ruff check scripts/experiment_d_10_gold_review.py tests/test_experiment_d_10_gold_review.py
uv run --directory apps/api python -m scripts.experiment_d_10_gold_review preflight-contract
uv run python scripts/check_docs.py
```

실제 draft 생성은 DB 읽기 전용이며 명령·draft ID·snapshot·stdout SHA를 진행 기록에 추가한다.

## 롤백

- draft 실패 시 임시 디렉터리를 게시하지 않고 기존 D-10 artifact를 그대로 둔다.
- 사용자 수정은 기존 draft를 덮어쓰지 않고 새 review revision으로 기록한다.
- seal 실패 시 `pending_user_review`를 유지한다.
- 코드 롤백은 기능 커밋 단위로 수행하며 운영 DB와 검색 동작에는 되돌릴 변경이 없다.

## 미결정과 차단 요소

- 실제 사용자 review와 adjudication 승인은 사용자 입력이 있어야 완료된다.
- Codex 단독 판정은 법률 전문가의 독립 검토를 대체하지 않는다. 공개 서비스의 정량 release gate에는 별도
  전문가 검토 또는 D-full 표본이 필요하다.
- 30,660개를 문항별로 모두 펼친 UI 대신 positive·경계 후보와 일괄 relevance-0 범위를 검토하는 방식이
  기본값이다. 사용자는 필요하면 전체 JSONL에서 개별 후보를 수정할 수 있다.

## 결정 로그

- 2026-08-07: 기존 0029 D-full 보류는 유지하고, D-10 10문항만 별도 active 계획으로 분리했다.
- 2026-08-07: 사용자 승인 전 adjudication은 초안이며 `approved_gold`로 봉인하지 않는다.
- 2026-08-07: 전 후보 판정은 로컬 artifact로 보존하고 Git에는 계약·코드·요약만 남긴다.

## 진행 기록

- 2026-08-07: clean `main`, origin/main 대비 32커밋 앞선 상태에서 착수했다. 기존 미커밋 변경은 없었다.
- 2026-08-07: 기존 D-full schema·preflight·runner와 D-10 frozen artifact를 감사했다. D-full은 정확히
  1,000문항·200 family split을 요구하므로 변경하지 않고 D-10 전용 workflow를 추가하기로 했다.
- 2026-08-07: `d10-gold-20260807t040448957688z`를 읽기 전용 DB에서 생성했다. snapshot과 3,066개
  fingerprint가 동결값과 일치했고 score·rank·모델 호출 없이 30,660개 judgment를 기록했다.
- 2026-08-07: relevance 2 35개, relevance 1 3개, relevance 0 30,622개와 answerability·facet·reference
  초안을 생성했다. 10문항 모두 사용자 adjudication 대기이며 seal은 실행하지 않았다.
- 2026-08-07: 사용자 질의에 따라 0251의 `route_for_user_facility`와 0521의
  `case_specific_rejection_reason`이 provision이 아닌 필수 답변 facet임을 확인했다. 각각 사용자 사실
  부족과 현재 corpus 근거 부족을 나타내므로 해당 facet 자체에는 positive qrel이 없고, 관련 일반 규칙만
  7개·6개 qrel로 연결된다는 점과 검토 순서를 설계 문서에 명시했다.

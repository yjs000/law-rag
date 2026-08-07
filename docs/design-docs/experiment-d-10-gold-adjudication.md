# 실험 D-10 전수 qrel과 사용자 adjudication

상태: annotation draft 생성 완료 · 사용자 검토 대기

최종 갱신: 2026-08-07

## 목적

기존 D-10의 검색 top 10 안에서 확인한 판정을 정식 Gold로 이름만 바꾸지 않는다. D-10 질문 10개와
2026-08-05의 3,066 provision snapshot을 별도 annotation 입력으로 고정하고, 질문마다 전체 corpus를
relevance 0/1/2로 분류한 뒤 사용자가 qrel·필수 답변 요소·기준 응답과 일괄 음성 판정을 adjudication한다.

이 작업은 1,000문항 D-full을 다시 열지 않는다. 결과는 같은 10문항에 이미 검색 조정이 이루어진
calibration Gold이며 held-out·모집단 일반화·운영 release gate가 아니다.

## 역할과 상태

1. Codex annotation proposal
   - 검색 score·rank·기존 판정 필드가 없는 canonical corpus export를 사용한다.
   - positive qrel과 relevance-0 전수 제안을 작성한다.
   - 과거 프로젝트 맥락을 본 한계를 provenance에 기록한다.
2. 사용자 review
   - positive qrel, 필수 답변 요소, answerability, reference response를 문항별로 확인한다.
   - 나머지 전체 provision의 relevance-0 일괄 제안을 확인한다.
   - 수정이 필요하면 seal하지 않고 새 proposal revision을 요청한다.
3. adjudication과 seal
   - annotator와 다른 reviewer ID, 시간대 포함 검토 시각과 10문항 승인을 요구한다.
   - 모든 문항의 positive·bulk negative·facet/reference 확인이 끝난 뒤 별도 `sealed/` artifact를 만든다.

사용자 승인 전 상태는 `pending_user_review`이고 `approved_gold`를 주장하지 않는다. 승인 뒤에도
`independent_human_gold=false`, `gold_scope=calibration_only_not_held_out`를 기록한다.

## 고정 계약

[workflow contract](../../experiments/d_gold_10/experiment-d-10-gold-contract.json)은 다음을 봉인한다.

- 질문 10개와 기존 D-10 frozen contract 파일 SHA-256
- 기준일 `2026-08-05`
- corpus snapshot `corpus-sha256:605b...9578`
- population fingerprint와 provision 수 3,066개
- 총 판정 수 30,660개
- relevance 0/1/2 의미
- annotation 입력 금지 필드: score, rank, 기존 판정 등
- 사용자 승인 전 금지 주장

## 실제 실행 결과

최종 사용자 검토 대상 draft ID는 `d10-gold-20260807t040448957688z`다.

| 항목 | 값 |
| --- | ---: |
| 질문 | 10 |
| 문항별 후보 | 3,066 |
| 전체 판정 | 30,660 |
| relevance 2 직접 근거 제안 | 35 |
| relevance 1 보조 문맥 제안 | 3 |
| relevance 0 제안 | 30,622 |
| 사용자 승인 대기 문항 | 10 |

문항별 qrel 수는 0201 8개, 0251 7개, 0521 6개, 0601 2개, 0111 5개, 0346 3개,
0561 7개이며 0605·0836·0943은 현재 corpus의 positive qrel이 없는 것으로 제안했다.

기존 D-10과 비교해 가장 중요한 검토 항목은 `0521`이다. 기존 top-10 진단은 직접 답변 가능으로
확인했지만 이번 초안은 세부 발급 운영규칙·신청·계량 상태가 corpus에 없다는 이유로 부분 답변을 제안했다.
사용자가 어느 질문 범위를 기준으로 삼을지 adjudication해야 한다.

## 사용자 검토 방법

검토 문서는 다음 로컬 파일이다.

```text
.data/experiments/d-gold-10/d10-gold-20260807t040448957688z/review/adjudication-review.md
```

문항마다 다음을 확인한다.

- answerability와 expected action
- 필수 답변 요소의 supported·unsupported·needs clarification 상태
- relevance 2 직접 근거와 relevance 1 보조 문맥의 원문·provision ID
- 기준 응답이 직접 근거만 인용하고 한계를 명시하는지
- positive를 제외한 전체 corpus의 relevance-0 일괄 판정을 승인할 수 있는지

승인할 때 같은 디렉터리의 `user-adjudication.json`을 수정한다.

```json
{
  "status": "confirmed",
  "reviewer_id": "user-reviewer-v1",
  "reviewed_at": "2026-08-07T13:00:00+09:00"
}
```

각 case는 다음 세 확인값과 `decision`을 설정한다.

```json
{
  "decision": "approved",
  "positive_qrels_confirmed": true,
  "bulk_negative_confirmed": true,
  "facets_and_reference_confirmed": true
}
```

하나라도 수정이 필요하면 `decision=needs_revision`으로 두고 comment에 변경사항을 적는다. 이 경우 Codex가
tracked proposal을 새 revision으로 고친 뒤 새 review bundle을 생성하며 기존 artifact를 덮어쓰지 않는다.

## 검증과 seal

사용자 검토 상태 확인:

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_gold_review preflight-draft `
  --review .data/experiments/d-gold-10/d10-gold-20260807t040448957688z/review
```

10문항이 모두 승인되면 `ready_to_seal`이 된다. 그때만 다음을 실행한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_gold_review seal `
  --review .data/experiments/d-gold-10/d10-gold-20260807t040448957688z/review
```

seal은 원본 draft를 바꾸지 않고 `review/sealed/`에 dataset, 30,660개 judgments, adjudication manifest와
상호 SHA manifest를 원자적으로 기록한다. 승인 전 seal은 실패한다.

## 결정 기록

- 2026-08-07: D-full 1,000문항은 계속 보류하고 D-10만 전수 qrel 대상으로 삼았다.
- 2026-08-07: 기존 retrieval 판정을 정답으로 복사하지 않고 score·rank 없는 canonical corpus export를
  별도 생성했다.
- 2026-08-07: relevance-0 30,622개는 assistant proposal이며 사용자의 명시적인 문항별 bulk 확인 전에는
  adjudicated judgment가 아니다.
- 2026-08-07: assistant annotation과 사용자 adjudication의 역할은 분리하지만 법률 전문가 2인 독립
  human Gold로 표현하지 않는다.

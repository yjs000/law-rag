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

v1 draft ID는 `d10-gold-20260807t040448957688z`(초안, pending_user_review로 보존), 최종 sealed
draft ID는 `d10-gold-20260807t065254073895z`(v3)다.

| 항목 | v1(초안) | v3(sealed, 최종) |
| --- | ---: | ---: |
| 질문 | 10 | 10 |
| 문항별 후보 | 3,066 | 3,066 |
| 전체 판정 | 30,660 | 30,660 |
| relevance 2 직접 근거 | 35 | 37 |
| relevance 1 보조 문맥 | 3 | 4 |
| relevance 0 | 30,622 | 30,619 |

v2에서 0346의 `approved_use_terms`(41ebaef4) 1건을 relevance 1→2로, v3에서 0601의 `9c93a34b`을
relevance 0→2로, `7cd6894f`를 relevance 0→1로 정정했다(회고 절 참고). 문항별 qrel 수(v3 기준)는 0201
8개, 0251 7개, 0521 6개, 0601 4개, 0111 5개, 0346 3개, 0561 7개이며 0605·0836·0943은 현재 corpus의
positive qrel이 없는 것으로 확정했다.

기존 D-10과 비교해 가장 중요한 검토 항목은 `0521`이다. 기존 top-10 진단은 직접 답변 가능으로
확인했지만 이번 초안은 세부 발급 운영규칙·신청·계량 상태가 corpus에 없다는 이유로 부분 답변을 제안했다.
사용자가 어느 질문 범위를 기준으로 삼을지 adjudication해야 한다.

## 0251·0521 필수 답변 요소의 위치와 의미

`route_for_user_facility`와 `case_specific_rejection_reason`은 provision ID가 아니라 질문에 안전하게
답하기 위해 확인해야 하는 **필수 답변 요소(facet)**의 식별자다. `supported` facet에는 직접 근거 qrel을
연결하지만, `needs_clarification`과 `unsupported` facet에는 이를 충족하는 현재 corpus의 provision이
없으므로 positive qrel을 억지로 연결하지 않는다.

| 문항·facet | 현재 제안 | 관련 정보가 있는 곳 | 판정에 미치는 영향 |
| --- | --- | --- | --- |
| `0251` · `route_for_user_facility` | `needs_clarification` | 법령 DB가 아니라 사용자에게 받아야 할 사실: 발전설비용량, 전압, 판매·자가소비 여부, 신규 설치·변경공사 여부 | 일반적인 허가·신고 구분은 설명할 수 있지만 질문자의 실제 절차는 추가 질문 전 확정하지 않는다. |
| `0521` · `case_specific_rejection_reason` | `unsupported` | 현재 9개 에너지 법령 corpus 밖의 대통령령·세부 운영규칙과 해당 신청·계량 기록. 이 초안은 구체 문서명이나 외부 출처를 아직 고정하지 않았다. | 일반적인 REC 발급 주체·신청·확인·제한은 설명하되 실제 미발급 사유와 제출서류는 확정하지 않는다. |

0251의 7개 relevance 2 qrel은 `route_for_user_facility`의 정답이 아니라, 사용자의 사실을 받은 뒤 어느
법적 갈래를 적용할지 판단하는 틀을 뒷받침한다.

- 전기사업 허가 원칙: 전기사업법 제7조제1항
  (`471dab54-74f6-5abb-8140-dafbea143180`)
- 3천킬로와트 이하 신청기관: 전기사업법 시행규칙 제4조제1항
  (`3b9af823-8b85-528e-b48a-5ec81934efec`)
- 사업용 설비 공사의 인가·신고: 전기사업법 제61조제1항·제3항
  (`553d5497-cc11-56a5-bfe9-cea1a2588835`, `3ee6a1a8-c1aa-58b1-a45f-de1b8754f7bc`)
- 자가용 설비 공사의 인가·신고·저압 예외: 전기안전관리법 제8조제1항·제2항·제3항
  (`f6043044-10b4-57a6-a076-3991ca49b9bd`, `4e893375-79da-57be-b009-33a901b87d28`,
  `15057cea-ae02-58d0-9f27-aa96b8f8962a`)

0521의 6개 relevance 2 qrel도 실제 미발급 사유를 증명하지 않고, 현재 corpus로 말할 수 있는 일반
발급 규칙과 제외 범위만 뒷받침한다.

- 발급 가능 주체·신청·공급량 확인: 신재생에너지법 제12조의7제1항·제2항·제3항
  (`06d15242-9c06-5d93-a02c-50899d67ebcb`, `324b2022-885a-5b12-927c-962e2eeb6471`,
  `9c677fb0-ba44-534c-8960-d9cfda49da82`)
- 정부 지원 설비의 발급 제한: 같은 조 제8항 (`343c49e0-6ad5-5832-b513-7e9649af9376`)
- 특정 직접공급·분산에너지 거래의 발급 제외: 전기사업법 제16조의5제5항과 분산에너지법 제43조제6항
  (`821628ba-aba4-5fd6-9ea1-0f3a4913d342`, `6e47c6a2-9bf0-5912-8355-cdb3b3e218d5`)

저장 위치와 역할은 다음과 같다.

| 위치 | 역할 |
| --- | --- |
| `experiments/d_gold_10/experiment-d-10-gold-annotation-proposal-v1.json` | 추적되는 원본 제안. `cases[case_id].facets`와 `positive_judgments`에 두 문항의 facet·qrel을 저장한다. |
| `.data/experiments/d-gold-10/d10-gold-20260807t040448957688z/review/annotation-draft.json` | 고정 corpus identity와 결합한 로컬 검토 초안. `cases[].facets`와 `cases[].qrels`에서 확인한다. |
| 같은 디렉터리의 `adjudication-review.md` | 사용자가 원문과 함께 읽는 렌더링 문서. 0251과 0521의 `필수 답변 요소`, `positive qrel`, `기준 응답 초안` 절에 있다. |
| 같은 디렉터리의 `judgments.jsonl` | 30,660개 provision 판정. 두 문제의 facet을 충족하는 provision이 없으므로 문제의 두 facet ID 자체는 positive judgment에 나타나지 않는다. |
| 같은 디렉터리의 `user-adjudication.json` | 문항별 승인·수정 입력. `facets_and_reference_confirmed`로 facet과 기준 응답을 함께 확인한다. |

## 현재 진행상황과 다음 작업 — 완료(v3, 2026-08-07)

D-10 Gold는 v1 draft → v2(0346 정정) → v3(0601 정정) 세 라운드를 거쳐 sealed됐다.
`d10-gold-20260807t065254073895z/review/sealed`가 최종본이며 `preflight-sealed`가
`valid_approved_calibration_gold`를 반환한다. v1/v2 draft는 plan 0030의 "덮어쓰지 않는다" 규칙에 따라
그대로 보존돼 있다. 정정 이력은 아래 "회고" 절과 [plan
0030](../exec-plans/completed/0030-d-10-full-corpus-qrels-adjudication.md)의 v3 추가 기록을 참고한다.

봉인 뒤 10문항 calibration Gold로 M3 raw/R1 순위를 다시 계산했다(아래 회고 참고). 그 다음 M4 AI 입력
문맥 확정, 검색 전 라우팅, NVIDIA 답변 생성과 E-10 사용자 평가로 이어진다. 이 10문항 결과는 held-out
성능이나 일반 운영 release gate로 확대 해석하지 않는다.

## 회고 — v1에서 놓친 것과 다음 평가에서 고려할 점

v1 draft는 3,066개 후보 대부분을 "필수 답변 요소를 직접 또는 보조로 뒷받침하지 않는 전수 corpus 음성
판정 초안"이라는 **정형 문구로 일괄 처리**했다. 이 일괄 처리 안에 원래 [0026 수동
검토](../exec-plans/completed/0026-experiment-d-10-manual-review.md)(2026-08-05, 사람이 raw top-10만
보고 판정)가 이미 찾아놓은 후보가 개별 재검토 없이 섞여 들어간 경우가 있었다.

사용자가 0026의 `direct_evidence_provision_ids`와 v1/v2 sealed 판정을 문항별로 대조해 6개 문항에서
불일치를 찾았고, 각 후보를 원문·facet과 대조해 다음처럼 갈렸다.

| 문항 | 불일치 후보 수 | 실제 결과 |
| --- | ---: | --- |
| `0201`, `0251`, `0111`(2건) | 4건 | v1/v2가 맞음 — 0026이 관련 맥락을 "직접 근거"로 느슨하게 묶었을 뿐, 해당 facet을 직접 서술하지 않음 |
| `0561`(3건) | 3건 | v1/v2가 맞음 — 위와 같은 패턴(발전차액·차액계약 조문은 가격 "구조" 배경일 뿐 `market_price_basis`·`settlement_and_metering_records`를 직접 서술하지 않음) |
| `0601`(2건) | 2건 | **v1/v2가 틀림** — `9c93a34b`(raw·R1 모두 top 1위)가 `deployment_program_basis`를 그대로 서술하는데 relevance 0으로 오채점, `7cd6894f`는 위임 조항이라 relevance 1이 맞음 |

9건 중 7건은 원래 v1/v2 판정이 맞았고, 2건(`0601`)만 실제 오류였다 — 즉 일괄 처리 자체가 전반적으로
부정확한 건 아니었지만, **일괄 처리에 섞인 후보 중 일부는 개별 검토를 받지 못하고 그대로 통과할 수
있다**는 게 확인된 사실이다.

부수적으로, `0561`은 v1/v2 자체는 맞았는데 **M3의 최초 공개 수치가 원래 0026의 느슨한 기준(4개 모두
"직접 근거")으로 계산돼 있어서, 정밀한 relevance-2 기준(v3)으로 다시 재면 raw 순위가 1위가 아니라
실제로는 8위였다**는 것도 같이 드러났다. `0346`이 원래 8위에 묻혀 있던 것과 같은 유형의 사례가
`0561`에도 하나 더 있었던 셈이다.

**다음 평가(0029 D-full 재개 등)에서 고려할 점**:

1. 대량 negative sweep을 적용하기 전에, 기존 독립 검토(사람 검토, 다른 라운드 등)가 이미 positive로
   표시한 후보 전부를 **명시적 교차 검증 대상 목록**으로 뽑아 개별 rationale 없이는 bulk negative로
   넘어가지 못하게 한다 — plan 0030도 "기존 D-10 사용자 판정은 비교·충돌 탐지에만 사용"한다고 명시했지만
   실제로는 일부만 반영됐다.
2. raw top-10 안에 있는 후보는 (corpus 전체 판정과 별개로) **순위 자체가 오류 발견 우선순위 신호다** —
   1위·2위처럼 상위 순위인데 relevance가 낮게 나온 조합은 자동으로 재검토 대상으로 플래그해야 한다.
   `0601`의 `9c93a34b`이 이 신호로 걸러졌을 사례다.
3. M3처럼 후속 지표(hit@k, MRR)를 계산하는 마일스톤은, 그 지표가 참조하는 "직접 근거" 정의가 **가장
   최신의 봉인된 Gold와 문항·후보 단위로 일치하는지** 별도로 검증한 뒤 발행한다. 서로 다른 라운드(사람
   top-10 검토 vs 전수 Gold)의 정의를 섞어 쓰면 숫자가 조용히 어긋날 수 있다.

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
  --review .data/experiments/d-gold-10/<draft-id>/review
```

seal은 원본 draft를 바꾸지 않고 `review/sealed/`에 dataset, 30,660개 judgments, adjudication manifest와
상호 SHA manifest를 원자적으로 기록한다. 승인 전 seal은 실패한다. 최종 `<draft-id>`는
`d10-gold-20260807t065254073895z`(v3)다 — v1/v2는 정정 이력으로 보존만 되고 sealed 상태가 아니다.

## 결정 기록

- 2026-08-07: D-full 1,000문항은 계속 보류하고 D-10만 전수 qrel 대상으로 삼았다.
- 2026-08-07: 기존 retrieval 판정을 정답으로 복사하지 않고 score·rank 없는 canonical corpus export를
  별도 생성했다.
- 2026-08-07: relevance-0 30,622개는 assistant proposal이며 사용자의 명시적인 문항별 bulk 확인 전에는
  adjudicated judgment가 아니다.
- 2026-08-07: assistant annotation과 사용자 adjudication의 역할은 분리하지만 법률 전문가 2인 독립
  human Gold로 표현하지 않는다.
- 2026-08-07: 사용자가 0346의 `approved_use_terms`(41ebaef4) relevance 1을 계약 위반으로 지적해 v2로
  정정하고 seal했다. v2 sealed 뒤 사용자가 0026과 v2를 전수 대조해 0601의 `9c93a34b`(deployment_program_
  basis, raw·R1 top 1위) relevance 0 오채점을 추가로 발견했다. v3로 정정(9c93a34b→2,
  7cd6894f→1)하고 재봉인했다. 나머지 발견된 불일치(0201·0251·0111·0561, 7건)는 원문 대조 결과 v1/v2
  판정이 맞았다.

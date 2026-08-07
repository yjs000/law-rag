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

## 현재 진행상황과 다음 작업

2026-08-07 현재 contract·runner·테스트와 annotation proposal은 main에 커밋되어 있다. 읽기 전용 DB
export로 질문 10개 × provision 3,066개 = 30,660개 judgment를 만들었고, relevance 2는 35개,
relevance 1은 3개, relevance 0 제안은 30,622개다. draft
`d10-gold-20260807t040448957688z`는 preflight를 통과했지만 10문항 모두 `pending`이고 `sealed/`는 없다.
따라서 현재 상태는 Gold 완료가 아니라 `pending_user_review`다.

다음 순서는 아래와 같다.

1. 사용자는 우선 0251에서 추가로 물어야 할 네 사실과 7개 qrel이 적절한지 확인한다.
2. 사용자는 0521을 `partially_answerable`로 둘지, 기존 D-10처럼 직접 답변 가능으로 수정할지 확인한다.
   이때 일반 발급 규칙과 실제 미발급 원인·제출서류를 구분한다.
3. 이어서 10문항 각각의 positive qrel, relevance-0 일괄 범위, facet·기준 응답을 `승인 | 수정 | 보류`로
   판정한다. 일부만 승인한 상태에서는 seal하지 않는다.
4. 전부 승인하면 `user-adjudication.json`을 확정하고 `preflight-draft`의 `ready_to_seal`을 확인한 뒤
   `seal`과 `preflight-sealed`를 실행한다. 수정이 있으면 proposal v2와 새 review bundle을 만들고 현재
   draft는 보존한다.
5. 봉인 뒤에만 10문항 calibration Gold로 M3 raw/R1 순위와 M4 AI 입력 문맥을 다시 계산·확정한다.
   그 다음 검색 전 라우팅을 거쳐 NVIDIA 답변 생성과 E-10 사용자 평가를 시작한다. 이 10문항 결과는
   held-out 성능이나 일반 운영 release gate로 확대 해석하지 않는다.

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

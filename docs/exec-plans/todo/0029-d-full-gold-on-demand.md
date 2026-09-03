> 작업 ID: `E-002`
> 상태: `Todo`
> 유형: `Experiment`
> 보조 라벨: `Evaluation`
> 선행 조건: D-full 일반화·release gate 필요성을 확인하고 대상 문항·인력·외부 호출 비용 상한을 다시 확정해야 한다.
> 다음 행동: D-full 일반화 판단이 필요해지면 대상 문항·비용 상한을 확정한다.
> 참고 범위:
> - `docs/exec-plans/completed/0030-d-10-full-corpus-qrels-adjudication.md` L12-L17 — D-10 Gold의 고정 10문항·사용자 adjudication 봉인 경계
> - `docs/exec-plans/completed/0030-d-10-full-corpus-qrels-adjudication.md` L30-L35 — 나머지 990문항 D-full과 일반 release 주장 제외 범위

# 0029: 필요 시 D-full Gold 제작

상태: `보류 · 미착수`

D-10 10문항만 전수 qrel과 사용자 adjudication 대상으로 만드는 현재 작업은
[활성 계획 0030](../completed/0030-d-10-full-corpus-qrels-adjudication.md)에서 진행한다. 이 계획은 10문항 밖
일반화가 필요할 때 여는 D-full 범위로 계속 보류한다.

제안 출처: 2026-08-07 사용자 결정. 승인된 1,000문항을 현재 모두 Gold로 승격하지 않고, 10문항
calibration으로 결정할 수 없는 실제 필요가 생길 때만 다시 검사해 정답 근거를 붙인다.

## 목적

D-10 밖으로 검색·문맥·답변 품질을 일반화하거나 운영 회귀 gate가 필요할 때 필요한 범위의 질문을 현재
corpus와 기준일에 맞춰 독립 Gold로 승격한다.

## 보존 자산

- 승인된 1,000문항 질문은행과 질문 문구·범위 승인 manifest
- D-full answerability·qrel·reference·adjudication schema
- gold preflight와 exhaustive exact cosine runner
- 기존 설계 문서와 합성 fixture 테스트

이 자산은 삭제하거나 현재 D-10 판정으로 덮어쓰지 않는다.

## active 승격 조건

- 10문항 밖의 일반화, 통계적 release gate 또는 반복 가능한 운영 회귀가 실제로 필요하다.
- 대상 문항 수와 질문군, 독립 주석·검토 인력, 외부 호출 비용 상한을 다시 확정한다.
- 현재 corpus snapshot과 질문별 기준일을 재검사한다.
- D-10의 top-10 한정 라벨을 전체 corpus qrels로 복사하지 않는다.

## 완료 조건

- 선택한 문항마다 answerability, 필수 답변 요소, 직접 qrels, reference context·answer가 현재 원문에 결박된다.
- 주석자·검토자·adjudicator가 분리되고 질문 승인보다 늦은 검토·확정 시간이 기록된다.
- 새 Gold manifest와 initial/locked preflight가 통과한다.
- 평가 모집단과 허용 가능한 일반화 범위를 결과에 명시한다.

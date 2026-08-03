# 실험 D gold 사전검사 보고

> 확인일: 2026-08-03
> 실행 명령: `uv run --directory apps/api python -m scripts.preflight_experiment_d_gold --dataset evaluation/experiment-d-v3-1000.json`
> 범위: Supabase current corpus와 저장된 메타데이터의 읽기 전용 비교
> 실행하지 않은 것: 질문 임베딩, 검색, 순위·점수 계산, Recall·MRR·nDCG 평가

이 명령은 당시 corpus를 읽기 전용으로 대조한 독립 검사다. 아래 수치는 과거 v3 draft를 검사한 시점의 기록이다. 이후 승인된 gold 전용 `scripts.evaluate_experiment_d_gold` runner와, 최종 preflight부터 검색 종료까지 corpus 공유 잠금을 유지하는 원자적 실행 게이트가 구현됐다. 다만 일반 사용자 질문 1,000개의 질문 승인·독립 정답 주석·gold adjudication은 아직 끝나지 않았으므로 실제 검색 평가는 실행하지 않았다.

## 판정

`ready=false`다. 현재 `experiment-d-v3-1000.json`은 미승인 draft이고 parser v3 전환 전 qrels를 가지므로 검색 평가 입력으로 사용할 수 없다. 이 실패가 정상적인 fail-closed 동작이다.

| 확인 항목 | 실제 값 | 판정 |
|---|---:|---|
| 문항 | 1,000 | 형식상 존재 |
| qrel | 2,787 | 존재하지만 stale |
| 고유 qrel provision ID | 1,624 | 전부 과거 ID |
| 현재 corpus에서 누락된 고유 qrel ID | 1,624 | 실패 |
| 본문 변경으로 불일치한 qrel ID | 0 | 공통 ID 자체가 없음 |
| 현재 searchable provision | 3,066 | parser v3 |
| 현재 parser 계약 | 3 | 정상 |
| 질문 승인 manifest | 없음 | 실패 |
| gold 실행 계약 | v3 draft 형식 | 실패 |

기존 draft가 선언한 corpus fingerprint는 `3b5e2686ff7f353dc67f266310f130cd385efc7ed0ae516b656cca18cf59ee01`이다. 현재 parser 버전·문서/버전/조문 ID·경로·효력기간·본문 SHA·임베딩 passage SHA를 포함해 계산한 fingerprint는 `b0f32af02a18387d4c2fc8c6293fa094a1aea9e23bb215a9c47e8d22e73573b2`다.

## 의미

- `changed_qrel_count=0`은 본문이 그대로라는 뜻이 아니다. 비교 가능한 동일 ID가 하나도 없고 1,624개가 모두 missing이라는 뜻이다.
- 과거 ID를 본문 SHA만으로 현재 ID에 자동 연결하지 않는다. 같은 본문이 다른 법률 위치에 존재할 수 있어 잘못된 정답을 만들 수 있다.
- 일반인 질문은행의 법령명 목록 해시는 corpus fingerprint가 아니다. 실제 corpus binding은 승인 후 만드는 gold에만 기록한다.
- 질문과 qrels가 준비돼도 `approved_gold`, 외부 질문 승인 manifest, 기준문맥 원문과 독립 검토가 없으면 실행하지 않는다.

## 다음 통과 조건

1. 일반인 질문 1,000개의 문구와 범위를 사용자가 승인한다.
2. 질문은행 버전과 질문 SHA를 별도 승인 manifest에 고정한다.
3. 현재 parser v3 corpus에서 answerability·필수 답변 요소·직접 근거 qrels·기준문맥·기준응답을 독립 주석한다.
4. 다른 검토자가 후보 pool과 대체 직접 근거를 재검토한다.
5. `scripts.preflight_experiment_d_gold`가 모든 항목을 통과한 뒤에만 dense-only 검색 평가를 실행한다.

# 실험 D — 검색 문맥 구성

상태: 계획됨, 아직 실행 명령은 구현되지 않음

## 목적

실험 C는 관련 가능성이 있는 후보를 넓게 찾는다. 실험 D는 그 후보에서 답변 모델에 전달할 직접 근거만
고르고, 근거가 부족하면 부족하다고 판정하는 검색 문맥 단계다. 답변 생성 자체는 이 실험에 포함하지 않는다.

```text
실험 C article candidates 최대 10개
-> 직접 관련성 판정
-> 같은 조 중복 제거와 필요한 인접 청크 보강
-> 근거 1~5개 또는 insufficient_evidence
-> 인용 가능한 context package
```

## 입력 계약

- 실험 C가 기록한 한 실행의 `article_candidates`와 `raw_chunk_candidates`
- 질문 원문, corpus SHA-256, 검색 실행 번호
- 각 후보의 법률명, MST, 조문 경로, 본문, source ID와 점수

후보 10개는 답변에 그대로 넣는 문맥이 아니다. 검색 단계의 recall을 확보하기 위한 관찰 범위이며, D가
그중 최대 1~5개를 근거로 선택한다.

## 출력 계약

- `status`: `ready` 또는 `insufficient_evidence`
- 선택된 근거 1~5개와 선택 이유
- 법률명, MST, 조문 경로, 본문, source ID를 포함한 인용 식별자
- 제거한 후보와 제거 이유
- 입력 검색 실행 번호와 corpus SHA-256
- 범위 밖 질문이면 현재 corpus 범위 제한

같은 조의 여러 청크는 하나의 근거 묶음으로 중복 제거한다. 질문을 직접 뒷받침할 때만 항·호·목 또는
인접/상위 청크를 함께 넣는다. 점수가 높다는 이유만으로 무관한 청크를 문맥에 포함하지 않는다.

## 실험 A에서 재사용할 기록 원칙

구현 시 성공 결과를 원자적으로 두 산출물에 자동 기록한다.

- `.data/experiments/context/context-runs.json`: 실제 context package와 입력·출력 SHA-256
- `.data/experiments/context/context-results.md`: 실행 비교와 실제 context package

모든 파일을 먼저 준비한 뒤 함께 교체하고, 기록 실패 시 이전 성공 결과를 보존한다. 질문 원문을 Git에
남길지 여부는 구현 전에 개인정보 경계를 검토한다. 기본값은 실험 C처럼 두 파일 모두 로컬 `.data`에
두며, 고정 평가셋 결과만 `docs/generated/experiment-d-search-context-evaluation.md`에 기록한다.

## 예정 CLI

아래는 인터페이스 초안이며 현재는 실행할 수 없다.

```powershell
uv run --directory apps/api python -m scripts.experiment_context build `
  --search-runs .data/experiments/search/search-runs.json `
  --run 1
```

## 완료 조건

- 정상: 직접 근거가 있는 질문에서 인용 가능한 근거 1~5개를 만든다.
- 실패: 검색 기록 없음, corpus 불일치, 손상된 입력을 명시적 오류로 종료한다.
- 경계: 범위 밖 또는 직접 근거가 없는 질문을 `insufficient_evidence`로 판정한다.
- 반복: 같은 입력에서 선택 결과가 같은지 실제 기록으로 비교한다.
- 검색 후보와 최종 문맥을 구분해, top 10 전체가 답변 프롬프트로 유입되지 않게 한다.

상세 실행 계획은 [0020 실험 D 계획](../../docs/exec-plans/active/0020-experiment-d-search-context.md)에 있다.

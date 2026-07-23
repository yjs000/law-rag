# 실행 계획 0020: 실험 D — 검색 문맥 구성

상태: 계획됨

작성일: 2026-07-23

소유자: 주 에이전트

## 목적과 사용자 결과

실험 C의 후보 최대 10개에서 질문을 직접 뒷받침하는 근거 1~5개만 선택해 인용 가능한 문맥 묶음을
만든다. 직접 근거가 없거나 corpus 범위 밖이면 답을 꾸미지 않고 `insufficient_evidence`를 출력한다.

## 범위와 비범위

범위:

- 기록된 실험 C 실행을 입력으로 읽기
- 조 단위 후보의 직접 관련성 판정과 중복 제거
- 필요한 경우에만 같은 조의 인접·상위 청크 보강
- 문맥 묶음과 실패 판정의 자동 기록
- 정상·실패·경계·반복 실행 테스트와 고정 평가

비범위:

- 생성 AI 답변 작성
- 실험 C dense 순위 또는 corpus 변경
- 키워드·BM25·PGroonga·RRF 결합
- production DB·검색·API 변경

## 완료 조건

- 입력 검색 실행 번호와 corpus SHA-256을 검증한다.
- 직접 근거 1~5개 또는 `insufficient_evidence` 중 하나만 반환한다.
- 각 근거에 법률명, MST, 조문 경로, 본문, source ID가 있다.
- 같은 조의 중복 청크가 하나의 근거 묶음으로 정리된다.
- 실험 A 방식으로 성공한 실제 결과를 로컬 JSON과 Markdown에 원자 기록한다.
- 기록 실패 시 이전 성공 이력을 보존한다.
- 고정 질문에서 관련성, 중복, 범위 밖 판정을 반복 검증한다.

## 단계와 체크리스트

- [ ] M1 — 입력·출력 스키마와 선택 규칙 확정
- [ ] M2 — context builder와 CLI 구현
- [ ] M3 — 자동 기록과 실패 복구 구현
- [ ] M4 — 고정 평가셋과 실제 결과 생성
- [ ] M5 — 전체 검증, 학습 문서, 완료 기록

## 검증과 롤백

예정 명령:

```powershell
uv run --directory apps/api python -m pytest tests/test_context_experiment.py -q
uv run --directory apps/api ruff check scripts/experiment_context.py tests/test_context_experiment.py
uv run python scripts/check_docs.py
pnpm.cmd verify
```

실험 산출물과 신규 CLI만 되돌리며 실험 C corpus와 검색 이력은 수정하지 않는다.

## 결정 로그

- 2026-07-23: 검색 후보 수와 답변 문맥 수를 분리했다. C는 후보 최대 10개를 관찰하고 D는 근거
  1~5개만 선택한다.
- 2026-07-23: 첫 버전은 생성 AI 없이 문맥 구성과 근거 부족 판정까지만 다룬다.
- 2026-07-23: 고정 평가 결과는 Git 문서에, 임의 질문 원문은 기본적으로 로컬 `.data`에 둔다.

## 미결정 사항과 차단 요소

- 직접 관련성 판정을 규칙 기반으로 시작할지 별도 reranker를 사용할지는 M1에서 비교한다.
- 개인정보가 포함될 수 있는 임의 질문을 생성 문서에 기록하는 기능은 기본 비활성으로 둔다.
- 현재 구현 차단 요소는 없으며, 이 계획은 실험 C 완료 후 별도 작업으로 착수한다.

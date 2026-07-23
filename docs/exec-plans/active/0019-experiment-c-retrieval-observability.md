# 실행 계획 0019: 실험 C — 검색 후보 관찰·기록·평가

상태: 진행 중
작성일: 2026-07-23
소유자: 주 에이전트

## 목적과 사용자 결과

실험 C의 dense 검색이 반복 가능하지만 실제 관련성이 낮은 이유를 관찰할 수 있게 한다. 한 질문에
대해 raw 청크 후보 10개와 조 단위 그룹 후보 10개를 함께 출력하고, 성공한 터미널 JSON을 실행 즉시
로컬 Markdown과 JSON 이력에 원자 기록한다. 고정 질문셋으로 기대 법률·조문의 rank와 Recall@K를
반복 측정한다.

## 범위와 비범위

범위:

- `candidate_k` 기본 10, CLI 조정 가능
- 전체 청크 cosine 순위와 조 단위 그룹 순위를 모두 출력
- 같은 조의 청크를 묶고 최고 하위 청크 점수를 조 점수로 사용하는 dense-only 기준선
- `ask` 성공 stdout, 시각, corpus SHA-256, stdout SHA-256의 로컬 자동 이력
- 고정 평가질문과 Law@1, article Recall@3/5/10, MRR 자동 계산
- 실험 D 검색 문맥 구성의 입력 계약 문서화

비범위:

- 키워드/BM25/PGroonga/RRF 결합 구현
- reranker 또는 생성 AI 호출
- AI에 전달할 최종 근거 1~5개 선정과 근거 부족 판정(실험 D)
- production 검색·DB·API 변경
- 기존 실험 B 미커밋 결과 변경

## 완료 조건

- 기본 `ask`가 raw 청크 10개와 중복 제거된 조 후보 10개를 출력한다.
- 같은 조의 여러 항·호·목은 하나의 article candidate 아래 묶이고 best chunk를 표시한다.
- `--candidate-k` 경계와 결정적 동점 순서를 검증한다.
- 성공한 ask만 `.data/experiments/search/`의 Markdown+JSON 이력에 원자 기록된다.
- 기록 stdout이 실제 터미널 stdout과 byte 단위로 일치하고 실패 시 이전 이력을 보존한다.
- 고정 질문별 기대 법률·조문, out-of-scope 여부와 자동 평가 지표가 저장된다.
- 키워드 결합은 구현하지 않고 비교 가능한 후속 설계로 남긴다.
- 실험 D가 C의 article candidates를 입력으로 받는 별도 계획과 실행 안내를 가진다.
- 관련 테스트, Ruff, 문서 검사와 전체 검증이 통과한다.

## 단계와 체크리스트

- [x] M1 — 현재 출력·기록·평가 계약과 실험 A 원자 기록 패턴 확인
- [x] M2 — candidate 10과 조 단위 그룹 검색 구현·테스트·커밋
- [ ] M3 — ask 자동 이력 기록 구현·테스트·커밋
- [ ] M4 — 고정 평가셋·평가 명령·대표 결과 구현·실행·커밋
- [ ] M5 — 키워드 결합 보류 설계, 실험 D 계획·README, 학습 문서
- [ ] M6 — 전체 검증, 완료 기록과 계획 이동

## 검증과 롤백

```powershell
uv run --directory apps/api python -m pytest tests/test_search_experiment.py -q
uv run --directory apps/api ruff check scripts/experiment_search.py tests/test_search_experiment.py
uv run python scripts/check_docs.py
pnpm.cmd verify
```

실험 출력은 `.data/experiments/search/`에만 쓰고 production 상태를 변경하지 않는다. 각 기록 파일은
모두 준비된 뒤 원자 교체하며 실패하면 기존 성공 이력을 유지한다. 롤백은 실험 C CLI·테스트·문서와
새 실험 D 문서를 되돌리는 것으로 충분하다.

## 결정 로그

- 2026-07-23: top 3을 top 5로 단순 확대하지 않고 관찰 후보를 10개로 확장한다.
- 2026-07-23: 조 점수는 첫 기준선으로 최고 하위 청크 cosine을 사용한다. 문맥 선정은 하지 않는다.
- 2026-07-23: 질문 원문 이력은 사용자가 요청한 로컬 실험 산출물로만 저장하고 Git·운영 로그에 넣지
  않는다.
- 2026-07-23: 키워드 결합은 dense 기준선 평가 후 결정하며 이번 구현에 포함하지 않는다.
- 2026-07-23: AI 근거 선택·중복 제거·근거 부족 게이트는 실험 D로 분리한다.

## 진행 기록

- 2026-07-23: 현재 `ask`는 top 3 JSON만 stdout에 출력하고 결과 파일을 만들지 않음을 확인했다.
- 2026-07-23: 실험 A가 Markdown과 JSON을 staging한 뒤 함께 교체하고 실패 시 이전 성공 결과를
  복원하는 패턴을 확인했다.
- 2026-07-23: 사용자 터미널의 이미 끝난 두 실행은 프로젝트 파일이나 연결된 터미널에 남지 않아
  소급 복구할 수 없음을 확인했다.
- 2026-07-23: raw 청크와 조 단위 후보의 기본 `candidate_k=10`, 최대 50, 조 점수 `max chunk
  cosine`, 조별 상위 하위청크 3개 출력 계약을 구현했고 관련 테스트 14개와 Ruff가 통과했다.

## 미결정과 차단 요소

- 사용자가 언급한 세 번째 질문의 실제 문장과 기존 top 3는 남아 있지 않다. 자동 기록 구현 후
  재실행 결과로 평가셋 기대값을 추가할 수 있다.
- 구현 차단 요소는 없다.

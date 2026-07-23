# 실행 계획 0019: 실험 C — 검색 후보 관찰·기록·평가

상태: 진행 중

작성일: 2026-07-23

소유자: 주 에이전트

## 목적과 사용자 결과

실험 C의 dense 검색이 반복 가능하지만 실제 관련성이 낮은 이유를 관찰할 수 있게 한다. 한 질문에 대한
raw 청크 후보 10개와 조 단위 후보 10개를 함께 출력하고, 성공한 실제 stdout을 즉시 로컬 Markdown과
JSON 이력에 기록한다. 고정 질문셋으로 기대 법률·조문의 순위와 Recall@K를 반복 측정한다.

## 범위와 비범위

범위:

- `candidate_k` 기본 10, CLI 조정 가능
- 전체 청크 cosine 순위와 조 단위 그룹 순위를 함께 출력
- 같은 조의 청크를 묶고 최고 하위 청크 점수를 조 점수로 사용
- 성공한 `ask`의 실제 stdout, 시각, corpus SHA-256, stdout SHA-256 자동 기록
- 고정 평가 질문과 Law@1, Article Recall@3/5/10, MRR 자동 계산
- 실험 D 검색 문맥 구성의 입력 계약 문서화

비범위:

- 키워드·BM25·PGroonga·RRF 결합 구현
- reranker 또는 생성 AI 호출
- AI가 전달할 최종 근거 1~5개 선택과 근거 부족 판정(실험 D)
- production 검색·DB·API 변경
- 기존 실험 B 미커밋 결과 변경

## 완료 조건

- 기본 `ask`가 raw 청크 10개와 중복 제거된 조 후보 10개를 출력한다.
- 같은 조의 항·호·목은 하나의 article candidate 아래 묶이고 best chunk가 표시된다.
- `--candidate-k` 경계와 결정적 동점 순서를 검증한다.
- 성공한 ask만 `.data/experiments/search/`의 Markdown+JSON 이력에 원자 기록한다.
- 기록 stdout은 실제 터미널 JSON과 byte 단위로 일치하고 실패 시 이전 성공 이력을 보존한다.
- 고정 질문별 기대 법률·조문, out-of-scope 여부와 자동 평가 지표가 저장된다.
- 키워드 결합은 구현하지 않고 비교 가능한 후속 설계로 남긴다.
- 실험 D가 C의 article candidates를 입력으로 받는 별도 계획과 안내를 가진다.
- 관련 테스트, Ruff, 문서 검사와 전체 검증이 통과한다.

## 단계와 체크리스트

- [x] M1 — 현재 출력·기록·평가 계약과 실험 A 원자 기록 패턴 확인
- [x] M2 — candidate 10과 조 단위 그룹 검색 구현·테스트·커밋
- [x] M3 — ask 자동 결과 기록 구현·테스트·커밋
- [x] M4 — 고정 평가셋·평가 명령·실제 결과 구현·실행·커밋
- [x] M5 — 키워드 결합 보류 설계, 실험 D 계획·README, 학습 문서
- [ ] M6 — 전체 검증, 완료 기록과 계획 이동

## 검증과 롤백

```powershell
uv run --directory apps/api python -m pytest tests/test_search_experiment.py -q
uv run --directory apps/api ruff check scripts/experiment_search.py tests/test_search_experiment.py
uv run python scripts/check_docs.py
pnpm.cmd verify
```

실험 출력은 `.data/experiments/search/`에만 쌓고 production 상태를 변경하지 않는다. 각 기록 파일은
모두 준비된 뒤 원자 교체하며 실패하면 기존 성공 이력을 유지한다. 롤백은 실험 C CLI·테스트·문서와
실험 D 계획 문서를 되돌리는 것으로 충분하다.

## 결정 로그

- 2026-07-23: top 3을 top 5로 단순 확대하지 않고 관찰 후보를 10개로 확장했다.
- 2026-07-23: 조 점수는 첫 기준선으로 최고 하위 청크 cosine을 사용한다. 문맥 선택은 하지 않는다.
- 2026-07-23: 임의 질문 이력은 질문 원문이 포함되므로 로컬 실험 산출물에만 저장한다.
- 2026-07-23: 키워드 결합은 dense 기준선 평가 뒤 결정하며 이번 구현에는 포함하지 않는다.
- 2026-07-23: AI 근거 선택·중복 제거·근거 부족 게이트는 실험 D로 분리한다.

## 진행 기록

- 2026-07-23: 기존 `ask`는 top 3 JSON만 stdout에 출력하고 결과 파일은 만들지 않음을 확인했다.
- 2026-07-23: 실험 A가 Markdown과 JSON을 staging한 뒤 함께 교체하고 실패 시 이전 성공 결과를
  복원하는 패턴을 확인했다.
- 2026-07-23: 사용자가 언급한 과거 터미널 실행은 프로젝트 파일이나 연결된 터미널에 남아 있지 않아
  사후 복구할 수 없음을 확인했다.
- 2026-07-23: raw 청크와 조 단위 후보에 기본 `candidate_k=10`, 최대 50, 조 점수 `max chunk
  cosine`, 조별 상위 하위청크 3개 출력 계약을 구현했다.
- 2026-07-23: 성공한 ask의 실제 stdout, corpus/stdout SHA-256을 로컬 JSON 이력과 Markdown에 원자
  기록하고 실행 번호를 누적하도록 구현했다.
- 2026-07-23: 고정 질문 6개와 Law@1·Article Recall@3/5/10·MRR을 구현했다. 실제 범위 내 5문항에서
  Law@1 `1.0`, Recall@3 `0.8`, Recall@5 `0.8`, Recall@10 `1.0`, MRR `0.82`였다.
- 2026-07-23: 실제 ask 1회를 실행해 로컬 run 1, stdout hash 일치와 Markdown의 exact stdout 포함을
  확인했다. 태양광 질문은 신재생에너지법 제2조가 raw·조 모두 1위였다.
- 2026-07-23: 키워드 결합은 RRF 후속 비교안으로 문서화하되 구현하지 않았다. 후보를 근거 1~5개로
  줄이는 일은 실험 D 계획 0020으로 분리했다.

## 미결정 사항과 차단 요소

- 키워드 결합의 tokenizer와 RRF 상수는 후속 비교 평가에서 결정한다.
- 실험 D의 직접 관련성 판정 방식은 계획 0020의 M1에서 비교한다.
- 현재 구현 차단 요소는 없다.

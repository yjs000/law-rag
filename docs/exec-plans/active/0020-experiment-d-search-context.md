# 실행 계획 0020: 실험 D — 검색 문맥 구성

상태: 완료

작성일: 2026-07-23

소유자: 주 에이전트

## 목적과 사용자 결과

검색 순서를 `corpus 정확성 -> 근거 충분성 -> 검색 개선`으로 고정한다. 먼저 Open API의 구조 표지가
실제 제1조를 덮어쓰는 파서 결함을 고치고 코퍼스 유효성 검사를 통과시킨다. 다음으로 실험 C의 후보
최대 10개를 조·항·호·목 계층으로 복원해 질문을 직접 뒷받침하는 근거 묶음을 만들며, 근거가 없거나
corpus 범위 밖이면 `insufficient_evidence`로 차단한다. 이 기준선이 확정된 뒤에만 lexical+dense
결합을 별도 비교하고 실제 지표가 좋아질 때 채택한다.

## 범위와 비범위

범위:

- Open API 구조 표지와 실제 조문의 중복 번호 처리 수정
- 임베딩 전에 본문 누락·구조 표지 오인·부모 경로 단절을 검사하는 corpus validator
- Article Recall과 Evidence Recall을 분리한 고정 평가
- 기록된 실험 C 실행을 입력으로 읽기
- 조 단위 후보의 중복 제거와 조·항·호·목 계층 복원
- 고정 평가의 요구 근거를 사용한 직접 관련성·근거 충분성 판정
- 문맥 묶음과 실패 판정의 자동 기록
- 정상·실패·경계·반복 실행 테스트와 고정 평가
- 수정된 dense-only 기준선과 lexical+dense 후보의 분리 비교

비범위:

- 생성 AI 답변 작성
- 생성 모델이나 별도 reranker를 사용한 의미 판정
- production DB·검색·API 변경
- 평가 개선이 확인되지 않은 lexical+dense 방식을 기본값으로 채택

## 완료 조건

- 입력 검색 실행 번호와 corpus SHA-256을 검증한다.
- 구조 표지가 실제 조문으로 저장되지 않고 제1조 본문 누락을 준비 단계에서 차단한다.
- Article Recall과 Evidence Recall을 별도로 출력한다.
- 직접 근거 1~5개 또는 `insufficient_evidence` 중 하나만 반환한다.
- 각 근거에 법률명, MST, 조문 경로, 본문, source ID가 있다.
- 같은 조의 중복 청크가 하나의 근거 묶음으로 정리된다.
- 실험 A 방식으로 성공한 실제 결과를 로컬 JSON과 Markdown에 원자 기록한다.
- 기록 실패 시 이전 성공 이력을 보존한다.
- 고정 질문에서 관련성, 중복, 범위 밖 판정을 반복 검증한다.

## 단계와 체크리스트

- [x] M1 — parser 중복 조문 수정과 corpus validator 구현
- [x] M2 — Evidence Recall 평가 계약과 고정 질문 근거 정의
- [x] M3 — context builder, 법률 계층 복원, 안전 게이트 구현
- [x] M4 — dense-only 재측정과 lexical+dense 비교·채택 여부 결정
- [x] M5 — 자동 기록, 실제 결과, 근거 문서와 학습 문서 생성
- [ ] M6 — 전체 검증, 기능별 커밋, main 병합·푸시와 브랜치 정리

## 작업 TODO

모든 항목은 주 에이전트가 순차 수행한다. parser 출력이 corpus와 평가, 문맥 구성 모두의 선행 조건이어서
동일 파일을 병렬 수정하지 않는다.

| 상태 | 담당 | 목적·수정 범위 | 선행 조건 | 완료·검증 |
|---|---|---|---|---|
| 완료 | 주 에이전트 | `packages/law-rag-core` parser와 parser 테스트에서 구조 표지/실제 조문 중복 수정 | 없음 | JSON·XML 정상/경계 테스트 |
| 완료 | 주 에이전트 | `experiment_search.py` corpus validator와 Evidence Recall 평가 | parser 수정 | 검색 실험 단위 테스트 |
| 완료 | 주 에이전트 | `experiment_context.py` 계층 복원·안전 게이트·원자 기록 | corpus/evidence 계약 | D 정상/실패/경계/반복 테스트 |
| 완료 | 주 에이전트 | dense 기준선 재생성과 lexical+dense 비교 | 위 구현 | 고정 평가 실제 지표 비교 |
| 완료 | 주 에이전트 | 설계·학습·근거·생성 문서 갱신 | 실제 측정 | 문서 검사와 링크 검사 |
| 대기 | 주 에이전트 | 커밋·main 병합·푸시·브랜치 정리 | 전체 검증 | 원격 main 확인, main 외 브랜치 0개 |

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
- 2026-08-03: Open API가 장 표지와 실제 제1조에 같은 `조문번호=1`을 주는 사례에서 parser가 첫
  레코드를 보존해 본문을 누락한 원인을 확인했다. 구조 표지는 범위 판정에만 쓰고 실제 `조문여부=조문`
  레코드를 검색 본문으로 보존한다.
- 2026-08-03: cosine 임계값 하나로 충분성을 판정하지 않는다. 고정 평가의 요구 근거와 복원된 법률
  계층을 기준으로 직접 근거 존재 여부를 검사하고, 일반 질문의 의미 판정은 후속 reranker/생성 단계로
  남긴다.
- 2026-08-03: RRF 식은 두 순위 기여도를 빼는 것이 아니라 더한다.
- 2026-08-03: Open API가 `목`을 상위 `호` 정보 없이 평탄화하는 응답을 확인했다. 목 번호 재시작으로
  그룹을 만들고 명시 문구·정확한 개수 일치·삭제 호 제외 순으로만 부모를 복원하며 불일치 시 실패한다.
- 2026-08-03: 최종 corpus 205개와 SHA-256
  `86fbfe0af0df4c308d46a910e2ba8ff3f102c3c8534c41f9777758b75054f3da`로 재평가했다. 범위 내 5개
  질문의 Law@1, Article Recall@3/5/10, Article MRR, Evidence Recall@3/5/10이 모두 1.0이었다.
- 2026-08-03: 현재 평가셋에서는 hybrid가 높일 지표가 없어 구현·채택하지 않았다. 더 다양한 질문을
  추가한 뒤 Evidence Recall을 유지하면서 MRR 또는 Evidence Precision이 개선될 때만 다시 검토한다.
- 2026-08-03: D 실제 실행에서 범위 내 5개는 `ready`, 범위 밖 제7조 질문은 근거 0개와
  `insufficient_evidence`로 차단됐다.

## 미결정 사항과 차단 요소

- 임의 자연어 질문의 직접 관련성은 규칙만으로 완전 판정할 수 없다. 이번 구현은 구조적·범위 기반의
  hard gate와 고정 평가의 명시적 요구 근거를 구현하고, 별도 reranker는 측정 후 후속 후보로 둔다.
- 개인정보가 포함될 수 있는 임의 질문을 생성 문서에 기록하는 기능은 기본 비활성으로 둔다.
- 현재 구현 차단 요소는 없다.

## 완료 결과

- corpus 결함 2종을 수정하고 준비 단계 검증을 추가했다.
- Article Recall과 Evidence Recall을 분리해 조문 ID 성공이 본문 근거 성공을 보장하지 않음을 측정했다.
- 실험 D CLI와 원자 기록을 구현하고 실제 6개 실행을 저장했다.
- dense-only 최종 기준선이 고정 평가의 모든 검색·근거 지표에서 1.0이므로 hybrid는 보류했다.
- 설계 근거, 공식 참고 자료, 영어 개념 학습 문서를 추가했다.

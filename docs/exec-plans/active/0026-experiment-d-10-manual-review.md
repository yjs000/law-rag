# 실행 계획 0026: 실험 D-10 수동 검색·문맥 진단

상태: 구현 완료 · 실제 D-10 실행과 Codex/사용자 검토 대기
작성일: 2026-08-05
소유자: 주 에이전트

## 목적과 사용자 결과

승인 질문은행에서 고정한 10문항을 현재 PostgreSQL의 확정 corpus와 활성 NVIDIA 512차원 벡터로 한 번
검색하고, raw 후보와 복원 조문 문맥을 자동 입력한 수동 검토 자료를 만든다. Codex의 1차 판정과 사용자
최종 확인이 끝난 뒤에만 D-10 진단값을 계산한다.

## 범위와 비범위

범위:

- 실험 C와 D-10/D-full 경계 문서화
- 질문 ID·문구 SHA·범위 SHA만 가진 10문항 입력
- 현재 DB 읽기 전용 preflight, query vector cache, exact-cosine top 11 검색
- raw top 10과 조문 계층 복원, JSON·Markdown run 원자 기록, stdout SHA
- 검토 artifact 검증과 사용자 확인 뒤 진단 집계
- 정상·실패·경계·반복 실행 테스트와 학습 문서

비범위:

- 실험 A·B·C 코드·결과 변경 또는 C 재실행
- 기존 질문은행·승인 manifest·D-full 1,000문항 gold 계약 변경
- 이번 구현 중 운영 DB/NIM 실제 호출과 실제 D-10 run
- answer 생성, Open API 수집, passage embedding, 새 corpus
- HNSW·hybrid·RRF·reranker, PR·push·deploy
- 사용자 확인 전 `docs/generated/` 결과 요약

## 완료 조건

- 입력이 승인된 10개 고유 ID와 개별 질문·범위 SHA에 정확히 결박되고 정답 필드를 허용하지 않는다.
- 초기 read-only preflight를 통과하기 전 query embedding을 호출하지 않는다.
- 같은 질문 SHA·profile·snapshot은 cache를 재사용하고 모든 miss는 최대 10개 한 batch로 호출한다.
- shared corpus lock 안에서 snapshot/profile 재검증과 10개 검색을 수행한다.
- 10/11위 동점을 실패시키고 partial run을 성공 artifact로 게시하지 않는다.
- raw top 10과 해당 조문 전체의 부모·하위 계층을 같은 run에 기록한다.
- JSON·Markdown과 stdout SHA가 새 run 디렉터리에 원자 게시되고 기존 run을 덮어쓰지 않는다.
- 사용자 확인이 10/10 완료되지 않으면 진단 집계를 거부한다.
- focused pytest, Ruff, 문서 검사와 전체 관련 회귀가 통과한다.

## 작업 TODO

공유 입력·runner·검토 schema가 순차 의존하므로 하위 에이전트 없이 주 에이전트가 한 파일 계약씩
완료하고 기능별 커밋한다.

| 상태 | 담당 | 목적·수정 범위 | 선행 조건 | 완료·검증 |
|---|---|---|---|---|
| 완료 | 주 에이전트 | 설계·계획·C/D 경계와 권위 문서 갱신 | 없음 | 문서 검사, diff |
| 완료 | 주 에이전트 | `experiments/d_manual/` 10문항 해시 입력과 검증 계약 | 설계 | 승인 manifest 대조 테스트 |
| 완료 | 주 에이전트 | `scripts.experiment_d_manual_review` DB·cache·검색·원자 run | 입력 | runner 정상·실패·경계 테스트 |
| 완료 | 주 에이전트 | 검토 template·사용자 확인 gate·진단 집계 | run schema | 10/10 확인 전후 테스트 |
| 완료 | 주 에이전트 | 학습·운영 안내, 전체 검증과 완료 전 상태 기록 | 위 구현 | Ruff·pytest·문서·diff |
| 사용자 후속 | 사용자·Codex | 실제 D-10 run, Codex 1차 검토, 사용자 최종 확인 | 구현 완료·credential | 확정 진단 artifact |

## 구현 순서

1. 설계와 C/D 경계를 커밋한다.
2. 질문 10개 입력과 hash 검증을 커밋한다.
3. read-only 검색·cache·원자 run을 커밋한다.
4. 검토·확인 gate·진단 집계를 커밋한다.
5. 전체 검증 뒤 이 계획은 “구현 완료·실행 대기”로 남긴다.
6. 실제 run과 사용자 확인이 끝난 뒤 결과를 기록하고 `completed/`로 이동한다.

## 검증과 롤백

예정 명령:

```powershell
uv run --directory apps/api python -m pytest tests/test_experiment_d_manual_review.py -q
uv run --directory apps/api ruff check scripts/experiment_d_manual_review.py tests/test_experiment_d_manual_review.py
uv run python scripts/check_docs.py
```

실제 DB/NIM은 이번 구현 검증에 사용하지 않는다. 실패 시 새 D-10 문서·입력·runner·테스트만 되돌리며
기존 C 결과와 D-full 계약은 유지한다.

## 결정 로그

- 2026-08-05: C는 역사적 로컬 후보 관찰 실험으로 보존하고 현재 DB 기준선으로 재사용하지 않는다.
- 2026-08-05: D-full보다 먼저 정답 없는 D-10 수동 진단을 수행하되 정식 Recall이라고 부르지 않는다.
- 2026-08-05: 운영 호출은 구현과 분리하고 사용자가 직접 실행할 때만 발생한다.

## 진행 기록

- 2026-08-05: `codex/corpus-publisher-preflight`를 로컬 `main`에 fast-forward 병합했다.
- 2026-08-05: 기존 C는 로컬 205청크, D-full은 approved-gold-only 계약임을 확인했다.
- 2026-08-05: 기존 DB snapshot/profile/top11/shared-lock/원자 게시 코드를 재사용할 수 있음을 확인했다.
- 2026-08-05: `2dc9659`에서 C/D 경계와 D-10 설계·계획을 커밋했다.
- 2026-08-05: `0f751e3`에서 10개 ID·질문 SHA·범위 SHA 입력과 fail-closed 계약을 커밋했다.
- 2026-08-05: 실제 DB/NIM 호출 없이 D-10 runner focused 테스트 8개와 Ruff·문서 검사를 통과했다.
- 2026-08-05: 검토 template과 10/10 사용자 확인 gate, 수동 진단 집계를 구현했다. focused 테스트는
  입력·runner·검토를 합쳐 13개 통과했다.
- 2026-08-05: 실제 DB/NIM 호출 없이 전체 API `520 passed, 2 skipped`, 전체 API Ruff, 문서 95개 검사와
  clean Git 상태를 확인했다. 실제 run과 검토가 남아 있으므로 계획은 active에 유지한다.

## 미결정과 차단 요소

- 구현에는 차단 요소가 없다.
- 실제 실행에는 운영 DB read credential과 NVIDIA API key가 필요하며 사용자가 후속으로 실행한다.
- 사용자 확인 전에는 확정 진단값과 운영 반영 결정을 만들 수 없다.

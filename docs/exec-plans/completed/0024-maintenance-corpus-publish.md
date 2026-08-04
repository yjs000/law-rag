# 0024 점검 모드 기반 코퍼스 원자 반영

상태: 완료
최종 갱신: 2026-08-04

## 목표

현재 parser와 NVIDIA 512차원 embedding 계약을 그대로 사용해 변경분을 로컬에서 준비한다. 변경이 있을 때만 검색 게이트를 먼저 닫고 65초 drain한 뒤, Supavisor session `DIRECT_URL`의 단일 transaction에서 코퍼스·벡터·검증·게이트 재개를 원자적으로 반영한다. 운영 검색 reader의 공유 advisory lock은 제거한다.

## 범위와 제외

- 포함: `prepare-current`, bundle 기반 `generate-cache`, `apply-prepared`, 예약 workflow, 운영 reader lock 제거, 테스트와 권위 문서 갱신
- 보존: `ProvisionRecord` 경계, `legal-provision-v1` 본문, writer lock 3종, 실험 D 공유 lock, history-retention lock
- 제외: 운영 DB 쓰기, 실제 평가 dataset 실행, HNSW, hybrid/RRF, generation pointer, frontend 점검 UI, 유료 서비스
- 기존 미커밋 `AGENTS.md` 변경은 이 작업의 staging·commit에 포함하지 않는다.

## TODO와 담당

| 상태 | 담당 | 작업 | 수정 범위 | 완료 조건 |
| --- | --- | --- | --- | --- |
| 완료 | 주 에이전트 | 공용 bundle·publisher 계약과 통합 | 실행 계획, workflow, 통합 diff | 하위 작업 인터페이스가 충돌하지 않음 |
| 완료 | reader-lock 에이전트 | 운영 reader shared lock 제거 | API repository·관련 API tests·시간/아키텍처 문서 | 운영 SQL에 shared lock 0개, 422/503 유지 |
| 완료 | prepare 에이전트 | 로컬 준비 bundle 구현 | core bundle 계약·collector 준비 경로·collector tests | 준비 중 DB write/lock 0회, 변경 없음 종료 |
| 완료 | publisher 에이전트 | bundle embedding·원자 반영 구현 | embedding script·collector repository/publisher·tests | Tx B commit 1회, 실패 rollback+gate false |
| 완료 | 주 에이전트 | workflow·CLI 통합과 전체 검증 | workflow, 충돌 파일, 문서·learning | 전체 로컬 검증 통과 |

## 고정 데이터 흐름

1. `prepare-current --output .data/corpus-updates/<update-id>`가 전체 허용 목록과 삭제 feed를 읽어 정규화 문서, 원문, 변경 목록과 기준 content snapshot을 기록한다. DB는 읽기만 하고 advisory lock과 Storage write를 사용하지 않는다.
2. `generate-cache --bundle <dir>`가 현재 정상 벡터를 ID·본문 SHA로 재사용하고 새·변경 본문만 NIM으로 생성한다. 변화가 없고 coverage가 정상이면 종료한다.
3. `apply-prepared --bundle <dir>`가 bundle checksum을 검사하고 raw를 불변 Storage 경로에 올린 뒤 기존 writer run lock을 얻는다. 기준 snapshot이 다르면 gate를 건드리지 않고 실패한다.
4. Tx A가 `corpus.search_ready=false`, `reason=corpus_publish`, `update_id`를 commit한다. 65초 drain 뒤 Tx B가 변경분을 100행씩 처리하되 commit은 한 번만 한다.
5. Tx B는 coverage, source SHA, 512차원, L2 norm, parser/profile/temporal 계약을 검사하고 마지막에 profile과 gate를 활성화한다. 실패하면 Tx B 전체는 rollback되고 Tx A의 gate=false는 남는다.

로컬 `embeddings.jsonl`은 준비·운반 계층이다. 웹/API runtime은 로컬 bundle을 읽지 않고 DB에 검증·commit된
활성 `provision_embeddings`만 검색한다. 기존 DB 벡터는 점검 전까지 서비스되고 새 로컬 벡터는 Tx B에서
DB에 복사된 뒤에만 사용자 검색에 사용된다.

`base_snapshot_id`는 runtime content ID가 아니라 stale publish 방지용 지문이다. 조문 내용과 함께
`effective_to`, lifecycle·source 상태, raw SHA와 조문 ordinal 등 writer가 변경할 수 있는 저장 필드를
포함한다.

## 검증

- 준비 실패·불완전 bundle/cache·base mismatch·writer lock 충돌은 gate 변경 전에 실패한다.
- gate=false이면 검색·질문·조문 조회가 provider와 retrieval 전에 `503 corpus_unready`를 반환한다.
- 운영 reader 검색 SQL에는 `pg_advisory_xact_lock_shared`가 없고 실험 D에는 남아 있다.
- 문서·삭제·vector·검증 단계별 실패에서 Tx B 전체 rollback과 gate=false를 확인한다.
- 빈 테스트 PostgreSQL만 사용하며 운영 DB와 실제 평가 dataset은 실행하지 않는다.

## 검증 결과

- API/core: `529 passed, 2 skipped`
- collector: `86 passed, 5 skipped`
- Ruff: API/core와 collector 전체 통과
- 문서 검사: `92 files` 통과
- workflow YAML: CI와 sync-corpus 파싱 통과
- 로컬에서 `CORPUS_PUBLISH_TEST_DATABASE_URL`이 없어 PostgreSQL publisher 통합 5건은 skip했다. CI의 전용
  PostgreSQL service에는 이 변수를 연결해 실제 Tx B rollback과 session lock 해제를 실행한다.
- 운영 DB write, 실제 법률 dataset, Open API, NIM, Storage 호출은 실행하지 않았다.
- 기존 미커밋 `AGENTS.md`는 보존하고 모든 커밋에서 제외했다.

## 커밋 단위

1. `5fa8508` 운영 reader shared lock 제거
2. `4fed6de` 로컬 준비 bundle과 테스트
3. `2a6caac` 원자 publisher·embedding cache·workflow와 테스트
4. 권위 문서·learning·완료 계획

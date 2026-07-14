# Law RAG Collector

웹/API 프로세스와 분리되어 같은 서버의 OS 스케줄러가 실행하는 수집 전용 프로젝트다. 법률 데이터는 국가법령정보 공동활용 Open API만 사용하며 JSON을 먼저 검증하고 스키마가 맞지 않을 때만 XML로 폴백한다.

## 실행

저장소 루트에서 환경변수 `LAW_OPEN_API_OC`를 주입한 뒤 실행한다. 비밀값을 명령행 인자로 넘기거나 저장소에 기록하지 않는다.

```powershell
uv sync --project apps/collector
uv run --project apps/collector law-rag-collector sync-current
uv run --project apps/collector law-rag-collector sync-history
uv run --project apps/collector law-rag-collector status
```

한 문서의 계약만 점검할 때는 허용 목록의 정확 명칭을 지정한다.

```powershell
uv run --project apps/collector law-rag-collector sync-history --title "전기사업법"
```

현재 저장소 어댑터는 `.collector-state/`에 원문과 활성 manifest를 보존하는 목업이다. `sync-history`는 최초 시행부터 현재까지 연혁 목록을 조회하고 다음 버전 시행일 전날을 `effective_to`로 기록한다.

수집한 버전은 정확 명칭·안정 ID·MST·시행일·고유 조문 경로·원문 SHA-256 검증을 모두 통과한 직후 활성 manifest에 반영한다. 시행예정 버전은 `scheduled`, 법적 폐지는 `abolished`로 보존한다. Open API의 삭제 표식은 법적 상태와 분리해 `source_record_state=deleted`로 기록한다. 선택 필드인 소관부처가 없어도 수집할 수 있지만 시행일 같은 버전 필드가 없으면 승격하지 않는다.

`sync-history`는 본문 연혁 수집 뒤 공식 삭제 데이터 목록 `lawSearch.do?target=delHst`를 `knd=1` 법령과 `knd=2` 행정규칙으로 각각 조회한다. 최초 실행은 오늘을 포함한 최근 8일, 이후에는 마지막 **삭제 동기화 성공일 하루 전**부터 오늘까지 겹쳐 조회한다. `display=100` 페이지를 끝까지 읽으며 JSON을 우선 검증하고 스키마가 맞지 않을 때만 같은 페이지를 XML로 폴백한다.

두 종류의 삭제 목록 조회가 모두 성공해야 일련번호와 manifest의 MST가 같은 허용 코퍼스 버전을 한 번에 반영한다. 해당 버전은 `source_record_state=deleted`, `source_deleted_on=삭제일자`가 되며 법적 효력 상태와 `effective_to`는 바꾸지 않는다. 원문은 보존하지만 출처에서 다시 확인할 수 없는 레코드는 답변 검색에서 격리한다. 어느 한 조회나 manifest 교체라도 실패하면 삭제 상태와 성공 체크포인트를 전혀 바꾸지 않고 실행 실패로 기록한다. 따라서 다음 주기나 수동 재실행이 같은 기간을 안전하게 다시 조회한다.

로컬 실행 시 설정은 `.env`를 먼저 읽고 `.env.local`로 덮어쓴다. OS·클라우드가 직접 주입한 환경변수는 두 파일보다 우선한다. 비밀값이 있는 `.env.local`은 Git에 커밋하지 않는다.

원문은 SHA-256이 포함된 불변 경로에 먼저 원자적으로 기록하고, manifest는 같은 디렉터리의 임시 파일을 `fsync`한 다음 원자 교체한다. 검증이나 교체가 실패하면 직전 manifest와 그것이 가리키는 원문은 변하지 않는다. 실패한 버전은 실행 상태에만 기록되며 다른 검증 성공 버전의 즉시 반영을 막지 않는다. 같은 버전과 SHA-256을 다시 수집하면 `unchanged`로 처리한다.

## Windows 작업 스케줄러

먼저 수동 실행으로 API 등록 IP와 환경변수를 검증한다.

```powershell
./apps/collector/ops/Invoke-Collector.ps1 -Command sync-history
```

검증 후 운영자가 명시적으로 등록·해제한다. 이 저장소의 설치나 테스트는 작업을 자동 등록하지 않는다.

```powershell
./apps/collector/ops/Register-CollectorTask.ps1
./apps/collector/ops/Unregister-CollectorTask.ps1
```

기본 일정은 매주 일요일 03:17이며 중복 실행을 차단한다. 향후 같은 서버를 클라우드로 옮길 때 법제처에 해당 서버의 고정 공인 출구 IP를 등록하고 OS 비밀 저장소에 `LAW_OPEN_API_OC`를 주입해야 한다.

## 주간 운영과 실패 복구

1. 매주 일요일 예약된 `sync-history`가 실행된다.
2. 각 버전은 독립 검증되고 성공 즉시 활성 manifest에 원자 승격된다.
3. 종료 후 `law-rag-collector status`에서 `last_run.failed`, `deletion_sync.completed_on`, 대상별 버전 수를 확인한다.
4. 실패가 있으면 비밀이나 원문 전문을 로그에 출력하지 말고 실패 유형과 API 상태만 확인한다.
5. 원인을 수정한 뒤 같은 명령을 재실행한다. 이미 반영된 SHA는 중복 생성되지 않는다.

삭제 목록 실패 시 `deletion_sync.completed_on`은 전진하지 않는다. manifest 교체 실패 시 임시 파일은 정리되고 직전 manifest가 유지되므로 수동으로 이전 파일을 복사할 필요가 없다. 장애 확인 중에는 `.collector-state/raw`의 고아 SHA 객체를 삭제하지 않는다. 활성 manifest에 연결되지 않은 객체의 정리는 향후 별도 보존 정책과 검사 도구를 도입한 뒤 수행한다.

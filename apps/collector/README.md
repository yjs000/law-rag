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

현재 저장소 어댑터는 `.collector-state/`에 원문과 manifest를 보존하는 목업이다. MST와 SHA-256이 같은 재수집은 `unchanged`로 처리한다. `sync-history`는 최초 시행부터 현재까지 연혁 목록을 조회하고 다음 버전 시행일 전날을 `effective_to`로 기록한다.

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

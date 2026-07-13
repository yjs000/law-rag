# 05. 독립 수집기와 시간 효력

## 개념

`apps/collector`는 사용자 요청을 처리하는 API와 실행 수명주기가 다른 배치 프로그램이다. `sync-current`, `sync-history`, `status` 명령을 제공하며 같은 서버의 OS 스케줄러가 별도 프로세스로 실행한다.

법령 연혁 목록은 실제 Open API 계약에 맞춰 `lawSearch.do?target=eflaw&nw=1`로 조회한다. 현행 진단은 `nw=3`, 행정규칙 연혁은 `target=admrul&nw=2`를 사용한다. `lsHstInf`와 `lsJoHstInf`는 각각 변경 법령·조문 변경 이력을 확인하는 별도 계약으로 유지한다.

버전 키는 안정 ID, MST, 시행일의 조합이다. 같은 MST가 여러 시행일에 노출되거나 같은 시행일에 복수 MST가 있어도 원문 스냅샷을 잃지 않는다. 효력 종료일은 다음 **서로 다른** 시행일의 전날로 계산한다.

## 왜 선택했는가

- 웹 재시작과 장시간 수집 작업의 실패 범위를 분리한다.
- 고정 공인 출구 IP가 등록된 한 서버에서만 Open API를 호출한다.
- JSON을 우선 사용하고 응답 스키마가 맞지 않을 때만 XML로 폴백한다. 인증·4xx·네트워크 장애는 포맷 폴백으로 숨기지 않는다.
- 버전 키와 원문 SHA-256을 함께 사용해 재실행 시 중복 저장을 막고 변경 원문만 승격한다.
- 목록의 시행일과 본문 메타데이터가 다르면 연혁 목록의 조회 기준일을 해당 스냅샷의 효력 시작일로 보존한다.

## 데이터 흐름

```text
OS scheduler -> collector CLI -> JSON request -> domain validation
                                      | schema failure only
                                      v
                                  XML fallback
                                      |
                      exact title + kind + MST validation
                                      |
              raw file + version manifest + run status upsert
                                      |
                       API mock repository state load
```

실제 등록 IP 환경의 smoke 실행에서 MVP 9개 문서의 현행 JSON 수집이 모두 성공했다. 최초 시행까지 연혁을 수집한 목업 manifest에는 9개 문서, 235개 버전 스냅샷이 기록됐고 마지막 보정 실행의 실패는 0건이었다. 이 산출물은 `.data/` 아래의 커밋 제외 로컬 검증 자료이며 비밀 OC 값은 URL과 상태 파일에 기록하지 않는다.

## 직접 실행할 명령

```powershell
uv sync --project apps/collector
uv run --project apps/collector pytest
uv run --project apps/collector ruff check .
uv run --project apps/collector law-rag-collector status
./apps/collector/ops/Invoke-Collector.ps1 -Command sync-history
```

작업 스케줄러 등록 스크립트는 운영자가 수동 수집 성공을 확인한 다음에만 실행한다.

## 다음 학습 주제

- 목업 manifest를 Supabase 트랜잭션과 Storage 원문 객체로 승격하는 방법
- 삭제 API와 폐지 상태를 버전 모델에 반영하는 방법
- 대량 연혁 수집의 rate limit, 체크포인트, 재개 전략
- 동일 시행일 복수 버전과 부칙별 시행일을 질의 시점에 해석하는 방법

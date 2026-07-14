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
- 주 1회 실행하되 검증 성공 버전은 별도 승인 대기 없이 즉시 활성 manifest에 승격한다. 한 버전의 실패는 직전 정상 상태와 다른 성공 버전을 막지 않는다.

## 데이터 흐름

```text
OS scheduler -> collector CLI -> JSON request -> domain validation
                                      | schema failure only
                                      v
                                  XML fallback
                                      |
                      exact title + kind + MST validation
                                      |
         SHA-addressed raw file -> validated version manifest
                                      |
                       temporary file + fsync + atomic replace
                                      |
                       API mock repository state load
```

활성화 게이트는 정확 명칭과 파서 검증 이후 출처 ID, MST, 시행일, 조문 경로 유일성, 비어 있지 않은 조문, 원문 포맷과 SHA-256 일치를 다시 확인한다. 선택 필드인 소관부처는 없어도 허용한다. 시행예정·법적 폐지 상태, Open API 레코드 가용성과 부칙 존재 여부는 서로 구분해 manifest 메타데이터로 남긴다.

Open API 레코드 삭제는 본문 파싱만으로 완전하게 알 수 없으므로 공식 `delHst` 목록을 별도 증분 스트림으로 취급한다. 법령(`knd=1`)과 행정규칙(`knd=2`)을 모두 받아야 한 manifest 트랜잭션에서 일련번호와 MST를 연결한다. `delHst`는 법적 폐지나 삭제 사유를 제공하지 않으므로 효력 종료일을 추론하지 않고 출처 레코드 상태만 `deleted`로 기록한다. 허용 코퍼스에 없는 일련번호는 무시한다.

첫 실행은 최근 8일을 조회하고 이후에는 마지막 삭제 동기화 성공일보다 하루 앞에서 다시 시작한다. 겹침 조회와 MST 기반 멱등 처리가 경계 시각 누락을 줄인다. 둘 중 한 목록이라도 실패하면 삭제 변경과 체크포인트를 함께 보류하므로 다음 실행이 같은 범위를 재시도한다. 각 페이지는 JSON 우선·XML 스키마 폴백 정책을 그대로 적용한다.

API 목업 저장소는 시행예정 버전을 기준일 필터로 제한한다. 법적 폐지 `abolished`와 출처 레코드 삭제 `source_record_state=deleted`는 서로 다른 축으로 저장하지만, 둘 다 현재 답변 근거에서는 제외한다. 출처 삭제 원문은 감사와 복구 판단을 위해 보존하며, 이전 연혁 버전은 법적 근거로 계산된 `effective_to`까지 과거 기준일 검색에 남는다.

manifest와 원문을 같은 이름으로 덮어쓰면 manifest 교체 직전 장애가 발생했을 때 이전 manifest가 새 원문을 가리킬 수 있다. 이를 막기 위해 원문 파일명에 SHA-256을 넣어 불변 객체로 저장한다. 새 manifest를 임시 파일에 완전히 쓰고 `fsync`한 후 원자 교체하므로 교체 실패 시 이전 manifest와 이전 SHA 원문 조합이 유지된다.

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

기본 운영 주기는 매주 일요일 03:17이다. 실행이 일부 실패하면 `status`의 실패 유형과 `deletion_sync.completed_on`을 확인하고 같은 `sync-history` 명령을 재실행한다. 성공한 동일 SHA와 이미 삭제 처리된 MST는 `unchanged`가 되며 실패한 버전만 다시 승격을 시도한다. 활성 manifest에 연결되지 않은 원문 객체는 즉시 삭제하지 않고 후속 무결성 검사·보존 정책에서 정리한다.

## 다음 학습 주제

- 목업 manifest를 Supabase 트랜잭션과 Storage 원문 객체로 승격하는 방법
- 삭제 목록의 장기 미수집·복구 범위를 관측하고 경고하는 방법
- 대량 연혁 수집의 rate limit, 체크포인트, 재개 전략
- 동일 시행일 복수 버전과 부칙별 시행일을 질의 시점에 해석하는 방법

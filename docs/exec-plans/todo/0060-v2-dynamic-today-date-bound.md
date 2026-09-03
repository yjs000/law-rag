> 작업 ID: `B-003`
> 상태: `Todo`
> 유형: `Bug`
> 보조 라벨: `Data`, `UX`
> 선행 조건: [F-005 V2 LlamaIndex 프레임워크 파이프라인 개편](../../design-docs/v2-llamaindex-framework-redesign.md)의 실행계획에서 v2 temporal adapter 경계를 확정해야 한다.
> 다음 행동: v2 temporal adapter 경계를 확정한다.
> 참고 범위:
> - `apps/api/app/domain/corpus_temporal_contract.py` L23-L59 — KST today와 지원 범위 검사 계약
> - `apps/api/app/adapters/postgres_repository.py` L577-L579 — 지원 상한을 주입받는 repository port 구현
> - `apps/web/app/page.tsx` L850-L856 — date input의 현재 KST today 상한

# 0060: V2 기준일 지원 상한을 한국 날짜 today로 동적 계산

상태: `확정됨, 미착수 (2026-08-27)`

## 배경

사용자는 기준일 filter가 특정 시작일과 특정 종료일 사이로 고정되지 않고, 지원 시작일부터 요청 시점의
오늘까지 열리도록 변경하라고 결정했다. 공통 API domain과 Web은 이미 `korea_today()`를 사용하는 경로가
있지만, F-005의 v2 Router·QueryEngine·generation 개편 과정에서 고정된 종료일이나 snapshot 생성일을
지원 상한으로 다시 사용하지 않는지 전체 v2 경로를 확인해야 한다.

이 작업에서 말하는 `today`는 서버 로컬 날짜나 UTC 날짜가 아니라 제품 계약인 UTC+9 한국 날짜다.

## 목표

v2의 사용자 요청 가능 기준일 범위를 다음 동적 계약 하나로 통일한다.

```text
supported_as_of_from = 현재 canonical corpus에서 계산한 지원 시작일
supported_as_of_through = TodayProvider.today(Asia/Seoul)

supported_as_of_from <= requested_as_of_date <= supported_as_of_through
```

종료일을 설정 파일, migration, generation metadata, prompt 또는 UI 상수에 날짜 literal로 하드코딩하지
않는다. `TodayProvider` 또는 동등한 clock port를 application 경계에 주입해 테스트에서 날짜를 고정할 수
있게 한다.

## 포함 범위

- F-005로 개편되는 v2 API, Router execution context, QueryEngine filter, active generation metadata와
  Web date input에서 지원 상한의 출처를 감사한다.
- 지원 시작일은 canonical corpus에서 계산된 값으로 유지하고, 지원 종료일만 요청 시점의 KST today로
  계산한다.
- 날짜가 생략된 요청의 기본값도 같은 KST today provider를 사용한다.
- 미래 날짜는 embedding·retrieval·generation 전에 기존 안정 오류 `422 unsupported_corpus_date`로
  거부한다.
- 자정 경계, 서버 timezone이 KST가 아닌 경우, 월말·연말, 윤일과 clock 주입을 회귀 테스트한다.
- API가 노출하는 `supported_as_of_through`와 Web date input `max`가 같은 날짜를 사용하는지 계약 테스트한다.
- source나 generation snapshot이 바뀌지 않아도 날짜가 바뀌면 상한이 새 today로 전진하는지 검사한다.

## 비범위

- 조문 자체의 법적 효력식
  `effective_from <= requested_as_of_date AND (effective_to IS NULL OR requested_as_of_date < effective_to)` 변경
- `effective_to`를 today로 덮어쓰거나 open-ended 법령 버전을 닫는 작업
- 과거 기준일 질문 제거: 사용자는 지원 시작일부터 오늘 사이의 날짜를 계속 선택할 수 있다.
- 평가셋·gold·snapshot manifest의 재현용 고정 `as_of_date` 변경
- v1 동작 변경: 현재 v1의 동적 KST today 계약은 회귀 기준으로만 사용한다.
- 브라우저나 서버의 로컬 timezone을 신뢰하는 구현

## 문제 상황·원인·해결

| 문제 상황 | 원인 | 해결 |
|---|---|---|
| 새 날짜가 되어도 선택 가능한 종료일이 과거에 머묾 | 고정 종료일 또는 snapshot 날짜 재사용 | 주입된 KST `TodayProvider`에서 매 요청 계산 |
| API와 UI의 최대 날짜가 다름 | 서로 다른 clock/timezone 사용 | 동일한 KST 날짜 계약과 API 상태값으로 정렬 |
| 법적 `effective_to`와 corpus 지원 상한이 섞임 | 서로 다른 두 시간 개념의 경계 불명확 | node 효력식은 유지하고 사용자 지원 상한만 today로 계산 |
| 테스트가 실제 시계에 따라 불안정함 | 정적 clock port 없음 | fake `TodayProvider`를 주입해 경계일 고정 |

## 완료 조건

- v2 runtime 경로에 지원 종료일 날짜 literal이 없고 KST today provider 하나에서 상한을 얻는다.
- 지원 시작일과 today 양끝을 포함하고, 시작일 이전과 today 이후를 거부하는 테스트가 통과한다.
- API, QueryEngine execution context와 Web date input이 같은 supported-through 날짜를 사용한다.
- 조문 `effective_from`/`effective_to` 반개구간 검색 회귀가 유지된다.
- 평가·gold fixture의 고정 기준일이 runtime 변경에 의해 수정되지 않는다.
- embedding이나 LLM 호출 전에 미래 날짜가 거부되는 통합 테스트가 통과한다.

## 승격 조건

F-005 실행계획을 작성할 때 이 작업을 같은 milestone의 temporal contract task로 포함할지, 독립된 선행
bugfix로 먼저 수행할지 결정한다. 어느 경우에도 B-003의 완료 조건을 F-005 구현 검증에서 추적한다.

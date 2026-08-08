# 실행 계획 운영법

실행 계획 생성 여부, 작성 절차 및 implementation workflow는 설치된 Superpowers의 현재 planning 관련
skill을 따른다. 이 문서는 plan이 필요한지 다시 판단하지 않는다.

이 문서의 역할은 law-rag repository 안에서 실행 계획의 저장 위치, 상태 lifecycle,
repository-specific metadata를 정의하는 것이다.

## 위치

- 사용자 제안·미착수: docs/exec-plans/todo/
- 진행 중: docs/exec-plans/active/
- 완료: docs/exec-plans/completed/
- 알려진 장기 부채: docs/exec-plans/tech-debt-tracker.md

## 작업 상태 계약

- 사용자가 다음 작업·추후 개선안으로 명시했지만 아직 착수하지 않은 일은 `todo/`에 등록한다.
- 사용자가 착수를 요청하고 범위·완료 조건·외부 병목 점검이 끝나면 같은 번호와 파일명을 유지한 채
  `todo/`에서 `active/`로 이동한다.
- 구현과 요구 검증이 끝나면 실제 결과와 잔여 작업을 기록하고 같은 파일을 `completed/`로 이동한다.
- `tech-debt-tracker.md`는 관찰된 결함·위험 원장이다. 부채 해결을 다음 작업으로 선택하더라도 TD 항목은
  원장에 유지하고 TODO 또는 active 계획에서 연결한다.
- GitHub 프로젝트 `Backlog`은 외부 이슈 상태다. 저장소 TODO와 자동 동기화하지 않으며 사용자가 요청한
  경우에만 이슈를 만들거나 상태를 변경한다.

## 기존 계획의 섹션 형식 (repository-specific metadata)

`0001`~`0034`의 기존 exec-plan은 다음 8섹션 형식을 따른다. 이 형식은 plan 생성 여부나 작성 절차를
정의하는 게 아니라, 이 저장소에 이미 쌓인 계획들의 metadata 구조를 기록한 것이다 — 기존 계획을
읽거나 갱신할 때는 이 구조를 유지한다.

1. 목적과 사용자 결과
2. 범위와 비범위
3. 측정 가능한 완료 조건
4. 순서 있는 단계와 체크리스트
5. 검증 및 롤백
6. 결정 로그
7. 날짜가 포함된 진행 기록
8. 미결정과 차단 요소

**새로 작성하는 계획은 이 형식을 강제하지 않는다.** Superpowers `writing-plans`가 만드는 현재 plan
템플릿을 그대로 쓴다 — 저장 위치(`docs/exec-plans/active/`)와 상태 lifecycle만 이 문서를 따르고,
내부 형식은 Superpowers가 결정한다.

계획은 살아 있는 문서다. 작업 중 체크박스, 발견, 결정, 범위 변화를 갱신한다. 완료 후 실제 결과, 검증 증거, 남은 부채를 기록하고 completed/로 이동한다. 현재 작업에서 새로 나온 비차단 아이디어는 현재 범위를 넓히지 않고 사용자가 후속 작업으로 채택했을 때만 todo/에 등록한다.

# 실행 계획 운영법

실행 계획 생성 여부, 작성 절차 및 implementation workflow는 설치된 Superpowers의 현재 planning 관련
skill을 따른다. 이 문서는 plan이 필요한지 다시 판단하지 않는다.

## 로드맵 정본과 최소 읽기

실행계획 파일의 상단 메타데이터가 상태·유형·제목·다음 행동·참고 범위의 유일한 정본이다. `docs/ROADMAP.md`는
그 헤더에서 생성되는 색인이므로 직접 편집하지 않고, 헤더를 바꾼 뒤 `python scripts/render_roadmap.py`로
재생성한다. `docs/exec-plans/{todo,active,completed}/README.md`는 artifact 위치를 안내하는 lifecycle README
navigation일 뿐 상태 정본이 아니다.

시작·재개·상태 전이 시 project-scoped [`roadmap-operator`](../.codex/skills/roadmap-operator/SKILL.md)의 네 가지
순서를 따른다: `docs/CURRENT_STATE.md` L1-L28과 생성된 roadmap의 마지막 비완료 행, 선택한 계획의 상단
메타데이터, 그 헤더의 명시된 참고 범위. 다른 계획 본문·완료 계획·전체 아키텍처는 기본적으로 읽지 않는다.
범위 밖 문맥이 반드시 필요하면 읽기 전에 경로, 시작줄, 끝줄, 이유를 선언하고 사용자에게 알리거나 작업 기록에
남긴다. 상태 전이 전후에는 읽은 범위를 같은 형식으로 간결하게 보고한다.

이 문서의 역할은 law-rag repository 안에서 실행 계획의 저장 위치, 상태 lifecycle,
repository-specific metadata를 정의하는 것이다.

## 위치

- 사용자 제안·미착수: docs/exec-plans/todo/
- 진행 중: docs/exec-plans/active/
- 완료: docs/exec-plans/completed/
- 알려진 장기 부채: docs/exec-plans/tech-debt-tracker.md

## 작업 관리 메타데이터

새 실행계획과 상태가 전이되는 실행계획의 상단에는 다음 색인 필드를 둔다.

```md
> 작업 ID: `F-001`
> 상태: `Todo`
> 유형: `Feature`
> 보조 라벨: `Data`, `Evaluation`
> 선행 조건: 없음
> 다음 행동: 요구사항별 회귀 테스트부터 시작
> 참고 범위:
> - `apps/api/app/history.py` L42-L118 — 현재 이력 경계
> - `docs/product-specs/history.md` L15-L38 — 사용자 요구
```

- 상태는 `Todo`, `Picked Up`, `Blocked`, `Done` 중 하나다.
  - `Todo`: 선행 조건이 충족됐지만 아직 착수하지 않은 milestone.
  - `Picked Up`: 현재 주 에이전트가 수행 중인 유일한 milestone. 없을 수는 있지만 둘 이상일 수 없다.
  - `Blocked`: 사용자 승인, credential, 운영환경 등 외부 입력을 기다리는 milestone. 본문에 차단 사유와
    재개 조건을 반드시 남긴다.
  - `Done`: 구현·검증·상태 문서 갱신까지 끝난 milestone.
- 유형은 `Feature`, `Bug`, `Tech Debt`, `Experiment`, `Operations`, `Documentation` 중 정확히 하나다.
- 보조 라벨은 선택 사항이며 `Security`, `Reliability`, `Performance`, `Data`, `UX`, `Evaluation`만
  사용한다. 새 보조 라벨은 필요한 실제 분류가 생겼을 때 이 문서를 먼저 갱신해 추가한다.
- 작업 ID는 유형별 독립 시퀀스이며 접두사는 다음과 같다.
  - `Feature`: `F-001`
  - `Bug`: `B-001`
  - `Tech Debt`: `TD-001`
  - `Experiment`: `E-001`
  - `Operations`: `O-001`
  - `Documentation`: `DOC-001`
  파일명의 기존 숫자 계획 ID는 바꾸지 않는다. 기존 `D-*` 로드맵 ID는 역사 식별자로 보존하며 새 ID로
  소급 변환하지 않는다.
- `참고 범위`의 각 항목은 저장소 상대 경로, 시작·끝 줄, 그 범위를 읽는 이유를 가진다. 줄을 고정 계약으로
  사용하지 않으며, 해당 참조 파일 또는 계획을 수정하는 작업에서만 범위를 갱신한다. 안정적인 설계·결정
  위치에는 섹션 앵커 링크를 우선할 수 있다.

## 작업 상태 계약

실행계획 디렉터리(`todo/`, `active/`, `completed/`)는 계획 artifact의 lifecycle을 보존하고, 문서 상단
`상태`는 현재 milestone의 운영 상태를 나타낸다.

- 사용자가 다음 작업·추후 개선안으로 명시했지만 아직 착수하지 않은 일은 `todo/`에 등록한다.
- 사용자가 착수를 요청하고 범위·완료 조건·외부 병목 점검이 끝나면 같은 번호와 파일명을 유지한 채
  `todo/`에서 `active/`로 이동한다.
- 구현과 요구 검증이 끝나면 실제 결과와 잔여 작업을 기록하고 같은 파일을 `completed/`로 이동한다.
- 진행 기록이 있는 계획이라도 다음 milestone이 아직 시작되지 않았다면 상단 상태는 `Todo`로 둘 수 있다.
- 정책 도입 시 초기 이행은 현재 `todo/`와 `active/` 계획에만 적용한다. 완료된 계획은 새 작업이
  완료되거나 수정될 때부터 적용하며, 완료 계획 전체를 새 메타데이터로 일괄 라벨링하지 않는다.
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

**새로 작성하는 계획의 본문 형식은 Superpowers가 결정한다.** `writing-plans`가 만드는 현재 plan
템플릿을 본문에 그대로 쓴다 — Superpowers가 결정하는 것은 본문 템플릿뿐이며, 위 여섯 필드 헤더는
모든 새 계획과 상태가 전이되는 계획에 항상 필수다. 저장 위치(`docs/exec-plans/active/`)와 상태
lifecycle은 이 문서를 따른다.

계획은 살아 있는 문서다. 작업 중 체크박스, 발견, 결정, 범위 변화를 갱신한다. 완료 후 실제 결과, 검증 증거, 남은 부채를 기록하고 completed/로 이동한다. 현재 작업에서 새로 나온 비차단 아이디어는 현재 범위를 넓히지 않고 사용자가 후속 작업으로 채택했을 때만 todo/에 등록한다.

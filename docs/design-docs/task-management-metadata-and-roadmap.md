# 작업 관리 메타데이터와 얇은 로드맵

상태: 승인

## 목적

실행계획과 로드맵을 읽는 에이전트·기여자가 현재 하나의 우선 작업, 대기 사유, 다음 후보를 짧은
문맥으로 판단하게 한다. 상세 범위·결정·검증 증거는 각 작업 문서 한 곳에만 보관해 상태 문서 간
복제를 없앤다.

## 적용 범위

- 적용 대상은 `docs/ROADMAP.md`, `docs/PLANS.md`, `docs/GITHUB_WORKFLOW.md`,
  `docs/exec-plans/{todo,active,completed}/`의 인덱스와 개별 실행계획이다.
- 설계 문서, 제품 명세, 학습 문서에는 이 메타데이터를 붙이지 않는다.
- GitHub Issue/Project와 저장소 문서는 자동 동기화하지 않는다. 이 문서는 사람이 두 시스템에서 같은
  유형 용어를 사용할 수 있게만 한다.

## 메타데이터 계약

새 실행계획과 상태가 전이되는 실행계획의 상단에는 다음 항목을 둔다.

```md
> 작업 ID: `F-001`
> 상태: `Todo`
> 유형: `Feature`
> 보조 라벨: `Data`, `Evaluation`
> 선행 조건: 없음
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
- 작업 ID는 유형별 독립 시퀀스다: `F-001`, `B-001`, `TD-001`, `E-001`, `O-001`, `DOC-001`.
  파일명의 기존 숫자 계획 ID는 바꾸지 않는다. 기존 `D-*` 로드맵 ID는 역사 식별자로 보존하며 새 ID로
  소급 변환하지 않는다.
- `참고 범위`의 각 항목은 저장소 상대 경로, 시작·끝 줄, 그 범위를 읽는 이유를 가진다. 줄을 고정 계약으로
  사용하지 않으며, 해당 참조 파일 또는 계획을 수정하는 작업에서만 범위를 갱신한다. 안정적인 설계·결정
  위치에는 섹션 앵커 링크를 우선할 수 있다.

## 로드맵과 실행계획의 역할

`docs/ROADMAP.md`는 `Picked Up`, `Todo`, `Blocked`, `Done` 순서의 링크 색인이다. 각 항목에는 작업 ID,
유형, 한 줄 결과 또는 다음 행동, 권위 실행계획 링크만 둔다. 범위, 담당, 수정 파일, 완료 조건, 검증 결과,
차단의 상세 사유는 로드맵에 복사하지 않는다.

`Done`에는 최근 10개 항목만 두고, 이전 완료 항목은 `docs/exec-plans/completed/README.md`의 연도/분기
인덱스로 이동한다. 이 규칙은 로드맵을 세션 시작용 얇은 색인으로 유지한다.

`docs/CURRENT_STATE.md`는 먼저 로드맵의 `Picked Up`을 가리킨다. `Picked Up`이 없으면 `Todo`의 첫
항목을 가리킨다. 세션 시작에서 로드맵 전체나 모든 실행계획을 읽지 않는다.

## 상태 전이와 이행

실행계획 디렉터리(`todo/`, `active/`, `completed/`)는 계획 artifact의 lifecycle을 보존하고, 문서 상단
`상태`는 현재 milestone의 운영 상태를 나타낸다. 진행 기록이 있는 계획의 다음 milestone이 아직
시작되지 않았다면 그 상태는 `Todo`일 수 있다.

정책 도입 시에는 현재 `todo/`와 `active/`의 개별 계획에만 메타데이터를 보강한다. 완료된 계획은 새
작업이 완료되거나 수정될 때부터 적용하며, 역사 문서 전체를 일괄 편집하지 않는다.

## GitHub 라벨 매핑

GitHub 이슈에는 유형 라벨을 하나만 둔다. 저장소 유형과 각각 `type: feature`, `type: bug`,
`type: tech-debt`, `type: experiment`, `type: operations`, `type: docs`로 대응한다. 상태는 GitHub Project
필드가 권위이고, `status: blocked`는 저장소의 `Blocked`와 같은 차단 사유·재개 조건이 이슈 본문 또는
댓글에 있을 때만 추가한다.

## 검증

- 로드맵에 `Picked Up` 항목이 0개 또는 1개인지 확인한다.
- 현재 `todo/`와 `active/` 계획에 필수 메타데이터와 단일 유형이 있는지 검사한다.
- 로드맵의 모든 링크와 완료 인덱스 링크를 검사한다.
- `git diff --check`로 Markdown 공백 오류를 검사한다.

## 결정 기록

- 2026-08-25: 로드맵은 상세 상태를 복사하지 않는 링크 색인으로 제한한다. 세션 문맥과 갱신 비용을
  낮추면서 각 실행계획을 단일 권위 원본으로 유지하기 위해서다.
- 2026-08-25: 상태와 계획 artifact 디렉터리를 분리한다. 진행 기록을 보존하면서도 실제로 Picked Up인
  milestone을 하나로 제한하기 위해서다.
- 2026-08-25: 완료 문서는 소급 라벨링하지 않는다. 역사 문서의 대규모 변환보다 이후 전이 시점의 정확한
  메타데이터를 우선한다.
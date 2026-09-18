> 작업 ID: `OC-001`
> 상태: `Done`
> 유형: `Orchestration`
> 보조 라벨: `Reliability`, `UX`
> 선행 조건: 없음
> 다음 행동: 없음 — 여섯 자식 모두 Done·completed/이고 통합·전체 검증이 완료됨.
> 참고 범위:
> - `docs/design-docs/roadmap-dropped-and-orchestration.md` L72-L156 — OC-001 자식·파동·상태 전이·완료 계약
> - `docs/exec-plans/completed/0065-remove-checklist-export-frontend.md` L1-L9 — 완료된 P1 자식(F-007)의 완료 기록
> - `docs/exec-plans/completed/0077-elementary-plain-language-prompt-refinement.md` L1-L11 — 완료된 P1 병렬 자식의 범위와 결과

# OC-001: 우선순위 로드맵 병렬 오케스트레이션

## 목표

구현 준비가 끝난 비실험 작업 여섯 개를 우선순위와 선행 관계에 따라 실행한다. 서로 소유 범위가 겹치지
않는 작업은 독립 worktree와 branch에서 동시에 진행하고, 각 자식의 검증·통합 상태를 헤더에서 추적한다.

이 계획은 자식의 제품 동작을 대신 설계하거나 구현하지 않는다. 각 자식 실행계획이 범위와 완료 조건의
정본이며, OC-001은 배정·병렬성·통합 순서·전체 완료 여부만 관리한다.

## 관리 작업

| 우선순위 | 작업 | 역할 | 초기 상태 | 선행 작업 |
| --- | --- | --- | --- | --- |
| P0 | `B-003` | V2 KST today 상한 | 준비 중 | 없음 |
| P0 | `B-008` | 내부 라우팅 문구 비노출 | 준비 중 | 없음 |
| P0 | `B-010` | 한 글자 질문 허용 | 대기 | `B-003`, `B-008` |
| P1 | `F-007` | 체크리스트 내보내기 제거 | 대기 | `B-003`, `B-008`, `B-010` |
| P1 | `F-010` | 쉬운 한국어 프롬프트 | 대기 | `B-003`, `B-008`, `B-010` |
| P1 | `F-009` | NVIDIA 지연 안내와 상단 진행 표시 | 대기 | `F-007` |

`B-009`, `B-001`, `B-002`, `F-002`, 모든 `E-*`와 Dropped 계획은 이 OC의 범위가 아니다.

## 실행 파동

### 1. P0 독립 수정

- 결과: `B-003`과 `B-008`이 서로 다른 worktree에서 동시에 구현·검증되고 통합 대기 상태가 된다.
- 대상: 각 자식 헤더의 `소유 범위`; 공유 roadmap과 계획 메타데이터는 OC 통합 담당자만 수정
- 예상 변경량: 자식 계획의 추정치를 따르며 OC 자체는 상태·진행 기록 약 10~20줄 수정
- 실행 절차: 두 자식을 `실행 중`으로 전이하고 병렬 배정한 뒤 focused 테스트, 리뷰, diff 확인을 각각 수행한다.
- 완료 증거: 두 자식 branch의 검증 결과와 commit이 기록되고 소유 범위 충돌이 없다.
- 의존성: 없음

### 2. P0 통합과 입력 경계 수정

- 결과: 첫 파동을 기준 branch에 통합·검증한 뒤 `B-010`을 독립 실행하고 P0 세 작업을 완료한다.
- 대상: `B-003`, `B-008`, `B-010` 계획과 각 소유 범위
- 예상 변경량: 자식 계획의 추정치를 따르며 OC 진행 기록 약 5~10줄 수정
- 실행 절차: 첫 파동을 한 작업씩 통합하고 전체 충돌을 확인한 뒤 `B-010`을 `준비 중`→`실행 중`으로 전이한다.
- 완료 증거: P0 세 작업이 `Done`이고 관련 Python·Web 회귀 검증이 통과한다.
- 의존성: 실행 파동 1의 두 child commit과 통합 검증

### 3. P1 병렬 수정

- 결과: P0 완료 뒤 `F-007`과 `F-010`을 병렬 실행하고, `F-007` 통합 뒤 `F-009`를 실행한다.
- 대상: 세 P1 자식의 헤더와 소유 범위
- 예상 변경량: 자식 계획의 추정치를 따르며 OC 진행 기록 약 10~20줄 수정
- 실행 절차: `F-007`·`F-010`의 소유 범위 비중첩을 checker로 확인하고 병렬 배정한다. `F-009`는 `F-007` 완료 뒤 시작한다.
- 완료 증거: 세 P1 작업이 `Done`이고 Web·API focused 검증과 통합 검증이 통과한다.
- 의존성: 실행 파동 2 완료, `F-009`는 `F-007` 완료

### 4. OC 전체 완료 판정

- 결과: 여섯 자식의 통합 결과와 최신 전체 검증을 근거로 OC-001을 완료한다.
- 대상: 여섯 자식 계획, `docs/ROADMAP.md`, 이 계획의 진행 기록
- 예상 변경량: 계획 전이·결과 기록 약 15~30줄
- 실행 절차: 미통합 branch와 worktree가 없는지 확인하고 roadmap checker, 문서 검사, Python·Web 전체 검증을 실행한다.
- 완료 증거: 여섯 자식이 모두 `Done`·`completed/`이고 각 commit·통합 순서·검증 결과가 이 계획에 기록돼 있다.
- 의존성: 실행 파동 1~3 완료

## 상태 관리 규칙

- 선행 작업이 모두 Done인 자식만 `준비 중` 이상으로 전이한다.
- worktree와 담당자가 배정되면 `실행 중`, focused 검증과 리뷰 통과 후 `통합 대기`, 기준 branch 반영 후
  `검증 중`으로 전이한다.
- 통합 검증을 통과하면 부모 `오케스트레이션` 연결만 남기고 실행용 OC 필드를 제거한 뒤 자식을
  `Done`으로 바꿔 `completed/`로 이동한다.
- 준비된 자식이 하나라도 있으면 다른 자식의 차단만으로 OC 전체를 Blocked 처리하지 않는다.
- 동시에 실행하는 자식은 최대 세 개이며 통합 담당자 슬롯 하나를 남긴다.

## 권한과 비범위

허용된 변경은 로컬 worktree·branch·문서·제품 코드·테스트와 로컬 commit까지다. 외부 네트워크, 운영 DB,
배포, 원격 push·PR은 이 계획의 승인 범위가 아니다. 자식 작업 실행 전에는 해당 계획의 별도 권한 요구를
다시 확인한다.

## 완료 조건

1. 여섯 자식이 모두 Done이고 `completed/`에 있다.
2. 자식마다 commit, focused 검증, 리뷰, 통합 순서가 기록되어 있다.
3. 동시에 실행된 자식 사이에 소유 범위 충돌이나 미통합 결과가 없다.
4. roadmap checker, 문서 검사, 관련 Python·Web 전체 검증이 최신 실행에서 통과한다.
5. 제품 작업을 추가로 끼워 넣지 않고 확정된 여섯 작업만 완료한다.

## 결과 기록

- B-003(V2 KST today 상한), B-008(내부 라우팅 문구 비노출), B-010(한 글자 질문 허용): 실행 파동 1-2에서
  병렬·순차 통합 완료. `docs/exec-plans/completed/0060-v2-dynamic-today-date-bound.md`,
  `0076-hide-internal-routing-copy-from-limitations.md`,
  `0079-allow-single-character-question-submission.md` 참고.
- F-007(체크리스트 내보내기 프런트 제거): worktree `.worktrees/codex-f007-remove-checklist-export`에서
  구현·검증 후 main merge commit `5bba32d`. web lint/typecheck/test(142)/build 전원 통과.
  `docs/exec-plans/completed/0065-remove-checklist-export-frontend.md` 참고.
- F-009(NVIDIA 무료 티어 지연 안내·finalize 상단 진행 표시): F-007 완료 뒤 worktree
  `.worktrees/codex-f009-nvidia-delay-progress`에서 구현·검증 후 main merge commit `41fbb28`
  (conflict는 completed 계획 파일·ROADMAP.md 재생성으로 해결). web test 147/147, build 통과.
  `docs/exec-plans/completed/0070-nvidia-free-tier-delay-and-sse-progress.md` 참고.
- F-010(쉬운 한국어 프롬프트 정교화): Task 1-2는 worktree `.worktrees/codex-f010-plain-language-prompt`에서
  구현·검증 후 main merge commit `18576c4`(pytest 122 passed). Task 3(대표 출력 실제 NVIDIA 평가)는
  사용자 승인(2026-09-18, "호출진행")을 받아 worktree `.worktrees/codex-f010-task3-eval`에서 실제
  NVIDIA 호출로 6개 대표 문항을 평가했고, 4개(허가·신고·기준일·적용 대상)는 네 기준을 전부 충족했다.
  나머지 2개(clarification, 근거 부족)는 F-010 소유 범위 밖 구조적 한계로 확인되어 사용자 결정(2026-09-18,
  "한계에 대해서는 별도 작업으로 달기")에 따라 완료 조건을 "언어 계약이 적용된 4개 대표 문항 전원 통과,
  2건은 범위 밖 한계로 별도 작업 이관"으로 정정하고 후속 작업
  `docs/exec-plans/todo/0082-clarification-missing-information-allowlist-drops-fields.md`,
  `docs/exec-plans/todo/0083-routing-unavailable-non-deterministic-prompt-compliance.md`으로 분리했다.
  merge commit `06582c1`. `docs/exec-plans/completed/0077-elementary-plain-language-prompt-refinement.md` 참고.
- 통합 HEAD는 main의 최신 merge commit이며, roadmap checker·문서 검사(187 files)·web 전체
  검증(lint/typecheck/test 147/build)이 최신 실행에서 통과했다. 사용한 worktree(F-007/F-009/F-010 계열)는
  병합 확인 후 모두 제거했다.
- OC-001의 여섯 관리 대상(B-003, B-008, B-010, F-007, F-010, F-009)이 모두 `Done`이고 `completed/`에 있다.
  F-010의 Task 3 한계 2건은 별도 Todo 계획으로 명시적으로 이관되었으며 OC-001 범위에는 포함하지 않는다.

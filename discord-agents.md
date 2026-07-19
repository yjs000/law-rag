# Discord 에이전트 오버레이

## 적용 범위와 우선순위

이 문서는 루트 [AGENTS.md](AGENTS.md)를 먼저 읽은 뒤 적용하는 project-local overlay다.

- 적용 대상: Discord thread ID `1528216345924337805`에서 시작한 작업
- 비적용 대상: 다른 Discord thread, Discord DM, 로컬 CLI, 웹, Telegram 등 다른 환경에서 시작한 작업
- 우선순위: 루트 `AGENTS.md`와 프로젝트 권위 문서를 유지하고, 이 문서는 해당 thread의 진행·위임·오류 기록 규칙만 추가한다.
- thread 대화는 요구사항 컨텍스트로 사용할 수 있지만 credential, 개인 사건자료, 법률 원문 전문은 저장소·Git·진행 보고에 복제하지 않는다.

## 작업 시작 계약

주 에이전트는 구현 전에 다음 순서로 진행한다.

1. `git status --short --branch`와 원격 차이를 확인한다.
2. `AGENTS.md`, `ARCHITECTURE.md`, 관련 명세·설계·실행 계획을 읽는다.
3. [Discord 작업 보드](docs/ROADMAP.md)에서 정확히 하나의 milestone만 `Picked Up`인지 확인한다.
4. TODO에 담당, 목적·범위, 수정 가능 파일, 선행 조건, 완료 조건, 검증 방법을 기록한다.
5. 기존 미커밋 변경과 파일·기능 범위가 겹치면 수정·staging·commit을 중단하고 충돌을 보고한다.
6. 사용자만 해결할 수 있는 승인·비밀·운영 병목은 즉시 보고하되, 독립적으로 가능한 작업은 계속한다.

## TODO와 위임

- 작업 순서와 상태의 Discord용 단일 진입점은 `docs/ROADMAP.md`다. 상세 설계와 체크리스트는 `docs/exec-plans/`에 두고 보드에서 링크한다.
- 한 번에 정확히 하나의 milestone만 `Picked Up`으로 둔다. 다음 항목은 현재 항목의 구현·검증·review·commit/push/PR·CI 계약이 끝난 뒤 착수한다.
- 하위 에이전트는 병렬 실행이 실제 시간을 줄이고 파일 소유권과 검증 범위가 독립적일 때만 사용한다.
- 같은 파일, 공용 설정, lockfile, migration, Git 상태를 여러 에이전트가 동시에 수정하지 않는다.
- 각 하위 에이전트에 수정 가능 파일, 금지 범위, 완료 조건, 검증 명령을 명시한다.
- 하위 에이전트 결과는 주장으로 취급한다. 주 에이전트가 실제 diff, 테스트, Git 상태를 직접 확인한 뒤 완료로 판정한다.
- 통합, staging, commit, push, PR과 최종 검증은 주 에이전트가 담당한다.

## 중간 지시와 상태 보존

- 사용자의 새 지시는 다음 tool boundary에서 반영한다.
- 명시적 취소가 아니면 busy 응답이나 중간 명령을 작업 취소로 해석하지 않는다.
- 방향 전환으로 현재 결과를 폐기해야 하면 삭제나 history rewrite 전에 별도 branch의 checkpoint commit으로 보존한다.
- gateway나 장기 프로세스 재시작은 실행 중 에이전트 결과를 회수하고 checkpoint를 남긴 뒤 마지막에 수행한다.

## 진행 보고

진행 보고는 고정 주기 로그가 아니라 사용자가 방향을 판단할 수 있는 운영 이벤트다.

### 보고 시점

- 작은 단계 시작과 완료
- 실패, 판단 변경, 범위 변경
- 검증 결과 확정
- 사용자 조치가 필요한 병목 발견
- 장시간 새 이벤트가 없을 때만 heartbeat

### 보고 내용

- 현재 판단과 근거
- 명령·테스트·diff로 확인한 실제 결과
- 결정 사항과 다음 단계
- 남은 문제와 필요한 사용자 조치

raw 내부 추론, credential, 법률 원문 전문, verbose tool dump, 의미 없는 반복 보고는 포함하지 않는다. 하위 에이전트의 외국어 보고도 사용자에게는 핵심만 한국어로 전달한다.

## 오류 Ledger

Discord 작업 중 오류·차단·오판·운영 사고가 발생하면 [Discord 오류 Ledger](docs/operations/discord-error-ledger.md)를 즉시 갱신한다. 진단 중에도 먼저 기록하고 새 증거가 생기면 같은 사건을 갱신한다.

각 사건에는 다음을 기록한다.

- 발생일과 상태
- 원문 또는 관찰(`credential`과 개인 원문은 `REDACTED`)
- 원인과 영향
- 해결 또는 완화
- 검증 근거
- 재발 방지
- 남은 사용자 조치

## 채팅 경로 표기

이 thread의 채팅에서 저장소 루트 `/home/twkim/Project/law-rag`는 `~`로 줄여 쓴다. 실제 shell 경로와 저장소 내부 Markdown 링크는 원래 경로·상대 경로를 유지한다.

## 완료 체크리스트

- [ ] 이 작업이 지정 Discord thread에서 시작됐는지 확인했다.
- [ ] 루트 계약과 관련 권위 문서를 먼저 읽었다.
- [ ] 보드에 단일 `Picked Up` milestone과 agent별 TODO·파일 소유권이 있다.
- [ ] 기존 변경과 현재 작업을 분리했다.
- [ ] 주 에이전트가 delegate 결과, diff, 테스트, Git 상태를 직접 검증했다.
- [ ] 오류가 있으면 ledger를 갱신했다.
- [ ] credential·개인 사건자료·법률 원문 전문을 저장하거나 보고하지 않았다.
- [ ] 완료 후 보드, 실행 계획, 기술 부채 상태를 실제 결과와 일치시켰다.
- [ ] commit/push/PR/CI를 요청 또는 계획 계약에 맞게 완료했거나 미실행 사유를 기록했다.

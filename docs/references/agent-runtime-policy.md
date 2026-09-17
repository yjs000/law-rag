# 에이전트 런타임 운영 정책

이 문서는 항상 읽는 시작 문맥이 아니다. subagent를 dispatch하거나 Windows Python runner가 실패하거나
GitHub 인증을 확인할 때만 관련 절을 읽는다.

## Subagent 모델과 reasoning

Subagent를 dispatch할 때는 역할에 맞는 `model`과 `reasoning_effort`를 모두 명시하고,
`fork_turns`는 `none` 또는 필요한 최근 turn 수로 제한한다.

- 명세가 완전한 단일 파일·기계적 구현·작은 scoped re-review: `gpt-5.6-luna`, `max`
- 일반 구현: `gpt-5.6-luna`, `max`
- 다중 파일 통합·디버깅·task-level review: `gpt-5.6-terra`, `xhigh`
- 아키텍처·설계 판단·최종 whole-branch review: `gpt-5.6-sol`, `medium`

Fix-loop escalation은 필요할 때만 한 단계 올린다. `gpt-5.6-sol`은 `medium` 이하만 사용한다. 요청한
조합을 사용할 수 없으면 조용히 fallback하지 말고 dispatch를 중단해 사용자에게 알린다. 모델을 직접
지정할 수 없는 내부 guardian은 이 정책의 적용 대상이 아니다.

## Windows Python 검증

- 준비된 workspace 의존성으로 Python 검증을 실행할 때는 `scripts/run_python.ps1`을 사용한다. 전체
  진입점은 `scripts/verify.ps1`이다.
- `uv run`이 cache 초기화, `.venv\.lock`, access denied 또는 trampoline 경로 오류로 실패하면 같은
  명령을 반복하지 말고 `scripts/run_python.ps1`로 전환한다.
- pytest `tmp_path`가 새 임시 디렉터리에서 access denied로 실패하면 다른 temp 경로를 반복하지 않는다.
  전체 `scripts/verify.ps1`을 platform runtime 권한 상승으로 한 번 재실행한다.
- 의존성 설치·동기화가 실제로 필요할 때만 sandbox가 쓸 수 있는 새 cache와 project environment를
  지정해 `uv`를 사용한다.

## GitHub 인증 확인

- sandbox의 `gh auth status`가 token을 `invalid`로 보고해도 Windows Credential Manager 접근 차단의
  false negative일 수 있으므로 재로그인을 바로 요구하지 않는다.
- 같은 read-only 명령을 권한 상승으로 한 번 확인한다. 이 결과도 실패할 때만 사용자에게
  `gh auth login -h github.com`을 요청하고, 로그인 뒤 같은 방식으로 다시 검증한다.
- token 원문은 출력하거나 문서·로그·채팅에 기록하지 않는다.

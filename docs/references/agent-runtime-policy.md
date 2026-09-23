# 에이전트 런타임 운영 정책

이 문서는 항상 읽는 시작 문맥이 아니다. subagent를 dispatch하거나 Windows Python runner가 실패하거나
GitHub 인증을 확인할 때만 관련 절을 읽는다.

## Codex 모델 정책 위치

Codex 개발 단계와 GPT-6 모델 배정의 정본은 [`docs/SDD.md`](../SDD.md) 6절이다. Subagent dispatch 전에 해당 절을 읽는다.

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

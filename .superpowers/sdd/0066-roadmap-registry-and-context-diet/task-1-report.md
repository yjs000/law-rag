# Task 1 구현·self-review 보고서

## 범위

로드맵 실행계획의 색인 헤더를 읽는 immutable registry 모델과 검증기를 구현했다. 계획 본문은
첫 `##` heading 직전까지만 읽으며, legacy completed 계획처럼 색인 필드가 전혀 없는 파일은
마이그레이션 경계상 건너뛴다. staged 모드에서는 git index의 계획·참조 파일을 읽는다.

## TDD 증거

### Red

필수 focused 명령:

```text
uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
```

첫 실행 결과: `uv`가 workspace 의존성 `marshmallow`를 다운로드하기 전에 네트워크 연결 거부로
종료했다. 따라서 테스트 모듈 import까지 도달하지 못했다.

환경 동기화를 우회해 같은 unittest를 확인한 명령:

```text
uv run --project apps/api --no-sync python -m unittest scripts.tests.test_roadmap_registry -v
```

결과: `ImportError`/`ModuleNotFoundError: No module named 'scripts.roadmap_registry'`로 실패했다.
이는 production module을 추가하기 전의 의도한 red 원인이다.

### Green

구현 후 요구된 focused 명령을 권한 상승 환경에서 다시 실행했다.

```text
uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
```

결과: 9개 테스트 실행, `OK` (실패 0).

추가 검증:

```text
uv run --project apps/api ruff check scripts/roadmap_registry.py scripts/tests/test_roadmap_registry.py
```

결과: `All checks passed!`

```text
uv run --project apps/api --no-sync python -m py_compile scripts/roadmap_registry.py scripts/tests/test_roadmap_registry.py
```

결과: 종료 코드 0.

```text
git diff --cached --check
```

결과: 출력 없음, 종료 코드 0.

## 변경 파일

- `scripts/roadmap_registry.py`
  - immutable `PlanRecord`, `ReferenceRange`, `RegistryError` dataclass
  - disk/index source reader와 first-`##` header parser
  - 필수 필드, 허용 status/type/label, ID 중복, Picked Up cardinality, lifecycle, reference path와
    inclusive line-range 검증
  - deterministic section grouping과 canonical SHA-256 digest
- `scripts/tests/test_roadmap_registry.py`
  - valid/immutable parser, missing fields, H1, length/range/path, unknown values, duplicate IDs,
    lifecycle, section/digest, staged-index fixtures

## 커밋

```text
645c02a feat: add roadmap registry parser
```

커밋에는 위 두 파일만 포함했다. 기존 `graphify-out/` 변경과 미커밋 `0066` 실행계획은 stage하지
않았다.

## Self-review 및 concerns

- `보조 라벨`은 `docs/PLANS.md`의 선택 사항 계약을 따라 생략을 허용하고, 값이 있을 때만 허용
  라벨 목록을 검사한다.
- 기존 완료 계획 중 새 색인 헤더가 없는 파일은 의도적으로 registry에서 제외한다. 따라서 현재
  저장소 전체를 즉시 valid로 만드는 작업은 Task 3의 계획된 metadata migration 범위다.
- sandbox ACL 때문에 임시 fixture와 git index lock에는 권한 상승이 필요했다. 구현·테스트 결과에는
  영향을 주지 않았다.
- AGENTS.md의 요구에 따라 `graphify update .`를 권한 상승으로 실행했다. curated graph 파일은
  graphify가 만든 timestamp backup에서 갱신 전 상태로 복원했고, graphify auxiliary 출력은 기존
  uncommitted 상태로 커밋에서 제외했다.

## Fix round 1 evidence

리뷰의 P1/P2 지적을 반영하기 전에 회귀 테스트를 추가하고 다음 focused 명령을 실행했다.

```text
uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
```

결과: 19개 테스트 실행, 13개 실패. 실패는 strict header grammar 5개, disk/staged first-H2
streaming, headerless todo/active actionability, `다음 행동` 복수 문장, Picked Up cardinality,
public alias 제거, staged reference fail-closed 회귀 사례였다.

구현 후 동일한 명령을 다시 실행했다.

```text
uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
```

결과: 19개 테스트 실행, `OK` (실패 0).

추가 fix-round 검증:

```text
uv run --project apps/api ruff check scripts/roadmap_registry.py scripts/tests/test_roadmap_registry.py
```

결과: `All checks passed!`

```text
uv run --project apps/api python -m py_compile scripts/roadmap_registry.py scripts/tests/test_roadmap_registry.py
```

결과: 종료 코드 0.

```text
git diff --check
```

결과: whitespace 오류 없음.

`graphify update .`도 실행해 AST graph를 갱신했다. graphify는 `pyproject.toml`이 zero-node라
graph에서 제외됐다는 기존 도구 경고와 5,000-node 초과 aggregate view 경고를 출력했지만 rebuild는
성공했다. 기존 curated graph 파일은 timestamp backup에서 복원했고 graphify auxiliary 출력은
커밋하지 않았다.

변경 파일은 다음 두 개로 제한했다.

- `scripts/roadmap_registry.py`: first exact H2에서 disk/index header를 line-streaming하고,
  staged reference를 index에서만 fail-closed로 읽으며, headerless todo/active 오류·completed skip,
  strict finite-state grammar, 한 문장/120자 `다음 행동`, global Picked Up cardinality를 적용하고
  지원 근거 없는 alias surface를 제거했다.
- `scripts/tests/test_roadmap_registry.py`: body-boundary/digest, staged body/index reference,
  headerless lifecycle actionability, seven forbidden pairs, sentence boundary, strict grammar,
  canonical public surface 회귀 테스트를 추가했다.

fix-round commit:

```text
2980fdc7a3c655c67688ab0b5cdd9237113fcec4 fix: harden roadmap registry validation
```

남은 concerns:

- 기존 `todo/`와 `active/`의 headerless legacy 계획은 이제 의도적으로 actionable validation error를
  내며, Task 3 metadata migration 전까지 전체 registry validation은 실패한다. headerless
  `completed/` 계획만 migration 경계상 건너뛴다.
- 첫 H2 전 H1 뒤에 비어 있지 않은 줄을 두는 형식은 strict grammar에 따라 거부된다. graphify
  outputs와 0066 실행계획/report는 사용자 기존 변경으로 커밋하지 않았다.

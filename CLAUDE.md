# CLAUDE.md

Before doing repository work, read and follow `AGENTS.md`.

`AGENTS.md` is the authoritative repository instruction file.
Do not duplicate its repository rules here.

Use the installed Superpowers skills according to their own trigger conditions
and workflow requirements.

## Subagent 모델 정책

Subagent dispatch 시 역할에 맞는 `model`을 항상 명시한다. 생략해 부모 세션 모델을 암묵적으로
상속하게 하지 않는다.

- 명세가 완전한 단일 파일·기계적 작업, 작은 scoped re-review: `haiku`
- 일반 구현, 다중 파일 통합, 디버깅, task-level review: `sonnet`
- 아키텍처·설계 판단, 최종 whole-branch review: `opus`

fix-loop escalation은 필요한 경우에만 한 단계 올리며, 최종 review라는 이유만으로 `opus`를
선택하지 않는다.

## Output Paths

| Artifact        | Location                  |
| ---------------- | -------------------------- |
| Design specs    | `docs/design-docs/`       |
| Execution plans | `docs/exec-plans/active/` |

**IMPORTANT: Superpowers design specs MUST use `docs/design-docs/`,
not `docs/superpowers/specs/`.**

**Superpowers execution plans MUST use `docs/exec-plans/active/`,
not `docs/superpowers/plans/`.**

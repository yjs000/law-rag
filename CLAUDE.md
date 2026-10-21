# CLAUDE.md

Before doing repository work, read and follow `AGENTS.md`.

`AGENTS.md` is the authoritative repository instruction file.
Do not duplicate its repository rules here.

Use the installed Superpowers skills according to their own trigger conditions
and workflow requirements.

## Claude 모델 선택 정책

`AGENTS.md`와 그 위임 문서의 작업 절차·승인·검증·위임 규칙을 그대로 따른다. Claude 세션에서는 모델 배정에 한해 이 절을 적용한다. Subagent 사용이 허용된 경우 dispatch마다 아래 모델을 명시하고, 부모 세션 모델을 암묵적으로 상속하지 않는다.

- 명세가 완전한 단일 파일·기계적 작업, 반복적인 형식 수정, 단순 테스트 추가, 작은 범위 재검토: `claude-sonnet-5` (Sonnet 5)
- 일반 구현, 다중 파일 통합, 기존 설계 안의 리팩터링, 테스트 작성, 일반적인 디버깅, 작업 단위 코드 리뷰 및 수정 루프: `claude-sonnet-5` (Sonnet 5)
- 요구사항 해석이 어렵거나 선택지가 여러 개인 작업, 아키텍처·설계 판단, 여러 subsystem에 걸친 변경의 구현 계획, 복잡한 장애의 원인 분석, 중요한 최종 whole-branch 리뷰 등 높은 추론이 필요한 작업: `claude-sonnet-5-5` (Sonnet 5.5)

사용 가능한 모델은 Sonnet 5와 Sonnet 5.5뿐이다. `haiku`와 Opus는 사용하지 않는다. 기본 모델은 Sonnet 5이고, 높은 수준의 추론이 실제로 필요할 때만 Sonnet 5.5를 사용한다. Sonnet 5.5를 단순·반복 작업에 배정하지 않는다. 다만 잘못된 설계가 뒤의 구현 비용을 크게 늘릴 수 있으면 처음부터 Sonnet 5.5로 판단한다. Sonnet 5가 같은 문제에서 반복해서 실패하거나 원인을 특정하지 못한 경우에도 Sonnet 5.5로 올릴 수 있다.

모델을 사용할 수 없으면 다른 모델로 조용히 대체하지 말고 알려준다.

## Output Paths

| Artifact        | Location                  |
| ---------------- | -------------------------- |
| Design specs    | `docs/design-docs/`       |
| Execution plans | `docs/exec-plans/active/` |

**IMPORTANT: Superpowers design specs MUST use `docs/design-docs/`,
not `docs/superpowers/specs/`.**

**Superpowers execution plans MUST use `docs/exec-plans/active/`,
not `docs/superpowers/plans/`.**

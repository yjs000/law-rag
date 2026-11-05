# law-rag 문서 안내

무엇을 확인하려는지에 따라 아래 문서에서 시작합니다.

| 찾는 내용 | 시작 문서 |
|---|---|
| 지금 진행 중인 일과 다음 우선순위 | [현재 상태](CURRENT_STATE.md) · [로드맵](ROADMAP.md) |
| 제품의 목적과 사용자가 경험하는 동작 | [제품 목적](PRODUCT_SENSE.md) · [제품 명세 색인](product-specs/index.md) |
| 시스템 구조와 기술 선택의 이유 | [아키텍처](../ARCHITECTURE.md) · [설계 문서 색인](design-docs/index.md) · [다이어그램](diagrams/README.md) |
| 화면, 개인정보, 장애 처리 기준 | [UI 설계](DESIGN.md) · [프런트엔드](FRONTEND.md) · [보안](SECURITY.md) · [신뢰성](RELIABILITY.md) |
| 실제 운영 명령과 장애 기록 | [코퍼스 운영·롤백 런북](references/operations-runbook.md) · [Discord 오류 원장](operations/discord-error-ledger.md) |
| 개발 작업 규칙과 계획 기록 | [저장소 작업 규칙](../AGENTS.md) · [SDD](SDD.md) · [GitHub 작업 흐름](GITHUB_WORKFLOW.md) · [실행계획 운영법](PLANS.md) |
| 학습 자료와 기술 조사 | [학습 코스](learning/index.md) · [참고 자료 색인](references/README.md) |
| 스키마와 평가 결과 | [생성된 DB 스키마](generated/db-schema.md) · [품질 평가](QUALITY_SCORE.md) |

## 문서를 둘 위치

- 사용자에게 약속하는 동작은 [제품 명세](product-specs/index.md)에, 구현 결정과 이유는 [설계 문서](design-docs/index.md)에 둡니다. 설계 도구의 별도 산출물은 `superpowers/specs/`에 있으며, 관련 실행계획에서 참조합니다.
- 실행 순서와 작업 기록은 [실행계획 운영법](PLANS.md)에 따라 `exec-plans/`의 상태별 폴더에 둡니다. 우선순위와 상태의 원본은 계획 상단 메타데이터입니다.
- 현재 구현을 읽는 데 필요한 그림은 [다이어그램](diagrams/README.md)에 둡니다. 학습용 그림은 [학습 코스](learning/index.md)에서 안내합니다.
- 운영 절차와 기술 조사 자료는 [참고 자료 색인](references/README.md)에서 구분합니다. 운영 중에 쌓인 사건 기록은 `operations/`에 둡니다.
- 도구가 만든 스키마, 평가 결과, 보고서는 `generated/`에 둡니다. 관련 설계나 실행계획에서 결과를 연결합니다.

# AGENTS.md

이 파일은 저장소의 목차이자 authoritative 규칙 문서다. 세부 지식을 여기에 복제하지 말고 아래의 권위
문서로 연결한다.

어떻게 개발할지(skill 선택, brainstorming, planning, TDD, 구현, 리뷰, 검증)는 설치된 Superpowers가
결정한다. 무엇을 지켜야 하는지(도메인 불변조건, 데이터·보안 규칙, 문서·Git 정책)는 이 파일이
결정한다. 자세한 역할 분담은 "개발 작업 워크플로우"를 참고한다.

이 저장소 규칙은 어떤 사용자·전역 설정(예: 사용자 홈 디렉터리의 전역 `AGENTS.md`)보다 우선한다. 이
문서와 전역 설정이 다르면 이 문서를 따른다. 전역 설정은 이 문서가 다루지 않는 부분에서만 보조로
적용한다.

## 작업 시작 순서

1. `git status --short --branch`로 현재 변경과 브랜치를 확인한다.
2. 이 파일과 `docs/CURRENT_STATE.md`를 읽는다.
3. 작업이 아키텍처·모듈 경계·배포를 건드리면 그때 `ARCHITECTURE.md`를 읽고, 특정 기능의 설계·제품
   요구사항이 필요하면 그때 관련 `docs/design-docs/` 및 `docs/product-specs/` 문서를 읽는다 — 매
   세션 전체를 미리 읽지 않는다.
4. brainstorming·설계 승인·planning 필요 여부와 절차는 설치된 Superpowers skill의 trigger 조건을
   따른다. 이 저장소는 작업 규모로 그 여부를 다시 판단하지 않는다.
5. `docs/ROADMAP.md`의 `Picked Up` 항목을 먼저 읽고, 해당 작업을 재개할 때만 연결된 실행계획을
   확인한다. `Picked Up`이 없으면 `Todo`의 첫 항목을 사용한다. 사용자가 이전에 다음 작업으로 등록한
   항목이면 `docs/exec-plans/todo/`에서 같은 계획을 확인한다. Superpowers `writing-plans`로 실행
   계획이 작성되면 같은 번호의 파일을 `active/`로 이동한다.
6. 가장 작은 검증 가능한 변경으로 구현하고 테스트·문서를 함께 갱신한다.

## Docker·로컬 DB 정책

- 명시적 사용자 승인 없이는 `supabase start` 또는 `docker compose up -d`를 실행하거나, `docker run -d`로 PostgreSQL·Redis·벡터 DB 등 상주형 로컬 서비스를 기동하지 않는다.
- 기본 DB 경로는 원격 개발·테스트 환경이다. 운영 DB를 테스트·초기화 대상으로 사용하지 않는다.
- 기존 테스트 명령이 요구하는 일회성 Docker 검증은 자동 실행할 수 있다. 단, `--rm` 등으로 종료 뒤 컨테이너가 남지 않아야 하며 상주형 로컬 DB·서비스를 기동해서는 안 된다.

## 개발 작업 워크플로우

개발 작업의 skill 선택, brainstorming, 설계 승인, planning, worktree 격리, TDD, 구현, 코드 리뷰,
검증 및 완료 절차는 설치된 Superpowers의 현재 skill과 trigger 조건을 따른다.

이 저장소는 Superpowers workflow의 발동 조건이나 절차를 별도로 재정의하지 않는다.

단, Superpowers가 생성하는 repository artifact의 저장 위치와 lifecycle은 이 저장소의 문서 규칙
(`docs/design-docs/`, `docs/exec-plans/active/`, 아래 "권위 문서")을 따른다 — `CLAUDE.md`가 경로를
override한다.

프로젝트의 도메인, 데이터, 보안, 개인정보, 아키텍처 및 검증 불변조건(아래 "변경 불변조건")은
Superpowers workflow 중에도 항상 유지한다.

## Subagent 모델·reasoning 정책

Superpowers를 포함해 subagent를 dispatch할 때는 역할에 맞는 `model`과 `reasoning_effort`를 항상
명시한다. 둘 중 하나라도 생략하여 부모 세션의 모델이나 reasoning effort를 암묵적으로 상속하게 해서는
안 된다.

- 명세가 완전한 단일 파일·기계적 구현 및 작은 scoped re-review: `gpt-5.6-luna`, `max`
- 일반 구현 : `gpt-5.6-luna`, `max`
- 다중 파일 통합, 디버깅 및 task-level review: `gpt-5.6-terra`, `xhigh`
- 아키텍처·설계 판단 및 최종 whole-branch review: `gpt-5.6-sol`, `medium`
- fix-loop escalation은 필요한 경우에만 한 단계 올리며, 최종 review가 아니라는 이유만으로
  `gpt-5.6-terra`를 선택하지 않는다.
- `gpt-5.6-sol`은 `medium` 이하에서만 사용하며, `high` 이상은 어떠한 경우에도 사용하지 않는다.

명시적 모델 override와 호환되도록 subagent의 `fork_turns`는 `none` 또는 필요한 최근 turn 수로
제한한다. 요청한 모델이나 effort를 사용할 수 없으면 다른 모델로 조용히 fallback하지 말고
dispatch를 중단해 사용자에게 알린다. 시스템이 자동 생성하는 guardian 등 모델을 직접 지정할 수 없는
내부 agent는 이 정책의 적용 대상에서 제외한다.

## 커밋 원칙

- 마일스톤 단위(구현 → 테스트 → 검증 → git diff 확인)가 끝나면 매번 승인을 구하지 않고 완료된 기능
  단위로 커밋한다. 이 durable 승인은 로컬 `git commit`에만 적용된다.
- 서로 다른 기능·목적의 변경은 한 커밋에 묶지 않고 분리한다.
- `git push`, force-push, 원격 브랜치·PR 생성·수정, 운영 DB·배포 작업은 이 승인 범위 밖이며 여전히
  매번 사용자 확인을 받는다.
- 커밋 대상에 `.env`, 자격 증명, 개인 사건자료가 섞이지 않았는지 커밋 전에 확인한다(금지 사항 참고).
- 사용자가 특정 작업에서 커밋 보류·단일 커밋·다른 방식을 명시하면 그 지시가 이 기본값보다 우선한다.
- 커밋 메시지는 무엇을·왜 바꿨는지 간결히 담고 저장소 관례(`feat:`, `fix:`, `docs:` 등)를 따른다.

## Discord 전용 오버레이

- Discord thread `1528216345924337805`에서 시작한 작업에만 루트 [discord-agents.md](discord-agents.md)를 추가로 읽고 적용한다.
- `1528216345924337805` thread 밖에서는 `discord-agents.md`와 `docs/operations/discord-error-ledger.md`만 적용하지 않는다. 공통 프로젝트 계약과 `docs/ROADMAP.md`는 모든 작업에 적용한다.
- 공통 프로젝트 계약은 항상 이 파일이 우선하며 Discord overlay는 진행 보고, TODO/위임, 상태 보존과 오류 기록만 보강한다.

## 권위 문서

- 세션 시작 포인터(무엇을 언제 읽을지): `docs/CURRENT_STATE.md`
- 제품 목적과 사용자 가치: `docs/PRODUCT_SENSE.md`
- 시스템 구조와 의존성: `ARCHITECTURE.md`
- 상세 기술 설계: `docs/design-docs/index.md`
- 제품 요구사항: `docs/product-specs/index.md`
- 현재 작업 우선순위 색인: `docs/ROADMAP.md`
- 실행 계획 저장 위치·lifecycle: `docs/PLANS.md`
- 사용자가 제안한 미착수 작업: `docs/exec-plans/todo/README.md`
- UI 원칙: `docs/DESIGN.md`, `docs/FRONTEND.md`
- 보안과 개인정보: `docs/SECURITY.md`
- 신뢰성 목표: `docs/RELIABILITY.md`
- 품질 현황: `docs/QUALITY_SCORE.md`
- 알려진 부채: `docs/exec-plans/tech-debt-tracker.md`

## 변경 불변조건

- 법률 답변의 실질적 주장은 검색된 근거와 인용 위치를 가져야 한다.
- 검색 원문, 파생 청크, 답변에 데이터 출처와 버전을 추적할 수 있어야 한다.
- 외부 입력은 시스템 경계에서 검증한다. 내부 계층은 검증된 타입만 받는다.
- 개인정보, 인증정보, 원문 전문을 로그에 남기지 않는다.
- 법률 조항·판례를 모델 기억만으로 보완하지 않는다. 근거 부족 상태를 명시한다.
- 도메인 계층은 인프라 SDK에 직접 의존하지 않는다.
- 새 동작에는 정상·실패·경계 사례 테스트와 관측 가능성을 추가한다.
- 정확성·보안·데이터 안전을 지키는 범위에서, 설계와 구현은 현재 사용자 가치에 필요한 핵심 기능을 충족하는 가장 단순하고 빠르며 비용이 낮은 방식을 기본으로 한다. 무중단·분산·고가용성·추가 자동화·유료 서비스는 실제 요구나 측정된 문제와 사용자 승인 없이는 추가하지 않는다.
- 법률 코퍼스 출처는 국가법령정보 공동활용 Open API로 제한한다. HTML·PDF·다른 웹 근거로 우회하지 않는다.
- 수집은 JSON 우선, 도메인 스키마 검증 실패 시 XML 폴백이며 포맷과 폴백 사유를 기록한다.
- `docs/learning/` 기술 브리핑은 매 구현 마일스톤·판정 정정·metric 재계산마다 갱신하지 않는다. 새
  개념을 처음 도입했거나, 아키텍처가 바뀌었거나, 사용자가 학습 자료 생성을 요청했거나, 큰 실험 하나가
  끝났을 때만 갱신한다.

## 문서 규칙

- 중요한 결정은 관련 설계 문서의 `결정 기록`에 날짜와 이유를 남긴다.
- 생성 파일은 `docs/generated/`에 두고 생성 명령과 기준 시점을 파일 머리에 기록한다.
- 완료된 실행 계획은 결과와 잔여 작업을 적은 뒤 `completed/`로 이동한다.
- 코드와 문서가 다르면 같은 변경에서 문서를 고친다.
- 확정되지 않은 내용은 사실처럼 쓰지 말고 `미결정` 또는 `가정`으로 표시한다.

## 검증 계약

현재 구현 도구가 정해지지 않았으므로 검증 명령은 첫 실행 계획에서 확정한다. 도구가 도입되면 이 섹션에는 대표 명령만 유지하고 세부 설명은 해당 문서로 연결한다.

최소 병합 조건:

1. 포맷, 린트, 타입 검사 통과
2. 단위·통합 테스트 통과
3. 검색/답변 변경 시 고정 평가셋 회귀 통과
4. 스키마 변경 시 마이그레이션 및 `docs/generated/db-schema.md` 갱신
5. 사용자 동작 변경 시 제품 명세와 운영 문서 갱신

## GitHub 인증 확인

- sandbox 안에서 실행한 `gh auth status`가 token을 `invalid`로 보고해도 곧바로 실제 인증 실패로 단정하거나 사용자에게 재로그인을 요구하지 않는다. Windows Credential Manager/keyring 접근이 sandbox에 차단된 false negative일 수 있다.
- 먼저 동일한 read-only 명령인 `gh auth status`를 승인된 권한 상승 실행으로 한 번 더 확인한다. 권한 상승 결과가 정상이라면 해당 결과를 기준으로 commit·push 작업을 계속한다.
- 권한 상승 확인에서도 인증이 실패할 때만 사용자에게 `gh auth login -h github.com` 실행을 요청한다. device login 직후에도 같은 권한 상승 확인으로 새 인증이 보이는지 검증한다.
- 인증 확인 과정에서 token 원문을 출력하거나 문서·로그·채팅에 기록하지 않는다.

## 금지 사항

- `.env`, API 키, 접근 토큰, 개인 사건자료 커밋
- 원격 데이터나 DB를 파괴하는 명령을 승인 없이 실행
- 인용 검증을 우회해 답변 품질을 높이는 것처럼 보이게 하는 변경
- 근거 없는 기술·법률 요구사항을 임의로 확정

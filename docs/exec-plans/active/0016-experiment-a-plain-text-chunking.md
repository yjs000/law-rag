# 실행 계획 0016: 실험 A — 일반 텍스트 조문 청킹 관찰

상태: 계획 완료, 구현 대기
작성일: 2026-07-22
소유자: Codex
브랜치: `codex/experiment-a-chunking`

## 목적과 사용자 결과

사용자가 UTF-8 텍스트 파일 하나를 지정하면, 외부 API·DB·임베딩·검색을 호출하지 않고
청킹 입력과 결과만 로컬에서 확인한다. 제공된 전기사업법 예시는 제7조부터 제12조까지
6개 조문 청크로 나뉘어야 하며, 각 청크의 경로·표제·본문을 사람이 읽을 수 있는 터미널
출력, 자동 생성 Markdown 보고서와 기계가 다시 읽을 수 있는 JSON으로 함께 확인할 수 있어야 한다.

현재 운영 청킹은 국가법령정보 Open API의 구조화된 JSON/XML을
`law_json.parse_legal_document()`가 `ProvisionRecord`로 만드는 방식이며 일반 `.txt` 입력을
직접 받지 않는다. 이 실험은 운영 청킹 함수와 결과 타입을 수정하거나 복제하지 않는다.
일반 텍스트를 기존 파서가 받는 최소 Open API JSON 구조로 바꾸는 입력 어댑터만 앞에 두고,
실제 청크 생성은 반드시 현재 `law_json.parse_legal_document()`를 그대로 호출한다.

## 착수 점검과 가정

- 2026-07-22 확인 시 `main`은 미커밋 변경 없이 깨끗했고 현재 작업과 겹치는 사용자 변경은 없다.
- 제공된 텍스트는 실험 fixture로만 사용한다. 국가법령정보 Open API 수집 원문으로 간주하거나
  운영 코퍼스·검색·답변 근거에 넣지 않는다.
- 입력 어댑터는 줄 시작의 `제N조` 또는 `제N조의M`과 괄호 표제를 Open API JSON의
  `조문단위`로 옮긴다. 본문 안의 `제53조`, `제61조제1항` 같은 인용은 새 조문단위가 아니다.
- `제2장`, `제1절`은 입력 문맥으로 보고 생성 보고서의 입력 개요에 표시하지만, 현재
  `ProvisionRecord`에 없는 필드를 추가하거나 청크 본문에 주입하지 않는다.
- 정확히 `조문체계도버튼연혁`인 UI 잔여 줄은 본문에서 제외하고 제거 개수를 결과에 기록한다.
- 조문 표지가 하나도 없지만 비어 있지 않은 파일은 첫 비어 있지 않은 줄을 제목, 나머지를
  본문으로 하는 Open API 단일 `조문단위`로 어댑트한다. 제목만 있고 본문이 없으면 실패한다.

## 범위와 비범위

범위:

- 일반 텍스트를 최소 Open API JSON 구조로 바꾸는 입력 어댑터와 실험 전용 로컬 CLI
- 현재 `law_json.parse_legal_document()`를 수정 없이 호출하는 연결부
- 제공된 입력 fixture와 정상·실패·경계 테스트
- 터미널 미리보기, 자동 생성 Markdown 보고서와 로컬 JSON 결과 파일
- 실행법, 출력 계약, 실패 복구를 설명하는 실험 README와 기술 브리핑

비범위:

- 실험 B 임베딩과 실험 C 검색
- FastAPI 엔드포인트나 Next.js 화면
- Supabase, pgvector, PGroonga, collector manifest 또는 `.collector-state/` 저장
- Open API JSON/XML 운영 파서의 동작 변경
- 현재 `ProvisionRecord` 필드나 parser schema version 변경
- 항·호·목을 각각 별도 청크로 추가 분할하거나 고정 토큰 길이로 재분할
- HTML/PDF/웹 크롤링 또는 외부 법률 근거 도입

## 보여주는 방식

저장소 루트에서 다음과 같이 실행하는 단일 명령을 제공한다.

```powershell
uv run --project packages/law-rag-core python experiments/chunking/run.py `
  experiments/chunking/fixtures/electric-utility-act-chapter-2.txt
```

터미널은 먼저 실행 요약을 출력한다.

```text
입력: experiments/chunking/fixtures/electric-utility-act-chapter-2.txt
SHA-256: <원문 해시>
청크: 6개 | 제거한 UI 줄: 6개 | 상태: success
보고서: docs/generated/experiment-a-chunking.md
JSON: .data/experiments/chunking/electric-utility-act-chapter-2.chunks.json
```

이어서 청크마다 아래 형식으로 전체 본문을 출력한다. 본문을 생략하거나 길이로 자르지 않는다.

```text
[1/6] 제7조 — 사업의 허가
본문:
제7조(사업의 허가) ① 전기사업을 하려는 자는 ...
...
```

로컬 실행이 성공하면 `docs/generated/experiment-a-chunking.md`가 즉시 생성 또는 교체된다.
보고서 머리에는 생성 명령, 기준 시점, 입력 경로와 SHA-256, 실제 호출한 함수
`law_rag_core.parsers.law_json.parse_legal_document`, parser schema version, 청크 수와 제거한
UI 줄 수를 기록하고, 이어서 모든 청크의 경로·표제·전체 본문을 담는다.

JSON은 같은 실행의 검증용 sidecar로 `status`, 입력 상대 경로, 입력 SHA-256, 현재 parser
schema version, 청크 수, 제거한 UI 줄 수와 `chunks[]`를 가진다. 각 청크는 기존
`ProvisionRecord` 그대로 `id`, `ordinal`, `path`, `heading`, `parent_path`, `content`를 직렬화한다.

## 저장 위치와 수명

- 재현 가능한 입력 fixture:
  `experiments/chunking/fixtures/electric-utility-act-chapter-2.txt` — Git 추적 대상
- 실행 코드와 사용 설명:
  `experiments/chunking/run.py`, `experiments/chunking/README.md` — Git 추적 대상
- 입력 어댑터와 테스트:
  `experiments/chunking/text_fixture_adapter.py`, `experiments/chunking/tests/` — Git 추적 대상
- 자동 생성 실험 보고서:
  `docs/generated/experiment-a-chunking.md` — Git 추적 대상, 성공한 대표 실행 결과를 커밋
- 기계 판독용 실행 결과:
  `.data/experiments/chunking/<입력파일명>.chunks.json` — 기존 `.gitignore`에 의해 Git 제외
- 학습 기록:
  `docs/learning/21-plain-text-article-chunking-experiment.md` 및 `docs/learning/index.md`

Markdown 보고서와 JSON은 성공 결과에 한해 임시 파일에서 원자적으로 교체한다. 따라서 로컬에서
명령을 실행하면 별도 복사 단계 없이 보고서가 바로 생긴다. DB와 외부 스토리지에는 저장하지
않는다. 사용자가 `--report`와 `--json-output`으로 저장 경로를 지정할 수 있게 하되, 기본 실행은
위 두 기본 경로를 사용한다.

## 실패 동작

- 파일 없음, 디렉터리 입력, UTF-8 디코딩 실패, 빈 입력, 제목만 있는 단일 청크, 중복 조문 경로,
  출력 디렉터리 생성/쓰기 실패는 JSON 오류 한 줄을 표준 오류에 출력하고 종료 코드 `2`를 반환한다.
- 인식하지 못한 일반 줄은 버리지 않고 현재 조문 본문에 보존한다. UI 잔여 줄처럼 명시적으로
  정의한 노이즈만 제거한다.
- 실패한 실행은 새 Markdown 보고서나 JSON을 남기지 않는다. 기존 성공 보고서와 JSON이 있으면
  임시 파일 교체 전 실패한 경우 그대로 보존한다.
- 일부 조문만 성공 결과로 저장하지 않는다. 중복 경로나 구조 오류가 하나라도 있으면 파일 전체를
  실패 처리한다.
- 오류에는 입력 경로, 오류 코드와 사람이 이해할 수 있는 이유만 포함하고 원문 전문은 출력하지 않는다.

## 측정 가능한 완료 조건

- 제공된 fixture가 `제7조`~`제12조` 순서의 정확히 6개 청크를 만든다.
- 현재 `law_json.parse_legal_document()`와 `ProvisionRecord` 구현 파일에는 변경이 없다.
- 어댑터가 만든 최소 Open API JSON을 현재 파서에 전달하고, 파서가 반환한 경로·표제·본문을
  추가 청킹 없이 그대로 출력한다.
- 보고서 입력 개요가 `제2장 전기사업`, `제1절 허가 등` 문맥을 표시하고 각 청크가 괄호 표제를 보존한다.
- 조문 내부의 다른 조문 인용과 `4의2` 같은 호 표기가 새 조문 청크를 만들지 않는다.
- UI 잔여 줄 6개가 본문에서 제거되고 제거 개수가 출력 계약에 남는다.
- 터미널 미리보기, Markdown 보고서와 저장 JSON의 청크 내용이 일치한다.
- 동일 입력 재실행의 경로, 순서, 내용과 SHA-256이 결정적이다.
- 단일 `제목+본문` 입력과 CRLF/LF, 가지조문, 선행/후행 공백 경계 테스트가 통과한다.
- 정상·실패·경계 테스트, Ruff와 문서 링크 검사가 통과한다.
- API·collector·DB·네트워크가 호출되지 않는 것이 테스트 또는 import 경계로 확인된다.

## TODO와 에이전트 배정

### 주 에이전트

- [x] `M1 — 기존 청킹 연결 계약`: `experiments/chunking/text_fixture_adapter.py`와 단위 테스트를
  작성한다. 완료 조건은 어댑터 출력이 현재 `law_json.parse_legal_document()`로 들어가 제공 fixture
  6개 `ProvisionRecord`를 반환하고 운영 파서 파일은 수정되지 않는 것이다.
- [x] `M2 — 관찰 CLI와 보고서 저장`: `experiments/chunking/run.py`, fixture, README와 CLI 테스트를
  작성한다. 완료 조건은 터미널/Markdown/JSON 동일성, 원자 저장과 종료 코드 계약 통과다.
- [ ] `M3 — 문서와 전체 검증`: 학습 브리핑과 인덱스를 갱신하고 코어 테스트, Ruff, 문서 검사,
  전체 저장소 검증을 실행한다. 변경 범위별 diff를 검토하고 각 마일스톤을 별도 커밋한다.

### 하위 에이전트

- 사용하지 않는다. 핵심 구현, CLI, fixture와 테스트가 같은 작은 경계 계약을 공유해 파일 소유권을
  안전하게 분리하기 어렵고 병렬화 이점이 작다.

## 구현 순서

1. 입력 정규화, 장/절/조문 표지 인식과 단일 제목+본문 폴백을 최소 Open API JSON으로만 변환한다.
2. 변환 결과를 현재 `law_json.parse_legal_document()`에 전달하고 반환 `ProvisionRecord`를 그대로 쓴다.
3. 제공 텍스트와 최소 fixture로 정상·실패·경계 테스트를 먼저 고정한다.
4. 파일 읽기, 사람이 읽는 출력, Markdown/JSON 직렬화와 임시 파일 원자 교체를 CLI에 연결한다.
5. CLI 통합 테스트로 stdout/stderr, 종료 코드와 기존 성공 결과 보존을 검증한다.
6. README와 `docs/learning/`에 기존 청킹 함수 재사용과 텍스트 입력 어댑터의 경계를 기록한다.
7. 마일스톤마다 관련 검증과 `git diff`를 확인한 뒤 해당 범위만 커밋한다.

## 검증 및 롤백

예정 검증 명령:

```powershell
uv run --project packages/law-rag-core pytest experiments/chunking/tests -q
uv run --project packages/law-rag-core ruff check experiments/chunking
uv run --project packages/law-rag-core python experiments/chunking/run.py `
  experiments/chunking/fixtures/electric-utility-act-chapter-2.txt
uv run python scripts/check_docs.py
pnpm.cmd verify
```

모든 새 코드는 운영 API·collector와 연결되지 않은 `experiments/chunking/` 경계에 두고 현재
JSON 파서를 import해 호출한다. 회귀가 있으면 실험 디렉터리와 생성·학습 문서만 되돌릴 수 있으며
기존 JSON/XML 파서와 운영 데이터에는 migration이나 롤백이 필요하지 않다.
`docs/generated/experiment-a-chunking.md`와 `.data/experiments/chunking/` JSON은 재생성 가능하다.

## 결정 로그

- 2026-07-22: 웹 UI 대신 로컬 CLI, 자동 생성 Markdown과 JSON을 사용한다. 입력, 전체 청크,
  종료 코드와 저장 결과를 한 번에 재현하면서 제품 화면과 API 범위를 늘리지 않기 위해서다.
- 2026-07-22: 새 청킹 함수를 만들지 않는다. 텍스트 입력 어댑터는 최소 Open API JSON까지만
  만들고 실제 청크는 현재 `law_json.parse_legal_document()`가 생성한다.
- 2026-07-22: 기본 단위는 조문 전체이며 장/절은 메타데이터로 보존한다. 항·호 분할은 이번 실험의
  “조문 또는 제목+본문” 관찰 범위를 넘어가므로 제외한다.
- 2026-07-22: 대표 결과는 `docs/generated/experiment-a-chunking.md`에 원자 생성해 문서화하고,
  JSON sidecar는 Git에서 제외된 `.data/experiments/chunking/`에 둔다.

## 진행 기록

- 2026-07-22: `main`의 깨끗한 상태, 관련 설계와 JSON/XML 파서, 테스트, CLI 패턴을 확인했다.
- 2026-07-22: `codex/experiment-a-chunking` 브랜치를 만들었다.
- 2026-07-22: 입력·출력·저장·실패 계약과 세 마일스톤을 계획했다. 구현은 사용자 확인 후 시작한다.
- 2026-07-22: 사용자 확인에 따라 새 청킹 구현 계획을 폐기하고 현재 JSON 파서 재사용으로 수정했다.
  로컬 실행 성공 즉시 `docs/generated/experiment-a-chunking.md`가 생기는 계약을 추가했다.
- 2026-07-22: 텍스트 입력 어댑터가 제공 fixture를 최소 Open API JSON으로 옮기고 기존
  `law_json.parse_legal_document()`가 제7조부터 제12조까지 6개 청크를 반환함을 7개 테스트로 확인했다.
- 2026-07-22: 로컬 CLI, UTF-8 Windows 터미널 출력, Markdown/JSON 원자 저장과 실패 시 기존 결과
  보존을 구현했다. 12개 실험 테스트와 Ruff가 통과했고 대표 보고서에 6개 청크를 생성했다.

## 미결정과 차단 요소

- 차단 요소는 없다. Python 3.14와 저장소 의존성만 사용하며 인증정보, 계정, 네트워크가 필요 없다.
- 이번 계획에서는 조문 전체를 청크로 확정한다. 실험 결과가 너무 길다고 관찰될 때만 후속 실험에서
  항 단위 또는 겹침 하위 청크를 별도 비교한다.

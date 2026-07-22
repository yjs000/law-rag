# 실행 계획 0016: 실험 A — 일반 텍스트 조문 청킹 관찰

상태: 계획 완료, 구현 대기
작성일: 2026-07-22
소유자: Codex
브랜치: `codex/experiment-a-chunking`

## 목적과 사용자 결과

사용자가 UTF-8 텍스트 파일 하나를 지정하면, 외부 API·DB·임베딩·검색을 호출하지 않고
청킹 입력과 결과만 로컬에서 확인한다. 제공된 전기사업법 예시는 제7조부터 제12조까지
6개 조문 청크로 나뉘어야 하며, 각 청크의 경로·표제·상위 장/절·본문을 사람이 읽을 수
있는 터미널 출력과 기계가 다시 읽을 수 있는 JSON으로 함께 확인할 수 있어야 한다.

현재 운영 청킹은 국가법령정보 Open API의 구조화된 JSON/XML에서 `ProvisionRecord`를 만드는
방식이며 일반 `.txt` 입력을 직접 받지 않는다. 이 실험은 운영 수집 계약을 바꾸지 않고,
일반 텍스트의 조문 경계만 인식하는 실험용 어댑터를 추가해 같은 구조 우선 원칙을 관찰한다.

## 착수 점검과 가정

- 2026-07-22 확인 시 `main`은 미커밋 변경 없이 깨끗했고 현재 작업과 겹치는 사용자 변경은 없다.
- 제공된 텍스트는 실험 fixture로만 사용한다. 국가법령정보 Open API 수집 원문으로 간주하거나
  운영 코퍼스·검색·답변 근거에 넣지 않는다.
- 조문 경계는 줄 시작의 `제N조` 또는 `제N조의M`과 괄호 표제를 기준으로 한다. 본문 안의
  `제53조`, `제61조제1항` 같은 인용은 새 청크가 아니다.
- `제2장`, `제1절`은 독립 검색 청크로 만들지 않고 뒤따르는 조문에 문맥 메타데이터로 붙인다.
- 정확히 `조문체계도버튼연혁`인 UI 잔여 줄은 본문에서 제외하고 제거 개수를 결과에 기록한다.
- 조문 표지가 하나도 없지만 비어 있지 않은 파일은 첫 비어 있지 않은 줄을 제목, 나머지를
  본문으로 하는 `제목+본문` 단일 청크로 처리한다. 제목만 있고 본문이 없으면 실패한다.

## 범위와 비범위

범위:

- 일반 텍스트용 순수 청킹 함수와 실험 전용 로컬 CLI
- 제공된 입력 fixture와 정상·실패·경계 테스트
- 터미널 미리보기와 로컬 JSON 결과 파일
- 실행법, 출력 계약, 실패 복구를 설명하는 실험 README와 기술 브리핑

비범위:

- 실험 B 임베딩과 실험 C 검색
- FastAPI 엔드포인트나 Next.js 화면
- Supabase, pgvector, PGroonga, collector manifest 또는 `.collector-state/` 저장
- Open API JSON/XML 운영 파서의 동작 변경
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
저장: .data/experiments/chunking/electric-utility-act-chapter-2.chunks.json
```

이어서 청크마다 아래 형식으로 전체 본문을 출력한다. 본문을 생략하거나 길이로 자르지 않는다.

```text
[1/6] 제7조 — 사업의 허가
문맥: 제2장 전기사업 > 제1절 허가 등
본문:
제7조(사업의 허가) ① 전기사업을 하려는 자는 ...
...
```

JSON은 `status`, 입력 상대 경로, 입력 SHA-256, 청커 버전, 청크 수, 제거한 UI 줄 수와
`chunks[]`를 가진다. 각 청크는 `ordinal`, `path`, `heading`, `chapter`, `section`, `content`를
보존한다. 운영 `ProvisionRecord`의 구조 우선 개념을 따르되 실험 메타데이터를 운영 DB 모델에
억지로 추가하지 않는다.

## 저장 위치와 수명

- 재현 가능한 입력 fixture:
  `experiments/chunking/fixtures/electric-utility-act-chapter-2.txt` — Git 추적 대상
- 실행 코드와 사용 설명:
  `experiments/chunking/run.py`, `experiments/chunking/README.md` — Git 추적 대상
- 순수 청킹 구현과 테스트:
  `experiments/chunking/article_text.py`, `experiments/chunking/tests/` — Git 추적 대상
- 실행 결과:
  `.data/experiments/chunking/<입력파일명>.chunks.json` — 기존 `.gitignore`에 의해 Git 제외
- 학습 기록:
  `docs/learning/21-plain-text-article-chunking-experiment.md` 및 `docs/learning/index.md`

결과 파일은 같은 입력 이름으로 재실행하면 성공 결과에 한해 원자적으로 교체한다. DB와 외부
스토리지에는 저장하지 않는다. 사용자가 `--output`으로 저장 경로를 지정할 수 있게 하되 기본
경로와 마찬가지로 저장소 안의 로컬 실험 경로 사용을 문서화한다.

## 실패 동작

- 파일 없음, 디렉터리 입력, UTF-8 디코딩 실패, 빈 입력, 제목만 있는 단일 청크, 중복 조문 경로,
  출력 디렉터리 생성/쓰기 실패는 JSON 오류 한 줄을 표준 오류에 출력하고 종료 코드 `2`를 반환한다.
- 인식하지 못한 일반 줄은 버리지 않고 현재 조문 본문에 보존한다. UI 잔여 줄처럼 명시적으로
  정의한 노이즈만 제거한다.
- 실패한 실행은 새 결과 JSON을 남기지 않는다. 기존의 성공 결과가 있으면 임시 파일 교체 전
  실패한 경우 그대로 보존한다.
- 일부 조문만 성공 결과로 저장하지 않는다. 중복 경로나 구조 오류가 하나라도 있으면 파일 전체를
  실패 처리한다.
- 오류에는 입력 경로, 오류 코드와 사람이 이해할 수 있는 이유만 포함하고 원문 전문은 출력하지 않는다.

## 측정 가능한 완료 조건

- 제공된 fixture가 `제7조`~`제12조` 순서의 정확히 6개 청크를 만든다.
- 각 청크가 `제2장 전기사업`, `제1절 허가 등` 문맥과 괄호 표제를 보존한다.
- 조문 내부의 다른 조문 인용과 `4의2` 같은 호 표기가 새 조문 청크를 만들지 않는다.
- UI 잔여 줄 6개가 본문에서 제거되고 제거 개수가 출력 계약에 남는다.
- 터미널 미리보기와 저장 JSON의 청크 내용이 일치한다.
- 동일 입력 재실행의 경로, 순서, 내용과 SHA-256이 결정적이다.
- 단일 `제목+본문` 입력과 CRLF/LF, 가지조문, 선행/후행 공백 경계 테스트가 통과한다.
- 정상·실패·경계 테스트, Ruff와 문서 링크 검사가 통과한다.
- API·collector·DB·네트워크가 호출되지 않는 것이 테스트 또는 import 경계로 확인된다.

## TODO와 에이전트 배정

### 주 에이전트

- [ ] `M1 — 순수 청킹 계약`: `experiments/chunking/article_text.py`와 단위 테스트를 작성한다.
  완료 조건은 제공 fixture 6개 청크와 정상·실패·경계 계약 통과다. 검증은 해당 pytest와 Ruff다.
- [ ] `M2 — 관찰 CLI와 저장`: `experiments/chunking/run.py`, fixture, README와 CLI 테스트를
  작성한다. 완료 조건은 터미널/JSON 동일성, 원자 저장과 종료 코드 계약 통과다.
- [ ] `M3 — 문서와 전체 검증`: 학습 브리핑과 인덱스를 갱신하고 코어 테스트, Ruff, 문서 검사,
  전체 저장소 검증을 실행한다. 변경 범위별 diff를 검토하고 각 마일스톤을 별도 커밋한다.

### 하위 에이전트

- 사용하지 않는다. 핵심 구현, CLI, fixture와 테스트가 같은 작은 경계 계약을 공유해 파일 소유권을
  안전하게 분리하기 어렵고 병렬화 이점이 작다.

## 구현 순서

1. 입력 정규화, 장/절/조문 표지 인식, 단일 제목+본문 폴백과 오류 타입을 순수 함수로 구현한다.
2. 제공 텍스트와 최소 fixture로 정상·실패·경계 테스트를 먼저 고정한다.
3. 파일 읽기, 사람이 읽는 출력, JSON 직렬화와 임시 파일 원자 교체를 CLI에 연결한다.
4. CLI 통합 테스트로 stdout/stderr, 종료 코드와 기존 성공 결과 보존을 검증한다.
5. README와 `docs/learning/`에 현재 Open API 파서와 실험용 텍스트 어댑터의 차이를 기록한다.
6. 마일스톤마다 관련 검증과 `git diff`를 확인한 뒤 해당 범위만 커밋한다.

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

모든 변경은 운영 API·collector와 연결되지 않은 `experiments/chunking/` 경계에 둔다. 회귀가 있으면
해당 디렉터리와 학습 문서만 되돌릴 수 있으며 기존 JSON/XML 파서와 운영 데이터에는 migration이나
롤백이 필요하지 않다. `.data/experiments/chunking/` 결과는 재생성 가능한 로컬 산출물이다.

## 결정 로그

- 2026-07-22: 웹 UI 대신 로컬 CLI와 JSON을 사용한다. 입력, 전체 청크, 종료 코드와 저장 결과를
  한 번에 재현하면서 제품 화면과 API 범위를 늘리지 않기 위해서다.
- 2026-07-22: 일반 텍스트 파서는 운영 Open API 파서에 합치지 않고 실험 경계에 둔다. 제공 입력은
  구조화 Open API 응답이 아니며 운영 코퍼스 출처 계약을 약화시키면 안 된다.
- 2026-07-22: 기본 단위는 조문 전체이며 장/절은 메타데이터로 보존한다. 항·호 분할은 이번 실험의
  “조문 또는 제목+본문” 관찰 범위를 넘어가므로 제외한다.
- 2026-07-22: 결과는 Git에서 제외된 `.data/experiments/chunking/`에 원자 저장한다. 반복 실험 결과를
  확인할 수 있으면서 생성 산출물이 커밋에 섞이지 않게 하기 위해서다.

## 진행 기록

- 2026-07-22: `main`의 깨끗한 상태, 관련 설계와 JSON/XML 파서, 테스트, CLI 패턴을 확인했다.
- 2026-07-22: `codex/experiment-a-chunking` 브랜치를 만들었다.
- 2026-07-22: 입력·출력·저장·실패 계약과 세 마일스톤을 계획했다. 구현은 사용자 확인 후 시작한다.

## 미결정과 차단 요소

- 차단 요소는 없다. Python 3.14와 저장소 의존성만 사용하며 인증정보, 계정, 네트워크가 필요 없다.
- 이번 계획에서는 조문 전체를 청크로 확정한다. 실험 결과가 너무 길다고 관찰될 때만 후속 실험에서
  항 단위 또는 겹침 하위 청크를 별도 비교한다.

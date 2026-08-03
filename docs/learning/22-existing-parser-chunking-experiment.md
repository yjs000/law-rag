# 기존 법령 파서를 재사용한 일반 텍스트 청킹 실험

## 결론

일반 텍스트를 곧바로 운영 파서에 넣을 수는 없지만, 조문 블록을 국가법령정보 Open API의 최소
JSON 구조로 옮기면 현재 `law_json.parse_legal_document()`를 수정하지 않고도 동일한
`ProvisionRecord` 결과를 관찰할 수 있다. 제공된 전기사업법 텍스트는 제7조부터 제12조까지
6개 조문 청크가 됐다.

현재 파서는 각 조문 전체를 하나의 청크로 유지하면서 연속 공백과 줄바꿈을 단일 공백으로
정규화한다. 따라서 입력의 항·호 줄바꿈은 결과에서 사라지지만 본문 내용은 조문 청크 안에 남는다.
이번 실험은 이 동작을 고치거나 재분할하지 않고 그대로 드러낸다.

## 용어

- 입력 어댑터: 일반 텍스트의 장·절·조문 표지를 읽어 최소 Open API JSON 필드로 옮기는 실험 코드
- 현재 파서: `law_rag_core.parsers.law_json.parse_legal_document()`
- 청크: 현재 파서가 반환한 `ProvisionRecord`; 경로, 표제, 본문, 부모 경로와 순서를 가진다.
- 생성 보고서: 한 번의 대표 실행 메타데이터와 전체 청크를 담는
  `docs/generated/experiment-a-chunking.md`
- JSON sidecar: 자동 검증용 `.data/experiments/chunking/*.chunks.json`; Git에는 포함하지 않는다.

## 데이터 흐름

```text
UTF-8 텍스트 fixture
  -> UI 잔여 줄 제거와 조문 블록 인식
  -> 최소 Open API JSON 조문단위
  -> 기존 law_json.parse_legal_document()
  -> 기존 ProvisionRecord 6개
  -> 터미널 + Markdown 보고서 + JSON sidecar
```

입력 어댑터는 최종 청크 ID, 경로, 순서나 본문 정규화를 직접 만들지 않는다. 조문 번호·가지번호·
표제·조문내용을 JSON에 배치한 뒤, UUID와 `ProvisionRecord`는 현재 파서가 생성한다. 본문의
`제53조`, `제61조제1항` 같은 인용과 `4의2` 같은 호는 줄 시작의 괄호 표제 조문이 아니므로 새
조문단위로 만들지 않는다.

## 현재와 목표의 차이

현재 운영 입력은 국가법령정보 Open API JSON/XML이며 일반 `.txt` 파일은 지원하지 않는다. 실험의
목표는 새 운영 입력 형식을 추가하는 것이 아니라, 사용자가 제공한 고정 텍스트로 현재 청킹 결과를
눈으로 확인하는 것이다. 따라서 어댑터와 CLI는 `experiments/chunking/`에 격리했고 API, collector,
DB와 검색 경로에는 연결하지 않았다.

현재 파서는 조문 내부 구조가 Open API의 `항`, `호`, `목` 배열로 제공되면 하위
`ProvisionRecord`도 만들 수 있다. 이번 일반 텍스트 어댑터는 항·호를 구조화해 추정하지 않고 조문
전체만 `조문내용`으로 전달한다. 구조를 추정해 하위 청크를 만드는 것은 현재 방법의 단순 재사용이
아니므로 실험 범위에서 제외했다.

## 판단 근거

- 운영 파서를 직접 수정하면 실험과 제품 동작이 섞이므로 import 후 호출만 한다.
- 사용자 제공 텍스트는 운영 법률 코퍼스나 법률 답변 근거로 사용하지 않는다.
- 장과 절은 현재 `ProvisionRecord` 필드가 아니므로 보고서 입력 개요에만 표시한다.
- 중복 조문 경로는 현재 파서에서 조용히 생략될 수 있어 어댑터 경계에서 전체 입력을 실패시킨다.
- 성공 보고서와 JSON은 임시 파일을 거쳐 교체해 실패한 실행이 부분 결과로 보이지 않게 한다.

## 검증 방법

저장소 루트에서 다음 명령으로 실험 테스트와 대표 실행을 재현한다.

```powershell
uv run --project packages/law-rag-core pytest experiments/chunking/tests -q
uv run --project packages/law-rag-core ruff check experiments/chunking
uv run --project packages/law-rag-core python -m experiments.chunking.run `
  experiments/chunking/fixtures/electric-utility-act-chapter-2.txt
```

대표 실행에서 확인할 값:

- 입력 SHA-256: `635f15e2d66fe8d95f59c461a75e03fd158b37bb9549b707152a7df6a9cd3b8d`
- 현재 parser schema version: `2`
- 청크 경로: `제7조`, `제8조`, `제9조`, `제10조`, `제11조`, `제12조`
- 제거한 UI 잔여 줄: 6개
- 외부 API·DB·임베딩·검색 호출: 없음

## 출처

- 현재 JSON 파서: `packages/law-rag-core/src/law_rag_core/parsers/law_json.py`
- 현재 도메인 타입: `packages/law-rag-core/src/law_rag_core/domain/entities.py`
- 실험 입력과 실행법: `experiments/chunking/`
- 대표 결과: `docs/generated/experiment-a-chunking.md`
- 설계 원칙: `docs/design-docs/rag-pipeline.md`

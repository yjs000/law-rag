# 실험 A — 기존 법령 파서 청킹 관찰

일반 텍스트를 최소 Open API JSON 구조로 옮긴 뒤 현재
`law_rag_core.parsers.law_json.parse_legal_document()`를 그대로 호출한다. 운영 파서,
`ProvisionRecord`, parser schema version은 수정하지 않는다. 이 fixture와 결과는 로컬 실험용이며
운영 법률 코퍼스나 답변 근거로 사용하지 않는다.

## 실행

저장소 루트에서 실행한다.

```powershell
uv run --project packages/law-rag-core python -m experiments.chunking.run `
  experiments/chunking/fixtures/electric-utility-act-chapter-2.txt
```

성공하면 전체 청크를 터미널에 출력하고 다음 두 파일을 만든다.

- `docs/generated/experiment-a-chunking.md`: 사람이 검토하고 Git에 기록할 대표 실험 보고서
- `.data/experiments/chunking/electric-utility-act-chapter-2.chunks.json`: Git에서 제외되는 JSON sidecar

다른 위치가 필요하면 `--report`와 `--json-output`을 지정한다. 조문형 입력의 문서명은 기본
`전기사업법`이며 `--title`로 바꿀 수 있다. 조문 표지가 없는 입력은 첫 줄을 제목, 나머지를 본문으로
현재 행정규칙 파서의 `본문/단락1` 폴백에 전달한다.

## 실패와 재실행

파일 없음, UTF-8 오류, 빈 입력, 제목만 있는 입력, 중복 조문 경로 또는 저장 실패는 원문 전문을
포함하지 않는 JSON 오류와 종료 코드 `2`를 반환한다. 검증 실패는 보고서와 JSON을 만들지 않으며
기존 성공 결과가 있으면 보존한다. 같은 입력을 다시 실행하면 성공 결과에 한해 같은 경로를
원자적으로 교체한다. 외부 API, DB, collector, 임베딩과 검색은 호출하지 않는다.

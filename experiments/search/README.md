# 실험 C — 로컬 10청크 NVIDIA 벡터 검색

국가법령정보 공동활용 Open API 원문을 기존 파서로 조·항·호 청킹하고, 선택한 10개 청크를 기존
`NvidiaNimEmbedder`의 `passage` 모드로 임베딩해 로컬 JSON에 저장한다. 질문할 때는 같은 모델의
`query` 모드로 임베딩하고 10개 전체에 코사인 유사도를 계산해 상위 3개와 점수를 터미널에 출력한다.

## 준비된 데이터

사용자가 제공한 국가법령정보센터 화면 URL은 법령명과 버전 식별에만 사용했다. 실제 본문은 HTML을
크롤링하지 않고 Open API의 JSON 우선/XML 폴백 경로에서 가져왔다.

| 법령 | 버전 | 저장한 기존 파서 경로 |
| --- | --- | --- |
| 저작권법 | 현행 MST `283335`, 시행 2026-05-11 | `제2조/호1.`, `제2조/호2.`, `제4조/항①/호1.` |
| 전기사업법 | 사용자 지정 과거 MST `180380`, 시행 2016-07-28 | `제7조/항①`, `제8조`, `제9조/항①`, `제10조/항①` |
| 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 | 현행 MST `268793`, 시행 2026-02-01 | `제2조/호1.`, `제2조/호2.`, `제12조/항②` |

최상위 `제7조`처럼 장·절 표제만 담긴 레코드를 합치거나 새 청킹 규칙을 만들지 않았다. Open API
파서가 이미 만든 하위 경로 중 독립적으로 의미가 있는 청크를 선택했다.

## 필요한 환경변수

비밀값은 저장소에 커밋하지 않고 루트 또는 앱별 `.env.local`에 둔다.

```dotenv
LAW_OPEN_API_OC=<국가법령정보 공동활용 Open API OC>
NVIDIA_API_KEY=<NVIDIA Build API key>
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b
EMBEDDING_DIMENSIONS=512
```

## 데이터 준비

저장소 루트에서 실행한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_search prepare
```

성공하면 `.data/experiments/search/corpus.json`에 정확히 10개 청크를 저장한다. 각 청크에는 다음이
들어 있다.

- 법령명, source ID, MST, 시행일
- OC가 제거된 Open API URL과 사용자가 준 화면 URL
- wire format, 원문 SHA-256, parser schema version
- 조·항·호 path, 표제, 원문 content, 실제 passage embedding 입력
- `nvidia/nemotron-3-embed-1b`의 512차원 L2 정규화 벡터

준비는 세 문서 수집, 10개 경로 검증과 전체 embedding이 모두 성공한 뒤 임시 파일을 원자적으로
교체한다. 중간 실패 시 기존 corpus를 덮어쓰지 않는다. 이 로컬 파일은 Git에서 제외되며 현재 PC에서
질문할 때 재사용한다.

## 질문과 상위 3개 출력

대화형으로 실행한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_search ask
질문> 전기사업을 하려면 누구의 허가를 받아야 하나?
```

한 줄 명령도 지원한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_search ask `
  --question "재생에너지란 무엇인가?"
```

출력 JSON에는 질문, provider/model, corpus 청크 수, `top_k=3`, score 종류와 다음 결과 필드가 포함된다.

- `rank`, `score`
- `title`, `source_id`, `mst`, `effective_from`
- `path`, `heading`, `content`

질문 원문과 검색 결과는 파일에 저장하지 않는다. 질문할 때 query embedding API만 호출하며 저장해 둔
10개 passage embedding은 다시 만들지 않는다.

## 점수 해석

`score`는 query와 chunk의 코사인 유사도다. 확률, 정답률 또는 법률적으로 같은 정도가 아니다. 이
실험은 10개를 모두 계산하는 exhaustive search이며 production의 PostgreSQL/pgvector, 키워드 검색,
기준일 필터와 하이브리드 병합은 사용하지 않는다. 따라서 이 10개 밖의 조문은 검색할 수 없다.

## 실패 동작

- corpus가 없으면 `corpus_missing`과 종료 코드 `2`
- Open API OC 또는 NVIDIA key가 없으면 해당 설정 누락 코드와 종료 코드 `2`
- Open API·NVIDIA·스키마·차원·유한값 검증 실패는 `experiment_c_failed`와 종료 코드 `2`
- provider 오류 전문, API key와 Authorization header는 출력하거나 corpus에 저장하지 않음
- 다른 임베딩 모델, 영벡터 또는 임의 결과로 자동 대체하지 않음

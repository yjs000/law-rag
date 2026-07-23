# 실험 C — 기존 전체 청크 NVIDIA 벡터 검색

국가법령정보 공동활용 Open API 원문을 기존 파서로 청킹하고, 파서가 반환한 청크를 빠짐없이 기존
`NvidiaNimEmbedder`의 `passage` 모드로 임베딩해 로컬 JSON에 저장한다. 질문은 같은 모델의 `query`
모드로 임베딩하고 저장된 전체 청크에 코사인 유사도를 계산해 상위 3개와 점수를 터미널에 출력한다.

## 데이터 범위

사용자가 제공한 국가법령정보센터 화면 URL은 법령명과 버전 식별에만 사용한다. 실제 본문은 HTML을
크롤링하지 않고 Open API의 JSON 우선/XML 폴백 경로에서 가져온다.

| 법령 | 준비된 버전 | 2026-07-23 실제 청크 수 |
| --- | --- | ---: |
| 저작권법 | 현행 MST `283335`, 시행 2026-05-11 | 950 |
| 전기사업법 | 사용자 지정 과거 MST `180380`, 시행 2016-07-28 | 703 |
| 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 | 현행 MST `268793`, 시행 2026-02-01 | 353 |

조·항·호, 장·절 표제나 제목 전용 청크를 실험 연결부에서 선별·병합·재청킹하지 않는다. 현재 로컬
corpus는 총 2,006개다. 현행 법령의 Open API 버전이 바뀐 뒤 다시 준비하면 개수도 달라질 수 있다.

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

성공하면 `.data/experiments/search/corpus.json`에 모든 청크와 passage embedding이 생긴다. 터미널에는
전체 청크 수와 법령별 청크 수만 출력해 대량 원문·벡터가 화면을 채우지 않게 한다. API 요청은 기본
32청크씩 나누며 필요하면 `--batch-size 16`처럼 바꿀 수 있다. 이 배치는 기존 임베더를 호출하는 단위일
뿐 청킹 결과나 벡터 계산 방식은 바꾸지 않는다.

각 저장 청크에는 다음이 들어 있다.

- 법령명, source ID, MST, 시행일
- OC가 제거된 Open API URL과 사용자가 준 화면 URL
- wire format, 원문 SHA-256, parser schema version
- 기존 파서의 path, 표제, 원문 content, 실제 passage embedding 입력
- `nvidia/nemotron-3-embed-1b`의 512차원 L2 정규화 벡터

세 문서 수집과 모든 embedding이 성공한 뒤 임시 파일을 원자적으로 교체한다. 중간 배치 하나라도
실패하거나 응답 개수·차원 검증에 실패하면 새 파일을 반영하지 않아 기존 corpus가 유지된다. 로컬
corpus는 Git에서 제외되며 현재 PC에서 질문할 때 재사용한다.

## 질문과 상위 3개 출력

```powershell
uv run --directory apps/api python -m scripts.experiment_search ask
질문> 전기사업을 하려면 누구의 허가를 받아야 하나?
```

```powershell
uv run --directory apps/api python -m scripts.experiment_search ask `
  --question "재생에너지란 무엇인가?"
```

출력 JSON에는 질문, provider/model, corpus 청크 수, `top_k=3`, score 종류와 `rank`, `score`, 법령명,
MST, 시행일, path, heading, content가 포함된다. 질문과 검색 결과는 파일에 저장하지 않는다. 질문할
때 query embedding API만 호출하고 저장해 둔 passage embedding은 다시 만들지 않는다.

## 점수와 실패 동작

`score`는 query와 chunk의 코사인 유사도이며 확률·정답률·법률적 동일성 점수가 아니다. 이 실험은
저장된 모든 청크를 직접 비교하는 exhaustive search이고 production의 PostgreSQL/pgvector, 키워드
검색, 기준일 필터와 하이브리드 병합은 사용하지 않는다.

- corpus가 없으면 `corpus_missing`과 종료 코드 `2`
- Open API OC 또는 NVIDIA key가 없으면 해당 설정 누락 코드와 종료 코드 `2`
- Open API·NVIDIA·스키마·차원·유한값 검증 실패는 `experiment_c_failed`와 종료 코드 `2`
- provider 오류 전문, API key와 Authorization header는 출력하거나 corpus에 저장하지 않음
- 다른 임베딩 모델, 영벡터 또는 임의 결과로 자동 대체하지 않음
